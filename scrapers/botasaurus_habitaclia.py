"""
Habitaclia scraper using Botasaurus.

This scraper extracts real estate listings from Habitaclia.com
using Botasaurus for anti-bot bypass (free, open-source).

Habitaclia is the #1 real estate portal in Catalonia.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from botasaurus.browser import browser, Driver

from scrapers.botasaurus_base import BotasaurusBaseScraper

logger = logging.getLogger(__name__)


# Geographic zones configuration
ZONAS_GEOGRAFICAS = {
    # =============================================================
    # PROVINCES (use 'viviendas-{slug}.htm' format without 'particulares')
    # =============================================================
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_slug': 'tarragona',
        'is_province': True,
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_slug': 'lleida',
        'is_province': True,
    },

    # =============================================================
    # COMARCAS - Composite zones (list of cities to scrape)
    # =============================================================
    # -- TARRAGONA COMARCAS --
    'tarragones': {
        'nombre': 'Tarragonès',
        'composite': ['tarragona', 'torredembarra', 'altafulla', 'constantí', 'el_morell'],
    },
    'baix_camp': {
        'nombre': 'Baix Camp',
        'composite': ['reus', 'cambrils', 'salou', 'vila-seca', 'mont-roig_del_camp', 'riudoms'],
    },
    'alt_camp': {
        'nombre': 'Alt Camp',
        'composite': ['valls', 'alcover'],
    },
    'conca_barbera': {
        'nombre': 'Conca de Barberà',
        'composite': ['montblanc', 'l_espluga_de_francolí', 'santa_coloma_de_queralt'],
    },
    'baix_penedes': {
        'nombre': 'Baix Penedès',
        'composite': ['el_vendrell', 'calafell', 'cunit'],
    },
    'baix_ebre': {
        'nombre': 'Baix Ebre',
        'composite': ['tortosa', 'deltebre', 'l_ametlla_de_mar'],
    },
    'montsia': {
        'nombre': 'Montsià',
        'composite': ['amposta', 'sant_carles_de_la_rapita', 'alcanar', 'ulldecona'],
    },
    'priorat': {
        'nombre': 'Priorat',
        'composite': ['falset'],
    },
    # Costa Daurada (tourist area grouping)
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'composite': ['salou', 'cambrils', 'tarragona', 'torredembarra', 'altafulla', 'calafell', 'el_vendrell', 'miami_platja'],
    },

    # -- LLEIDA COMARCAS --
    'segria': {
        'nombre': 'Segrià',
        'composite': ['lleida', 'alcarras', 'almacelles', 'alpicat'],
    },
    'noguera': {
        'nombre': 'Noguera',
        'composite': ['balaguer', 'artesa_de_segre', 'ponts'],
    },
    'pla_urgell': {
        'nombre': "Pla d'Urgell",
        'composite': ['mollerussa', 'bellpuig', 'linyola'],
    },
    'urgell': {
        'nombre': 'Urgell',
        'composite': ['tarrega', 'agramunt'],
    },
    'garrigues': {
        'nombre': 'Les Garrigues',
        'composite': ['les_borges_blanques', 'juneda'],
    },

    # =============================================================
    # CITIES - Single municipality searches
    # =============================================================
    # -- TARRAGONA CITIES --
    'tarragona': {'nombre': 'Tarragona', 'url_slug': 'tarragona'},
    'salou': {'nombre': 'Salou', 'url_slug': 'salou'},
    'cambrils': {'nombre': 'Cambrils', 'url_slug': 'cambrils'},
    'reus': {'nombre': 'Reus', 'url_slug': 'reus'},
    'calafell': {'nombre': 'Calafell', 'url_slug': 'calafell'},
    'torredembarra': {'nombre': 'Torredembarra', 'url_slug': 'torredembarra'},
    'vendrell': {'nombre': 'El Vendrell', 'url_slug': 'el_vendrell'},
    'el_vendrell': {'nombre': 'El Vendrell', 'url_slug': 'el_vendrell'},
    'valls': {'nombre': 'Valls', 'url_slug': 'valls'},
    'tortosa': {'nombre': 'Tortosa', 'url_slug': 'tortosa'},
    'amposta': {'nombre': 'Amposta', 'url_slug': 'amposta'},
    'montblanc': {'nombre': 'Montblanc', 'url_slug': 'montblanc'},
    'altafulla': {'nombre': 'Altafulla', 'url_slug': 'altafulla'},
    'vila-seca': {'nombre': 'Vila-seca', 'url_slug': 'vila-seca'},
    'mont-roig_del_camp': {'nombre': 'Mont-roig del Camp', 'url_slug': 'mont-roig_del_camp'},
    'miami_platja': {'nombre': 'Miami Platja', 'url_slug': 'miami_platja'},
    'riudoms': {'nombre': 'Riudoms', 'url_slug': 'riudoms'},
    'alcover': {'nombre': 'Alcover', 'url_slug': 'alcover'},
    'constantí': {'nombre': 'Constantí', 'url_slug': 'constanti'},
    'el_morell': {'nombre': 'El Morell', 'url_slug': 'el_morell'},
    'cunit': {'nombre': 'Cunit', 'url_slug': 'cunit'},
    'deltebre': {'nombre': 'Deltebre', 'url_slug': 'deltebre'},
    'l_ametlla_de_mar': {'nombre': "L'Ametlla de Mar", 'url_slug': 'l_ametlla_de_mar'},
    'sant_carles_de_la_rapita': {'nombre': 'Sant Carles de la Ràpita', 'url_slug': 'sant_carles_de_la_rapita'},
    'alcanar': {'nombre': 'Alcanar', 'url_slug': 'alcanar'},
    'ulldecona': {'nombre': 'Ulldecona', 'url_slug': 'ulldecona'},
    'falset': {'nombre': 'Falset', 'url_slug': 'falset'},
    'l_espluga_de_francolí': {'nombre': "L'Espluga de Francolí", 'url_slug': 'l_espluga_de_francoli'},
    'santa_coloma_de_queralt': {'nombre': 'Santa Coloma de Queralt', 'url_slug': 'santa_coloma_de_queralt'},

    # -- LLEIDA CITIES --
    'lleida': {'nombre': 'Lleida', 'url_slug': 'lleida'},
    'balaguer': {'nombre': 'Balaguer', 'url_slug': 'balaguer'},
    'mollerussa': {'nombre': 'Mollerussa', 'url_slug': 'mollerussa'},
    'tarrega': {'nombre': 'Tàrrega', 'url_slug': 'tarrega'},
    'alcarras': {'nombre': 'Alcarràs', 'url_slug': 'alcarras'},
    'almacelles': {'nombre': 'Almacelles', 'url_slug': 'almacelles'},
    'alpicat': {'nombre': 'Alpicat', 'url_slug': 'alpicat'},
    'artesa_de_segre': {'nombre': 'Artesa de Segre', 'url_slug': 'artesa_de_segre'},
    'ponts': {'nombre': 'Ponts', 'url_slug': 'ponts'},
    'bellpuig': {'nombre': 'Bellpuig', 'url_slug': 'bellpuig'},
    'linyola': {'nombre': 'Linyola', 'url_slug': 'linyola'},
    'agramunt': {'nombre': 'Agramunt', 'url_slug': 'agramunt'},
    'les_borges_blanques': {'nombre': 'Les Borges Blanques', 'url_slug': 'les_borges_blanques'},
    'juneda': {'nombre': 'Juneda', 'url_slug': 'juneda'},
}


class BotasaurusHabitaclia(BotasaurusBaseScraper):
    """Habitaclia scraper using Botasaurus."""

    PORTAL_NAME = 'habitaclia'
    BASE_URL = 'https://www.habitaclia.com'

    def _extract_habitaclia_phone(self, html: str) -> Optional[str]:
        """
        Extract phone number from Habitaclia detail page.

        IMPORTANT: Only extract phones from legitimate contact sections.
        Do NOT scan entire HTML for 9-digit numbers as this can pick up
        listing IDs, tracking codes, or other non-phone numbers.

        Returns None if no phone is found in a contact-related context.
        """
        # Pattern 1: Phone in a visible tel: link (most reliable)
        tel_link = re.search(r'href="tel:(\+?34)?([679]\d{8})"', html)
        if tel_link:
            return tel_link.group(2)

        # Pattern 2: Phone displayed near contact button/section
        # Look for phone in a contact-related container
        contact_section = re.search(
            r'(?:class="[^"]*(?:contact|phone|telefono|llamar)[^"]*"[^>]*>.*?'
            r'|data-phone[^>]*>.*?'
            r'|id="[^"]*phone[^"]*"[^>]*>.*?)'
            r'([679]\d[\d\s\.\-]{7,12})',
            html, re.IGNORECASE | re.DOTALL
        )
        if contact_section:
            phone = re.sub(r'[\s\.\-]', '', contact_section.group(1))
            if len(phone) == 9:
                return phone

        # Pattern 3: Phone after "Teléfono:" or "Tel:" label
        phone_label = re.search(
            r'(?:tel[ée]fono|tel\.?|llamar|phone)\s*:?\s*([679]\d[\d\s\.\-]{7,12})',
            html, re.IGNORECASE
        )
        if phone_label:
            phone = re.sub(r'[\s\.\-]', '', phone_label.group(1))
            if len(phone) == 9:
                return phone

        # Pattern 4: Phone in JSON-LD structured data
        json_phone = re.search(r'"telephone"\s*:\s*"(\+?34)?([679]\d{8})"', html)
        if json_phone:
            return json_phone.group(2)

        # NO phone found in legitimate contact contexts
        # Do NOT fall back to scanning entire HTML
        return None

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        headless: bool = True,
        only_private: bool = True,
    ):
        super().__init__(tenant_id, postgres_config, headless)
        self.zones = zones or ['tarragona_provincia']
        self.only_private = only_private

    def build_url(self, zona_key: str, page: int = 1) -> str:
        """Build search URL for Habitaclia."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        slug = zona['url_slug']
        is_province = zona.get('is_province', False)

        # Province searches don't support -particulares- filter in URL
        # We'll filter agencies later in the scraper
        if is_province:
            url = f"{self.BASE_URL}/viviendas-{slug}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-{slug}-pag{page}.htm"
        elif self.only_private:
            # City searches can use -particulares- filter
            url = f"{self.BASE_URL}/viviendas-particulares-{slug}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-particulares-{slug}-pag{page}.htm"
        else:
            url = f"{self.BASE_URL}/viviendas-{slug}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-{slug}-pag{page}.htm"

        return url

    def scrape(self) -> List[Dict[str, Any]]:
        """Run the scraper and return all listings."""
        all_listings = []

        for zona_key in self.zones:
            logger.info(f"Scraping zone: {zona_key}")
            try:
                listings = self._scrape_zone(zona_key)
                all_listings.extend(listings)
                logger.info(f"Zone {zona_key}: {len(listings)} listings")
            except Exception as e:
                logger.error(f"Failed to scrape zone {zona_key}: {e}")
                continue  # Continue with next zone

        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    def _scrape_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape a single zone (or composite zone with multiple cities)."""
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Handle composite zones (comarcas) - scrape each city
        if 'composite' in zona_info:
            logger.info(f"Composite zone {zona_key}: {zona_info['composite']}")
            all_listings = []
            for city_key in zona_info['composite']:
                if city_key in ZONAS_GEOGRAFICAS:
                    logger.info(f"  Scraping city: {city_key}")
                    city_listings = self._scrape_single_zone(city_key, zona_info['nombre'])
                    all_listings.extend(city_listings)
                else:
                    logger.warning(f"  City not found in config: {city_key}")
            return all_listings

        # Single zone
        return self._scrape_single_zone(zona_key)

    def _scrape_single_zone(self, zona_key: str, parent_zone_name: str = None) -> List[Dict[str, Any]]:
        """Scrape a single municipality zone."""
        url = self.build_url(zona_key)
        headless = self.headless
        base_url = self.BASE_URL
        portal = self.PORTAL_NAME
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
        # Use parent zone name for composite zones (comarca name)
        zone_display_name = parent_zone_name or zona_info.get('nombre', zona_key)

        @browser(headless=headless, block_images=True)
        def scrape_page(driver: Driver, data: dict):
            url = data['url']

            logger.info(f"Loading: {url}")
            driver.get(url)
            driver.sleep(4)

            # Scroll to load content
            driver.run_js('window.scrollTo({top: 800, behavior: "smooth"})')
            driver.sleep(2)

            html = driver.page_html

            # Check for blocking
            if len(html) < 50000:
                logger.warning("Possible blocking or empty results")
                return []

            # Extract listing URLs - Habitaclia format (may have query params)
            links = re.findall(r'href="(https://www\.habitaclia\.com/comprar-(?:piso|casa|chalet|vivienda)[^"]+\.htm)[^"]*"', html)
            unique_links = list(dict.fromkeys(links))

            # Filter out map/list view links
            unique_links = [l for l in unique_links if 'vistamapa' not in l and '-i' in l]

            logger.info(f"Found {len(unique_links)} listing links")

            listings = []
            for link in unique_links[:20]:  # Limit to avoid timeout
                # Extract ID from URL (format: ...-i{ID}.htm)
                id_match = re.search(r'-i(\d{9,})', link)
                if not id_match:
                    continue

                anuncio_id = id_match.group(1)

                listings.append({
                    'anuncio_id': anuncio_id,
                    'detail_url': link,
                    'url_anuncio': link,
                    'portal': portal,
                    'zona_busqueda': zone_display_name,
                    'zona_geografica': zone_display_name,
                })

            return listings

        try:
            basic_listings = scrape_page({'url': url})
        except Exception as e:
            logger.error(f"Error scraping {zona_key}: {e}")
            return []

        if not basic_listings:
            return []

        # Enrich with detail page data
        try:
            enriched_listings = self._enrich_listings(basic_listings[:10])
        except Exception as e:
            logger.error(f"Error enriching listings for {zona_key}: {e}")
            # Return basic listings without enrichment
            return basic_listings[:10]

        return enriched_listings

    def _enrich_listings(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch detail pages to extract more info."""
        headless = self.headless

        @browser(headless=headless, block_images=True)
        def fetch_details(driver: Driver, data: dict):
            results = []

            for listing in data['listings']:
                url = listing['detail_url']
                logger.info(f"Fetching detail: {url[:60]}...")

                try:
                    driver.get(url)
                    driver.sleep(3)

                    html = driver.page_html

                    # Extract title
                    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                    listing['titulo'] = title_match.group(1).strip() if title_match else None

                    # Extract price
                    price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*(?:EUR|euros|€)', html, re.IGNORECASE)
                    if price_match:
                        price_str = price_match.group(1).replace('.', '')
                        listing['precio'] = float(price_str)

                    # Extract phones - ONLY from contact section, NOT from entire HTML
                    # Habitaclia typically hides phone behind "Ver teléfono" button
                    # We should NOT invent phones from random numbers in the page
                    phone = self._extract_habitaclia_phone(html)
                    if phone:
                        listing['telefono'] = phone
                        listing['telefono_norm'] = self.normalize_phone(phone)

                    # Extract features
                    metros_match = re.search(r'(\d+)\s*m[²2]', html)
                    if metros_match:
                        listing['metros'] = int(metros_match.group(1))

                    habs_match = re.search(r'(\d+)\s*hab', html, re.IGNORECASE)
                    if habs_match:
                        listing['habitaciones'] = int(habs_match.group(1))

                    # Extract location
                    ubicacion_match = re.search(r'class="[^"]*location[^"]*"[^>]*>([^<]+)', html, re.IGNORECASE)
                    if ubicacion_match:
                        listing['ubicacion'] = ubicacion_match.group(1).strip()

                    # Extract description - Habitaclia uses class="comment" for descriptions
                    # First try to find the comment section (permissive match)
                    desc_match = re.search(
                        r'<div[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</div>',
                        html, re.DOTALL | re.IGNORECASE
                    )
                    if not desc_match:
                        # Try section with comment
                        desc_match = re.search(
                            r'<section[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</section>',
                            html, re.DOTALL | re.IGNORECASE
                        )
                    if not desc_match:
                        # Try any element with descripcion/description in class
                        desc_match = re.search(
                            r'class="[^"]*(?:descripcion|description)[^"]*"[^>]*>(.*?)</(?:div|section|p)',
                            html, re.DOTALL | re.IGNORECASE
                        )
                    # Fallback: find long text blocks directly in HTML (>100 chars between tags)
                    if not desc_match or 'descripcion' not in listing:
                        text_blocks = re.findall(r'>([^<]{100,})<', html)
                        for block in text_blocks:
                            clean_text = block.strip()
                            # Skip JavaScript code, cookie banners, and other non-content
                            if (clean_text and
                                'cookie' not in clean_text.lower() and
                                'javascript' not in clean_text.lower() and
                                'privacy' not in clean_text.lower() and
                                'google' not in clean_text.lower() and
                                'analytics' not in clean_text.lower() and
                                'gdpr' not in clean_text.lower() and
                                'window.' not in clean_text.lower() and
                                'function' not in clean_text.lower() and
                                '__tcfapi' not in clean_text and
                                'addEventListener' not in clean_text and
                                not clean_text.startswith('{')):
                                listing['descripcion'] = clean_text[:2000]
                                break
                    if desc_match and 'descripcion' not in listing:
                        desc_text = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
                        desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                        if len(desc_text) > 30:
                            listing['descripcion'] = desc_text[:2000]

                    # Extract photos - Habitaclia uses images.habimg.com/imgh/ structure
                    # Pattern: //images.habimg.com/imgh/XXX-XXXXXXX/filename.jpg
                    # IMPORTANT: Only capture photos matching THIS listing's ID to avoid
                    # capturing images from "similar properties" sections
                    anuncio_id = listing.get('anuncio_id', '')
                    # Extract the numeric part for matching (e.g., "500006030072" -> "6030072")
                    id_for_match = anuncio_id[-7:] if len(anuncio_id) > 7 else anuncio_id

                    photos = re.findall(
                        r'(?:https?:)?//images\.habimg\.com/imgh/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp)',
                        html, re.IGNORECASE
                    )
                    unique_photos = []
                    seen = set()
                    for photo in photos:
                        # Ensure https://
                        if photo.startswith('//'):
                            photo = 'https:' + photo
                        # Only keep photos that contain this listing's ID in the path
                        # This filters out "similar properties" images
                        if id_for_match and id_for_match in photo:
                            photo_base = re.sub(r'_[A-Z]{1,2}\.', '.', photo)
                            if photo_base not in seen and 'logo' not in photo.lower():
                                unique_photos.append(photo)
                                seen.add(photo_base)
                    listing['fotos'] = unique_photos[:10]

                    # Check if particular or agency
                    # When using /viviendas-particulares- URL, all listings are already filtered
                    # Only mark as agency if there's a specific agency section
                    agency_section = re.search(r'class="[^"]*(?:agent|agency|professional|inmobiliaria)[^"]*"', html, re.IGNORECASE)
                    agency_name_pattern = re.search(r'data-(?:agent|agency|professional)-name', html, re.IGNORECASE)

                    if agency_section or agency_name_pattern:
                        listing['vendedor'] = 'Inmobiliaria'
                        listing['es_particular'] = False
                    else:
                        # Default to particular since we're using particulares filter
                        listing['vendedor'] = 'Particular'
                        listing['es_particular'] = True

                    results.append(listing)

                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")

            return results

        enriched = fetch_details({'listings': listings})

        # Filter to only particulares
        particulares = [l for l in enriched if l.get('es_particular', True)]
        filtered = len(enriched) - len(particulares)

        if filtered > 0:
            logger.info(f"Filtered out {filtered} agency listings")
            self.stats['filtered_out'] += filtered

        return particulares

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            self.stats['total_listings'] += 1

            # Additional filter check
            if not self.should_scrape(listing):
                self.stats['filtered_out'] += 1
                continue

            if self.save_to_postgres(listing, self.PORTAL_NAME):
                self.stats['saved'] += 1

        logger.info(f"Stats: {self.stats}")
        return self.stats


def run_habitaclia_botasaurus(
    zones: List[str] = None,
    postgres: bool = False,
    headless: bool = True,
    only_private: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convenience function to run the Habitaclia scraper.

    Args:
        zones: List of zones to scrape
        postgres: Enable PostgreSQL saving
        headless: Run in headless mode

    Returns:
        List of scraped listings
    """
    postgres_config = None
    if postgres:
        postgres_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'casa_teva_db',
            'user': 'casa_teva',
            'password': 'casateva2024',
        }

    with BotasaurusHabitaclia(
        zones=zones or ['tarragona_provincia'],
        postgres_config=postgres_config,
        headless=headless,
        only_private=only_private,
    ) as scraper:
        if postgres:
            scraper.scrape_and_save()
        return scraper.scrape()


if __name__ == '__main__':
    import sys

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['tarragona']
    print(f"Scraping zones: {zones}")
    print(f"Available zones: {list(ZONAS_GEOGRAFICAS.keys())}")

    listings = run_habitaclia_botasaurus(zones=zones, headless=True)

    print(f"\nFound {len(listings)} listings:")
    for l in listings[:5]:
        print(f"  - {l.get('titulo', 'N/A')[:50]}... | {l.get('precio')}€ | {l.get('vendedor')}")

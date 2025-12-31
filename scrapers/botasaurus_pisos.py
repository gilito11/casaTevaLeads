"""
Pisos.com scraper using Botasaurus.

This scraper extracts real estate listings from Pisos.com
using Botasaurus for anti-bot bypass (free, open-source).
"""

import logging
import re
from typing import Dict, Any, List, Optional

from botasaurus.browser import browser, Driver

from scrapers.botasaurus_base import BotasaurusBaseScraper, CONTAINER_CHROME_ARGS

logger = logging.getLogger(__name__)


# Geographic zones configuration
ZONAS_GEOGRAFICAS = {
    # =============================================================
    # PROVINCES
    # =============================================================
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_path': 'pisos-tarragona',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'pisos-lleida',
    },

    # =============================================================
    # COMARCAS - Composite zones (list of cities to scrape)
    # =============================================================
    # -- TARRAGONA COMARCAS --
    'tarragones': {
        'nombre': 'Tarragonès',
        'composite': ['tarragona_capital', 'torredembarra', 'altafulla'],
    },
    'baix_camp': {
        'nombre': 'Baix Camp',
        'composite': ['reus', 'cambrils', 'salou', 'vila_seca'],
    },
    'alt_camp': {
        'nombre': 'Alt Camp',
        'composite': ['valls'],
    },
    'conca_barbera': {
        'nombre': 'Conca de Barberà',
        'composite': ['montblanc'],
    },
    'baix_penedes': {
        'nombre': 'Baix Penedès',
        'composite': ['vendrell', 'calafell'],
    },
    'baix_ebre': {
        'nombre': 'Baix Ebre',
        'composite': ['tortosa'],
    },
    'montsia': {
        'nombre': 'Montsià',
        'composite': ['amposta'],
    },
    # Costa Daurada (tourist area grouping)
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'composite': ['salou', 'cambrils', 'tarragona_capital', 'torredembarra', 'calafell', 'vendrell'],
    },

    # -- LLEIDA COMARCAS --
    'segria': {
        'nombre': 'Segrià',
        'composite': ['lleida_capital'],
    },

    # =============================================================
    # CITIES - Single municipality searches
    # =============================================================
    'tarragona_capital': {'nombre': 'Tarragona Capital', 'url_path': 'pisos-tarragona_capital'},
    'lleida_capital': {'nombre': 'Lleida Capital', 'url_path': 'pisos-lleida_capital'},
    'salou': {'nombre': 'Salou', 'url_path': 'pisos-salou'},
    'cambrils': {'nombre': 'Cambrils', 'url_path': 'pisos-cambrils'},
    'reus': {'nombre': 'Reus', 'url_path': 'pisos-reus'},
    'calafell': {'nombre': 'Calafell', 'url_path': 'pisos-calafell'},
    'torredembarra': {'nombre': 'Torredembarra', 'url_path': 'pisos-torredembarra'},
    'vendrell': {'nombre': 'El Vendrell', 'url_path': 'pisos-el_vendrell'},
    'valls': {'nombre': 'Valls', 'url_path': 'pisos-valls'},
    'tortosa': {'nombre': 'Tortosa', 'url_path': 'pisos-tortosa'},
    'amposta': {'nombre': 'Amposta', 'url_path': 'pisos-amposta'},
    'altafulla': {'nombre': 'Altafulla', 'url_path': 'pisos-altafulla'},
    'vila_seca': {'nombre': 'Vila-seca', 'url_path': 'pisos-vila_seca'},
    'montblanc': {'nombre': 'Montblanc', 'url_path': 'pisos-montblanc'},
}


class BotasaurusPisos(BotasaurusBaseScraper):
    """Pisos.com scraper using Botasaurus."""

    PORTAL_NAME = 'pisos.com'
    BASE_URL = 'https://www.pisos.com'

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        headless: bool = True,
    ):
        super().__init__(tenant_id, postgres_config, headless)
        self.zones = zones or ['tarragona_provincia']

    def build_url(self, zona_key: str, page: int = 1) -> str:
        """Build search URL for Pisos.com."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        url = f"{self.BASE_URL}/venta/{zona['url_path']}/"

        if page > 1:
            url += f'{page}/'

        return url

    def scrape(self) -> List[Dict[str, Any]]:
        """Run the scraper and return all listings."""
        all_listings = []

        for zona_key in self.zones:
            logger.info(f"Scraping zone: {zona_key}")
            listings = self._scrape_zone(zona_key)
            all_listings.extend(listings)

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

        @browser(headless=headless, block_images=False, add_arguments=CONTAINER_CHROME_ARGS)
        def scrape_page(driver: Driver, data: dict):
            url = data['url']

            logger.info(f"Loading: {url}")
            driver.get(url)
            driver.sleep(6)

            # Scroll multiple times to load all lazy content
            for i in range(4):
                driver.run_js(f'window.scrollTo({{top: {800 * (i+1)}, behavior: "smooth"}})')
                driver.sleep(1.5)

            html = driver.page_html

            # Check for blocking
            if len(html) < 50000:
                logger.warning("Possible blocking or empty results")
                return []

            # Extract listing links - Pisos.com format
            # Links are like /comprar/piso-zona-ID_price/ (from ad-preview__title)
            links = re.findall(r'href="(/comprar/piso[^"]+)"', html)
            unique_links = list(dict.fromkeys(links))

            logger.info(f"Found {len(unique_links)} listing links")

            listings = []
            for link in unique_links[:20]:  # Limit to avoid timeout
                # Extract ID from URL (format: -ID_price/)
                id_match = re.search(r'-(\d{10,})(?:_\d+)?/?$', link)
                if not id_match:
                    continue

                anuncio_id = id_match.group(1)
                detail_url = f"{base_url}{link}"

                listings.append({
                    'anuncio_id': anuncio_id,
                    'detail_url': detail_url,
                    'url_anuncio': detail_url,
                    'portal': portal,
                    'zona_busqueda': zone_display_name,
                    'zona_geografica': zone_display_name,
                })

            return listings

        basic_listings = scrape_page({'url': url})

        if not basic_listings:
            return []

        # Enrich with detail page data
        enriched_listings = self._enrich_listings(basic_listings[:10])

        return enriched_listings

    def _enrich_listings(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch detail pages to extract more info."""
        headless = self.headless

        @browser(headless=headless, block_images=True, add_arguments=CONTAINER_CHROME_ARGS)
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

                    # Extract phones
                    phones = self.extract_phones_from_html(html)
                    if phones:
                        listing['telefono'] = phones[0]
                        listing['telefono_norm'] = self.normalize_phone(phones[0])

                    # Extract features
                    metros_match = re.search(r'(\d+)\s*m[²2]', html)
                    if metros_match:
                        listing['metros'] = int(metros_match.group(1))

                    habs_match = re.search(r'(\d+)\s*hab', html, re.IGNORECASE)
                    if habs_match:
                        listing['habitaciones'] = int(habs_match.group(1))

                    # Extract description - look for substantial text blocks
                    desc_match = re.search(
                        r'class="[^"]*(?:ad-detail-description|description|comment|detalle|texto)[^"]*"[^>]*>(.*?)</(?:div|p|section)',
                        html, re.DOTALL | re.IGNORECASE
                    )
                    if not desc_match:
                        # Find long text blocks (property descriptions are 100+ chars)
                        text_blocks = re.findall(r'>([^<]{100,})<', html)
                        for block in text_blocks:
                            clean_text = block.strip()
                            if (clean_text and
                                'cookie' not in clean_text.lower() and
                                'javascript' not in clean_text.lower() and
                                'privacy' not in clean_text.lower()):
                                listing['descripcion'] = clean_text[:2000]
                                break
                    if desc_match and 'descripcion' not in listing:
                        desc_text = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
                        desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                        if len(desc_text) > 50:
                            listing['descripcion'] = desc_text[:2000]

                    # Extract photos - Pisos.com uses various CDN patterns
                    # img.pisos.com, cdn.pisos.com, or direct pisos.com paths
                    photos = re.findall(
                        r'((?:https?:)?//[^"\'<>\s]*(?:pisos\.com|cdn\.pisos)[^"\'<>\s]*\.(?:jpg|jpeg|png|webp))',
                        html, re.IGNORECASE
                    )
                    # Also check data-src and srcset attributes
                    photos += re.findall(
                        r'data-src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                        html, re.IGNORECASE
                    )
                    unique_photos = []
                    seen = set()
                    for photo in photos:
                        if photo.startswith('//'):
                            photo = 'https:' + photo
                        photo_base = re.sub(r'\?.*$', '', photo)
                        if (photo_base not in seen and
                            'logo' not in photo.lower() and
                            'icon' not in photo.lower() and
                            len(photo_base) > 30):
                            unique_photos.append(photo)
                            seen.add(photo_base)
                    listing['fotos'] = unique_photos[:10]

                    # Check if particular or agency
                    # Detection based on:
                    # 1. /inmobiliaria- links in owner section = Agency
                    # 2. "Inmobiliaria recomendada" badge = Agency
                    # 3. Agency profile links in owner-info = Agency
                    has_agency_link = bool(re.search(r'href="[^"]*\/inmobiliaria-', html, re.IGNORECASE))
                    has_agency_badge = bool(re.search(r'Inmobiliaria\s+recomendada', html, re.IGNORECASE))
                    has_agency_profile = bool(re.search(r'owner-info[^>]*>.*?/inmobiliaria-', html, re.IGNORECASE | re.DOTALL))

                    is_agency = has_agency_link or has_agency_badge or has_agency_profile

                    if is_agency:
                        listing['vendedor'] = 'Inmobiliaria'
                        listing['es_particular'] = False
                    else:
                        # No agency indicators found - assume particular
                        listing['vendedor'] = 'Particular'
                        listing['es_particular'] = True

                    results.append(listing)

                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")

            return results

        enriched = fetch_details({'listings': listings})

        # No filtering - return all listings
        return enriched

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            self.stats['total_listings'] += 1
            # No filtering - save all listings
            if self.save_to_postgres(listing, self.PORTAL_NAME):
                self.stats['saved'] += 1

        logger.info(f"Stats: {self.stats}")
        return self.stats


def run_pisos_botasaurus(
    zones: List[str] = None,
    postgres: bool = False,
    headless: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convenience function to run the Pisos.com scraper.

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

    with BotasaurusPisos(
        zones=zones or ['tarragona_provincia'],
        postgres_config=postgres_config,
        headless=headless,
    ) as scraper:
        if postgres:
            scraper.scrape_and_save()
        return scraper.scrape()


if __name__ == '__main__':
    import sys

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")
    print(f"Available zones: {list(ZONAS_GEOGRAFICAS.keys())}")

    listings = run_pisos_botasaurus(zones=zones, headless=True)

    print(f"\nFound {len(listings)} listings:")
    for l in listings[:5]:
        print(f"  - {l.get('titulo', 'N/A')[:50]}... | {l.get('precio')}€ | {l.get('vendedor')}")

"""
Idealista scraper using ScrapingBee API.

This scraper extracts real estate listings from Idealista.com
using ScrapingBee's stealth proxy to bypass DataDome protection.

Cost: 75 credits per page (stealth mode)
"""

import logging
import re
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode

from scrapers.scrapingbee_base import ScrapingBeeClient

logger = logging.getLogger(__name__)


# Geographic zones configuration for Idealista
ZONAS_GEOGRAFICAS = {
    # =============================================================
    # PROVINCES
    # =============================================================
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_path': 'tarragona-provincia',
        'url_code': 'tarragona-provincia',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'lleida-provincia',
        'url_code': 'lleida-provincia',
    },

    # =============================================================
    # COMARCAS - Composite zones
    # =============================================================
    'tarragones': {
        'nombre': 'Tarragonès',
        'composite': ['tarragona', 'torredembarra', 'altafulla'],
    },
    'baix_camp': {
        'nombre': 'Baix Camp',
        'composite': ['reus', 'cambrils', 'salou', 'vila_seca'],
    },
    'baix_penedes': {
        'nombre': 'Baix Penedès',
        'composite': ['vendrell', 'calafell'],
    },
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'composite': ['salou', 'cambrils', 'tarragona', 'torredembarra', 'calafell', 'vendrell'],
    },
    'segria': {
        'nombre': 'Segrià',
        'composite': ['lleida'],
    },

    # =============================================================
    # CITIES - Lleida
    # =============================================================
    'lleida': {
        'nombre': 'Lleida',
        'url_path': 'lleida-lleida',
        'url_code': 'lleida-lleida',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_path': 'balaguer-lleida',
        'url_code': 'balaguer-lleida',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'url_path': 'mollerussa-lleida',
        'url_code': 'mollerussa-lleida',
    },
    'tremp': {
        'nombre': 'Tremp',
        'url_path': 'tremp-lleida',
        'url_code': 'tremp-lleida',
    },
    'tarrega': {
        'nombre': 'Tàrrega',
        'url_path': 'tarrega-lleida',
        'url_code': 'tarrega-lleida',
    },

    # =============================================================
    # CITIES - Tarragona
    # =============================================================
    'tarragona': {
        'nombre': 'Tarragona',
        'url_path': 'tarragona-tarragona',
        'url_code': 'tarragona-tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'reus-tarragona',
        'url_code': 'reus-tarragona',
    },
    'salou': {
        'nombre': 'Salou',
        'url_path': 'salou-tarragona',
        'url_code': 'salou-tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'cambrils-tarragona',
        'url_code': 'cambrils-tarragona',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'calafell-tarragona',
        'url_code': 'calafell-tarragona',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_path': 'el-vendrell-tarragona',
        'url_code': 'el-vendrell-tarragona',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'torredembarra-tarragona',
        'url_code': 'torredembarra-tarragona',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'url_path': 'altafulla-tarragona',
        'url_code': 'altafulla-tarragona',
    },
    'miami_platja': {
        'nombre': 'Miami Platja',
        'url_path': 'miami-platja-tarragona',
        'url_code': 'miami-platja-tarragona',
    },
    'vila_seca': {
        'nombre': 'Vila-seca',
        'url_path': 'vila-seca-tarragona',
        'url_code': 'vila-seca-tarragona',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'valls-tarragona',
        'url_code': 'valls-tarragona',
    },
    'montblanc': {
        'nombre': 'Montblanc',
        'url_path': 'montblanc-tarragona',
        'url_code': 'montblanc-tarragona',
    },

    # Terres de l'Ebre
    'tortosa': {
        'nombre': 'Tortosa',
        'url_path': 'tortosa-tarragona',
        'url_code': 'tortosa-tarragona',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_path': 'amposta-tarragona',
        'url_code': 'amposta-tarragona',
    },
    'deltebre': {
        'nombre': 'Deltebre',
        'url_path': 'deltebre-tarragona',
        'url_code': 'deltebre-tarragona',
    },
    'sant_carles_rapita': {
        'nombre': 'Sant Carles de la Ràpita',
        'url_path': 'sant-carles-de-la-rapita-tarragona',
        'url_code': 'sant-carles-de-la-rapita-tarragona',
    },
}


class ScrapingBeeIdealista(ScrapingBeeClient):
    """
    Idealista scraper using ScrapingBee API.

    Uses stealth proxy to bypass DataDome protection.
    """

    PORTAL_NAME = 'idealista'
    BASE_URL = 'https://www.idealista.com'

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        use_stealth: bool = True,
        max_pages_per_zone: int = 2,
        only_particulares: bool = True,
    ):
        """
        Initialize Idealista scraper.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            zones: List of zones to scrape
            postgres_config: PostgreSQL config (auto-detected if None)
            use_stealth: Use stealth proxy (required for Idealista)
            max_pages_per_zone: Maximum pages per zone (budget control)
            only_particulares: Only scrape particular listings (not agencies)
        """
        super().__init__(
            portal_name=self.PORTAL_NAME,
            tenant_id=tenant_id,
            use_stealth=use_stealth,
            postgres_config=postgres_config,
        )
        self.zones = zones or ['salou']
        self.max_pages_per_zone = max_pages_per_zone
        self.only_particulares = only_particulares

    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        """Build Idealista search URL for a zone."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        # Idealista URL format: /venta-viviendas/zona/
        # Note: Idealista doesn't have a public URL filter for particulares
        # Agency filtering is done programmatically in _scrape_detail_page()
        url_path = zona['url_path']
        base_url = f"{self.BASE_URL}/venta-viviendas/{url_path}/"

        if page > 1:
            base_url += f'pagina-{page}.htm'

        return base_url

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to float."""
        if not price_text:
            return None
        try:
            # Remove currency symbols, spaces, dots (thousand separators)
            cleaned = re.sub(r'[€$\s\xa0.]', '', price_text)
            # Replace comma with dot if it's a decimal separator
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except:
            return None

    def _extract_listings_from_html(self, html: str, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listing URLs and basic data from search results HTML."""
        listings = []

        # Check for actual blocking indicators (DataDome, access denied, etc.)
        # Note: "blocked" and "captcha" appear in normal page content (CSS classes, URL configs)
        blocking_patterns = [
            r'access.denied|acceso.denegado',
            r'you.have.been.blocked',
            r'datadome.*blocked',
            r'<title>.*blocked.*</title>',
            r'please.complete.*captcha.*to.continue',
        ]
        for pattern in blocking_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                logger.warning(f"Blocking detected: {pattern}")
                return []

        # Find listing URLs in article elements
        # Idealista format: /inmueble/ID/
        url_pattern = r'href="(/inmueble/(\d+)/)"'
        matches = re.findall(url_pattern, html)

        if not matches:
            # Alternative pattern for listing cards
            url_pattern = r'href="(/venta-viviendas/[^"]+/(\d{5,})/)"'
            matches = re.findall(url_pattern, html)

        seen_ids = set()
        for path, anuncio_id in matches:
            if anuncio_id in seen_ids:
                continue
            seen_ids.add(anuncio_id)

            detail_url = f"{self.BASE_URL}{path}"
            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            listings.append({
                'anuncio_id': anuncio_id,
                'detail_url': detail_url,
                'url_anuncio': detail_url,
                'portal': self.PORTAL_NAME,
                'zona_busqueda': zona_info.get('nombre', zona_key),
                'zona_geografica': zona_info.get('nombre', zona_key),
            })

        logger.info(f"Found {len(listings)} listing URLs in search results")
        return listings

    def _scrape_detail_page(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape detail page to extract full listing data."""
        detail_url = listing['detail_url']

        html = self.fetch_page(
            detail_url,
            wait_for='.detail-info',
        )

        if not html:
            return listing

        # Check if agency listing (skip if only_particulares)
        is_agency = bool(re.search(
            r'class="[^"]*professional[^"]*"|class="[^"]*agency[^"]*"|inmobiliaria',
            html, re.IGNORECASE
        ))

        if is_agency and self.only_particulares:
            logger.info(f"Skipping agency listing: {listing['anuncio_id']}")
            listing['es_particular'] = False
            listing['vendedor'] = 'Profesional'
            return listing

        listing['es_particular'] = not is_agency
        listing['vendedor'] = 'Particular' if not is_agency else 'Profesional'

        # Extract title
        title_match = re.search(r'<h1[^>]*class="[^"]*main-info__title[^"]*"[^>]*>([^<]+)</h1>', html)
        if not title_match:
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            listing['titulo'] = title_match.group(1).strip()

        # Extract description
        desc_match = re.search(
            r'class="[^"]*comment[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if not desc_match:
            desc_match = re.search(
                r'class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL
            )
        if desc_match:
            desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1))
            listing['descripcion'] = desc_text.strip()[:2000]

        # Extract price
        price_match = re.search(
            r'class="[^"]*info-data-price[^"]*"[^>]*>([^<]+)',
            html
        )
        if not price_match:
            price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*€', html)
        if price_match:
            listing['precio'] = self._parse_price(price_match.group(1))

        # Extract location
        location_match = re.search(
            r'class="[^"]*main-info__title-minor[^"]*"[^>]*>([^<]+)',
            html
        )
        if location_match:
            listing['ubicacion'] = location_match.group(1).strip()

        # Try to extract phone from description (many sellers put it there)
        descripcion = listing.get('descripcion', '')
        phone = self.extract_phone_from_description(descripcion)
        if phone:
            listing['telefono'] = phone
            listing['telefono_norm'] = phone
            logger.info(f"Phone found in description: {phone}")
        else:
            listing['telefono'] = None
            listing['telefono_norm'] = None

        # Extract features from info-features section
        # Metros cuadrados
        metros_match = re.search(r'(\d+)\s*m[²2]', html)
        if metros_match:
            listing['metros'] = int(metros_match.group(1))

        # Habitaciones
        habs_match = re.search(r'(\d+)\s*(?:hab|habitaci|dormitor)', html, re.IGNORECASE)
        if habs_match:
            listing['habitaciones'] = int(habs_match.group(1))

        # Baños
        banos_match = re.search(r'(\d+)\s*(?:baño|wc)', html, re.IGNORECASE)
        if banos_match:
            listing['banos'] = int(banos_match.group(1))

        # Extract photos (Idealista CDN: img3.idealista.com)
        photos = re.findall(
            r'(https://img\d*\.idealista\.com/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp))',
            html, re.IGNORECASE
        )
        unique_photos = []
        seen = set()
        for photo in photos:
            photo_clean = re.sub(r'\?.*$', '', photo)
            if photo_clean not in seen and 'logo' not in photo.lower():
                unique_photos.append(photo)
                seen.add(photo_clean)
        listing['fotos'] = unique_photos[:10]

        # Extract energy certificate
        energy_match = re.search(
            r'class="[^"]*energy[^"]*"[^>]*>([A-G])</span>',
            html, re.IGNORECASE
        )
        if energy_match:
            listing['certificado_energetico'] = energy_match.group(1).upper()

        return listing

    def scrape_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape all listings from a zone (handles composite zones)."""
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Handle composite zones (comarcas)
        if 'composite' in zona_info:
            logger.info(f"Composite zone {zona_key}: {zona_info['composite']}")
            all_listings = []
            for city_key in zona_info['composite']:
                if city_key in ZONAS_GEOGRAFICAS:
                    logger.info(f"  Scraping city: {city_key}")
                    city_listings = self._scrape_single_zone(city_key)
                    all_listings.extend(city_listings)
                else:
                    logger.warning(f"  City not found: {city_key}")
            return all_listings

        return self._scrape_single_zone(zona_key)

    def _scrape_single_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape a single municipality zone."""
        all_listings = []
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        logger.info(f"Scraping zone: {zona_info.get('nombre', zona_key)}")

        for page in range(1, self.max_pages_per_zone + 1):
            search_url = self.build_search_url(zona_key, page)
            logger.info(f"Scraping page {page} of {zona_key}")

            html = self.fetch_page(
                search_url,
                wait_for='.items-list',
            )

            if not html:
                logger.warning(f"Failed to fetch page {page}")
                break

            # Extract listing URLs from search results
            basic_listings = self._extract_listings_from_html(html, zona_key)

            if not basic_listings:
                logger.info(f"No more listings found on page {page}")
                break

            self.stats['pages_scraped'] += 1

            # Scrape each detail page
            for i, listing in enumerate(basic_listings[:10]):  # Limit per page
                logger.info(f"Detail page {i+1}/{len(basic_listings[:10])}")

                enriched = self._scrape_detail_page(listing)
                self.stats['listings_found'] += 1

                # Only keep particular listings if filter is enabled
                if self.only_particulares and not enriched.get('es_particular', True):
                    continue

                all_listings.append(enriched)

                # Delay between requests
                time.sleep(0.5)

            # Check if we should continue to next page
            if len(basic_listings) < 10:
                logger.info("Less than 10 listings, assuming last page")
                break

            # Delay between pages
            time.sleep(1)

        return all_listings

    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape all configured zones."""
        all_listings = []

        for zona_key in self.zones:
            try:
                listings = self.scrape_zone(zona_key)
                all_listings.extend(listings)
                logger.info(f"Zone {zona_key}: {len(listings)} listings")
            except Exception as e:
                logger.error(f"Error scraping zone {zona_key}: {e}")
                self.stats['errors'] += 1

        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            # Only save if it has a phone (useful leads)
            if listing.get('telefono_norm'):
                self.save_to_postgres(listing)

        logger.info(f"Scraping complete. Stats: {self.get_stats()}")
        return self.get_stats()


def run_scrapingbee_idealista(
    zones: List[str] = None,
    tenant_id: int = 1,
    max_pages_per_zone: int = 2,
    only_particulares: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to run ScrapingBee Idealista scraper.

    Args:
        zones: List of zones to scrape
        tenant_id: Tenant ID
        max_pages_per_zone: Max pages per zone (budget control)
        only_particulares: Only scrape particular listings

    Returns:
        Scraping statistics
    """
    with ScrapingBeeIdealista(
        zones=zones or ['salou', 'cambrils'],
        tenant_id=tenant_id,
        max_pages_per_zone=max_pages_per_zone,
        only_particulares=only_particulares,
    ) as scraper:
        scraper.scrape_and_save()
        return scraper.get_stats()


if __name__ == '__main__':
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")
    print(f"Available zones: {list(ZONAS_GEOGRAFICAS.keys())}")

    stats = run_scrapingbee_idealista(zones=zones, max_pages_per_zone=2)
    print(f"\nStats: {stats}")

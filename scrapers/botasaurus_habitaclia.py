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
    # Provinces
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_slug': 'tarragona_provincia',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_slug': 'lleida_provincia',
    },
    # Cities - Tarragona
    'tarragona': {
        'nombre': 'Tarragona',
        'url_slug': 'tarragona',
    },
    'salou': {
        'nombre': 'Salou',
        'url_slug': 'salou',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_slug': 'cambrils',
    },
    'reus': {
        'nombre': 'Reus',
        'url_slug': 'reus',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_slug': 'calafell',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_slug': 'torredembarra',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_slug': 'el_vendrell',
    },
    'valls': {
        'nombre': 'Valls',
        'url_slug': 'valls',
    },
    'tortosa': {
        'nombre': 'Tortosa',
        'url_slug': 'tortosa',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_slug': 'amposta',
    },
    # Cities - Lleida
    'lleida': {
        'nombre': 'Lleida',
        'url_slug': 'lleida',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_slug': 'balaguer',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'url_slug': 'mollerussa',
    },
}


class BotasaurusHabitaclia(BotasaurusBaseScraper):
    """Habitaclia scraper using Botasaurus."""

    PORTAL_NAME = 'habitaclia'
    BASE_URL = 'https://www.habitaclia.com'

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

        # Use /viviendas-particulares-{zona}.htm to filter private sellers
        if self.only_private:
            url = f"{self.BASE_URL}/viviendas-particulares-{zona['url_slug']}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-particulares-{zona['url_slug']}-pag{page}.htm"
        else:
            url = f"{self.BASE_URL}/viviendas-{zona['url_slug']}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-{zona['url_slug']}-pag{page}.htm"

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
        """Scrape a single zone."""
        url = self.build_url(zona_key)
        headless = self.headless
        base_url = self.BASE_URL
        portal = self.PORTAL_NAME
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

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
                    'zona_busqueda': zona_info.get('nombre', zona_key),
                    'zona_geografica': zona_info.get('nombre', zona_key),
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

                    # Extract location
                    ubicacion_match = re.search(r'class="[^"]*location[^"]*"[^>]*>([^<]+)', html, re.IGNORECASE)
                    if ubicacion_match:
                        listing['ubicacion'] = ubicacion_match.group(1).strip()

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

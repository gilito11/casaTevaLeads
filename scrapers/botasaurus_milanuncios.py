"""
Milanuncios scraper using Botasaurus.

This scraper extracts real estate listings from Milanuncios.com
using Botasaurus for anti-bot bypass (free, open-source).
"""

import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode, quote

from botasaurus.browser import browser, Driver

from scrapers.botasaurus_base import BotasaurusBaseScraper

logger = logging.getLogger(__name__)


# Geographic zones configuration
ZONAS_GEOGRAFICAS = {
    # LLEIDA
    'lleida_ciudad': {
        'nombre': 'Lleida Ciudad',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
    },
    'lleida_20km': {
        'nombre': 'Lleida (20 km)',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
        'distance': 20000,
    },
    'lleida_50km': {
        'nombre': 'Lleida (50 km)',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
        'distance': 50000,
    },
    # TARRAGONA
    'tarragona_ciudad': {
        'nombre': 'Tarragona Ciudad',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
    },
    'tarragona_30km': {
        'nombre': 'Tarragona (30 km)',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
        'distance': 30000,
    },
    # COSTA DAURADA
    'salou': {
        'nombre': 'Salou',
        'latitude': 41.0764,
        'longitude': 1.1416,
        'geoProvinceId': 43,
        'geolocationTerm': 'Salou, Tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'latitude': 41.0672,
        'longitude': 1.0597,
        'geoProvinceId': 43,
        'geolocationTerm': 'Cambrils, Tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'latitude': 41.1548,
        'longitude': 1.1078,
        'geoProvinceId': 43,
        'geolocationTerm': 'Reus, Tarragona',
    },
}


class BotasaurusMilanuncios(BotasaurusBaseScraper):
    """Milanuncios scraper using Botasaurus."""

    PORTAL_NAME = 'milanuncios'

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        headless: bool = True,
        distance: int = 20000,
    ):
        super().__init__(tenant_id, postgres_config, headless)
        self.zones = zones or ['salou']
        self.distance = distance

    def build_url(self, zona_key: str, page: int = 1) -> str:
        """Build search URL for Milanuncios."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        zone_distance = zona.get('distance', self.distance)

        params = {
            'vendedor': 'part',  # Only particulares
            'latitude': zona['latitude'],
            'longitude': zona['longitude'],
            'distance': zone_distance,
            'geoProvinceId': zona['geoProvinceId'],
            'geolocationTerm': zona['geolocationTerm'],
            'orden': 'date',
            'fromSearch': 1,
            'desde': 5000,  # Min price filter
        }

        if page > 1:
            params['pagina'] = page

        return f"https://www.milanuncios.com/inmobiliaria/?{urlencode(params, quote_via=quote)}"

    def parse_listing_card(self, card_html: str, zona_key: str) -> Optional[Dict[str, Any]]:
        """Parse a listing card HTML to extract data."""
        try:
            # Extract title
            title_match = re.search(r'<h2[^>]*>([^<]+)</h2>', card_html)
            titulo = title_match.group(1).strip() if title_match else None

            # Extract URL and ID
            url_match = re.search(r'href="(/[^"]+\-(\d+)\.htm)"', card_html)
            if not url_match:
                return None

            detail_path = url_match.group(1)
            anuncio_id = url_match.group(2)
            detail_url = f"https://www.milanuncios.com{detail_path}"

            # Extract price
            price_match = re.search(r'class="[^"]*AdPrice[^"]*"[^>]*>([^<]+)', card_html)
            precio = None
            if price_match:
                price_text = price_match.group(1)
                precio = self._parse_price(price_text)

            # Extract location
            location_match = re.search(r'class="[^"]*AdLocation[^"]*"[^>]*>([^<]+)', card_html)
            ubicacion = location_match.group(1).strip() if location_match else None

            # Extract features
            habitaciones = None
            metros = None
            features = re.findall(r'class="[^"]*AdTag-label[^"]*"[^>]*>([^<]+)', card_html)
            for feature in features:
                if 'dorm' in feature.lower():
                    habitaciones = self._parse_number(feature)
                elif 'm²' in feature.lower() or 'm2' in feature.lower():
                    if '€' not in feature:
                        metros = self._parse_number(feature)

            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            return {
                'anuncio_id': anuncio_id,
                'titulo': titulo,
                'precio': precio,
                'ubicacion': ubicacion,
                'habitaciones': habitaciones,
                'metros': metros,
                'detail_url': detail_url,
                'url_anuncio': detail_url,
                'portal': self.PORTAL_NAME,
                'zona_busqueda': zona_info.get('nombre', zona_key),
                'zona_geografica': zona_info.get('nombre', zona_key),
                'vendedor': 'Particular',  # Filtered by URL
            }

        except Exception as e:
            logger.error(f"Error parsing card: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to float."""
        if not price_text:
            return None
        try:
            cleaned = re.sub(r'[€$\s\xa0]', '', price_text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            return float(cleaned)
        except:
            return None

    def _parse_number(self, text: str) -> Optional[int]:
        """Extract first number from text."""
        if not text:
            return None
        match = re.search(r'\d+', text)
        return int(match.group()) if match else None

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

        @browser(headless=headless, block_images=True)
        def scrape_page(driver: Driver, data: dict):
            url = data['url']
            zona_key = data['zona_key']

            logger.info(f"Loading: {url}")
            driver.get(url)
            driver.sleep(4)

            html = driver.page_html

            # Check for blocking
            if len(html) < 10000 or 'captcha' in html.lower():
                logger.warning("Possible blocking detected")
                return []

            # Extract listing cards
            cards = re.findall(
                r'data-testid="AD_CARD"[^>]*>(.*?)</article>',
                html,
                re.DOTALL
            )

            logger.info(f"Found {len(cards)} listing cards")
            return {'html': html, 'cards': cards, 'zona_key': zona_key}

        result = scrape_page({'url': url, 'zona_key': zona_key})

        if not result or not result.get('cards'):
            return []

        listings = []
        for card_html in result['cards']:
            listing = self.parse_listing_card(card_html, zona_key)
            if listing:
                self.stats['total_listings'] += 1

                # Apply filters
                if listing.get('precio') and listing['precio'] < 5000:
                    self.stats['filtered_out'] += 1
                    continue

                if not self.should_scrape(listing):
                    self.stats['filtered_out'] += 1
                    continue

                listings.append(listing)

        return listings

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            if self.save_to_postgres(listing, self.PORTAL_NAME):
                self.stats['saved'] += 1

        logger.info(f"Stats: {self.stats}")
        return self.stats


def run_milanuncios_botasaurus(
    zones: List[str] = None,
    postgres: bool = False,
    headless: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convenience function to run the Milanuncios scraper.

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

    with BotasaurusMilanuncios(
        zones=zones or ['salou'],
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

    listings = run_milanuncios_botasaurus(zones=zones, headless=True)

    print(f"\nFound {len(listings)} listings:")
    for l in listings[:5]:
        print(f"  - {l['titulo'][:50]}... | {l['precio']}€ | {l['ubicacion']}")

"""
Milanuncios scraper using Botasaurus.

This scraper extracts real estate listings from Milanuncios.com
using Botasaurus for anti-bot bypass (free, open-source).
"""

import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode, quote

from botasaurus.browser import browser, Driver

from scrapers.botasaurus_base import BotasaurusBaseScraper

logger = logging.getLogger(__name__)

# Cookie file path
COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'milanuncios_cookies.json')

def load_milanuncios_cookies():
    """Load cookies from file if exists."""
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, 'r') as f:
                data = json.load(f)
                cookies = data.get('cookies', [])
                if cookies:
                    logger.info(f"Loaded {len(cookies)} cookies from {COOKIES_FILE}")
                return cookies
        except Exception as e:
            logger.warning(f"Could not load cookies: {e}")
    return []


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

            # Extract URL and ID - try multiple patterns
            # Pattern 1: Standard format with dash before ID
            url_match = re.search(r'href="(/[^"]+\-(\d+)\.htm)"', card_html)

            # Pattern 2: Try any .htm URL with ID at end
            if not url_match:
                url_match = re.search(r'href="(/[^"]*?(\d{6,})\.htm)"', card_html)

            # Pattern 3: Look for anuncio ID in data attributes
            if not url_match:
                anuncio_id_match = re.search(r'data-ad-id="(\d+)"', card_html)
                href_match = re.search(r'href="(/[^"]+\.htm)"', card_html)
                if anuncio_id_match and href_match:
                    url_match = type('obj', (object,), {
                        'group': lambda self, n: href_match.group(1) if n == 1 else anuncio_id_match.group(1)
                    })()

            if not url_match:
                # Log some card content to debug
                logger.debug(f"No URL found in card. First 200 chars: {card_html[:200]}")
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

    @staticmethod
    def _scrape_detail_page_internal(driver: Driver, detail_url: str, parse_price_func) -> Dict[str, Any]:
        """
        Visit detail page and extract full listing data (internal method for use within browser session).

        Returns dict with: descripcion, telefono, fotos, precio (if not already set)
        """
        try:
            logger.info(f"Visiting detail page: {detail_url}")
            driver.get(detail_url)
            driver.sleep(2)

            html = driver.page_html
            result = {}

            # Extract description
            desc_match = re.search(
                r'class="[^"]*AdDetail-description[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL
            )
            if desc_match:
                desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1))
                result['descripcion'] = desc_text.strip()

            # Extract phone number - look for "Ver teléfono" button or revealed number
            phone_match = re.search(r'tel:(\d{9,})', html)
            if phone_match:
                result['telefono'] = phone_match.group(1)
            else:
                # Try to find phone in description or specific elements
                phone_in_text = re.search(r'(\d{3}[\s.-]?\d{3}[\s.-]?\d{3})', html)
                if phone_in_text:
                    result['telefono'] = re.sub(r'[\s.-]', '', phone_in_text.group(1))

            # Extract all photos
            photos = re.findall(
                r'(https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)',
                html, re.IGNORECASE
            )
            # Filter to unique, full-size images (from milanuncios CDN)
            unique_photos = []
            seen = set()
            for photo in photos:
                # Only keep milanuncios images
                if 'milanuncios' not in photo.lower():
                    continue
                # Skip thumbnails and duplicates
                if 'thumbnail' not in photo.lower() and photo not in seen:
                    photo_clean = re.sub(r'\?.*$', '', photo)
                    if photo_clean not in seen:
                        unique_photos.append(photo)
                        seen.add(photo_clean)
            result['fotos'] = unique_photos[:10]  # Max 10 photos

            # Extract price if not already set (from detail page)
            price_match = re.search(
                r'class="[^"]*AdDetail[^"]*[Pp]rice[^"]*"[^>]*>([^<]+)',
                html
            )
            if price_match:
                result['precio_detail'] = parse_price_func(price_match.group(1))

            # Extract seller name
            seller_match = re.search(
                r'class="[^"]*AdDetail-sellerName[^"]*"[^>]*>([^<]+)',
                html
            )
            if seller_match:
                result['vendedor'] = seller_match.group(1).strip()

            return result

        except Exception as e:
            logger.error(f"Error scraping detail page {detail_url}: {e}")
            return {}

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
        """Scrape a single zone by clicking on each card to visit detail pages."""
        url = self.build_url(zona_key)
        headless = self.headless
        scraper_self = self  # Reference for inner function
        parse_price_func = self._parse_price
        should_scrape_func = self.should_scrape
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Chrome flags for container environments
        container_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-setuid-sandbox',
            '--single-process',
        ]

        # Use full stealth mode with realistic user agent
        @browser(
            headless=headless,
            block_images=False,  # Need images for photos
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            add_arguments=container_args,
        )
        def scrape_zone_by_clicking(driver: Driver, data: dict):
            url = data['url']
            zona_key = data['zona_key']

            logger.info(f"Loading: {url}")
            driver.get(url)
            driver.sleep(5)  # Wait longer for full page load

            html = driver.page_html
            logger.info(f"Page HTML length: {len(html)}")

            # Check for blocking - be more lenient
            if len(html) < 5000:
                logger.warning(f"Page too short ({len(html)} chars), possible blocking")
                return []

            # Check for AD_CARD presence as the primary validation
            has_cards = 'data-testid="AD_CARD"' in html or 'AD_LIST' in html
            if not has_cards:
                # Save HTML for debugging
                with open('/app/output/milanuncios_failed.html', 'w') as f:
                    f.write(html)
                logger.warning(f"No listing cards found in HTML. Saved to milanuncios_failed.html")
                return []

            logger.info("Page loaded successfully with listings")

            # Find all listing URLs in the full page HTML
            # Search for URLs with numeric IDs (like -568292696.htm)
            listing_urls = driver.run_js('''
                const html = document.documentElement.outerHTML;
                const urlPattern = /href="(\\/[\\w-]+\\/[\\w-]+-\\d+\\.htm)"/g;
                const urls = [];
                let match;
                while ((match = urlPattern.exec(html)) !== null) {
                    // Filter to real estate URLs only
                    const url = match[1];
                    if (url.includes('venta-de-') || url.includes('alquiler-de-')) {
                        urls.push(url);
                    }
                }
                return [...new Set(urls)];  // Remove duplicates
            ''')

            logger.info(f"Found {len(listing_urls)} listing URLs in page")

            listings = []

            for i, path in enumerate(listing_urls):
                try:
                    scraper_self.stats['total_listings'] += 1

                    detail_url = f"https://www.milanuncios.com{path}"
                    logger.info(f"Listing {i+1}/{len(listing_urls)}: {detail_url[:70]}...")

                    driver.get(detail_url)
                    driver.sleep(2)

                    # Extract anuncio_id from URL
                    id_match = re.search(r'-(\d+)\.htm', detail_url)
                    if not id_match:
                        logger.warning(f"Listing {i+1}: No ID in URL {detail_url}")
                        continue

                    anuncio_id = id_match.group(1)

                    # Extract data from detail page
                    detail_html = driver.page_html

                    # Extract title
                    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', detail_html)
                    titulo = title_match.group(1).strip() if title_match else None

                    # Extract description
                    desc_match = re.search(
                        r'class="[^"]*AdDetail-description[^"]*"[^>]*>(.*?)</div>',
                        detail_html, re.DOTALL
                    )
                    descripcion = None
                    if desc_match:
                        descripcion = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

                    # Extract price
                    price_match = re.search(r'class="[^"]*[Pp]rice[^"]*"[^>]*>([^<]+)', detail_html)
                    precio = parse_price_func(price_match.group(1)) if price_match else None

                    # Extract location
                    location_match = re.search(r'class="[^"]*AdDetail[^"]*[Ll]ocation[^"]*"[^>]*>([^<]+)', detail_html)
                    ubicacion = location_match.group(1).strip() if location_match else None

                    # Extract phone
                    phone_match = re.search(r'tel:(\d{9,})', detail_html)
                    telefono = phone_match.group(1) if phone_match else None
                    if not telefono:
                        phone_in_text = re.search(r'(\d{3}[\s.-]?\d{3}[\s.-]?\d{3})', detail_html)
                        if phone_in_text:
                            telefono = re.sub(r'[\s.-]', '', phone_in_text.group(1))

                    # Extract photos
                    photos = re.findall(
                        r'(https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)',
                        detail_html, re.IGNORECASE
                    )
                    unique_photos = []
                    seen = set()
                    for photo in photos:
                        if 'milanuncios' not in photo.lower():
                            continue
                        if 'thumbnail' in photo.lower():
                            continue
                        photo_clean = re.sub(r'\?.*$', '', photo)
                        if photo_clean not in seen:
                            unique_photos.append(photo)
                            seen.add(photo_clean)
                    fotos = unique_photos[:10]

                    # Build listing
                    listing = {
                        'anuncio_id': anuncio_id,
                        'titulo': titulo,
                        'precio': precio,
                        'ubicacion': ubicacion,
                        'descripcion': descripcion,
                        'telefono': telefono,
                        'telefono_norm': telefono,
                        'fotos': fotos,
                        'detail_url': detail_url,
                        'url_anuncio': detail_url,
                        'portal': 'milanuncios',
                        'zona_busqueda': zona_info.get('nombre', zona_key),
                        'zona_geografica': zona_info.get('nombre', zona_key),
                        'vendedor': 'Particular',
                    }

                    # Apply price filter
                    if precio and precio < 5000:
                        logger.info(f"Listing {i+1}: Filtered (price {precio} < 5000)")
                        scraper_self.stats['filtered_out'] += 1
                        continue

                    # Apply particular filter
                    if not should_scrape_func(listing):
                        logger.info(f"Listing {i+1}: Filtered (not particular)")
                        scraper_self.stats['filtered_out'] += 1
                        continue

                    logger.info(f"Listing {i+1}: OK - {titulo[:40] if titulo else 'No title'}... | {precio}€ | Phone: {telefono}")
                    listings.append(listing)

                    # Small delay
                    driver.sleep(1)

                except Exception as e:
                    logger.error(f"Listing {i+1}: Error - {e}")

            return listings

        return scrape_zone_by_clicking({'url': url, 'zona_key': zona_key})

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

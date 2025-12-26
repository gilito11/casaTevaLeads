"""
Fotocasa scraper using Botasaurus.

This scraper extracts real estate listings from Fotocasa.es
using Botasaurus for anti-bot bypass (free, open-source).
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
        'url_path': 'tarragona-provincia/todas-las-zonas',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'lleida-provincia/todas-las-zonas',
    },
    # Cities
    'tarragona': {
        'nombre': 'Tarragona',
        'url_path': 'tarragona/todas-las-zonas',
    },
    'lleida': {
        'nombre': 'Lleida',
        'url_path': 'lleida/todas-las-zonas',
    },
    'salou': {
        'nombre': 'Salou',
        'url_path': 'salou/todas-las-zonas',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'cambrils/todas-las-zonas',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'reus/todas-las-zonas',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'calafell/todas-las-zonas',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'torredembarra/todas-las-zonas',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'valls/todas-las-zonas',
    },
}


class BotasaurusFotocasa(BotasaurusBaseScraper):
    """Fotocasa scraper using Botasaurus."""

    PORTAL_NAME = 'fotocasa'
    BASE_URL = 'https://www.fotocasa.es'

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
        """Build search URL for Fotocasa."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        # Note: /particulares/ filter doesn't work for all zones, filter in detail page instead
        url = f"{self.BASE_URL}/es/comprar/viviendas/{zona['url_path']}/l"

        if page > 1:
            url += f'?pageNumber={page}'

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

        @browser(headless=headless, block_images=False)
        def scrape_page(driver: Driver, data: dict):
            url = data['url']

            logger.info(f"Loading: {url}")
            driver.get(url)
            driver.sleep(6)

            # Scroll multiple times to load all lazy content
            for i in range(4):
                driver.run_js(f'window.scrollTo({{top: {1000 * (i+1)}, behavior: "smooth"}})')
                driver.sleep(1.5)

            html = driver.page_html

            # Check for blocking
            if len(html) < 50000:
                logger.warning("Possible blocking or empty results")
                return []

            # Extract listing URLs (format: /es/comprar/vivienda/zona/.../ID/d or .../ID1/ID2)
            links = re.findall(r'href="(/es/comprar/vivienda/[^?"]+)"', html)
            # Filter to only property detail links (end with /d or /digits)
            links = [l for l in links if re.search(r'/\d+(?:/d)?$', l)]
            unique_links = list(dict.fromkeys(links))

            logger.info(f"Found {len(unique_links)} listing links")

            listings = []
            for link in unique_links[:20]:  # Limit to avoid timeout
                detail_url = f"{base_url}{link}"

                # Extract ID from URL (last number before /d)
                id_match = re.search(r'/(\d{7,})(?:/d)?$', link)
                if not id_match:
                    continue

                anuncio_id = id_match.group(1)

                listings.append({
                    'anuncio_id': anuncio_id,
                    'detail_url': detail_url,
                    'url_anuncio': detail_url,
                    'portal': portal,
                    'zona_busqueda': zona_info.get('nombre', zona_key),
                    'zona_geografica': zona_info.get('nombre', zona_key),
                })

            return listings

        basic_listings = scrape_page({'url': url})

        if not basic_listings:
            return []

        # Enrich with detail page data
        enriched_listings = self._enrich_listings(basic_listings[:10])  # Limit for speed

        return enriched_listings

    def _enrich_listings(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch detail pages to extract more info - one browser per listing."""
        import random
        import time
        headless = self.headless
        results = []

        for i, listing in enumerate(listings):
            url = listing['detail_url']
            logger.info(f"Fetching detail {i+1}/{len(listings)}: {url[:60]}...")

            # Random delay between requests (3-8 seconds)
            if i > 0:
                delay = random.uniform(3, 8)
                logger.info(f"Waiting {delay:.1f}s before next request...")
                time.sleep(delay)

            # Create a new browser session for each listing
            @browser(headless=headless, block_images=False, reuse_driver=False)
            def fetch_single_detail(driver: Driver, data: dict):
                try:
                    driver.get(data['url'])
                    driver.sleep(random.uniform(3, 5))

                    # Human-like scrolling
                    for pos in [300, 600, 900]:
                        driver.run_js(f'window.scrollTo({{top: {pos}, behavior: "smooth"}})')
                        driver.sleep(random.uniform(0.5, 1.0))

                    return driver.page_html
                except Exception as e:
                    logger.error(f"Error in browser: {e}")
                    return None

            html = fetch_single_detail({'url': url})

            if not html:
                continue

            # Check for blocking
            if 'SENTIMOS LA INTERRUPCIÓN' in html or 'captcha' in html.lower():
                logger.warning("Fotocasa anti-bot detected, skipping this listing")
                continue

            try:
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
                # Fotocasa descriptions are typically in divs or paragraphs
                desc_match = re.search(
                    r'class="[^"]*(?:re-DetailDescription|description|comment|detalle)[^"]*"[^>]*>(.*?)</(?:div|p|section)',
                    html, re.DOTALL | re.IGNORECASE
                )
                if not desc_match:
                    # Find long text blocks (property descriptions tend to be 100+ chars)
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

                # Extract photos - Fotocasa uses static.fotocasa.es/images/
                # Match full UUIDs and paths
                photos = re.findall(
                    r'(https?://static\.fotocasa\.es/images/[^"\'<>\s]+)',
                    html, re.IGNORECASE
                )
                unique_photos = []
                seen = set()
                for photo in photos:
                    # Remove query params for dedup
                    photo_base = re.sub(r'\?.*$', '', photo)
                    if photo_base not in seen and len(photo_base) > 50:
                        # Add original quality param
                        unique_photos.append(photo_base + '?rule=original')
                        seen.add(photo_base)
                listing['fotos'] = unique_photos[:10]

                # Check if particular or agency
                is_particular = 'particular' in html.lower()
                is_agency = 'inmobiliaria' in html.lower() or 'agencia' in html.lower()

                if is_agency and not is_particular:
                    listing['vendedor'] = 'Inmobiliaria'
                    listing['es_particular'] = False
                else:
                    listing['vendedor'] = 'Particular'
                    listing['es_particular'] = True

                results.append(listing)

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")

        # Filter out agencies if only_private
        if self.only_private:
            particulares = [l for l in results if l.get('es_particular', True)]
            filtered = len(results) - len(particulares)
            if filtered > 0:
                logger.info(f"Filtered out {filtered} agency listings")
            return particulares

        return results

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            # Additional filter check
            if not self.should_scrape(listing):
                self.stats['filtered_out'] += 1
                continue

            if self.save_to_postgres(listing, self.PORTAL_NAME):
                self.stats['saved'] += 1

        logger.info(f"Stats: {self.stats}")
        return self.stats


def run_fotocasa_botasaurus(
    zones: List[str] = None,
    postgres: bool = False,
    headless: bool = True,
    only_private: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convenience function to run the Fotocasa scraper.

    Args:
        zones: List of zones to scrape
        postgres: Enable PostgreSQL saving
        headless: Run in headless mode
        only_private: Only scrape particular listings

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

    with BotasaurusFotocasa(
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

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['tarragona_provincia']
    print(f"Scraping zones: {zones}")
    print(f"Available zones: {list(ZONAS_GEOGRAFICAS.keys())}")

    listings = run_fotocasa_botasaurus(zones=zones, headless=True)

    print(f"\nFound {len(listings)} listings:")
    for l in listings[:5]:
        print(f"  - {l.get('titulo', 'N/A')[:50]}... | {l.get('precio')}€ | {l.get('vendedor')}")

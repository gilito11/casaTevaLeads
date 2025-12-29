"""
Milanuncios scraper using Camoufox anti-detect browser.

Camoufox bypasses GeeTest captcha through C++ level fingerprint injection.
This replaces the ScrapingBee version - completely FREE.

Cost: €0 (no API credits needed)
"""

import hashlib
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import psycopg2

logger = logging.getLogger(__name__)


# Geographic zones configuration for Milanuncios
ZONAS_GEOGRAFICAS = {
    # Lleida
    'lleida_ciudad': {
        'nombre': 'Lleida Ciudad',
        'url_path': 'pisos-en-lleida-lleida/',
    },
    'lleida_20km': {
        'nombre': 'Lleida 20km',
        'url_path': 'pisos-en-lleida-lleida/',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_path': 'pisos-en-balaguer-lleida/',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'url_path': 'pisos-en-mollerussa-lleida/',
    },
    'tarrega': {
        'nombre': 'Tarrega',
        'url_path': 'pisos-en-tarrega-lleida/',
    },
    # Tarragona
    'tarragona_ciudad': {
        'nombre': 'Tarragona Ciudad',
        'url_path': 'pisos-en-tarragona/',
    },
    'salou': {
        'nombre': 'Salou',
        'url_path': 'pisos-en-salou/',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'pisos-en-cambrils-tarragona/',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'pisos-en-reus-tarragona/',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_path': 'pisos-en-el-vendrell-tarragona/',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'pisos-en-calafell-tarragona/',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'pisos-en-torredembarra-tarragona/',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'url_path': 'pisos-en-altafulla-tarragona/',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'pisos-en-valls-tarragona/',
    },
    'tortosa': {
        'nombre': 'Tortosa',
        'url_path': 'pisos-en-tortosa-tarragona/',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_path': 'pisos-en-amposta-tarragona/',
    },
}


def get_postgres_config() -> Dict[str, Any]:
    """Get PostgreSQL configuration from environment."""
    database_url = os.environ.get('DATABASE_URL', '')

    if database_url:
        match = re.match(
            r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)',
            database_url
        )
        if match:
            return {
                'host': match.group(3),
                'port': int(match.group(4)),
                'database': match.group(5).split('?')[0],
                'user': match.group(1),
                'password': match.group(2),
                'sslmode': 'require' if 'sslmode=require' in database_url else None,
            }

    return {
        'host': os.environ.get('POSTGRES_HOST', 'postgres'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
    }


class CamoufoxMilanuncios:
    """
    Milanuncios scraper using Camoufox anti-detect browser.
    Bypasses GeeTest captcha for free.
    """

    BASE_URL = "https://www.milanuncios.com"
    PORTAL_NAME = "milanuncios"

    def __init__(
        self,
        zones: List[str] = None,
        tenant_id: int = 1,
        max_pages_per_zone: int = 3,
        only_particulares: bool = True,
        headless: bool = True,
    ):
        self.zones = zones or ['salou']
        self.tenant_id = tenant_id
        self.max_pages_per_zone = max_pages_per_zone
        self.only_particulares = only_particulares
        self.headless = headless

        self.postgres_conn = None
        self.stats = {
            'pages_scraped': 0,
            'listings_found': 0,
            'listings_saved': 0,
            'errors': 0,
        }

    def _init_postgres(self):
        """Initialize PostgreSQL connection."""
        try:
            config = get_postgres_config()
            conn_params = {
                'host': config['host'],
                'port': config['port'],
                'database': config['database'],
                'user': config['user'],
                'password': config['password'],
            }
            if config.get('sslmode'):
                conn_params['sslmode'] = config['sslmode']

            self.postgres_conn = psycopg2.connect(**conn_params)
            logger.info(f"PostgreSQL connected: {config['host']}")
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            raise

    def normalize_phone(self, phone_str: str) -> Optional[str]:
        """Normalize Spanish phone to 9 digits."""
        if not phone_str:
            return None

        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone_str)

        if cleaned.startswith('+34'):
            cleaned = cleaned[3:]
        elif cleaned.startswith('0034'):
            cleaned = cleaned[4:]
        elif cleaned.startswith('34') and len(cleaned) == 11:
            cleaned = cleaned[2:]

        digits = re.sub(r'\D', '', cleaned)

        if len(digits) == 9 and digits[0] in '679':
            return digits
        return None

    def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Random delay to simulate human behavior."""
        time.sleep(random.uniform(min_sec, max_sec))

    def _warmup_navigation(self, page):
        """Warmup: visit homepage first to build trust."""
        logger.info("Warming up: visiting homepage...")

        page.goto(self.BASE_URL, wait_until='domcontentloaded')
        self._human_delay(2, 4)

        # Scroll a bit
        page.mouse.wheel(0, random.randint(100, 300))
        self._human_delay(1, 2)

        # Accept cookies if present
        try:
            accept_btn = page.query_selector('button[id*="accept"], button:has-text("Aceptar")')
            if accept_btn:
                accept_btn.click()
                self._human_delay(1, 2)
        except:
            pass

        logger.info("Warmup complete")

    def build_search_url(self, zona_key: str, page_num: int = 1) -> str:
        """Build Milanuncios search URL."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        url_path = zona['url_path']
        base_url = f"{self.BASE_URL}/{url_path}"

        # Add pagination
        if page_num > 1:
            base_url = base_url.rstrip('/') + f'?pagina={page_num}'

        return base_url

    def _extract_listings_from_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listing data from search results page."""
        listings = []

        try:
            # Wait for listings
            selectors = [
                'article.ma-AdCard',
                'article[class*="AdCard"]',
                '.ma-AdCardV2',
                'article.AdCard',
            ]

            items = []
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    items = page.query_selector_all(selector)
                    if items:
                        logger.info(f"Found {len(items)} cards using: {selector}")
                        break
                except:
                    continue

            if not items:
                logger.warning("No listing cards found")
                return []

            for item in items:
                try:
                    listing = self._parse_listing_card(item, zona_key)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.debug(f"Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting listings: {e}")

        return listings

    def _parse_listing_card(self, item, zona_key: str) -> Optional[Dict[str, Any]]:
        """Parse a single listing card."""
        try:
            # Check if professional (agency)
            pro_badge = item.query_selector('[class*="professional"], [class*="Pro"], .ma-AdTag--pro')
            if pro_badge and self.only_particulares:
                return None

            # Get link and ID
            link = item.query_selector('a[href*="/anuncios/"]')
            if not link:
                return None

            href = link.get_attribute('href')
            if not href:
                return None

            # Extract ID from URL
            id_match = re.search(r'/(\d+)\.htm', href)
            if not id_match:
                id_match = re.search(r'-(\d+)$', href.rstrip('/'))

            if not id_match:
                return None

            anuncio_id = id_match.group(1)

            # Title
            title_elem = item.query_selector('h2, .ma-AdCard-title, [class*="title"]')
            titulo = title_elem.inner_text().strip() if title_elem else ''

            # Price
            price_elem = item.query_selector('[class*="price"], .ma-AdCard-price')
            precio = None
            if price_elem:
                price_text = price_elem.inner_text()
                precio = self._parse_price(price_text)

            # Description
            desc_elem = item.query_selector('[class*="description"], .ma-AdCard-description')
            descripcion = desc_elem.inner_text().strip()[:500] if desc_elem else ''

            # Location
            location_elem = item.query_selector('[class*="location"], .ma-AdCard-location')
            ubicacion = location_elem.inner_text().strip() if location_elem else ''

            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            return {
                'anuncio_id': anuncio_id,
                'titulo': titulo,
                'precio': precio,
                'descripcion': descripcion,
                'ubicacion': ubicacion,
                'zona_geografica': zona_info.get('nombre', zona_key),
                'zona_busqueda': zona_key,
                'url_anuncio': f"{self.BASE_URL}{href}" if href.startswith('/') else href,
                'es_particular': True,
                'tipo_inmueble': 'piso',
            }

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to float."""
        if not price_text:
            return None
        try:
            cleaned = re.sub(r'[€$\s\xa0.]', '', price_text)
            cleaned = cleaned.replace(',', '.')
            match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

    def _scrape_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape phone from detail page."""
        try:
            url = listing.get('url_anuncio')
            if not url:
                return listing

            logger.info(f"Getting details: {url}")

            page.goto(url, wait_until='domcontentloaded')
            self._human_delay(2, 4)

            # Scroll
            page.mouse.wheel(0, random.randint(200, 400))
            self._human_delay(1, 2)

            # Look for phone button
            try:
                phone_btn = page.query_selector('button[class*="phone"], [data-testid*="phone"], .ma-ContactButtons-phone')
                if phone_btn:
                    phone_btn.click()
                    self._human_delay(1, 2)

                    # Get phone
                    phone_elem = page.query_selector('[class*="phone-number"], [class*="PhoneNumber"], a[href^="tel:"]')
                    if phone_elem:
                        phone_text = phone_elem.inner_text() or phone_elem.get_attribute('href') or ''
                        phone_text = phone_text.replace('tel:', '')
                        normalized = self.normalize_phone(phone_text)
                        if normalized:
                            listing['telefono'] = phone_text
                            listing['telefono_norm'] = normalized
            except Exception as e:
                logger.debug(f"Could not get phone: {e}")

            # Get full description
            try:
                desc_elem = page.query_selector('[class*="description"], .ma-AdDetail-description')
                if desc_elem:
                    listing['descripcion'] = desc_elem.inner_text()[:2000]
            except:
                pass

            return listing

        except Exception as e:
            logger.warning(f"Error on detail page: {e}")
            return listing

    def save_to_postgres(self, listing: Dict[str, Any]) -> bool:
        """Save listing to PostgreSQL."""
        if not self.postgres_conn:
            return False

        try:
            cursor = self.postgres_conn.cursor()

            anuncio_id = str(listing.get('anuncio_id', ''))
            if not anuncio_id:
                return False

            raw_data = {
                'anuncio_id': anuncio_id,
                'titulo': listing.get('titulo', ''),
                'telefono': listing.get('telefono', ''),
                'telefono_norm': listing.get('telefono_norm', ''),
                'direccion': listing.get('ubicacion', ''),
                'zona': listing.get('zona_geografica', ''),
                'zona_busqueda': listing.get('zona_busqueda', ''),
                'zona_geografica': listing.get('zona_geografica', ''),
                'tipo_inmueble': listing.get('tipo_inmueble', 'piso'),
                'precio': listing.get('precio'),
                'descripcion': listing.get('descripcion', ''),
                'url': listing.get('url_anuncio', ''),
                'es_particular': listing.get('es_particular', True),
                'scraper_type': 'camoufox',
            }

            sql = """
                INSERT INTO raw.raw_listings (
                    tenant_id, portal, data_lake_path, raw_data, scraping_timestamp
                ) VALUES (
                    %s, %s, %s, %s, %s
                )
            """

            now = datetime.now()
            data_lake_path = f"camoufox/{self.PORTAL_NAME}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

            cursor.execute(sql, (
                self.tenant_id,
                self.PORTAL_NAME,
                data_lake_path,
                json.dumps(raw_data),
                now,
            ))

            self.postgres_conn.commit()
            cursor.close()

            logger.info(f"Saved: {self.PORTAL_NAME} - {anuncio_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving: {e}")
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def scrape(self) -> Dict[str, Any]:
        """Main scraping method."""
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            logger.error("Camoufox not installed. Run: pip install camoufox && camoufox fetch")
            raise

        self._init_postgres()

        all_listings = []
        headless_mode = "virtual" if self.headless else False

        logger.info(f"Starting Camoufox Milanuncios scraper")
        logger.info(f"  Zones: {self.zones}")
        logger.info(f"  Max pages: {self.max_pages_per_zone}")

        try:
            with Camoufox(
                humanize=True,
                headless=headless_mode,
            ) as browser:
                page = browser.new_page()

                self._warmup_navigation(page)

                for zona_key in self.zones:
                    zona_info = ZONAS_GEOGRAFICAS.get(zona_key)
                    if not zona_info:
                        logger.warning(f"Zone not found: {zona_key}")
                        continue

                    logger.info(f"Scraping zone: {zona_info['nombre']}")

                    for page_num in range(1, self.max_pages_per_zone + 1):
                        try:
                            url = self.build_search_url(zona_key, page_num)
                            logger.info(f"Page {page_num}: {url}")

                            page.goto(url, wait_until='domcontentloaded')
                            self._human_delay(3, 5)

                            # Scroll to load content
                            for _ in range(3):
                                page.mouse.wheel(0, random.randint(300, 600))
                                self._human_delay(0.5, 1)

                            self.stats['pages_scraped'] += 1

                            # Check for captcha
                            is_blocked = False
                            try:
                                captcha = page.query_selector('.geetest_holder, [class*="geetest"], iframe[src*="geetest"]')
                                if captcha:
                                    is_blocked = True
                                    logger.warning("GeeTest captcha detected!")
                            except:
                                pass

                            if is_blocked:
                                self.stats['errors'] += 1
                                break

                            # Extract listings
                            listings = self._extract_listings_from_page(page, zona_key)
                            logger.info(f"Found {len(listings)} particular listings")

                            if not listings:
                                break

                            # Get details for each
                            for listing in listings[:10]:
                                self.stats['listings_found'] += 1

                                listing = self._scrape_detail_page(page, listing)

                                if self.save_to_postgres(listing):
                                    self.stats['listings_saved'] += 1
                                    all_listings.append(listing)

                                self._human_delay(1, 2)

                        except Exception as e:
                            logger.error(f"Error on page {page_num}: {e}")
                            self.stats['errors'] += 1
                            continue

                    self._human_delay(3, 6)

        except Exception as e:
            logger.error(f"Camoufox error: {e}")
            self.stats['errors'] += 1
            raise

        finally:
            if self.postgres_conn:
                self.postgres_conn.close()

        logger.info(f"Complete. Stats: {self.stats}")
        return self.stats


def run_camoufox_milanuncios(
    zones: List[str] = None,
    tenant_id: int = 1,
    max_pages_per_zone: int = 2,
    headless: bool = True,
) -> Dict[str, Any]:
    """Run the Camoufox Milanuncios scraper."""
    scraper = CamoufoxMilanuncios(
        zones=zones or ['salou'],
        tenant_id=tenant_id,
        max_pages_per_zone=max_pages_per_zone,
        headless=headless,
    )
    return scraper.scrape()


if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")

    stats = run_camoufox_milanuncios(
        zones=zones,
        max_pages_per_zone=2,
        headless=True,
    )
    print(f"\nStats: {stats}")

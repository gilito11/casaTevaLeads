"""
Idealista scraper using Camoufox anti-detect browser.

Camoufox is an open-source Firefox-based browser that bypasses anti-bot systems
like DataDome through C++ level fingerprint injection (not detectable via JS).

Features:
- Human-like mouse movements
- Realistic fingerprint generation
- Virtual headless mode for servers
- GeoIP timezone matching

Cost: FREE (no API credits needed)
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


# Geographic zones configuration for Idealista
ZONAS_GEOGRAFICAS = {
    # Provinces
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_path': 'tarragona-provincia',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'lleida-provincia',
    },
    # Cities - Lleida
    'lleida': {
        'nombre': 'Lleida',
        'url_path': 'lleida-lleida',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_path': 'balaguer-lleida',
    },
    # Cities - Tarragona
    'tarragona': {
        'nombre': 'Tarragona',
        'url_path': 'tarragona-tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'reus-tarragona',
    },
    'salou': {
        'nombre': 'Salou',
        'url_path': 'salou-tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'cambrils-tarragona',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_path': 'el-vendrell-tarragona',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'calafell-tarragona',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'torredembarra-tarragona',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'url_path': 'altafulla-tarragona',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'valls-tarragona',
    },
    'tortosa': {
        'nombre': 'Tortosa',
        'url_path': 'tortosa-tarragona',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_path': 'amposta-tarragona',
    },
}


def get_postgres_config() -> Dict[str, str]:
    """Get PostgreSQL configuration from environment."""
    database_url = os.environ.get('DATABASE_URL', '')

    if database_url:
        # Parse DATABASE_URL
        import re
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

    # Default local config
    return {
        'host': os.environ.get('POSTGRES_HOST', 'postgres'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
    }


class CamoufoxIdealista:
    """
    Idealista scraper using Camoufox anti-detect browser.

    This scraper:
    1. Uses Camoufox to bypass DataDome anti-bot protection
    2. Simulates human-like browsing behavior
    3. Extracts property listings from Idealista
    4. Saves to PostgreSQL
    """

    BASE_URL = "https://www.idealista.com"
    PORTAL_NAME = "idealista"

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
        """
        Simulate human warmup: visit homepage first, then navigate.
        This improves trust score with anti-bot systems.
        """
        logger.info("Warming up: visiting homepage first...")

        # Visit homepage
        page.goto(self.BASE_URL, wait_until='domcontentloaded')
        self._human_delay(2, 4)

        # Scroll a bit
        page.mouse.wheel(0, random.randint(100, 300))
        self._human_delay(1, 2)

        # Maybe click on "Venta" menu
        try:
            venta_link = page.query_selector('a[href*="venta-viviendas"]')
            if venta_link:
                venta_link.click()
                self._human_delay(2, 3)
        except:
            pass

        logger.info("Warmup complete")

    def build_search_url(self, zona_key: str, page_num: int = 1) -> str:
        """Build Idealista search URL."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        url_path = zona['url_path']
        # Don't use filters like ultimas-48-horas - they increase detection risk
        base_url = f"{self.BASE_URL}/venta-viviendas/{url_path}/"

        if page_num > 1:
            base_url = base_url.rstrip('/') + f'/pagina-{page_num}.htm'

        return base_url

    def _extract_listings_from_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listing data from search results page."""
        listings = []

        try:
            # Wait for listings to load - try multiple selectors
            selectors = ['article.item', 'article[data-element-id]', '.item-info-container', '.items-container article']
            items = []

            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    items = page.query_selector_all(selector)
                    if items:
                        logger.info(f"Found {len(items)} listings using selector: {selector}")
                        break
                except:
                    continue

            if not items:
                # Try to get any links that look like listings
                items = page.query_selector_all('a[href*="/inmueble/"]')
                logger.info(f"Found {len(items)} listing links")

            for item in items:
                try:
                    listing = self._parse_listing_card(item, zona_key)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(f"Error parsing listing: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting listings: {e}")

        return listings

    def _parse_listing_card(self, item, zona_key: str) -> Optional[Dict[str, Any]]:
        """Parse a single listing card element."""
        try:
            # Get listing URL and ID
            link = item.query_selector('a.item-link')
            if not link:
                return None

            href = link.get_attribute('href')
            if not href:
                return None

            # Extract ID from URL
            id_match = re.search(r'/inmueble/(\d+)/', href)
            if not id_match:
                id_match = re.search(r'-(\d+)\.htm', href)

            if not id_match:
                return None

            anuncio_id = id_match.group(1)

            # Check if it's from professional (agency)
            profesional = item.query_selector('.professional-logo, .logo-branding')
            if profesional and self.only_particulares:
                logger.debug(f"Skipping professional listing: {anuncio_id}")
                return None

            # Extract title
            title_elem = item.query_selector('.item-title, h3.item-title')
            titulo = title_elem.inner_text() if title_elem else ''

            # Extract price
            price_elem = item.query_selector('.item-price, span.item-price')
            precio = None
            if price_elem:
                price_text = price_elem.inner_text()
                precio = self._parse_price(price_text)

            # Extract details (rooms, m2, etc.)
            details = item.query_selector('.item-detail')
            habitaciones = None
            metros = None
            if details:
                detail_text = details.inner_text()
                # Extract rooms
                rooms_match = re.search(r'(\d+)\s*hab', detail_text, re.I)
                if rooms_match:
                    habitaciones = int(rooms_match.group(1))
                # Extract m2
                m2_match = re.search(r'(\d+)\s*m[²2]', detail_text)
                if m2_match:
                    metros = float(m2_match.group(1))

            # Extract description preview
            desc_elem = item.query_selector('.item-description, .ellipsis')
            descripcion = desc_elem.inner_text() if desc_elem else ''

            # Extract location
            location_elem = item.query_selector('.item-location')
            ubicacion = location_elem.inner_text() if location_elem else ''

            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            return {
                'anuncio_id': anuncio_id,
                'titulo': titulo.strip(),
                'precio': precio,
                'habitaciones': habitaciones,
                'metros': metros,
                'descripcion': descripcion.strip()[:500],
                'ubicacion': ubicacion.strip(),
                'zona_geografica': zona_info.get('nombre', zona_key),
                'zona_busqueda': zona_key,
                'url_anuncio': f"{self.BASE_URL}{href}" if href.startswith('/') else href,
                'es_particular': True,
                'tipo_inmueble': 'piso',
            }

        except Exception as e:
            logger.warning(f"Error parsing listing card: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to float."""
        if not price_text:
            return None
        try:
            cleaned = re.sub(r'[€$\s\xa0.]', '', price_text)
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except:
            return None

    def _scrape_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape additional details from listing detail page."""
        try:
            url = listing.get('url_anuncio')
            if not url:
                return listing

            logger.info(f"Scraping detail: {url}")

            page.goto(url, wait_until='domcontentloaded')
            self._human_delay(2, 4)

            # Scroll to trigger lazy loading
            page.mouse.wheel(0, random.randint(200, 500))
            self._human_delay(1, 2)

            # Try to find phone button and click it
            try:
                phone_btn = page.query_selector('a.contact-phones-link, button[class*="phone"]')
                if phone_btn:
                    phone_btn.click()
                    self._human_delay(1, 2)

                    # Look for phone number
                    phone_elem = page.query_selector('.phone-number, [class*="phone"]')
                    if phone_elem:
                        phone_text = phone_elem.inner_text()
                        phones = re.findall(r'[679]\d{8}', phone_text.replace(' ', ''))
                        if phones:
                            listing['telefono'] = phones[0]
                            listing['telefono_norm'] = self.normalize_phone(phones[0])
            except Exception as e:
                logger.debug(f"Could not get phone: {e}")

            # Get full description
            try:
                desc_elem = page.query_selector('.comment, .adCommentsLanguage')
                if desc_elem:
                    listing['descripcion'] = desc_elem.inner_text()[:2000]
            except:
                pass

            # Get photos
            try:
                photos = []
                img_elems = page.query_selector_all('.detail-image-gallery img, .gallery-container img')
                for img in img_elems[:10]:
                    src = img.get_attribute('src') or img.get_attribute('data-src')
                    if src and 'idealista' in src:
                        photos.append(src)
                if photos:
                    listing['fotos'] = photos
            except:
                pass

            return listing

        except Exception as e:
            logger.warning(f"Error scraping detail page: {e}")
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
                'email': listing.get('email'),
                'nombre': listing.get('vendedor', ''),
                'direccion': listing.get('ubicacion', ''),
                'zona': listing.get('zona_geografica', ''),
                'zona_busqueda': listing.get('zona_busqueda', ''),
                'zona_geografica': listing.get('zona_geografica', ''),
                'codigo_postal': listing.get('codigo_postal'),
                'tipo_inmueble': listing.get('tipo_inmueble', 'piso'),
                'precio': listing.get('precio'),
                'habitaciones': listing.get('habitaciones'),
                'metros': listing.get('metros'),
                'descripcion': listing.get('descripcion', ''),
                'fotos': listing.get('fotos', []),
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
                ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
                WHERE raw_data->>'anuncio_id' IS NOT NULL
                DO NOTHING
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

            rows_affected = cursor.rowcount
            self.postgres_conn.commit()
            cursor.close()

            if rows_affected > 0:
                logger.info(f"Lead saved: {self.PORTAL_NAME} - {anuncio_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error saving to PostgreSQL: {e}")
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def scrape(self) -> Dict[str, Any]:
        """Main scraping method using Camoufox."""
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            logger.error("Camoufox not installed. Run: pip install camoufox && camoufox fetch")
            raise

        self._init_postgres()

        all_listings = []

        # Determine headless mode
        headless_mode = "virtual" if self.headless else False

        logger.info(f"Starting Camoufox Idealista scraper")
        logger.info(f"  Zones: {self.zones}")
        logger.info(f"  Max pages: {self.max_pages_per_zone}")
        logger.info(f"  Headless: {headless_mode}")

        try:
            with Camoufox(
                humanize=True,
                headless=headless_mode,
            ) as browser:
                page = browser.new_page()

                # Warmup navigation
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

                            # Scroll to load lazy content
                            for _ in range(3):
                                page.mouse.wheel(0, random.randint(300, 600))
                                self._human_delay(0.5, 1)

                            self.stats['pages_scraped'] += 1

                            # Check for real blocking (not false positives from page scripts)
                            # Look for actual captcha elements, not just keywords in HTML
                            is_blocked = False
                            try:
                                # Check for visible captcha iframe or DataDome challenge
                                captcha_elem = page.query_selector('iframe[src*="captcha"], iframe[src*="datadome"], #datadome-widget')
                                access_denied = page.query_selector('h1:has-text("Access Denied"), h1:has-text("Acceso denegado")')
                                if captcha_elem or access_denied:
                                    is_blocked = True
                                    logger.warning("Real blocking detected: captcha element found")
                            except:
                                pass

                            if is_blocked:
                                try:
                                    page.screenshot(path='/tmp/idealista_blocked.png')
                                except:
                                    pass
                                self.stats['errors'] += 1
                                break

                            # Accept cookies if banner appears
                            try:
                                accept_btn = page.query_selector('button:has-text("Aceptar"), button:has-text("Rechazar")')
                                if accept_btn:
                                    accept_btn.click()
                                    self._human_delay(1, 2)
                            except:
                                pass

                            # Extract listings
                            listings = self._extract_listings_from_page(page, zona_key)
                            logger.info(f"Found {len(listings)} listings on page {page_num}")

                            if not listings:
                                logger.info("No listings found, stopping pagination")
                                break

                            # Scrape details for each listing
                            for listing in listings[:10]:  # Limit to 10 per page
                                self.stats['listings_found'] += 1

                                # Get phone from detail page
                                if not listing.get('telefono'):
                                    listing = self._scrape_detail_page(page, listing)

                                # Save to DB - save even without phone for Idealista
                                # (phones are hard to get, we can enrich later)
                                if self.save_to_postgres(listing):
                                    self.stats['listings_saved'] += 1
                                    all_listings.append(listing)
                                    logger.info(f"Saved listing: {listing.get('anuncio_id')} - {listing.get('titulo', '')[:50]}")

                                self._human_delay(1, 2)

                        except Exception as e:
                            logger.error(f"Error on page {page_num}: {e}")
                            self.stats['errors'] += 1
                            continue

                    # Delay between zones
                    self._human_delay(3, 6)

        except Exception as e:
            logger.error(f"Camoufox error: {e}")
            self.stats['errors'] += 1
            raise

        finally:
            if self.postgres_conn:
                self.postgres_conn.close()

        logger.info(f"Scraping complete. Stats: {self.stats}")
        return self.stats


def run_camoufox_idealista(
    zones: List[str] = None,
    tenant_id: int = 1,
    max_pages_per_zone: int = 2,
    headless: bool = True,
) -> Dict[str, Any]:
    """Run the Camoufox Idealista scraper."""
    scraper = CamoufoxIdealista(
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")

    stats = run_camoufox_idealista(
        zones=zones,
        max_pages_per_zone=2,
        headless=True,
    )
    print(f"\nStats: {stats}")

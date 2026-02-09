"""
Idealista scraper using Camoufox anti-detect browser with IPRoyal proxy.

Bypasses DataDome protection using:
- Camoufox: Anti-detect Firefox with C++ level fingerprint injection
- IPRoyal proxy: Spanish residential IPs (~$1/GB, never expires)
- geoip=True: Automatic timezone/locale matching to proxy location

Cost: ~$0.01/scrape (vs ~$2.50/scrape with ScrapingBee)
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
from urllib.parse import urlparse

import psycopg2

logger = logging.getLogger(__name__)


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
    # Test zone
    'igualada': {
        'nombre': 'Igualada',
        'url_path': 'igualada-barcelona',
    },
}


def get_postgres_config() -> Dict[str, Any]:
    """Get PostgreSQL configuration from DATABASE_URL or NEON_DATABASE_URL."""
    database_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL', '')

    if database_url:
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/').split('?')[0],
            'user': parsed.username,
            'password': parsed.password,
            'sslmode': 'require',
        }

    # Default local config
    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
    }


def parse_proxy(proxy_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse proxy string to Camoufox format.

    Input format: user:pass_country-es@geo.iproyal.com:12321
    Output format: {"server": "http://host:port", "username": "user", "password": "pass"}
    """
    if not proxy_str:
        return None

    try:
        if "@" in proxy_str:
            auth, addr = proxy_str.rsplit("@", 1)
            user, passwd = auth.split(":", 1)
            host, port = addr.split(":")
            return {
                "server": f"http://{host}:{port}",
                "username": user,
                "password": passwd,
            }
        else:
            return {"server": f"http://{proxy_str}"}
    except Exception as e:
        logger.error(f"Invalid proxy format: {proxy_str} - {e}")
        return None


class CamoufoxIdealista:
    """
    Idealista scraper using Camoufox anti-detect browser + IPRoyal proxy.

    Bypasses DataDome by:
    1. Using Camoufox's C++ level fingerprint injection
    2. Using IPRoyal Spanish residential proxy
    3. geoip=True matches timezone/locale to proxy location
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
        proxy: str = None,
    ):
        self.zones = zones or ['salou']
        self.tenant_id = tenant_id
        self.max_pages_per_zone = max_pages_per_zone
        self.only_particulares = only_particulares
        self.headless = headless
        # Proxy from param or env (DATADOME_PROXY)
        self.proxy = proxy or os.environ.get('DATADOME_PROXY')

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

        page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
        self._human_delay(2, 4)

        # Scroll a bit
        page.mouse.wheel(0, random.randint(100, 300))
        self._human_delay(1, 2)

        # Check for DataDome
        if self._check_blocked(page):
            logger.warning("Blocked on homepage warmup")
            return False

        # Accept cookies
        self._accept_cookies(page)

        logger.info("Warmup complete")
        return True

    def _check_blocked(self, page) -> bool:
        """Check if blocked by DataDome."""
        try:
            url = page.url
            content = page.content()

            # Check if redirected to captcha
            if "geo.captcha-delivery.com" in url:
                logger.warning("Blocked: redirected to captcha-delivery")
                return True

            # Check for visible DataDome elements
            captcha_elem = page.query_selector(
                'iframe[src*="captcha"], iframe[src*="datadome"], #datadome-widget'
            )
            if captcha_elem:
                logger.warning("Blocked: DataDome widget detected")
                return True

            # Check for access denied page
            access_denied = page.query_selector(
                'h1:has-text("Access Denied"), h1:has-text("Acceso denegado")'
            )
            if access_denied:
                logger.warning("Blocked: Access Denied page")
                return True

            return False

        except Exception as e:
            logger.debug(f"Error checking blocked state: {e}")
            return False

    def _accept_cookies(self, page):
        """Accept cookies popup if present."""
        selectors = [
            'button:has-text("Aceptar")',
            'button:has-text("Rechazar")',
            '#didomi-notice-agree-button',
        ]
        for selector in selectors:
            try:
                btn = page.query_selector(selector)
                if btn:
                    btn.click()
                    self._human_delay(1, 2)
                    return
            except:
                continue

    def _verify_listing_detail(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Visit listing detail page to verify if particular and extract more data.
        Returns updated listing with verified es_particular, phone, full description.
        """
        url = listing.get('url_anuncio')
        if not url:
            return listing

        try:
            page.goto(url, timeout=60000)
            self._human_delay(2, 3)

            # Check if particular by looking at advertiser section
            sections = page.query_selector_all('[class*="contact"], [id*="contact"]')
            for sec in sections:
                try:
                    text = sec.inner_text()
                    if 'Referencia del anuncio' in text:
                        if '\nParticular\n' in text:
                            listing['es_particular'] = True
                            listing['verified'] = True
                            # Extract advertiser name
                            lines = text.split('\n')
                            for i, line in enumerate(lines):
                                if line.strip() == 'Particular' and i + 1 < len(lines):
                                    listing['vendedor'] = lines[i + 1].strip()
                                    break
                        else:
                            listing['es_particular'] = False
                            listing['verified'] = True
                        break
                except:
                    continue

            # Try to get phone
            try:
                phone_btn = page.query_selector('a:has-text("Ver teléfono"), button:has-text("Ver teléfono")')
                if phone_btn:
                    phone_btn.click()
                    self._human_delay(1, 2)

                    # Look for phone number in page
                    content = page.content()
                    phones = re.findall(r'tel:(?:\+?34)?([679]\d{8})', content)
                    if phones:
                        listing['telefono'] = phones[0]
                        listing['telefono_norm'] = self.normalize_phone(phones[0])
            except Exception as e:
                logger.debug(f"Could not get phone: {e}")

            # Get full description
            try:
                desc_elem = page.query_selector('.comment, .adCommentsLanguage, [class*="description"]')
                if desc_elem:
                    full_desc = desc_elem.inner_text()
                    if len(full_desc) > len(listing.get('descripcion', '')):
                        listing['descripcion'] = full_desc[:2000]
            except:
                pass

            # Extract photos from detail page
            try:
                content = page.content()
                # Idealista uses img3/img4.idealista.com for property photos
                photo_urls = set(re.findall(
                    r'https://img[34]\.idealista\.com/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp)',
                    content, re.IGNORECASE
                ))
                if photo_urls:
                    # Filter out tiny thumbnails and icons, keep large images
                    fotos = []
                    for url in photo_urls:
                        # Skip tiny images (thumbs, logos)
                        if '/WEB_LISTING/' in url or '/WEB_DETAIL/' in url or 'resize' in url.lower():
                            fotos.append(url)
                    # If the filter was too aggressive, use all
                    if not fotos:
                        fotos = list(photo_urls)
                    listing['fotos'] = fotos[:10]
            except Exception as e:
                logger.debug(f"Could not extract photos: {e}")

            return listing

        except Exception as e:
            logger.warning(f"Error verifying detail for {listing.get('anuncio_id')}: {e}")
            return listing

    def build_search_url(self, zona_key: str, page_num: int = 1) -> str:
        """Build Idealista search URL."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        url_path = zona['url_path']

        if self.only_particulares:
            base_url = f"{self.BASE_URL}/venta-viviendas/{url_path}/con-publicado_particular/"
        else:
            base_url = f"{self.BASE_URL}/venta-viviendas/{url_path}/"

        if page_num > 1:
            base_url = base_url.rstrip('/') + f'/pagina-{page_num}.htm'

        return base_url

    def _extract_listings_from_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listing data from search results page."""
        listings = []

        try:
            # Wait for listings
            selectors = [
                'article.item',
                'article[data-element-id]',
                '.item-info-container',
                '.items-container article'
            ]
            items = []

            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    items = page.query_selector_all(selector)
                    if items:
                        logger.info(f"Found {len(items)} listings using selector: {selector}")
                        break
                except:
                    continue

            if not items:
                logger.warning("No listing elements found on page")
                return []

            for item in items:
                try:
                    listing = self._parse_listing_card(item, zona_key)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.debug(f"Error parsing listing: {e}")
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

            # Check if professional (agency) - heuristic from listing HTML
            # Note: This is not 100% accurate, final filtering done in dbt
            item_html = item.inner_html()
            is_professional = (
                'logo-branding' in item_html or
                'professional' in item_html.lower() or
                'item-not-clickable-logo' in item_html
            )

            # Extract title
            title_elem = item.query_selector('.item-title, h3.item-title')
            titulo = title_elem.inner_text() if title_elem else ''

            # Extract price
            price_elem = item.query_selector('.item-price, span.item-price')
            precio = None
            if price_elem:
                price_text = price_elem.inner_text()
                precio = self._parse_price(price_text)

            # Extract details (rooms, m2)
            details = item.query_selector('.item-detail')
            habitaciones = None
            metros = None
            if details:
                detail_text = details.inner_text()
                rooms_match = re.search(r'(\d+)\s*hab', detail_text, re.I)
                if rooms_match:
                    habitaciones = int(rooms_match.group(1))
                m2_match = re.search(r'(\d+)\s*m[²2]', detail_text)
                if m2_match:
                    metros = float(m2_match.group(1))

            # Extract description preview
            desc_elem = item.query_selector('.item-description, .ellipsis')
            descripcion = desc_elem.inner_text() if desc_elem else ''

            # Extract location
            location_elem = item.query_selector('.item-location')
            ubicacion = location_elem.inner_text() if location_elem else ''

            # Skip listings under 10000€
            if precio is not None and precio < 10000:
                logger.debug(f"Skipping low price ({precio}€): {anuncio_id}")
                return None

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
                'es_particular': not is_professional,
                'tipo_inmueble': 'piso',
            }

        except Exception as e:
            logger.debug(f"Error parsing listing card: {e}")
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

            # Track price history for price drop detection
            precio = listing.get('precio')
            if precio and anuncio_id:
                try:
                    cursor2 = self.postgres_conn.cursor()
                    cursor2.execute("""
                        INSERT INTO raw.listing_price_history (tenant_id, portal, anuncio_id, precio)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (tenant_id, portal, anuncio_id, precio) DO NOTHING
                    """, (self.tenant_id, self.PORTAL_NAME, anuncio_id, precio))
                    self.postgres_conn.commit()
                    cursor2.close()
                except Exception as e:
                    logger.debug(f"Price history insert skipped: {e}")

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

        # Build Camoufox options
        camoufox_opts = {
            "humanize": 2.5,
            "headless": self.headless,
            "os": "windows",
            "block_webrtc": True,
            "locale": ["es-ES", "es"],
        }

        # Add proxy if configured
        proxy_config = parse_proxy(self.proxy)
        if proxy_config:
            camoufox_opts["proxy"] = proxy_config
            # Only use geoip when NOT in virtual/CI mode (can cause fingerprint inconsistency)
            if self.headless != "virtual":
                camoufox_opts["geoip"] = True
            logger.info(f"Using proxy: {proxy_config['server']}")
        else:
            camoufox_opts["geoip"] = True
            logger.warning("No DATADOME_PROXY configured - may get blocked")

        logger.info(f"Starting Camoufox Idealista scraper")
        logger.info(f"  Zones: {self.zones}")
        logger.info(f"  Max pages: {self.max_pages_per_zone}")
        logger.info(f"  Headless: {self.headless}")
        logger.info(f"  Proxy: {'configured' if proxy_config else 'none'}")

        try:
            with Camoufox(**camoufox_opts) as browser:
                page = browser.new_page()

                # Warmup navigation
                if not self._warmup_navigation(page):
                    logger.error("Failed warmup - likely blocked")
                    self.stats['errors'] += 1
                    return self.stats

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

                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            self._human_delay(3, 5)

                            # Scroll to load lazy content
                            for _ in range(3):
                                page.mouse.wheel(0, random.randint(300, 600))
                                self._human_delay(0.5, 1)

                            self.stats['pages_scraped'] += 1

                            # Check for blocking
                            if self._check_blocked(page):
                                try:
                                    page.screenshot(path='/tmp/idealista_blocked.png')
                                except:
                                    pass
                                self.stats['errors'] += 1
                                logger.error("Blocked - stopping this zone")
                                break

                            # Accept cookies
                            self._accept_cookies(page)

                            # Extract listings
                            listings = self._extract_listings_from_page(page, zona_key)
                            logger.info(f"Found {len(listings)} listings on page {page_num}")

                            if not listings:
                                logger.info("No listings found, stopping pagination")
                                break

                            # Verify each listing by visiting detail page
                            for listing in listings:
                                self.stats['listings_found'] += 1

                                # Visit detail page to verify particular and get phone
                                listing = self._verify_listing_detail(page, listing)

                                # Only save if particular (when filtering enabled)
                                if self.only_particulares and not listing.get('es_particular'):
                                    logger.debug(f"Skipping professional: {listing.get('anuncio_id')}")
                                    continue

                                if self.save_to_postgres(listing):
                                    self.stats['listings_saved'] += 1

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
    proxy: str = None,
) -> Dict[str, Any]:
    """Run the Camoufox Idealista scraper."""
    scraper = CamoufoxIdealista(
        zones=zones or ['salou'],
        tenant_id=tenant_id,
        max_pages_per_zone=max_pages_per_zone,
        headless=headless,
        proxy=proxy,
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

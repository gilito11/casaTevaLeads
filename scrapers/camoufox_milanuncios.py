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

    def _human_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Random delay to simulate human behavior - longer delays avoid detection."""
        time.sleep(random.uniform(min_sec, max_sec))

    def _warmup_navigation(self, page):
        """Warmup: visit homepage first to build trust and look human."""
        logger.info("Warming up: visiting homepage...")

        page.goto(self.BASE_URL, wait_until='domcontentloaded')
        self._human_delay(4, 7)  # Longer initial wait

        # Scroll multiple times like a human browsing
        for _ in range(random.randint(2, 4)):
            page.mouse.wheel(0, random.randint(150, 400))
            self._human_delay(1.5, 3)

        # Accept cookies if present
        try:
            accept_btn = page.query_selector('button[id*="accept"], button:has-text("Aceptar")')
            if accept_btn:
                accept_btn.click()
                self._human_delay(2, 4)
        except:
            pass

        # Maybe click on something random (categories) to look more human
        try:
            categories = page.query_selector_all('a[href*="/inmobiliaria/"], a[href*="/pisos"]')
            if categories and random.random() > 0.5:
                random.choice(categories[:5]).click()
                self._human_delay(3, 5)
                page.go_back()
                self._human_delay(2, 4)
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
        """Extract listing data from search results page.

        Milanuncios is a React SPA that embeds listing data in window.__INITIAL_PROPS__.
        We extract directly from JSON for reliability instead of fragile CSS selectors.
        """
        listings = []

        try:
            # Method 1: Extract from embedded JSON (most reliable)
            try:
                json_data = page.evaluate("""
                    () => {
                        // Try __INITIAL_PROPS__ first
                        if (window.__INITIAL_PROPS__) {
                            return window.__INITIAL_PROPS__;
                        }
                        // Try __NEXT_DATA__ (Next.js apps)
                        if (window.__NEXT_DATA__) {
                            return window.__NEXT_DATA__.props;
                        }
                        // Try to find script tags with JSON
                        const scripts = document.querySelectorAll('script');
                        for (const script of scripts) {
                            const text = script.textContent || '';
                            if (text.includes('__INITIAL_PROPS__') || text.includes('"ads":[')) {
                                try {
                                    const match = text.match(/window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\)/);
                                    if (match) {
                                        return JSON.parse(match[1].replace(/\\"/g, '"').replace(/\\\\/g, '\\\\'));
                                    }
                                } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)

                if json_data:
                    logger.info(f"Found JSON data with keys: {list(json_data.keys()) if isinstance(json_data, dict) else type(json_data)}")
                    listings = self._parse_json_listings(json_data, zona_key)
                    if listings:
                        logger.info(f"Extracted {len(listings)} listings from JSON data")
                        return listings
                    else:
                        logger.warning("JSON data found but no listings extracted")
                else:
                    logger.debug("No JSON data found in page")

            except Exception as e:
                logger.warning(f"JSON extraction failed: {e}")

            # Method 2: Fallback to DOM selectors
            selectors = [
                'article[data-testid="ad-card"]',
                'article[class*="AdCard"]',
                'div[class*="AdCard"]',
                'article.ma-AdCard',
                '.ma-AdCardV2',
                'article.AdCard',
                '[data-testid="listing"]',
                'article[data-ad-id]',
            ]

            items = []
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    items = page.query_selector_all(selector)
                    if items:
                        logger.info(f"Found {len(items)} cards using selector: {selector}")
                        break
                except:
                    continue

            if not items:
                # Debug: log what we can find
                try:
                    html_sample = page.evaluate("() => document.body.innerHTML.substring(0, 2000)")
                    logger.debug(f"Page HTML sample: {html_sample[:500]}")
                except:
                    pass
                logger.warning("No listing cards found via DOM or JSON")
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

    def _parse_json_listings(self, json_data: Dict, zona_key: str) -> List[Dict[str, Any]]:
        """Parse listings from Milanuncios JSON structure."""
        listings = []

        try:
            # Navigate JSON structure to find ads array
            ads = None

            # Try different paths where ads might be
            if isinstance(json_data, dict):
                # Direct ads array
                if 'ads' in json_data:
                    ads = json_data['ads']
                # Nested in pageProps
                elif 'pageProps' in json_data and 'ads' in json_data['pageProps']:
                    ads = json_data['pageProps']['ads']
                # Nested in data
                elif 'data' in json_data and 'ads' in json_data['data']:
                    ads = json_data['data']['ads']
                # Search in all keys
                else:
                    for key, value in json_data.items():
                        if isinstance(value, dict) and 'ads' in value:
                            ads = value['ads']
                            break
                        elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                            if 'id' in value[0] and 'url' in value[0]:
                                ads = value
                                break

            if not ads:
                # Debug: show structure to help find ads
                if isinstance(json_data, dict):
                    logger.warning(f"Could not find ads. Top-level keys: {list(json_data.keys())}")
                    for key, value in json_data.items():
                        if isinstance(value, dict):
                            logger.debug(f"  {key}: dict with keys {list(value.keys())[:5]}")
                        elif isinstance(value, list):
                            logger.debug(f"  {key}: list with {len(value)} items")
                return []

            logger.info(f"Found {len(ads)} ads in JSON, filtering particulares...")
            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            for ad in ads:
                try:
                    # Filter professionals if needed
                    seller_type = ad.get('sellerType', '').lower()
                    if self.only_particulares and seller_type == 'professional':
                        continue

                    anuncio_id = str(ad.get('id', ''))
                    if not anuncio_id:
                        continue

                    # Extract price
                    precio = None
                    price_data = ad.get('price', {})
                    if isinstance(price_data, dict):
                        cash_price = price_data.get('cashPrice', {})
                        if isinstance(cash_price, dict):
                            precio = cash_price.get('value')
                        elif 'value' in price_data:
                            precio = price_data.get('value')
                    elif isinstance(price_data, (int, float)):
                        precio = price_data

                    # Build URL
                    url_path = ad.get('url', '')
                    url_anuncio = f"{self.BASE_URL}{url_path}" if url_path.startswith('/') else url_path

                    # Extract location
                    ubicacion = ''
                    if 'city' in ad and isinstance(ad['city'], dict):
                        ubicacion = ad['city'].get('name', '')
                    elif 'location' in ad:
                        ubicacion = ad.get('location', '')

                    listing = {
                        'anuncio_id': anuncio_id,
                        'titulo': ad.get('title', ''),
                        'precio': precio,
                        'descripcion': ad.get('description', '')[:500] if ad.get('description') else '',
                        'ubicacion': ubicacion,
                        'zona_geografica': zona_info.get('nombre', zona_key),
                        'zona_busqueda': zona_key,
                        'url_anuncio': url_anuncio,
                        'es_particular': seller_type != 'professional',
                        'tipo_inmueble': 'piso',
                    }

                    # Extract images if available
                    if 'images' in ad and ad['images']:
                        listing['imagenes'] = ad['images'][:5]

                    listings.append(listing)

                except Exception as e:
                    logger.debug(f"Error parsing JSON ad: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing JSON listings: {e}")

        return listings

    def _parse_listing_card(self, item, zona_key: str) -> Optional[Dict[str, Any]]:
        """Parse a single listing card from DOM (fallback method)."""
        try:
            # Check if professional (agency) - various patterns
            pro_selectors = [
                '[class*="professional"]',
                '[class*="Professional"]',
                '[class*="Pro"]',
                '.ma-AdTag--pro',
                '[data-seller-type="professional"]',
                '[class*="agency"]',
            ]
            for sel in pro_selectors:
                try:
                    if item.query_selector(sel) and self.only_particulares:
                        return None
                except:
                    continue

            # Get link and ID - multiple patterns
            link = None
            link_selectors = [
                'a[href*=".htm"]',
                'a[href*="/anuncios/"]',
                'a[href*="/pisos"]',
                'a[data-testid="ad-link"]',
                'a[class*="Link"]',
            ]
            for sel in link_selectors:
                try:
                    link = item.query_selector(sel)
                    if link:
                        break
                except:
                    continue

            if not link:
                # Try getting any link
                link = item.query_selector('a')

            if not link:
                return None

            href = link.get_attribute('href')
            if not href:
                return None

            # Extract ID from URL - multiple patterns
            anuncio_id = None
            id_patterns = [
                r'-(\d{8,})\.htm',    # xxx-12345678.htm
                r'/(\d{8,})\.htm',    # /12345678.htm
                r'-(\d{8,})$',        # -12345678
                r'id=(\d+)',          # ?id=12345678
                r'(\d{8,})',          # any 8+ digit number
            ]
            for pattern in id_patterns:
                match = re.search(pattern, href)
                if match:
                    anuncio_id = match.group(1)
                    break

            if not anuncio_id:
                # Try data attribute
                anuncio_id = item.get_attribute('data-ad-id') or item.get_attribute('data-id')

            if not anuncio_id:
                return None

            # Title - multiple patterns
            titulo = ''
            title_selectors = ['h2', 'h3', '[class*="title"]', '[class*="Title"]', '[data-testid="ad-title"]']
            for sel in title_selectors:
                try:
                    elem = item.query_selector(sel)
                    if elem:
                        titulo = elem.inner_text().strip()
                        if titulo:
                            break
                except:
                    continue

            # Price - multiple patterns
            precio = None
            price_selectors = ['[class*="price"]', '[class*="Price"]', '[data-testid="ad-price"]']
            for sel in price_selectors:
                try:
                    elem = item.query_selector(sel)
                    if elem:
                        price_text = elem.inner_text()
                        precio = self._parse_price(price_text)
                        if precio:
                            break
                except:
                    continue

            # Description
            descripcion = ''
            desc_selectors = ['[class*="description"]', '[class*="Description"]', 'p']
            for sel in desc_selectors:
                try:
                    elem = item.query_selector(sel)
                    if elem:
                        text = elem.inner_text().strip()
                        if len(text) > 20:  # Avoid short labels
                            descripcion = text[:500]
                            break
                except:
                    continue

            # Location
            ubicacion = ''
            loc_selectors = ['[class*="location"]', '[class*="Location"]', '[class*="city"]']
            for sel in loc_selectors:
                try:
                    elem = item.query_selector(sel)
                    if elem:
                        ubicacion = elem.inner_text().strip()
                        if ubicacion:
                            break
                except:
                    continue

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
            # Enhanced anti-detection config to avoid triggering GeeTest
            # - geoip: matches fingerprint (timezone, locale) to IP location
            # - locale: Spanish locale for Spanish site
            # - block_webrtc: prevents IP leak that could expose datacenter
            # - os: Windows is most common in Spain
            # - humanize: slower, more realistic cursor movements
            with Camoufox(
                humanize=2.5,  # Slower cursor movements (max 2.5 seconds)
                headless=headless_mode,
                geoip=True,  # Auto-match timezone/locale to IP
                os="windows",  # Most common OS in Spain
                block_webrtc=True,  # Prevent WebRTC IP leak
                locale=["es-ES", "es"],  # Spanish locale
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

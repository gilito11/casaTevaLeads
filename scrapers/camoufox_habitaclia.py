"""
Habitaclia scraper using Camoufox anti-detect browser.

Bypasses Imperva/Incapsula bot protection that blocks Botasaurus Chrome
from datacenter IPs (Contabo VPS).

Falls back to Botasaurus when Camoufox is not available (GitHub Actions).
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

from scrapers.botasaurus_habitaclia import ZONAS_GEOGRAFICAS
from scrapers.camoufox_idealista import parse_proxy
from scrapers.utils.particular_filter import debe_scrapear

logger = logging.getLogger(__name__)


def get_postgres_config() -> Dict[str, Any]:
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
    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', ''),
    }


def extract_phone_from_description(description: str) -> Optional[str]:
    if not description:
        return None
    clean_desc = description.replace(' ', '').replace('.', '').replace('-', '').replace('/', '')
    phones = re.findall(r'[679]\d{8}', clean_desc)
    BLACKLIST = {'666666666', '777777777', '999999999', '600000000', '700000000', '900000000', '123456789', '987654321'}
    for phone in phones:
        if phone not in BLACKLIST and len(set(phone)) > 2:
            return phone
    return None


class CamoufoxHabitaclia:
    """Habitaclia scraper using Camoufox to bypass Imperva bot protection."""

    BASE_URL = "https://www.habitaclia.com"
    PORTAL_NAME = "habitaclia"

    def __init__(
        self,
        zones: List[str] = None,
        tenant_id: int = 1,
        headless: bool = True,
        only_private: bool = True,
        quick_scan: bool = False,
        proxy: str = None,
    ):
        self.zones = zones or ['salou']
        self.tenant_id = tenant_id
        self.headless = headless
        self.only_private = only_private
        self.quick_scan = quick_scan
        self.proxy = proxy or os.environ.get('DATADOME_PROXY')
        self.postgres_conn = None
        self._scraped_listings = []
        self.stats = {
            'total_listings': 0,
            'filtered_out': 0,
            'saved': 0,
            'errors': 0,
            'pages_scraped': 0,
            'duplicates': 0,
        }

    def _init_postgres(self):
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

    def _human_delay(self, min_sec=2.0, max_sec=5.0):
        env_min = float(os.environ.get('SCRAPER_MIN_DELAY', '0'))
        min_sec = max(min_sec, env_min)
        max_sec = max(max_sec, min_sec)
        time.sleep(random.uniform(min_sec, max_sec))

    def _generate_lead_id(self, anuncio_id: str) -> int:
        unique_string = f"{self.tenant_id}:{self.PORTAL_NAME}:{anuncio_id}"
        hash_hex = hashlib.md5(unique_string.encode()).hexdigest()
        return int(hash_hex, 16) % 2147483647

    def build_url(self, zona_key: str, page: int = 1) -> str:
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")
        slug = zona['url_slug']
        is_province = zona.get('is_province', False)
        if is_province:
            url = f"{self.BASE_URL}/viviendas-{slug}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-{slug}-pag{page}.htm"
        elif self.only_private:
            url = f"{self.BASE_URL}/viviendas-particulares-{slug}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-particulares-{slug}-pag{page}.htm"
        else:
            url = f"{self.BASE_URL}/viviendas-{slug}.htm"
            if page > 1:
                url = f"{self.BASE_URL}/viviendas-{slug}-pag{page}.htm"
        return url

    def _accept_cookies(self, page):
        """Accept cookies/consent popups."""
        try:
            page.evaluate('''
                if (window.__tcfapi) {
                    window.__tcfapi('postCustomConsent', 2, function(){}, [1,2,3,4,5,6,7,8,9,10], [1,2,3,4,5,6,7,8,9,10], [1,2,3,4,5,6,7,8,9,10]);
                }
            ''')
        except:
            pass

        selectors = [
            '#didomi-notice-agree-button',
            'button[id*="accept"]',
            'button[class*="accept"]',
            'button[aria-label*="aceptar" i]',
            'button:has-text("Aceptar")',
        ]
        for sel in selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self._human_delay(1, 2)
                    break
            except:
                continue

    def _wait_for_content(self, page, timeout=30) -> bool:
        """Wait for listing links to appear."""
        for attempt in range(timeout // 2):
            try:
                count = page.evaluate('document.querySelectorAll(\'a[href*="/comprar-"]\').length')
                if count and count > 0:
                    logger.info(f"Content loaded after {(attempt+1)*2}s: {count} listing links")
                    return True
            except:
                pass
            time.sleep(2)
        return False

    def _extract_listing_links(self, page) -> List[str]:
        """Extract listing URLs from search page."""
        html = page.content()
        logger.info(f"HTML length: {len(html)}")

        links = re.findall(
            r'href="(https://www\.habitaclia\.com/comprar-(?:piso|casa|chalet|vivienda)[^"]+\.htm)[^"]*"',
            html
        )
        unique_links = list(dict.fromkeys(links))
        unique_links = [l for l in unique_links if 'vistamapa' not in l and '-i' in l]
        logger.info(f"Found {len(unique_links)} listing links")
        return unique_links

    def _enrich_listing(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch detail page and extract listing data."""
        url = listing['detail_url']
        logger.info(f"Fetching detail: {url[:70]}...")

        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self._human_delay(2, 4)

            # Try clicking phone button
            try:
                phone_btn = page.query_selector('[class*="phone"], [class*="telefono"], button[class*="call"], a[href^="tel:"]')
                if phone_btn and phone_btn.is_visible():
                    phone_btn.click()
                    time.sleep(1)
            except:
                pass

            html = page.content()

            # Title
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            listing['titulo'] = title_match.group(1).strip() if title_match else None

            # Price
            feature_container = re.search(
                r'class="[^"]*feature-container[^"]*"[^>]*>(.*?)</ul>',
                html, re.DOTALL | re.IGNORECASE
            )
            if feature_container:
                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*€', feature_container.group(1))
                if price_match:
                    listing['precio'] = float(price_match.group(1).replace('.', ''))
            if 'precio' not in listing:
                title_price = re.search(r'por\s+(\d{1,3}(?:\.\d{3})*)\s*€', html, re.IGNORECASE)
                if title_price:
                    listing['precio'] = float(title_price.group(1).replace('.', ''))

            # Rooms
            habs = re.search(r'<li>(\d+)\s*habitacion', html, re.IGNORECASE)
            if habs:
                listing['habitaciones'] = int(habs.group(1))

            # Size
            metros = re.search(r'<li>Superficie\s*(\d+)(?:&nbsp;|\s)*m', html, re.IGNORECASE)
            if metros:
                listing['metros'] = int(metros.group(1))
            elif not metros:
                metros2 = re.search(r'de\s+(\d+)\s+metros', html, re.IGNORECASE)
                if metros2:
                    listing['metros'] = int(metros2.group(1))

            # Bathrooms
            banos = re.search(r'<li>(\d+)\s*Ba[ñn]o', html, re.IGNORECASE)
            if banos:
                listing['banos'] = int(banos.group(1))

            # Location
            ubicacion = re.search(r'class="[^"]*location[^"]*"[^>]*>([^<]+)', html, re.IGNORECASE)
            if ubicacion:
                listing['ubicacion'] = ubicacion.group(1).strip()

            # Description
            detail_desc = re.search(
                r'<p[^>]*class="[^"]*detail-description[^"]*"[^>]*>(.*?)</p>',
                html, re.DOTALL | re.IGNORECASE
            )
            if detail_desc:
                desc_text = re.sub(r'<[^>]+>', '\n', detail_desc.group(1))
                desc_text = re.sub(r'\n+', '\n', desc_text).strip()
                listing['descripcion'] = desc_text[:2000]
            if 'descripcion' not in listing:
                meta_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html, re.IGNORECASE)
                if meta_desc:
                    listing['descripcion'] = meta_desc.group(1).strip()[:2000]

            # Phone from description
            phone = extract_phone_from_description(listing.get('descripcion', ''))
            if phone:
                listing['telefono'] = phone
                listing['telefono_norm'] = phone
                logger.info(f"Phone found in description: {phone}")
            else:
                # Phone from tel: links
                tel_link = re.search(r'href="tel:(?:\+?34)?([679]\d{8})"', html)
                if tel_link:
                    listing['telefono'] = tel_link.group(1)
                    listing['telefono_norm'] = tel_link.group(1)
                else:
                    listing['telefono'] = None
                    listing['telefono_norm'] = None

            # Photos
            photos = re.findall(
                r'(?:https?:)?//images\.habimg\.com/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp)',
                html, re.IGNORECASE
            )
            unique_photos = []
            seen_ids = set()
            for photo in photos:
                if photo.startswith('//'):
                    photo = 'https:' + photo
                if 'logo' in photo.lower():
                    continue
                id_match = re.search(
                    r'/(?:imgh|thumb)/(\d+-\d+)/([^/]+?)(?:_(?:XXL|XL|L|M|S|T))?\.(?:jpg|jpeg|png|webp)$',
                    photo, re.IGNORECASE
                )
                if id_match:
                    unique_id = f"{id_match.group(1)}/{id_match.group(2)}"
                    if unique_id not in seen_ids:
                        seen_ids.add(unique_id)
                        large_url = f"https://images.habimg.com/imgh/{id_match.group(1)}/{id_match.group(2)}_XXL.jpg"
                        unique_photos.append(large_url)
            listing['fotos'] = unique_photos[:10]

            # Particular vs agency
            agency = re.search(r'class="[^"]*(?:agent|agency|professional|inmobiliaria)[^"]*"', html, re.IGNORECASE)
            listing['es_particular'] = not bool(agency)
            listing['vendedor'] = 'Inmobiliaria' if agency else 'Particular'

        except Exception as e:
            logger.error(f"Error enriching {url}: {e}")

        return listing

    def save_to_postgres(self, listing: Dict[str, Any]) -> bool:
        if not self.postgres_conn:
            return False

        anuncio_id = str(listing.get('anuncio_id', ''))
        if not anuncio_id:
            return False

        raw_data = {
            'anuncio_id': anuncio_id,
            'titulo': listing.get('titulo', ''),
            'telefono': listing.get('telefono', ''),
            'telefono_norm': listing.get('telefono_norm', ''),
            'nombre': listing.get('vendedor', ''),
            'direccion': listing.get('ubicacion', ''),
            'zona': listing.get('zona_geografica', ''),
            'zona_busqueda': listing.get('zona_busqueda', ''),
            'zona_geografica': listing.get('zona_geografica', ''),
            'tipo_inmueble': listing.get('tipo_inmueble', 'piso'),
            'precio': listing.get('precio'),
            'habitaciones': listing.get('habitaciones'),
            'metros': listing.get('metros'),
            'descripcion': listing.get('descripcion', ''),
            'fotos': listing.get('fotos', []),
            'url': listing.get('url_anuncio') or listing.get('detail_url', ''),
            'es_particular': listing.get('es_particular', True),
            'vendedor': listing.get('vendedor', ''),
            'scraper_type': 'camoufox',
        }

        sql = """
            INSERT INTO raw.raw_listings (
                tenant_id, portal, data_lake_path, raw_data, scraping_timestamp
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
            WHERE raw_data->>'anuncio_id' IS NOT NULL
            DO NOTHING
        """

        now = datetime.now()
        data_lake_path = f"camoufox/{self.PORTAL_NAME}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

        try:
            cursor = self.postgres_conn.cursor()
            cursor.execute(sql, (
                self.tenant_id, self.PORTAL_NAME, data_lake_path,
                json.dumps(raw_data, ensure_ascii=False), now,
            ))
            rows = cursor.rowcount
            self.postgres_conn.commit()

            if rows > 0 and listing.get('precio'):
                try:
                    cursor.execute("""
                        INSERT INTO raw.listing_price_history (tenant_id, portal, anuncio_id, precio)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (tenant_id, portal, anuncio_id, precio) DO NOTHING
                    """, (self.tenant_id, self.PORTAL_NAME, anuncio_id, listing['precio']))
                    self.postgres_conn.commit()
                except:
                    pass

            cursor.close()
            return rows > 0
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"DB connection lost, reconnecting: {e}")
            try:
                self.postgres_conn = psycopg2.connect(**{
                    k: v for k, v in get_postgres_config().items()
                })
                cursor = self.postgres_conn.cursor()
                cursor.execute(sql, (
                    self.tenant_id, self.PORTAL_NAME, data_lake_path,
                    json.dumps(raw_data, ensure_ascii=False), now,
                ))
                self.postgres_conn.commit()
                cursor.close()
                return True
            except:
                return False
        except Exception as e:
            logger.error(f"Error saving: {e}")
            try:
                self.postgres_conn.rollback()
            except:
                pass
            return False

    def scrape(self) -> Dict[str, int]:
        """Main scraping method using Camoufox."""
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            logger.error("Camoufox not installed. Run: pip install camoufox && camoufox fetch")
            raise

        self._init_postgres()

        camoufox_opts = {
            "humanize": 2.5,
            "headless": self.headless,
            "geoip": True,
            "os": "windows",
            "block_webrtc": True,
            "locale": ["es-ES", "es"],
        }

        proxy_config = parse_proxy(self.proxy)
        if proxy_config:
            camoufox_opts["proxy"] = proxy_config
            logger.info(f"Using proxy: {proxy_config['server']}")

        logger.info(f"Starting Camoufox Habitaclia scraper")
        logger.info(f"  Zones: {self.zones}")
        logger.info(f"  Headless: {self.headless}")
        logger.info(f"  Proxy: {'configured' if proxy_config else 'none (will use direct IP)'}")

        try:
            with Camoufox(**camoufox_opts) as browser:
                page = browser.new_page()

                # Warmup: visit homepage first
                logger.info("Warming up: visiting homepage...")
                page.goto(self.BASE_URL, wait_until='domcontentloaded')
                self._human_delay(3, 5)
                self._accept_cookies(page)
                self._human_delay(2, 3)

                for zona_key in self.zones:
                    zona_info = ZONAS_GEOGRAFICAS.get(zona_key)
                    if not zona_info:
                        logger.warning(f"Zone not found: {zona_key}")
                        continue

                    # Handle composite zones
                    if 'composite' in zona_info:
                        logger.info(f"Composite zone {zona_key}: {zona_info['composite']}")
                        for city_key in zona_info['composite']:
                            if city_key in ZONAS_GEOGRAFICAS:
                                self._scrape_zone(page, city_key, zona_info['nombre'])
                    else:
                        self._scrape_zone(page, zona_key)

                page.close()

        except Exception as e:
            logger.error(f"Scraper error: {e}")
        finally:
            if self.postgres_conn:
                self.postgres_conn.close()

        # Validate results and log run
        try:
            from scrapers.error_handling import validate_scraping_results, log_scraper_run
            validate_scraping_results(
                listings=self._scraped_listings,
                portal_name='habitaclia',
                expected_min_count=3,
                required_fields=['titulo', 'precio', 'url'],
            )
            log_scraper_run('habitaclia', self.stats, self.tenant_id)
        except Exception as e:
            logger.debug(f"Post-scrape validation/logging error: {e}")

        logger.info(f"Stats: {self.stats}")
        return self.stats

    def _scrape_zone(self, page, zona_key: str, parent_zone_name: str = None):
        """Scrape a single zone."""
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
        zone_name = parent_zone_name or zona_info.get('nombre', zona_key)
        url = self.build_url(zona_key)

        logger.info(f"Scraping zone: {zone_name} ({url})")

        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self._human_delay(2, 4)
            self._accept_cookies(page)

            # Wait for content
            if not self._wait_for_content(page):
                logger.warning(f"No content loaded for {zona_key}")
                # Save debug HTML
                debug_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'debug_habitaclia.html')
                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                logger.warning(f"Debug HTML saved to {debug_path}")
                return

            # Scroll to load lazy content
            for i in range(4):
                page.mouse.wheel(0, random.randint(400, 700))
                self._human_delay(1, 2)

            self.stats['pages_scraped'] += 1

            # Extract listing links
            links = self._extract_listing_links(page)
            if not links:
                return

            # Build basic listings
            basic_listings = []
            for link in links[:20]:
                id_match = re.search(r'-i(\d{9,})', link)
                if not id_match:
                    continue
                basic_listings.append({
                    'anuncio_id': id_match.group(1),
                    'detail_url': link,
                    'url_anuncio': link,
                    'portal': self.PORTAL_NAME,
                    'zona_busqueda': zone_name,
                    'zona_geografica': zone_name,
                })

            logger.info(f"Zone {zona_key}: {len(basic_listings)} listings")

            if self.quick_scan:
                # Save basic listings without enrichment
                for listing in basic_listings:
                    self.stats['total_listings'] += 1
                    self._scraped_listings.append(listing)
                    if self.save_to_postgres(listing):
                        self.stats['saved'] += 1
                    else:
                        self.stats['duplicates'] += 1
                return

            # Enrich with detail pages
            for listing in basic_listings[:10]:
                self.stats['total_listings'] += 1
                enriched = self._enrich_listing(page, listing)
                self._scraped_listings.append(enriched)
                if self.save_to_postgres(enriched):
                    self.stats['saved'] += 1
                else:
                    self.stats['duplicates'] += 1
                self._human_delay(1, 3)

        except Exception as e:
            logger.error(f"Error scraping zone {zona_key}: {e}")
            self.stats['errors'] += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.postgres_conn:
            self.postgres_conn.close()

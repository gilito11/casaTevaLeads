"""
Fotocasa scraper using Camoufox anti-detect browser.

Botasaurus Chrome gets blocked by Fotocasa (21KB empty shell, React never hydrates).
Camoufox bypasses this with anti-fingerprint Firefox.
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
import requests as http_requests

from scrapers.botasaurus_fotocasa import ZONAS_GEOGRAFICAS

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


class CamoufoxFotocasa:
    PORTAL_NAME = 'fotocasa'
    BASE_URL = 'https://www.fotocasa.es'

    def __init__(self, zones=None, headless=True, postgres=False, tenant_id=1, proxy=None):
        self.zones = zones or ['salou']
        self.headless = headless
        self.postgres = postgres
        self.tenant_id = tenant_id
        self.postgres_conn = None
        self.proxy = proxy or os.environ.get('DATADOME_PROXY', '')
        self.captcha_api_key = os.environ.get('CAPTCHA_API_KEY', '')
        self._scraped_listings = []
        self.stats = {
            'pages_scraped': 0,
            'listings_found': 0,
            'listings_saved': 0,
            'errors': 0,
        }

    def _init_postgres(self):
        if not self.postgres:
            return
        config = get_postgres_config()
        self.postgres_conn = psycopg2.connect(**config)
        self.postgres_conn.autocommit = False
        logger.info(f"PostgreSQL connected: {config['host']}")

    def _human_delay(self, min_s=1, max_s=3):
        time.sleep(random.uniform(min_s, max_s))

    @staticmethod
    def _parse_proxy(proxy_str: str):
        """Parse proxy string to Camoufox format. Input: user:pass@host:port"""
        if not proxy_str:
            return None
        try:
            if "@" in proxy_str:
                auth, addr = proxy_str.rsplit("@", 1)
                user, passwd = auth.split(":", 1)
                host, port = addr.split(":")
                return {"server": f"http://{host}:{port}", "username": user, "password": passwd}
            return {"server": f"http://{proxy_str}"}
        except Exception as e:
            logger.error(f"Invalid proxy format: {e}")
            return None

    def build_url(self, zona_key: str) -> str:
        zona = ZONAS_GEOGRAFICAS.get(zona_key, {})
        url_path = zona.get('url_path', f'{zona_key}/todas-las-zonas')
        return f"{self.BASE_URL}/es/comprar/viviendas/particulares/{url_path}/pl"

    def _accept_cookies(self, page):
        selectors = [
            '[data-testid="TcfAccept"]',
            'button:has-text("Aceptar")',
            'button:has-text("Aceptar y continuar")',
            '#didomi-notice-agree-button',
            'button[id*="accept"]',
            '.sui-AtomButton--primary',
        ]
        for selector in selectors:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    logger.info(f"Cookie consent accepted via: {selector}")
                    self._human_delay(1, 2)
                    return True
            except:
                continue

        # Try TCF API
        try:
            page.evaluate('''
                if (window.__tcfapi) {
                    window.__tcfapi('postCustomConsent', 2, function(){},
                        [1,2,3,4,5,6,7,8,9,10],
                        [1,2,3,4,5,6,7,8,9,10],
                        [1,2,3,4,5,6,7,8,9,10]);
                }
            ''')
            logger.info("TCF API consent granted")
            return True
        except:
            pass

        return False

    def _check_geetest_blocked(self, page) -> bool:
        """Check if page is a GeeTest captcha challenge."""
        try:
            content = page.content()
            if 'SENTIMOS LA INTERRUPCI' in content or 'geetest' in content.lower():
                logger.warning("GeeTest captcha detected")
                return True
        except:
            pass
        return False

    def _get_2captcha_key(self) -> str:
        """Clean and return the 2Captcha API key."""
        api_key = self.captcha_api_key.strip().strip('"').strip("'").strip()
        api_key = re.sub(r'[^a-fA-F0-9]', '', api_key)
        if len(api_key) > 32:
            api_key = api_key[-32:]
        return api_key

    def _solve_geetest(self, page, max_attempts=2) -> bool:
        """Solve GeeTest captcha using 2Captcha API with retry."""
        if not self.captcha_api_key:
            logger.error("CAPTCHA_API_KEY not set - cannot solve GeeTest")
            return False

        api_key = self._get_2captcha_key()
        logger.info(f"2Captcha key length: {len(api_key)} chars")

        for attempt in range(max_attempts):
            if attempt > 0:
                logger.info(f"GeeTest solve attempt {attempt + 1}/{max_attempts}")
                # Reload to get a fresh challenge
                page.reload(wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)

            try:
                content = page.content()

                # Extract GeeTest v3 params
                gt_match = re.search(r'gt:\s*"([^"]+)"', content)
                challenge_match = re.search(r'challenge:\s*"([^"]+)"', content)
                api_server_match = re.search(r'api_server:\s*"([^"]+)"', content)

                # Also try alternative param locations (data attributes, JSON)
                if not gt_match:
                    gt_match = re.search(r'"gt"\s*:\s*"([^"]+)"', content)
                if not challenge_match:
                    challenge_match = re.search(r'"challenge"\s*:\s*"([^"]+)"', content)

                if not gt_match or not challenge_match:
                    # Check for GeeTest v4 (captcha_id)
                    v4_match = re.search(r'captcha_id["\s:]+["\']([\w]+)', content)
                    if v4_match:
                        logger.info("Detected GeeTest v4, attempting v4 solve...")
                        result = self._solve_geetest_v4(page, api_key, v4_match.group(1))
                        if result:
                            return True
                        continue
                    logger.error("Could not extract GeeTest gt/challenge from page")
                    continue

                gt = gt_match.group(1)
                challenge = challenge_match.group(1)
                api_server = api_server_match.group(1) if api_server_match else None
                page_url = page.url

                logger.info(f"GeeTest v3: gt={gt[:16]}... challenge={challenge[:16]}...")
                if api_server:
                    logger.info(f"  api_server: {api_server}")

                # Submit to 2Captcha
                submit_data = {
                    'key': api_key,
                    'method': 'geetest',
                    'gt': gt,
                    'challenge': challenge,
                    'pageurl': page_url,
                    'json': 1,
                }
                if api_server:
                    submit_data['api_server'] = api_server

                submit_resp = http_requests.post(
                    "https://2captcha.com/in.php",
                    data=submit_data,
                    timeout=30,
                )
                result = submit_resp.json()

                if result.get('status') != 1:
                    logger.error(f"2Captcha submit error: {result}")
                    continue

                request_id = result['request']
                logger.info(f"2Captcha request ID: {request_id}")

                # Poll for solution
                solved = False
                for _ in range(30):  # Max 150s
                    time.sleep(5)
                    poll_resp = http_requests.get(
                        "https://2captcha.com/res.php",
                        params={
                            'key': api_key,
                            'action': 'get',
                            'id': request_id,
                            'json': 1,
                        },
                        timeout=30,
                    )
                    poll_result = poll_resp.json()

                    if poll_result.get('status') == 1:
                        solution = poll_result['request']
                        logger.info("GeeTest solved by 2Captcha")

                        # Submit the solution back to the page
                        page.evaluate(f'''() => {{
                            if (typeof solvedCaptcha === 'function') {{
                                solvedCaptcha({{
                                    geetest_challenge: "{solution['geetest_challenge']}",
                                    geetest_validate: "{solution['geetest_validate']}",
                                    geetest_seccode: "{solution['geetest_seccode']}"
                                }});
                            }} else if (typeof geetestCallback === 'function') {{
                                geetestCallback({{
                                    geetest_challenge: "{solution['geetest_challenge']}",
                                    geetest_validate: "{solution['geetest_validate']}",
                                    geetest_seccode: "{solution['geetest_seccode']}"
                                }});
                            }} else {{
                                // Try submitting via form
                                var form = document.querySelector('form');
                                if (form) {{
                                    var inputs = {{
                                        'geetest_challenge': '{solution['geetest_challenge']}',
                                        'geetest_validate': '{solution['geetest_validate']}',
                                        'geetest_seccode': '{solution['geetest_seccode']}'
                                    }};
                                    for (var key in inputs) {{
                                        var inp = document.querySelector('[name="' + key + '"]');
                                        if (inp) inp.value = inputs[key];
                                        else {{
                                            inp = document.createElement('input');
                                            inp.type = 'hidden';
                                            inp.name = key;
                                            inp.value = inputs[key];
                                            form.appendChild(inp);
                                        }}
                                    }}
                                    form.submit();
                                }}
                            }}
                        }}''')
                        time.sleep(5)

                        if not self._check_geetest_blocked(page):
                            logger.info("GeeTest bypass successful!")
                            return True
                        else:
                            logger.warning("GeeTest solution submitted but still blocked")
                            solved = True  # Don't retry 2Captcha, challenge changed
                            break

                    elif 'CAPCHA_NOT_READY' in str(poll_result):
                        continue
                    elif 'ERROR_CAPTCHA_UNSOLVABLE' in str(poll_result):
                        logger.warning("2Captcha: challenge unsolvable, will retry with fresh challenge")
                        break  # Get fresh challenge
                    else:
                        logger.error(f"2Captcha error: {poll_result}")
                        break

                if solved:
                    continue  # Try another attempt

            except Exception as e:
                logger.error(f"GeeTest solving error: {e}")
                continue

        logger.error(f"GeeTest solving failed after {max_attempts} attempts")
        return False

    def _solve_geetest_v4(self, page, api_key: str, captcha_id: str) -> bool:
        """Solve GeeTest v4 captcha."""
        try:
            submit_resp = http_requests.post(
                "https://2captcha.com/in.php",
                data={
                    'key': api_key,
                    'method': 'geetest_v4',
                    'captcha_id': captcha_id,
                    'pageurl': page.url,
                    'json': 1,
                },
                timeout=30,
            )
            result = submit_resp.json()
            if result.get('status') != 1:
                logger.error(f"2Captcha v4 submit error: {result}")
                return False

            request_id = result['request']
            logger.info(f"2Captcha v4 request ID: {request_id}")

            for _ in range(30):
                time.sleep(5)
                poll_resp = http_requests.get(
                    "https://2captcha.com/res.php",
                    params={'key': api_key, 'action': 'get', 'id': request_id, 'json': 1},
                    timeout=30,
                )
                poll_result = poll_resp.json()
                if poll_result.get('status') == 1:
                    logger.info("GeeTest v4 solved")
                    # v4 solutions need different injection - TBD based on actual page
                    return False  # Placeholder - need to see actual v4 page first
                elif 'CAPCHA_NOT_READY' in str(poll_result):
                    continue
                else:
                    logger.error(f"2Captcha v4 error: {poll_result}")
                    return False
            return False
        except Exception as e:
            logger.error(f"GeeTest v4 error: {e}")
            return False

    def _wait_for_listings(self, page, timeout=20) -> bool:
        """Wait for listing links to appear in the DOM."""
        for i in range(timeout // 2):
            count = page.evaluate('''
                document.querySelectorAll('a[href*="/es/comprar/vivienda/"]').length
            ''')
            if count and count > 0:
                logger.info(f"Found {count} listing links after {(i+1)*2}s")
                return True
            time.sleep(2)
        return False

    def _extract_listing_links(self, page) -> List[str]:
        """Extract listing URLs from search results page."""
        html = page.content()
        html_lower = html.lower()

        # Find divider between particulares and agencies
        divider_markers = [
            'anuncios de inmobiliarias',
            'ver más anuncios',
            'mira algunos de los anuncios',
        ]
        divider_pos = len(html)
        for marker in divider_markers:
            pos = html_lower.find(marker)
            if 0 < pos < divider_pos:
                divider_pos = pos
                logger.info(f"Found divider '{marker}' at position {pos}")

        particulares_html = html[:divider_pos]

        # Extract listing links
        links = re.findall(r'href="(/es/comprar/vivienda/[^"]+/\d{7,}/d)', particulares_html)
        unique_links = list(dict.fromkeys(links))
        logger.info(f"Found {len(unique_links)} particular listing links")
        return unique_links

    def _parse_detail_page(self, page, url: str, zona_name: str) -> Optional[Dict]:
        """Visit detail page and extract listing data."""
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self._human_delay(2, 4)

            # Scroll to load content
            for pos in [300, 600, 900]:
                page.mouse.wheel(0, pos)
                self._human_delay(0.3, 0.6)

            html = page.content()

            if len(html) < 5000:
                logger.warning(f"Detail page too small: {len(html)} bytes")
                return None

            # Extract ID from URL
            id_matches = re.findall(r'/(\d{7,})', url)
            if not id_matches:
                return None
            anuncio_id = id_matches[-1]

            listing = {
                'anuncio_id': anuncio_id,
                'url_anuncio': url,
                'portal': self.PORTAL_NAME,
                'zona_busqueda': zona_name,
                'zona_geografica': zona_name,
            }

            # Title
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            listing['titulo'] = title_match.group(1).strip() if title_match else None

            # Price
            for pattern in [
                r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?',
                r'(\d{1,3}(?:\.\d{3})*)\s*(?:EUR|€)',
                r'class="[^"]*price[^"]*"[^>]*>([^<]+)',
            ]:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    raw = match.group(1)
                    price_str = re.sub(r'[^\d]', '', raw)
                    if price_str.isdigit() and int(price_str) > 10000:
                        listing['precio'] = float(price_str)
                        break

            # M2
            for pattern in [r'<span[^>]*>\s*<span>(\d+)</span>\s*m[²2]', r'(\d+)\s*m[²2]']:
                match = re.search(pattern, html)
                if match:
                    val = int(match.group(1))
                    if 10 < val < 10000:
                        listing['metros'] = val
                        break

            # Rooms
            for pattern in [r'<span[^>]*>\s*<span>(\d+)</span>\s*hab', r'(\d+)\s*hab']:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    val = int(match.group(1))
                    if 0 < val < 50:
                        listing['habitaciones'] = val
                        break

            # Description
            for pattern in [
                r'class="[^"]*(?:Description|description|comment)[^"]*"[^>]*>(.*?)</(?:div|p|section)',
                r'<meta\s+name="description"\s+content="([^"]{50,})"',
            ]:
                match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                if match:
                    desc = re.sub(r'<[^>]+>', ' ', match.group(1))
                    desc = re.sub(r'\s+', ' ', desc).strip()
                    if len(desc) > 50:
                        listing['descripcion'] = desc[:2000]
                        break

            # Phone from description
            desc = listing.get('descripcion', '')
            phone_match = re.search(r'(?:tel|tfno?|movil|llamar?)[\s.:]*(\d[\d\s]{7,12})', desc, re.IGNORECASE)
            if not phone_match:
                phone_match = re.search(r'\b(6\d{8}|7\d{8}|9\d{8})\b', desc)
            if phone_match:
                phone = re.sub(r'\s+', '', phone_match.group(1))
                if len(phone) == 9:
                    listing['telefono'] = phone
                    listing['telefono_norm'] = phone

            # Photos
            photos = re.findall(r'(https?://static\.fotocasa\.es/images/[^"\'<>\s]+)', html, re.IGNORECASE)
            unique_photos = []
            seen = set()
            for photo in photos:
                base = re.sub(r'\?.*$', '', photo)
                if base not in seen and len(base) > 50:
                    unique_photos.append(base + '?rule=original')
                    seen.add(base)
            listing['fotos'] = unique_photos[:10]

            # Particular detection
            html_lower = html.lower()
            is_particular = any(ind in html_lower for ind in [
                'anuncio particular', 'particular_user_icon', 'anunciante particular'
            ])
            if not is_particular:
                agency_patterns = [r'partner\s+inmobiliario', r'tu\s+agente']
                is_particular = not any(re.search(p, html_lower) for p in agency_patterns)

            listing['es_particular'] = is_particular
            listing['vendedor'] = 'Particular' if is_particular else 'Agencia'

            return listing

        except Exception as e:
            logger.error(f"Error parsing detail {url[:60]}: {e}")
            return None

    def _ensure_postgres_connection(self):
        """Reconnect if Neon dropped the idle SSL connection."""
        try:
            if self.postgres_conn and not self.postgres_conn.closed:
                self.postgres_conn.cursor().execute("SELECT 1")
                return
        except Exception:
            logger.warning("PostgreSQL connection dropped, reconnecting...")
        self._init_postgres()

    def save_to_postgres(self, listing: Dict) -> bool:
        if not self.postgres_conn:
            return False

        try:
            self._ensure_postgres_connection()
            raw_data = {
                'anuncio_id': listing.get('anuncio_id'),
                'titulo': listing.get('titulo'),
                'telefono': listing.get('telefono'),
                'precio': listing.get('precio'),
                'habitaciones': listing.get('habitaciones'),
                'metros': listing.get('metros'),
                'fotos': listing.get('fotos', []),
                'url': listing.get('url_anuncio'),
                'es_particular': listing.get('es_particular', True),
                'vendedor': listing.get('vendedor'),
                'descripcion': listing.get('descripcion'),
                'zona_geografica': listing.get('zona_geografica'),
            }

            anuncio_id = listing.get('anuncio_id', '')
            now = datetime.utcnow()
            data_lake_path = f"camoufox/{self.PORTAL_NAME}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

            with self.postgres_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO raw.raw_listings (tenant_id, portal, data_lake_path, raw_data, scraping_timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
                    WHERE raw_data->>'anuncio_id' IS NOT NULL
                    DO NOTHING
                """, (
                    self.tenant_id,
                    self.PORTAL_NAME,
                    data_lake_path,
                    json.dumps(raw_data, ensure_ascii=False),
                    now,
                ))
            self.postgres_conn.commit()
            return True

        except Exception as e:
            logger.error(f"PostgreSQL save error: {e}")
            try:
                self.postgres_conn.rollback()
            except:
                pass
            return False

    def scrape(self) -> Dict[str, int]:
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

        # Add proxy if configured (residential IP avoids GeeTest trigger)
        proxy_config = self._parse_proxy(self.proxy)
        if proxy_config:
            camoufox_opts["proxy"] = proxy_config
            logger.info(f"Using proxy: {proxy_config['server']}")

        logger.info(f"Starting Camoufox Fotocasa scraper")
        logger.info(f"  Zones: {self.zones}")
        logger.info(f"  Headless: {self.headless}")
        logger.info(f"  Proxy: {'configured' if proxy_config else 'none'}")

        try:
            with Camoufox(**camoufox_opts) as browser:
                page = browser.new_page()

                # Warmup
                logger.info("Warming up: visiting homepage...")
                page.goto(self.BASE_URL, wait_until='domcontentloaded')
                self._human_delay(3, 5)

                # Check for GeeTest on homepage
                if self._check_geetest_blocked(page):
                    if not self._solve_geetest(page):
                        logger.error("Failed to solve GeeTest on homepage")
                        return self.stats

                self._accept_cookies(page)
                self._human_delay(2, 3)

                for zona_key in self.zones:
                    zona_info = ZONAS_GEOGRAFICAS.get(zona_key)
                    if not zona_info:
                        logger.warning(f"Zone not found: {zona_key}")
                        continue

                    if 'composite' in zona_info:
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

        # Validate results and send alerts
        try:
            from scrapers.error_handling import validate_scraping_results
            validate_scraping_results(
                listings=self._scraped_listings,
                portal_name='fotocasa',
                expected_min_count=3,
                required_fields=['titulo', 'precio', 'url_anuncio'],
            )
        except Exception as e:
            logger.debug(f"Post-scrape validation error: {e}")

        logger.info(f"Scraping complete. Stats: {self.stats}")
        return self.stats

    def _scrape_zone(self, page, zona_key: str, parent_zone_name: str = None):
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
        zone_name = parent_zone_name or zona_info.get('nombre', zona_key)
        url = self.build_url(zona_key)

        logger.info(f"Scraping zone: {zone_name} ({url})")

        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self._human_delay(2, 3)

            # Check for GeeTest captcha
            if self._check_geetest_blocked(page):
                logger.info("GeeTest detected on search page - solving...")
                if not self._solve_geetest(page):
                    logger.error("Failed to solve GeeTest on search page")
                    self.stats['errors'] += 1
                    return

            self._accept_cookies(page)

            # Wait for network to settle
            try:
                page.wait_for_load_state('networkidle', timeout=15000)
            except:
                pass

            # Log page state
            html_len = len(page.content())
            page_url = page.url
            logger.info(f"Page loaded: {page_url} ({html_len} bytes)")

            # Wait for listing links
            if not self._wait_for_listings(page):
                logger.warning(f"No listings loaded for {zona_key}")
                content = page.content()
                logger.info(f"HTML length: {len(content)}")

                # Log any links found (for debugging selector issues)
                all_links = re.findall(r'href="(/es/[^"]+)"', content)
                logger.info(f"All /es/ links found: {len(all_links)}")
                for link in all_links[:10]:
                    logger.info(f"  Link: {link[:80]}")

                # Save debug HTML
                debug_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          'output', 'debug_fotocasa.html')
                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.warning(f"Debug HTML saved to {debug_path}")
                return

            # Scroll to load lazy content
            for i in range(4):
                page.mouse.wheel(0, random.randint(400, 700))
                self._human_delay(0.5, 1)

            self.stats['pages_scraped'] += 1

            # Extract listing links
            links = self._extract_listing_links(page)
            if not links:
                return

            # Visit detail pages
            for i, link in enumerate(links[:15]):
                if i > 0:
                    self._human_delay(3, 6)

                detail_url = f"{self.BASE_URL}{link}"
                logger.info(f"Detail {i+1}/{min(len(links), 15)}: {detail_url[:70]}")

                listing = self._parse_detail_page(page, detail_url, zone_name)
                if not listing:
                    self.stats['errors'] += 1
                    continue

                self.stats['listings_found'] += 1

                if not listing.get('es_particular', True):
                    logger.info(f"  Skipped (agency): {listing.get('titulo', '')[:40]}")
                    continue

                self._scraped_listings.append(listing)
                if self.postgres and self.save_to_postgres(listing):
                    self.stats['listings_saved'] += 1
                    logger.info(f"  Saved: {listing.get('titulo', '')[:40]} | {listing.get('precio')}€")
                else:
                    logger.info(f"  Found: {listing.get('titulo', '')[:40]} | {listing.get('precio')}€")

        except Exception as e:
            logger.error(f"Error scraping {zona_key}: {e}")
            self.stats['errors'] += 1

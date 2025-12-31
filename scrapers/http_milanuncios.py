"""
Milanuncios HTTP scraper using curl_cffi with browser TLS impersonation.

This attempts to bypass GeeTest by:
1. Using curl_cffi to impersonate Chrome's TLS fingerprint
2. Using mobile user agent (mobile often has less protection)
3. Maintaining session cookies

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
from urllib.parse import urljoin

import psycopg2

# Try to import curl_cffi, fallback to requests
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests as curl_requests
    CURL_CFFI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Configure logging
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

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
        # Parse DATABASE_URL
        import re
        pattern = r'postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+?)(?:\?.*)?$'
        match = re.match(pattern, database_url)
        if match:
            return {
                'host': match.group(3),
                'port': int(match.group(4)) if match.group(4) else 5432,
                'database': match.group(5).split('?')[0],
                'user': match.group(1),
                'password': match.group(2),
            }

    # Fallback to individual env vars
    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
    }


class MilanunciosHTTPScraper:
    """Milanuncios scraper using HTTP with curl_cffi TLS impersonation."""

    BASE_URL = "https://www.milanuncios.com"

    # Mobile Chrome user agents (often less protected)
    MOBILE_USER_AGENTS = [
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
    ]

    # Desktop Chrome user agents
    DESKTOP_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, zones: List[str], max_pages: int = 2, tenant_id: int = 1, use_postgres: bool = True, use_mobile: bool = True):
        self.zones = zones
        self.max_pages = max_pages
        self.tenant_id = tenant_id
        self.use_postgres = use_postgres
        self.use_mobile = use_mobile
        self.session = None
        self.pg_conn = None
        self.stats = {
            'pages_scraped': 0,
            'listings_found': 0,
            'listings_saved': 0,
            'errors': 0,
        }

        # Select user agent
        if use_mobile:
            self.user_agent = random.choice(self.MOBILE_USER_AGENTS)
        else:
            self.user_agent = random.choice(self.DESKTOP_USER_AGENTS)

        logger.info(f"curl_cffi available: {CURL_CFFI_AVAILABLE}")
        logger.info(f"Using {'mobile' if use_mobile else 'desktop'} user agent")

    def _get_session(self):
        """Get or create HTTP session with browser impersonation."""
        if self.session is None:
            if CURL_CFFI_AVAILABLE:
                # Use curl_cffi session with Chrome impersonation
                self.session = curl_requests.Session(impersonate="chrome120")
            else:
                # Fallback to regular requests
                import requests
                self.session = requests.Session()

            # Set headers
            self.session.headers.update({
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?1' if self.use_mobile else '?0',
                'Sec-Ch-Ua-Platform': '"Android"' if self.use_mobile else '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            })

        return self.session

    def _connect_postgres(self):
        """Connect to PostgreSQL."""
        if not self.use_postgres:
            return None

        if self.pg_conn is None:
            config = get_postgres_config()
            try:
                self.pg_conn = psycopg2.connect(**config)
                logger.info(f"Connected to PostgreSQL: {config['host']}/{config['database']}")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                self.pg_conn = None

        return self.pg_conn

    def _close_postgres(self):
        """Close PostgreSQL connection."""
        if self.pg_conn:
            self.pg_conn.close()
            self.pg_conn = None
            logger.info("PostgreSQL connection closed")

    def _human_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Random delay to simulate human behavior."""
        time.sleep(random.uniform(min_sec, max_sec))

    def _build_url(self, zona_key: str, page_num: int = 1) -> str:
        """Build search URL for zone and page."""
        zone_config = ZONAS_GEOGRAFICAS.get(zona_key, {})
        url_path = zone_config.get('url_path', f'pisos-en-{zona_key}/')

        url = f"{self.BASE_URL}/{url_path}"
        if page_num > 1:
            url = url.rstrip('/') + f'?pagina={page_num}'

        return url

    def _warmup(self):
        """Warmup: visit homepage first to get cookies."""
        logger.info("Warming up: visiting homepage...")
        session = self._get_session()

        try:
            # Visit homepage
            if CURL_CFFI_AVAILABLE:
                resp = session.get(self.BASE_URL, impersonate="chrome120")
            else:
                resp = session.get(self.BASE_URL)

            logger.info(f"Homepage status: {resp.status_code}")
            self._human_delay(3, 5)

            # Check for cookies
            logger.info(f"Cookies: {len(session.cookies)} collected")

        except Exception as e:
            logger.warning(f"Warmup failed: {e}")

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content."""
        session = self._get_session()

        try:
            if CURL_CFFI_AVAILABLE:
                resp = session.get(url, impersonate="chrome120", timeout=30)
            else:
                resp = session.get(url, timeout=30)

            if resp.status_code == 200:
                return resp.text
            else:
                logger.warning(f"Non-200 status: {resp.status_code} for {url}")
                return None

        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    def _extract_json_from_html(self, html: str) -> Optional[Dict]:
        """Extract __INITIAL_PROPS__ JSON from HTML."""
        # Pattern for JSON.parse with escaped JSON string
        # The content is like: JSON.parse("{\"isMobile\":false,...}")
        pattern = r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\);'
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                raw_json = match.group(1)
                # Unescape the JSON string (it's escaped for embedding in JS)
                unescaped = raw_json.encode().decode('unicode_escape')
                data = json.loads(unescaped)
                logger.info(f"Extracted JSON data with keys: {list(data.keys())[:5]}")
                return data
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"JSON parse failed: {e}")

        # Check for blocked/captcha indicators
        if 'geetest' in html.lower() or 'captcha' in html.lower():
            logger.warning("Captcha/GeeTest detected in page")
        elif 'Robot' in html or 'blocked' in html.lower():
            logger.warning("Possible block detected in page")
        elif '__INITIAL_PROPS__' not in html:
            logger.warning("No __INITIAL_PROPS__ found in page")

        return None

    def _parse_listings(self, json_data: Dict, zona_key: str) -> List[Dict]:
        """Parse listings from JSON data."""
        listings = []

        if not json_data:
            return listings

        # Navigate to ads array - Milanuncios structure:
        # adListPagination.adList.ads
        ads = None
        try:
            if 'adListPagination' in json_data:
                ad_list = json_data['adListPagination'].get('adList', {})
                ads = ad_list.get('ads', [])
            elif 'ads' in json_data:
                ads = json_data['ads']
            elif 'pageProps' in json_data:
                # Nested in pageProps
                pp = json_data['pageProps']
                if 'adListPagination' in pp:
                    ads = pp['adListPagination'].get('adList', {}).get('ads', [])
                elif 'ads' in pp:
                    ads = pp['ads']
        except Exception as e:
            logger.warning(f"Error navigating JSON structure: {e}")

        if not ads:
            logger.warning(f"No ads found in JSON. Top keys: {list(json_data.keys())[:10]}")
            return listings

        logger.info(f"Found {len(ads)} total ads, filtering for particulares...")
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        for ad in ads:
            try:
                # Check if particular (not agency)
                # Milanuncios uses 'private' for particulares and 'professional' for agencies
                seller_type = str(ad.get('sellerType', '')).lower()
                is_particular = seller_type in ('private', 'particular', '')

                if not is_particular:
                    continue

                # Extract location - structure: location.city.name or location.province.name
                location_data = ad.get('location', {})
                ubicacion = (
                    location_data.get('city', {}).get('name', '') or
                    location_data.get('province', {}).get('name', '') or
                    zona_info.get('nombre', '')
                )

                # Extract images
                images = ad.get('images', [])
                fotos = [img.get('url', '') if isinstance(img, dict) else str(img) for img in images[:5]]

                # Extract listing data
                listing = {
                    'portal': 'milanuncios',
                    'external_id': str(ad.get('id', '')),
                    'titulo': ad.get('title', ''),
                    'descripcion': ad.get('description', ''),
                    'precio': self._parse_price(ad.get('price', {})),
                    'ubicacion': ubicacion,
                    'telefono': ad.get('phone', ''),
                    'url': f"https://www.milanuncios.com{ad.get('url', '')}",
                    'fotos': fotos,
                    'vendedor': ad.get('sellerName', '') or ad.get('userId', ''),
                    'zona_key': zona_key,
                    'zona_nombre': zona_info.get('nombre', ''),
                    'es_particular': True,
                    'tenant_id': self.tenant_id,
                    'raw_data': ad,
                }

                # Generate hash for deduplication
                hash_input = f"milanuncios:{listing['external_id']}"
                listing['hash'] = hashlib.md5(hash_input.encode()).hexdigest()

                listings.append(listing)

            except Exception as e:
                logger.debug(f"Error parsing ad: {e}")
                continue

        return listings

    def _parse_price(self, price_data) -> Optional[float]:
        """Parse price from various formats.

        Milanuncios structure: {'cashPrice': {'value': 550}}
        """
        if isinstance(price_data, (int, float)):
            return float(price_data)
        elif isinstance(price_data, dict):
            # Try cashPrice.value first (Milanuncios format)
            if 'cashPrice' in price_data:
                cash_price = price_data['cashPrice']
                if isinstance(cash_price, dict):
                    value = cash_price.get('value') or cash_price.get('amount')
                    if value:
                        return float(value)
            # Fallback to direct value/amount
            amount = price_data.get('amount') or price_data.get('value')
            if amount:
                return float(amount)
        elif isinstance(price_data, str):
            numbers = re.findall(r'[\d,.]+', price_data.replace('.', '').replace(',', '.'))
            if numbers:
                return float(numbers[0])
        return None

    def _save_to_postgres(self, listing: Dict) -> bool:
        """Save listing to PostgreSQL raw.raw_listings."""
        conn = self._connect_postgres()
        if not conn:
            return False

        try:
            cur = conn.cursor()

            # Prepare JSONB data
            jsonb_data = json.dumps({
                'titulo': listing.get('titulo', ''),
                'descripcion': listing.get('descripcion', ''),
                'precio': listing.get('precio'),
                'ubicacion': listing.get('ubicacion', ''),
                'telefono': listing.get('telefono', ''),
                'url': listing.get('url', ''),
                'fotos': listing.get('fotos', []),
                'vendedor': listing.get('vendedor', ''),
                'zona_key': listing.get('zona_key', ''),
                'zona_nombre': listing.get('zona_nombre', ''),
                'es_particular': listing.get('es_particular', True),
                'raw': listing.get('raw_data', {}),
            }, ensure_ascii=False)

            # Insert with conflict handling
            cur.execute("""
                INSERT INTO raw.raw_listings (
                    portal, external_id, data, hash, tenant_id, scraped_at
                ) VALUES (
                    %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (hash) DO UPDATE SET
                    data = EXCLUDED.data,
                    scraped_at = NOW()
                RETURNING id
            """, (
                listing['portal'],
                listing['external_id'],
                jsonb_data,
                listing['hash'],
                listing['tenant_id'],
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                logger.debug(f"Saved listing {listing['external_id']}")
                return True

        except Exception as e:
            logger.error(f"Failed to save listing: {e}")
            conn.rollback()

        return False

    def scrape(self) -> Dict[str, int]:
        """Run the scraper."""
        logger.info(f"Starting Milanuncios HTTP scraper")
        logger.info(f"Zones: {', '.join(self.zones)}")
        logger.info(f"Max pages per zone: {self.max_pages}")

        # Warmup
        self._warmup()

        all_listings = []

        for zona_key in self.zones:
            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {'nombre': zona_key})
            logger.info(f"Scraping zone: {zona_info.get('nombre', zona_key)}")

            for page_num in range(1, self.max_pages + 1):
                url = self._build_url(zona_key, page_num)
                logger.info(f"Page {page_num}: {url}")

                html = self._fetch_page(url)
                if not html:
                    self.stats['errors'] += 1
                    continue

                self.stats['pages_scraped'] += 1

                # Try to extract JSON data
                json_data = self._extract_json_from_html(html)
                if json_data:
                    listings = self._parse_listings(json_data, zona_key)
                    logger.info(f"Found {len(listings)} particular listings")
                    all_listings.extend(listings)
                else:
                    logger.warning("No JSON data found in page - possibly blocked")

                self._human_delay(2, 4)

            self._human_delay(3, 5)

        self.stats['listings_found'] = len(all_listings)

        # Save to PostgreSQL
        if self.use_postgres and all_listings:
            for listing in all_listings:
                if self._save_to_postgres(listing):
                    self.stats['listings_saved'] += 1

        self._close_postgres()

        logger.info(f"Complete. Stats: {self.stats}")
        return self.stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Milanuncios HTTP Scraper')
    parser.add_argument('--zones', type=str, default='salou,reus',
                        help='Comma-separated zone keys')
    parser.add_argument('--max-pages', type=int, default=2,
                        help='Max pages per zone')
    parser.add_argument('--tenant-id', type=int, default=1,
                        help='Tenant ID')
    parser.add_argument('--postgres', action='store_true', default=True,
                        help='Save to PostgreSQL')
    parser.add_argument('--mobile', action='store_true', default=True,
                        help='Use mobile user agent')

    args = parser.parse_args()

    zones = [z.strip() for z in args.zones.split(',')]

    print("=" * 60)
    print("MILANUNCIOS HTTP SCRAPER (curl_cffi)")
    print("=" * 60)
    print(f"curl_cffi available: {CURL_CFFI_AVAILABLE}")
    print(f"Zones: {', '.join(zones)}")
    print(f"Max pages: {args.max_pages}")
    print(f"Mobile UA: {args.mobile}")
    print("=" * 60)
    print()

    scraper = MilanunciosHTTPScraper(
        zones=zones,
        max_pages=args.max_pages,
        tenant_id=args.tenant_id,
        use_postgres=args.postgres,
        use_mobile=args.mobile,
    )

    stats = scraper.scrape()

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Pages scraped: {stats['pages_scraped']}")
    print(f"Listings found: {stats['listings_found']}")
    print(f"Listings saved: {stats['listings_saved']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 60)
    print()
    print(f"{stats['listings_saved']} leads saved")


if __name__ == '__main__':
    main()

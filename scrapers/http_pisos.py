"""
Pisos.com scraper using HTTP requests (no browser needed).

Pisos.com has NO anti-bot protection, making it ideal for simple HTTP scraping.
This is 10x faster and 100% more reliable than browser-based scraping.
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests
from bs4 import BeautifulSoup
import psycopg2

logger = logging.getLogger(__name__)

# Same zone configuration as botasaurus version
ZONAS_GEOGRAFICAS = {
    # Provinces
    'tarragona_provincia': {'nombre': 'Tarragona Provincia', 'url_path': 'pisos-tarragona'},
    'lleida_provincia': {'nombre': 'Lleida Provincia', 'url_path': 'pisos-lleida'},

    # Comarcas (composite zones)
    'tarragones': {'nombre': 'Tarragonès', 'composite': ['tarragona_capital', 'torredembarra', 'altafulla']},
    'baix_camp': {'nombre': 'Baix Camp', 'composite': ['reus', 'cambrils', 'salou', 'vila_seca']},
    'alt_camp': {'nombre': 'Alt Camp', 'composite': ['valls']},
    'conca_barbera': {'nombre': 'Conca de Barberà', 'composite': ['montblanc']},
    'baix_penedes': {'nombre': 'Baix Penedès', 'composite': ['vendrell', 'calafell']},
    'baix_ebre': {'nombre': 'Baix Ebre', 'composite': ['tortosa']},
    'montsia': {'nombre': 'Montsià', 'composite': ['amposta']},
    'costa_daurada': {'nombre': 'Costa Daurada', 'composite': ['salou', 'cambrils', 'tarragona_capital', 'torredembarra', 'calafell', 'vendrell']},
    'segria': {'nombre': 'Segrià', 'composite': ['lleida_capital']},

    # Cities
    'tarragona_capital': {'nombre': 'Tarragona Capital', 'url_path': 'pisos-tarragona_capital'},
    'lleida_capital': {'nombre': 'Lleida Capital', 'url_path': 'pisos-lleida_capital'},
    'salou': {'nombre': 'Salou', 'url_path': 'pisos-salou'},
    'cambrils': {'nombre': 'Cambrils', 'url_path': 'pisos-cambrils'},
    'reus': {'nombre': 'Reus', 'url_path': 'pisos-reus'},
    'calafell': {'nombre': 'Calafell', 'url_path': 'pisos-calafell'},
    'torredembarra': {'nombre': 'Torredembarra', 'url_path': 'pisos-torredembarra'},
    'vendrell': {'nombre': 'El Vendrell', 'url_path': 'pisos-el_vendrell'},
    'valls': {'nombre': 'Valls', 'url_path': 'pisos-valls'},
    'tortosa': {'nombre': 'Tortosa', 'url_path': 'pisos-tortosa'},
    'amposta': {'nombre': 'Amposta', 'url_path': 'pisos-amposta'},
    'altafulla': {'nombre': 'Altafulla', 'url_path': 'pisos-altafulla'},
    'vila_seca': {'nombre': 'Vila-seca', 'url_path': 'pisos-vila_seca'},
    'montblanc': {'nombre': 'Montblanc', 'url_path': 'pisos-montblanc'},
}


class HttpPisosScraper:
    """
    HTTP-based Pisos.com scraper.

    No browser needed - pisos.com has no anti-bot protection.
    Uses requests + BeautifulSoup for fast, reliable scraping.
    """

    PORTAL_NAME = 'pisos.com'
    BASE_URL = 'https://www.pisos.com'

    # Standard browser headers to avoid basic blocking
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        max_pages_per_zone: int = 2,
        delay_between_requests: float = 1.0,
    ):
        self.tenant_id = tenant_id
        self.zones = zones or ['salou']
        self.max_pages_per_zone = max_pages_per_zone
        self.delay = delay_between_requests
        self.postgres_conn = None

        if postgres_config:
            self._init_postgres(postgres_config)

        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        self.stats = {
            'total_listings': 0,
            'filtered_out': 0,
            'saved': 0,
            'errors': 0,
            'pages_scraped': 0,
        }

        logger.info(f"HttpPisosScraper initialized for zones: {self.zones}")

    def _init_postgres(self, config: Dict[str, str]):
        """Initialize PostgreSQL connection."""
        try:
            conn_params = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 5432),
                'database': config.get('database', 'casa_teva_db'),
                'user': config.get('user', 'casa_teva'),
                'password': config.get('password', ''),
            }
            if config.get('sslmode'):
                conn_params['sslmode'] = config.get('sslmode')

            self.postgres_conn = psycopg2.connect(**conn_params)
            logger.info(f"PostgreSQL connected: {config.get('host')}")
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            raise

    def _generate_lead_id(self, anuncio_id: str) -> int:
        """Generate unique lead ID as truncated hash."""
        unique_string = f"{self.tenant_id}:{self.PORTAL_NAME}:{anuncio_id}"
        hash_hex = hashlib.md5(unique_string.encode()).hexdigest()
        return int(hash_hex, 16) % 2147483647

    def normalize_phone(self, phone_str: str) -> Optional[str]:
        """Normalize Spanish phone number to 9 digits."""
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

        if len(digits) == 9:
            return digits
        return None

    def extract_phones_from_html(self, html: str) -> List[str]:
        """Extract Spanish phone numbers from HTML."""
        clean_html = html.replace(' ', '').replace('.', '').replace('-', '')
        phones = set(re.findall(r'[679]\d{8}', clean_html))
        mobiles = [p for p in phones if p.startswith(('6', '7'))]
        return mobiles

    def build_url(self, zona_key: str, page: int = 1) -> str:
        """Build search URL for Pisos.com."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona or 'composite' in zona:
            raise ValueError(f"Zone not found or is composite: {zona_key}")

        url = f"{self.BASE_URL}/venta/{zona['url_path']}/"
        if page > 1:
            url += f'{page}/'
        return url

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with retry logic."""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                time.sleep(2 ** attempt)

        logger.error(f"Failed to fetch {url} after 3 attempts")
        self.stats['errors'] += 1
        return None

    def _parse_listing_page(self, html: str, zona_name: str) -> List[Dict[str, Any]]:
        """Parse listing page and extract basic listing info."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Find all listing links - format: /comprar/piso-zona-ID_price/
        links = soup.find_all('a', href=re.compile(r'/comprar/piso'))

        seen_ids = set()
        for link in links:
            href = link.get('href', '')

            # Extract ID from URL
            id_match = re.search(r'-(\d{10,})(?:_\d+)?/?$', href)
            if not id_match:
                continue

            anuncio_id = id_match.group(1)
            if anuncio_id in seen_ids:
                continue
            seen_ids.add(anuncio_id)

            detail_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href

            listings.append({
                'anuncio_id': anuncio_id,
                'detail_url': detail_url,
                'url_anuncio': detail_url,
                'portal': self.PORTAL_NAME,
                'zona_busqueda': zona_name,
                'zona_geografica': zona_name,
            })

        logger.info(f"Found {len(listings)} listings on page")
        return listings

    def _enrich_listing(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch detail page and extract all information."""
        url = listing['detail_url']

        html = self._fetch_page(url)
        if not html:
            return listing

        soup = BeautifulSoup(html, 'html.parser')

        # Extract title
        h1 = soup.find('h1')
        if h1:
            listing['titulo'] = h1.get_text(strip=True)

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

        # Extract features (metros, habitaciones)
        metros_match = re.search(r'(\d+)\s*m[²2]', html)
        if metros_match:
            listing['metros'] = int(metros_match.group(1))

        habs_match = re.search(r'(\d+)\s*hab', html, re.IGNORECASE)
        if habs_match:
            listing['habitaciones'] = int(habs_match.group(1))

        # Extract description
        desc_div = soup.find('div', class_=re.compile(r'description|comment|detalle', re.I))
        if desc_div:
            listing['descripcion'] = desc_div.get_text(strip=True)[:2000]
        else:
            # Find long text blocks
            for p in soup.find_all(['p', 'div']):
                text = p.get_text(strip=True)
                if len(text) > 100 and 'cookie' not in text.lower() and 'javascript' not in text.lower():
                    listing['descripcion'] = text[:2000]
                    break

        # Extract photos
        photos = []
        for img in soup.find_all('img', src=re.compile(r'pisos\.com.*\.(jpg|jpeg|png|webp)', re.I)):
            src = img.get('src') or img.get('data-src')
            if src and 'logo' not in src.lower() and 'icon' not in src.lower():
                if src.startswith('//'):
                    src = 'https:' + src
                photos.append(src)
        listing['fotos'] = list(dict.fromkeys(photos))[:10]

        # Check if particular or agency
        has_agency_link = bool(re.search(r'href="[^"]*\/inmobiliaria-', html, re.IGNORECASE))
        has_agency_badge = bool(re.search(r'Inmobiliaria\s+recomendada', html, re.IGNORECASE))

        if has_agency_link or has_agency_badge:
            listing['vendedor'] = 'Inmobiliaria'
            listing['es_particular'] = False
        else:
            listing['vendedor'] = 'Particular'
            listing['es_particular'] = True

        return listing

    def save_to_postgres(self, listing: Dict[str, Any]) -> bool:
        """Save listing to PostgreSQL raw.raw_listings table."""
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
                'direccion': listing.get('direccion', ''),
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
                'vendedor': listing.get('vendedor', ''),
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
            data_lake_path = f"http/{self.PORTAL_NAME}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

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

    def scrape_zone(self, zona_key: str, parent_zone_name: str = None) -> List[Dict[str, Any]]:
        """Scrape a single zone."""
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Handle composite zones
        if 'composite' in zona_info:
            logger.info(f"Composite zone {zona_key}: {zona_info['composite']}")
            all_listings = []
            for city_key in zona_info['composite']:
                if city_key in ZONAS_GEOGRAFICAS and 'url_path' in ZONAS_GEOGRAFICAS[city_key]:
                    city_listings = self.scrape_zone(city_key, zona_info['nombre'])
                    all_listings.extend(city_listings)
                    time.sleep(self.delay)
            return all_listings

        zone_name = parent_zone_name or zona_info.get('nombre', zona_key)
        all_listings = []

        for page in range(1, self.max_pages_per_zone + 1):
            url = self.build_url(zona_key, page)
            logger.info(f"Scraping {zona_key} page {page}: {url}")

            html = self._fetch_page(url)
            if not html:
                break

            self.stats['pages_scraped'] += 1

            # Check for blocking or empty results
            if len(html) < 10000:
                logger.warning(f"Page too small ({len(html)} bytes), possible issue")
                break

            listings = self._parse_listing_page(html, zone_name)
            if not listings:
                logger.info(f"No more listings on page {page}")
                break

            # Enrich each listing with detail page data
            for listing in listings[:10]:  # Limit per page to avoid overload
                enriched = self._enrich_listing(listing)
                all_listings.append(enriched)
                self.stats['total_listings'] += 1
                time.sleep(self.delay)

            time.sleep(self.delay * 2)  # Extra delay between pages

        logger.info(f"Zone {zona_key}: {len(all_listings)} listings")
        return all_listings

    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape all configured zones."""
        all_listings = []

        for zona_key in self.zones:
            logger.info(f"Scraping zone: {zona_key}")
            listings = self.scrape_zone(zona_key)
            all_listings.extend(listings)

        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            if self.save_to_postgres(listing):
                self.stats['saved'] += 1

        logger.info(f"Stats: {self.stats}")
        return self.stats

    def close(self):
        """Close connections."""
        if self.postgres_conn:
            self.postgres_conn.close()
            logger.info("PostgreSQL connection closed")
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def run_http_pisos(
    zones: List[str] = None,
    postgres_config: Optional[Dict[str, str]] = None,
    max_pages: int = 2,
    tenant_id: int = 1,
) -> Dict[str, int]:
    """
    Run the HTTP-based Pisos.com scraper.

    Args:
        zones: List of zones to scrape
        postgres_config: PostgreSQL connection config
        max_pages: Max pages per zone
        tenant_id: Tenant ID

    Returns:
        Stats dictionary
    """
    with HttpPisosScraper(
        tenant_id=tenant_id,
        zones=zones or ['salou'],
        postgres_config=postgres_config,
        max_pages_per_zone=max_pages,
    ) as scraper:
        return scraper.scrape_and_save()


if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")

    with HttpPisosScraper(zones=zones, max_pages_per_zone=1) as scraper:
        listings = scraper.scrape()

        print(f"\nFound {len(listings)} listings:")
        for l in listings[:5]:
            print(f"  - {l.get('titulo', 'N/A')[:50]}...")
            print(f"    Price: {l.get('precio')}€ | {l.get('metros')}m² | {l.get('habitaciones')} hab")
            print(f"    Phone: {l.get('telefono')} | {l.get('vendedor')}")
            print()

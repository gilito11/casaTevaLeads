"""
Base scraper using Botasaurus for anti-bot bypass.

Botasaurus is an open-source library that handles:
- Browser fingerprinting
- Anti-bot detection bypass
- Automatic retries
- Stealth mode

This replaces the need for paid services like ScrapingBee for most portals.
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

import psycopg2
from botasaurus.browser import browser, Driver

from scrapers.utils.particular_filter import debe_scrapear, es_profesional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BotasaurusBaseScraper:
    """
    Base class for all Botasaurus-based scrapers.

    Provides common functionality:
    - PostgreSQL persistence
    - Phone normalization
    - Particular/agency filtering
    - Lead ID generation
    """

    def __init__(
        self,
        tenant_id: int = 1,
        postgres_config: Optional[Dict[str, str]] = None,
        headless: bool = True
    ):
        """
        Initialize the base scraper.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            postgres_config: PostgreSQL connection config
            headless: Run browser in headless mode
        """
        self.tenant_id = tenant_id
        self.headless = headless
        self.postgres_conn = None

        if postgres_config:
            self.postgres_conn = self._init_postgres(postgres_config)

        self.stats = {
            'total_listings': 0,
            'filtered_out': 0,
            'saved': 0,
            'errors': 0,
            'pages_scraped': 0,
        }

        logger.info(f"BotasaurusBaseScraper initialized for tenant_id={tenant_id}")

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

            conn = psycopg2.connect(**conn_params)
            logger.info(f"PostgreSQL connected: {config.get('host')}")
            return conn
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            raise

    def _generate_lead_id(self, portal: str, anuncio_id: str) -> int:
        """Generate unique lead ID as truncated hash."""
        unique_string = f"{self.tenant_id}:{portal}:{anuncio_id}"
        hash_hex = hashlib.md5(unique_string.encode()).hexdigest()
        return int(hash_hex, 16) % 2147483647

    def normalize_phone(self, phone_str: str) -> Optional[str]:
        """Normalize Spanish phone number to 9 digits."""
        if not phone_str:
            return None

        # Remove spaces, dashes, parentheses
        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone_str)

        # Remove country code
        if cleaned.startswith('+34'):
            cleaned = cleaned[3:]
        elif cleaned.startswith('0034'):
            cleaned = cleaned[4:]
        elif cleaned.startswith('34') and len(cleaned) == 11:
            cleaned = cleaned[2:]

        # Keep only digits
        digits = re.sub(r'\D', '', cleaned)

        # Validate 9 digits
        if len(digits) == 9:
            return digits
        return None

    def extract_phones_from_html(self, html: str) -> List[str]:
        """Extract Spanish phone numbers from HTML."""
        # Remove spaces and dots for matching
        clean_html = html.replace(' ', '').replace('.', '').replace('-', '')

        # Find all 9-digit numbers starting with 6, 7, or 9
        phones = set(re.findall(r'[679]\d{8}', clean_html))

        # Filter to likely mobile numbers (6xx, 7xx)
        mobiles = [p for p in phones if p.startswith(('6', '7'))]

        return mobiles

    def should_scrape(self, listing_data: Dict[str, Any]) -> bool:
        """Check if listing should be scraped (particular filter)."""
        return debe_scrapear(listing_data)

    def is_agency(self, listing_data: Dict[str, Any]) -> bool:
        """Check if listing is from an agency."""
        return es_profesional(listing_data)

    def save_to_postgres(
        self,
        listing_data: Dict[str, Any],
        portal: str
    ) -> bool:
        """Save listing to PostgreSQL raw.raw_listings table."""
        if not self.postgres_conn:
            logger.warning("PostgreSQL not configured")
            return False

        try:
            cursor = self.postgres_conn.cursor()

            anuncio_id = str(listing_data.get('anuncio_id', ''))
            if not anuncio_id:
                return False

            # Prepare raw_data as JSONB (include all listing data)
            raw_data = {
                'anuncio_id': anuncio_id,
                'titulo': listing_data.get('titulo', ''),
                'telefono': listing_data.get('telefono', ''),
                'telefono_norm': listing_data.get('telefono_norm', ''),
                'email': listing_data.get('email'),
                'nombre': listing_data.get('vendedor') or listing_data.get('nombre', ''),
                'direccion': listing_data.get('direccion') or listing_data.get('ubicacion', ''),
                'zona': listing_data.get('zona_geografica') or listing_data.get('zona_busqueda', ''),
                'zona_busqueda': listing_data.get('zona_busqueda', ''),
                'zona_geografica': listing_data.get('zona_geografica', ''),
                'codigo_postal': listing_data.get('codigo_postal'),
                'tipo_inmueble': listing_data.get('tipo_inmueble', 'piso'),
                'precio': listing_data.get('precio'),
                'habitaciones': listing_data.get('habitaciones'),
                'metros': listing_data.get('metros'),
                'descripcion': listing_data.get('descripcion', ''),
                'fotos': listing_data.get('fotos', []),
                'url': listing_data.get('url_anuncio') or listing_data.get('detail_url', ''),
                'es_particular': listing_data.get('es_particular', True),
                'vendedor': listing_data.get('vendedor', ''),
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
            data_lake_path = f"botasaurus/{portal}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

            cursor.execute(sql, (
                self.tenant_id,
                portal,
                data_lake_path,
                json.dumps(raw_data),
                now,
            ))

            rows_affected = cursor.rowcount
            self.postgres_conn.commit()
            cursor.close()

            if rows_affected > 0:
                logger.info(f"Lead saved: {portal} - {anuncio_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error saving to PostgreSQL: {e}")
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def close(self):
        """Close connections."""
        if self.postgres_conn:
            self.postgres_conn.close()
            logger.info("PostgreSQL connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Chrome flags optimized for Azure Container Apps
# IMPORTANT: Do NOT use --single-process or --no-zygote as they cause WebSocket disconnection
CONTAINER_CHROME_ARGS = [
    '--no-sandbox',                    # Required for containers (no root sandboxing)
    '--disable-setuid-sandbox',        # Disable setuid sandbox
    '--disable-dev-shm-usage',         # Use /tmp instead of /dev/shm
    '--disable-gpu',                   # No GPU in containers
    '--disable-software-rasterizer',   # Disable software GPU
    '--disable-extensions',            # No extensions needed
    '--disable-background-networking', # Reduce network activity
    '--disable-sync',                  # No sync needed
    '--disable-translate',             # No translation needed
    '--disable-default-apps',          # No default apps
    '--disable-hang-monitor',          # Disable hang monitor
    '--disable-prompt-on-repost',      # Disable repost prompts
    '--disable-client-side-phishing-detection',  # Disable phishing detection
    '--disable-component-update',      # Disable component updates
    '--disable-domain-reliability',    # Disable domain reliability
    '--disable-features=TranslateUI,BlinkGenPropertyTrees,VizDisplayCompositor',
    '--mute-audio',                    # No audio
    '--no-first-run',                  # Skip first run
    '--password-store=basic',          # Simple password store
    '--use-mock-keychain',             # Mock keychain for headless
    '--enable-features=NetworkService,NetworkServiceInProcess',
    '--window-size=1920,1080',         # Set window size
    '--remote-debugging-port=0',       # Random debugging port
]


# Reusable browser decorator with optimal settings for containers
def create_browser_scraper(headless: bool = True):
    """Create a browser decorator with optimal anti-bot settings.

    Includes Chrome flags required for running in containers (Docker, Azure Container Apps).
    IMPORTANT: Removed --single-process and --no-zygote which cause WebSocket issues.
    """
    return browser(
        headless=headless,
        block_images=True,
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        add_arguments=CONTAINER_CHROME_ARGS,
    )

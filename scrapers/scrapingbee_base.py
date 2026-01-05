"""
ScrapingBee base client for portals with strong anti-bot protection.

This module provides a unified interface for scraping using ScrapingBee API,
supporting both Milanuncios and Idealista portals.

Cost structure (Stealth proxy):
- 75 credits per request
- Plan 50€/month = 250,000 credits = ~3,333 requests/month
"""

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

import requests
import psycopg2

from scrapers.error_handling import (
    RetryConfig,
    retry_with_backoff,
    send_alert,
    AlertSeverity,
    validate_scraping_results,
)

logger = logging.getLogger(__name__)

# Retry config for ScrapingBee API calls
SCRAPINGBEE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    retryable_exceptions=(
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ),
)


def fix_encoding(text: str) -> str:
    """
    Fix common encoding issues in scraped text.
    Handles cases where UTF-8 text was incorrectly decoded as Latin-1.
    """
    if not text:
        return text

    # Try to fix UTF-8 double encoding (most common issue)
    try:
        # If text contains high bytes, try to fix double-encoding
        if any(ord(c) > 127 for c in text):
            # Try to decode as Latin-1 and re-encode as UTF-8
            fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            if fixed and len(fixed) >= len(text) * 0.8:  # Sanity check
                return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    # Remove null bytes
    text = text.replace('\x00', '')

    return text


def get_scrapingbee_api_key() -> str:
    """Get ScrapingBee API key from environment."""
    api_key = os.environ.get('SCRAPINGBEE_API_KEY', '')
    if not api_key:
        raise ValueError(
            "SCRAPINGBEE_API_KEY not set. "
            "Set it in environment or .env file."
        )
    return api_key


def get_postgres_config() -> Dict[str, str]:
    """
    Get PostgreSQL config from environment.
    Works for both local Docker and Azure environments.
    """
    # Try DATABASE_URL first (Azure format)
    database_url = os.environ.get('DATABASE_URL', '')

    if database_url:
        # Parse DATABASE_URL (format: postgresql://user:pass@host:port/db?sslmode=require)
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'inmoleadsdb',
            'user': parsed.username or 'inmoleadsadmin',
            'password': parsed.password or '',
            'sslmode': 'require' if 'azure' in (parsed.hostname or '') else 'prefer',
        }

    # Fall back to individual env vars (local Docker)
    return {
        'host': os.environ.get('POSTGRES_HOST', 'postgres'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
        'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer'),
    }


class ScrapingBeeClient:
    """
    Base client for ScrapingBee API.

    Provides common functionality for all portals:
    - API request handling with stealth proxy
    - PostgreSQL persistence (same schema as Botasaurus scrapers)
    - Credit tracking
    - Error handling and retries
    """

    SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"

    def __init__(
        self,
        portal_name: str,
        tenant_id: int = 1,
        use_stealth: bool = True,
        postgres_config: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize ScrapingBee client.

        Args:
            portal_name: Name of the portal (milanuncios, idealista)
            tenant_id: Tenant ID for multi-tenancy
            use_stealth: Use stealth proxy (75 credits) vs premium (25 credits)
            postgres_config: PostgreSQL connection config (auto-detected if None)
        """
        self.portal_name = portal_name
        self.tenant_id = tenant_id
        self.use_stealth = use_stealth
        self.api_key = get_scrapingbee_api_key()

        # Initialize PostgreSQL connection
        self.postgres_config = postgres_config or get_postgres_config()
        self.postgres_conn = self._init_postgres()

        # Stats tracking
        self.stats = {
            'requests': 0,
            'credits_used': 0,
            'credits_saved': 0,  # Credits saved by skipping duplicates/agencies
            'pages_scraped': 0,
            'listings_found': 0,
            'listings_saved': 0,
            'listings_skipped': 0,  # Skipped due to already in DB
            'errors': 0,
        }

        logger.info(
            f"ScrapingBeeClient initialized for {portal_name} "
            f"(tenant_id={tenant_id}, stealth={use_stealth})"
        )

    def _init_postgres(self) -> Optional[psycopg2.extensions.connection]:
        """Initialize PostgreSQL connection."""
        try:
            conn_params = {
                'host': self.postgres_config.get('host', 'localhost'),
                'port': self.postgres_config.get('port', 5432),
                'database': self.postgres_config.get('database', 'casa_teva_db'),
                'user': self.postgres_config.get('user', 'casa_teva'),
                'password': self.postgres_config.get('password', ''),
            }
            if self.postgres_config.get('sslmode'):
                conn_params['sslmode'] = self.postgres_config.get('sslmode')

            conn = psycopg2.connect(**conn_params)
            logger.info(f"PostgreSQL connected: {conn_params['host']}")
            return conn
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            raise

    def fetch_page(
        self,
        url: str,
        wait_for: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        js_scenario: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Fetch a page using ScrapingBee API with retry logic.

        Args:
            url: URL to fetch
            wait_for: CSS selector to wait for (optional)
            custom_headers: Custom headers to send (optional)
            js_scenario: JavaScript scenario with instructions (optional)

        Returns:
            HTML content or None if failed
        """
        return self._fetch_page_with_retry(url, wait_for, custom_headers, js_scenario)

    def _fetch_page_with_retry(
        self,
        url: str,
        wait_for: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        js_scenario: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> Optional[str]:
        """Internal method with retry logic."""
        params = {
            'api_key': self.api_key,
            'url': url,
            'render_js': 'true',
            'premium_proxy': 'true',
            'country_code': 'es',
        }

        if self.use_stealth:
            params['stealth_proxy'] = 'true'

        if wait_for:
            params['wait_for'] = wait_for

        if js_scenario:
            params['js_scenario'] = json.dumps(js_scenario)

        if custom_headers:
            for key, value in custom_headers.items():
                params[f'Spb-{key}'] = value

        try:
            logger.info(f"Fetching (attempt {attempt}/{max_attempts}): {url[:80]}...")
            response = requests.get(
                self.SCRAPINGBEE_ENDPOINT,
                params=params,
                timeout=60,
            )

            # Track credits used
            credits = 75 if self.use_stealth else 25
            self.stats['requests'] += 1
            self.stats['credits_used'] += credits

            if response.status_code == 200:
                try:
                    html = response.content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        html = response.content.decode('latin-1')
                    except:
                        html = response.content.decode('utf-8', errors='replace')
                logger.info(f"Success: {len(html)} chars")
                return html

            # Handle retryable HTTP errors (429, 500, 502, 503, 504)
            elif response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    f"Retryable error {response.status_code} on attempt {attempt}"
                )
                if attempt < max_attempts:
                    delay = min(2.0 * (2 ** (attempt - 1)), 30.0)  # Exponential backoff
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    return self._fetch_page_with_retry(
                        url, wait_for, custom_headers, js_scenario,
                        attempt + 1, max_attempts
                    )
                else:
                    logger.error(f"Max retries reached for {url[:50]}")
                    self.stats['errors'] += 1
                    return None
            else:
                logger.error(
                    f"ScrapingBee error: {response.status_code} - "
                    f"{response.text[:200]}"
                )
                self.stats['errors'] += 1
                return None

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Network error on attempt {attempt}: {e}")
            if attempt < max_attempts:
                delay = min(2.0 * (2 ** (attempt - 1)), 30.0)
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
                return self._fetch_page_with_retry(
                    url, wait_for, custom_headers, js_scenario,
                    attempt + 1, max_attempts
                )
            else:
                logger.error(f"Max retries reached due to network error: {e}")
                self.stats['errors'] += 1
                return None

        except Exception as e:
            logger.error(f"Request error: {e}")
            self.stats['errors'] += 1
            return None

    def _generate_lead_id(self, anuncio_id: str) -> int:
        """Generate unique lead ID as truncated hash."""
        unique_string = f"{self.tenant_id}:{self.portal_name}:{anuncio_id}"
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

    def extract_phone_from_description(self, description: str) -> Optional[str]:
        """
        Extract phone number from listing description.

        Many sellers put their phone in the description to avoid portal fees.
        This is the most reliable way to get phones without login.
        """
        if not description:
            return None

        # Clean the description - remove common separators
        clean_desc = description.replace(' ', '').replace('.', '').replace('-', '').replace('/', '')

        # Find all 9-digit Spanish phone numbers (6xx, 7xx, 8xx, 9xx)
        phones = re.findall(r'[6789]\d{8}', clean_desc)

        # Filter out fake/invalid numbers
        BLACKLIST = {
            '666666666', '777777777', '888888888', '999999999',
            '600000000', '700000000', '800000000', '900000000',
            '123456789', '987654321',
        }

        for phone in phones:
            # Skip blacklisted
            if phone in BLACKLIST:
                continue
            # Skip numbers with too many repeated digits (e.g., 666777888)
            if re.match(r'(\d)\1{5,}', phone):
                continue
            # Valid phone found
            return phone

        return None

    def url_exists_in_db(self, url: str) -> bool:
        """Check if URL already exists in raw_listings."""
        if not self.postgres_conn:
            return False
        try:
            cursor = self.postgres_conn.cursor()
            cursor.execute(
                "SELECT 1 FROM raw.raw_listings WHERE raw_data->>'url' = %s LIMIT 1",
                (url,)
            )
            exists = cursor.fetchone() is not None
            cursor.close()
            return exists
        except Exception as e:
            logger.warning(f"Error checking URL existence: {e}")
            return False

    def save_to_postgres(self, listing_data: Dict[str, Any]) -> bool:
        """
        Save listing to PostgreSQL raw.raw_listings table.
        Uses the same schema as Botasaurus scrapers for uniformity.
        """
        if not self.postgres_conn:
            logger.warning("PostgreSQL not configured")
            return False

        try:
            cursor = self.postgres_conn.cursor()

            anuncio_id = str(listing_data.get('anuncio_id', ''))
            if not anuncio_id:
                return False

            # Prepare raw_data as JSONB (same structure as Botasaurus scrapers)
            # Apply encoding fix to text fields
            raw_data = {
                'anuncio_id': anuncio_id,
                'titulo': fix_encoding(listing_data.get('titulo', '')),
                'telefono': listing_data.get('telefono', ''),
                'telefono_norm': listing_data.get('telefono_norm', ''),
                'email': listing_data.get('email'),
                'nombre': fix_encoding(listing_data.get('vendedor') or listing_data.get('nombre', '')),
                'direccion': fix_encoding(listing_data.get('direccion') or listing_data.get('ubicacion', '')),
                'zona': fix_encoding(listing_data.get('zona_geografica') or listing_data.get('zona_busqueda', '')),
                'zona_busqueda': fix_encoding(listing_data.get('zona_busqueda', '')),
                'zona_geografica': fix_encoding(listing_data.get('zona_geografica', '')),
                'codigo_postal': listing_data.get('codigo_postal'),
                'tipo_inmueble': listing_data.get('tipo_inmueble', 'piso'),
                'precio': listing_data.get('precio'),
                'habitaciones': listing_data.get('habitaciones'),
                'metros': listing_data.get('metros'),
                'banos': listing_data.get('banos'),
                'descripcion': fix_encoding(listing_data.get('descripcion', '')),
                'fotos': listing_data.get('fotos', []),
                'url': listing_data.get('url_anuncio') or listing_data.get('detail_url', ''),
                'es_particular': listing_data.get('es_particular', True),
                'vendedor': fix_encoding(listing_data.get('vendedor', '')),
                # ScrapingBee specific metadata
                'scraper_type': 'scrapingbee',
                'stealth_mode': self.use_stealth,
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
            data_lake_path = f"scrapingbee/{self.portal_name}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

            cursor.execute(sql, (
                self.tenant_id,
                self.portal_name,
                data_lake_path,
                json.dumps(raw_data, ensure_ascii=False),
                now,
            ))

            rows_affected = cursor.rowcount
            self.postgres_conn.commit()
            cursor.close()

            if rows_affected > 0:
                self.stats['listings_saved'] += 1
                logger.info(f"Lead saved: {self.portal_name} - {anuncio_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error saving to PostgreSQL: {e}")
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get scraping statistics."""
        credits_used = self.stats['credits_used']
        credits_saved = self.stats['credits_saved']
        return {
            **self.stats,
            'portal': self.portal_name,
            'tenant_id': self.tenant_id,
            'cost_estimate_eur': round(credits_used / 250000 * 50, 2),
            'savings_estimate_eur': round(credits_saved / 250000 * 50, 2),
            'efficiency_pct': round(credits_saved / (credits_used + credits_saved) * 100, 1) if (credits_used + credits_saved) > 0 else 0,
        }

    def close(self):
        """Close connections."""
        if self.postgres_conn:
            self.postgres_conn.close()
            logger.info("PostgreSQL connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

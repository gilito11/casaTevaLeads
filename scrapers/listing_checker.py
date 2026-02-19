"""
Listing availability checker.

Verifies if listings in the database are still active on their portals.
Uses simple HTTP requests — only works reliably for habitaclia and fotocasa.
Milanuncios/idealista have anti-bot (GeeTest/DataDome) so HTTP checks may fail.
"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import psycopg2

logger = logging.getLogger(__name__)

# Patterns indicating a listing has been removed
REMOVED_PATTERNS = {
    'habitaclia': [
        r'este anuncio ya no existe',
        r'anuncio no disponible',
        r'el anuncio ha sido eliminado',
        r'página no encontrada',
    ],
    'fotocasa': [
        r'este anuncio ya no está disponible',
        r'anuncio no disponible',
        r'el inmueble que buscas ya no está',
        r'página no encontrada',
    ],
    'milanuncios': [
        r'este anuncio ya no está disponible',
        r'anuncio eliminado',
        r'el anuncio ha sido retirado',
        r'no hemos encontrado el anuncio',
    ],
    'idealista': [
        r'este inmueble ya no está disponible',
        r'anuncio no disponible',
        r'el anuncio ha sido eliminado',
        r'página no encontrada',
    ],
}

# CRM states to exclude from checking — these are already managed by the user
EXCLUDED_ESTADOS = (
    'YA_VENDIDO', 'CLIENTE', 'NO_CONTACTAR', 'INTERESADO', 'EN_PROCESO',
)

# Portals safe to check via simple HTTP (no anti-bot)
SAFE_PORTALS = ('habitaclia', 'fotocasa')

# User agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}


def get_postgres_config() -> Dict[str, str]:
    """Get PostgreSQL config from environment."""
    database_url = os.environ.get('DATABASE_URL', '')

    if database_url:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'inmoleadsdb',
            'user': parsed.username or 'inmoleadsadmin',
            'password': parsed.password or '',
            'sslmode': 'require' if parsed.hostname and parsed.hostname != 'localhost' else 'prefer',
        }

    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
        'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer'),
    }


def send_telegram(message: str):
    """Send a Telegram notification."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


class ListingChecker:
    """
    Checks if listings are still available on their source portals.
    Uses simple HTTP GET requests to verify URL status.
    Only checks habitaclia/fotocasa by default (milanuncios/idealista have anti-bot).
    """

    REQUEST_DELAY = 2.0  # seconds between requests
    REQUEST_TIMEOUT = 15  # seconds

    def __init__(self, postgres_config: Optional[Dict[str, str]] = None):
        self.postgres_config = postgres_config or get_postgres_config()
        self.conn = self._init_postgres()
        self.stats = {
            'checked': 0,
            'active': 0,
            'removed': 0,
            'errors': 0,
        }
        self._last_request_time = 0

    def _init_postgres(self):
        """Initialize PostgreSQL connection."""
        try:
            conn = psycopg2.connect(**self.postgres_config)
            logger.info(f"Connected to PostgreSQL: {self.postgres_config['host']}")
            return conn
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            raise

    def _enforce_rate_limit(self):
        """Rate limit requests to avoid being blocked."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _detect_portal(self, url: str) -> Optional[str]:
        """Detect portal from URL."""
        if not url:
            return None
        url_lower = url.lower()
        for portal in REMOVED_PATTERNS.keys():
            if portal in url_lower:
                return portal
        return None

    def _is_redirect_to_search(self, original_url: str, final_url: str, portal: Optional[str]) -> bool:
        """
        Detect if the request was redirected to a search results page.
        This happens when a listing is removed — the portal redirects to
        a generic search instead of showing a 404.
        """
        if original_url == final_url:
            return False

        original_parsed = urlparse(original_url.lower())
        final_parsed = urlparse(final_url.lower())

        # Different domain = definitely a redirect (shouldn't happen normally)
        if original_parsed.hostname != final_parsed.hostname:
            return True

        if portal == 'habitaclia':
            # Habitaclia: specific listing URLs contain '-i{ID}.htm'
            # If the final URL doesn't contain the listing ID, it's a redirect
            id_match = re.search(r'-i(\d{9,})\.htm', original_url)
            if id_match and id_match.group(1) not in final_url:
                return True
            # Redirect to search: /comprar-* without specific listing ID
            if '/comprar-' in final_parsed.path and '-i' not in final_parsed.path:
                return True

        elif portal == 'fotocasa':
            # Fotocasa: listing URLs contain /d at the end with a numeric ID
            id_match = re.search(r'/(\d{7,})/d', original_url)
            if id_match and id_match.group(1) not in final_url:
                return True

        return False

    def check_url(self, url: str, portal: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if a listing URL is still active.

        Returns:
            Tuple of (is_active, reason)
        """
        if not url:
            return False, 'empty_url'

        portal = portal or self._detect_portal(url)
        self._enforce_rate_limit()

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=self.REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            # HTTP 404 = definitely removed
            if response.status_code == 404:
                return False, 'http_404'

            # HTTP 410 Gone = explicitly removed
            if response.status_code == 410:
                return False, 'http_410'

            # HTTP 403 = anti-bot blocked, can't determine status
            if response.status_code == 403:
                self.stats['errors'] += 1
                return True, 'blocked_403'

            final_url = response.url

            # Check for redirect to homepage
            parsed = urlparse(final_url.lower())
            if parsed.path in ('/', '', '/es/', '/ca/'):
                return False, 'redirected_to_home'

            # Check for redirect to search results page (key improvement)
            if self._is_redirect_to_search(url, final_url, portal):
                return False, 'redirected_to_search'

            # Check HTML content for removal patterns
            if response.status_code == 200 and portal and portal in REMOVED_PATTERNS:
                html_lower = response.text.lower()
                for pattern in REMOVED_PATTERNS[portal]:
                    if re.search(pattern, html_lower):
                        return False, f'content_match:{pattern[:30]}'

            # If we got here, assume active
            return True, 'active'

        except requests.exceptions.Timeout:
            return True, 'timeout'  # Assume active on timeout
        except requests.exceptions.ConnectionError:
            return True, 'connection_error'  # Assume active on connection error
        except Exception as e:
            logger.warning(f"Error checking {url[:50]}: {e}")
            return True, f'error:{str(e)[:30]}'

    def get_leads_to_check(
        self,
        limit: int = 100,
        portal: Optional[str] = None,
        safe_only: bool = True,
    ) -> List[Dict]:
        """
        Get leads from database that need checking.
        Excludes leads already in active CRM states (INTERESADO, CLIENTE, etc).
        Prioritizes older leads.
        """
        cursor = self.conn.cursor()

        query = """
            SELECT
                d.lead_id,
                d.listing_url,
                d.source_portal,
                d.fecha_primera_captura
            FROM public_marts.dim_leads d
            LEFT JOIN leads_lead_estado e ON d.lead_id = e.lead_id
            WHERE d.listing_url IS NOT NULL
              AND d.listing_url != ''
              AND (e.estado IS NULL OR e.estado NOT IN %s)
        """
        params: list = [EXCLUDED_ESTADOS]

        if portal:
            query += " AND d.source_portal = %s"
            params.append(portal)
        elif safe_only:
            query += " AND d.source_portal IN %s"
            params.append(SAFE_PORTALS)

        query += " ORDER BY d.fecha_primera_captura ASC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)

        leads = []
        for row in cursor.fetchall():
            leads.append({
                'lead_id': row[0],
                'url': row[1],
                'portal': row[2],
                'scraped_at': row[3],
            })

        cursor.close()
        return leads

    def mark_as_removed(self, lead_id: str, reason: str) -> bool:
        """Mark a lead as YA_VENDIDO in the database."""
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT tenant_id, telefono_norm
                FROM public_marts.dim_leads
                WHERE lead_id = %s
            """, (lead_id,))

            row = cursor.fetchone()
            if not row:
                logger.warning(f"Lead {lead_id} not found in dim_leads")
                cursor.close()
                return False

            tenant_id, telefono_norm = row

            cursor.execute("""
                INSERT INTO leads_lead_estado (
                    lead_id, tenant_id, telefono_norm, estado,
                    fecha_cambio_estado, numero_intentos, notas
                ) VALUES (
                    %s, %s, %s, 'YA_VENDIDO', NOW(), 0, %s
                )
                ON CONFLICT (lead_id) DO UPDATE SET
                    estado = 'YA_VENDIDO',
                    fecha_cambio_estado = NOW(),
                    notas = COALESCE(leads_lead_estado.notas, '') || %s
            """, (
                lead_id, tenant_id, telefono_norm or '',
                f'[Auto] Anuncio eliminado del portal: {reason}',
                f'\n[Auto] Anuncio eliminado del portal: {reason}',
            ))

            self.conn.commit()
            cursor.close()
            return True

        except Exception as e:
            logger.error(f"Error marking lead {lead_id} as removed: {e}")
            self.conn.rollback()
            return False

    def check_leads(
        self,
        limit: int = 100,
        portal: Optional[str] = None,
        mark_removed: bool = True,
        safe_only: bool = True,
        notify: bool = True,
    ) -> Dict:
        """
        Check multiple leads and optionally mark removed ones.

        Args:
            limit: Maximum number of leads to check
            portal: Filter by portal (optional)
            mark_removed: If True, update database for removed leads
            safe_only: If True, only check habitaclia/fotocasa (no anti-bot)
            notify: If True, send Telegram notification with summary
        """
        leads = self.get_leads_to_check(limit=limit, portal=portal, safe_only=safe_only)
        logger.info(f"Checking {len(leads)} leads (safe_only={safe_only})...")

        removed_leads = []

        for lead in leads:
            is_active, reason = self.check_url(lead['url'], lead['portal'])
            self.stats['checked'] += 1

            if is_active:
                self.stats['active'] += 1
                logger.debug(f"Active: {lead['lead_id']} - {reason}")
            else:
                self.stats['removed'] += 1
                removed_leads.append({
                    'lead_id': lead['lead_id'],
                    'url': lead['url'],
                    'portal': lead['portal'],
                    'reason': reason,
                })
                logger.info(f"Removed: {lead['lead_id']} ({lead['portal']}) - {reason}")

                if mark_removed:
                    self.mark_as_removed(lead['lead_id'], reason)

        results = {
            'stats': self.stats,
            'removed_leads': removed_leads,
        }

        # Send Telegram summary
        if notify and self.stats['checked'] > 0:
            msg = (
                f"<b>Listing Check</b>\n"
                f"Checked: {self.stats['checked']}\n"
                f"Active: {self.stats['active']}\n"
                f"Removed: {self.stats['removed']}"
            )
            if removed_leads:
                portals = {}
                for rl in removed_leads:
                    portals[rl['portal']] = portals.get(rl['portal'], 0) + 1
                msg += "\n\nBy portal: " + ", ".join(f"{p}: {c}" for p, c in portals.items())
            send_telegram(msg)

        return results

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def check_removed_listings(limit: int = 50, portal: Optional[str] = None) -> Dict:
    """Convenience function to check listings and mark removed ones."""
    with ListingChecker() as checker:
        return checker.check_leads(limit=limit, portal=portal, mark_removed=True)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    import argparse
    parser = argparse.ArgumentParser(description='Check if listings are still active')
    parser.add_argument('--limit', type=int, default=200, help='Max leads to check')
    parser.add_argument('--portal', type=str, help='Filter by portal')
    parser.add_argument('--all-portals', action='store_true', help='Check all portals (including anti-bot)')
    parser.add_argument('--dry-run', action='store_true', help='Do not update database')
    parser.add_argument('--no-notify', action='store_true', help='Skip Telegram notification')
    args = parser.parse_args()

    with ListingChecker() as checker:
        results = checker.check_leads(
            limit=args.limit,
            portal=args.portal,
            mark_removed=not args.dry_run,
            safe_only=not args.all_portals,
            notify=not args.no_notify,
        )

    print(f"\n=== Results ===")
    print(f"Checked: {results['stats']['checked']}")
    print(f"Active: {results['stats']['active']}")
    print(f"Removed: {results['stats']['removed']}")
    print(f"Errors: {results['stats']['errors']}")

    if results['removed_leads']:
        print(f"\nRemoved listings:")
        for lead in results['removed_leads']:
            print(f"  - {lead['lead_id'][:12]}... ({lead['portal']}): {lead['reason']}")

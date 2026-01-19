"""
Dagster assets for automated contact processing.

Processes the contact_queue table and uses Playwright to contact leads
via Fotocasa and Habitaclia (with 2Captcha for Habitaclia).
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

from dagster import asset, AssetExecutionContext, MetadataValue, Output

from casa_teva_pipeline.resources.postgres_resource import PostgresResource

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)

# Import alerting utilities
try:
    from scrapers.error_handling import send_alert, AlertSeverity, get_madrid_time
    ALERTING_AVAILABLE = True
except ImportError:
    ALERTING_AVAILABLE = False
    from zoneinfo import ZoneInfo
    def send_alert(*args, **kwargs):
        pass
    def get_madrid_time():
        return datetime.now(ZoneInfo('Europe/Madrid'))
    class AlertSeverity:
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"


def get_pending_contacts(postgres: PostgresResource, limit: int = 5) -> list:
    """Get pending contacts from queue ordered by priority."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Join with lead_estado to get assigned comercial
            cur.execute("""
                SELECT
                    cq.id, cq.tenant_id, cq.lead_id, cq.portal, cq.listing_url,
                    cq.titulo, cq.mensaje, cq.prioridad,
                    le.asignado_a_id
                FROM leads_contact_queue cq
                LEFT JOIN leads_lead_estado le ON cq.lead_id = le.lead_id AND cq.tenant_id = le.tenant_id
                WHERE cq.estado = 'PENDIENTE'
                ORDER BY cq.prioridad DESC, cq.created_at ASC
                LIMIT %s
            """, (limit,))
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def update_contact_status(
    postgres: PostgresResource,
    contact_id: int,
    estado: str,
    telefono: Optional[str] = None,
    mensaje_enviado: bool = False,
    error: Optional[str] = None
):
    """Update contact queue item status."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads_contact_queue
                SET
                    estado = %s,
                    telefono_extraido = COALESCE(%s, telefono_extraido),
                    mensaje_enviado = %s,
                    error = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (estado, telefono, mensaje_enviado, error, contact_id))
        conn.commit()


def get_portal_credentials(postgres: PostgresResource, tenant_id: int, portal: str) -> tuple:
    """
    Get credentials for a portal, with fallback to env vars.
    Returns (email, password) or (None, None) if not found.
    """
    # Try tenant-specific credentials first
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT email, password_encrypted
                FROM leads_portal_credential
                WHERE tenant_id = %s AND portal = %s AND is_active = true
            """, (tenant_id, portal))
            row = cur.fetchone()

            if row:
                email, password_encrypted = row
                # Decrypt password using Fernet
                try:
                    from cryptography.fernet import Fernet
                    import base64

                    key = os.environ.get('CREDENTIAL_ENCRYPTION_KEY')
                    if not key:
                        # Dev fallback key
                        key = 'dev-only-key-do-not-use-in-prod!'
                        key = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'\0')).decode()

                    f = Fernet(key.encode())
                    password = f.decrypt(password_encrypted.encode()).decode()
                    return (email, password)
                except Exception as e:
                    logger.warning(f"Failed to decrypt credentials for {portal}: {e}")

    # Fallback to env vars
    portal_upper = portal.upper()
    email = os.environ.get(f'{portal_upper}_EMAIL')
    password = os.environ.get(f'{portal_upper}_PASSWORD')

    if email and password:
        return (email, password)

    return (None, None)


def update_credential_last_used(postgres: PostgresResource, tenant_id: int, portal: str):
    """Update last_used timestamp for credential."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads_portal_credential
                SET last_used = NOW(), updated_at = NOW()
                WHERE tenant_id = %s AND portal = %s
            """, (tenant_id, portal))
        conn.commit()


def update_credential_error(postgres: PostgresResource, tenant_id: int, portal: str, error: str):
    """Update last_error for credential."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads_portal_credential
                SET last_error = %s, updated_at = NOW()
                WHERE tenant_id = %s AND portal = %s
            """, (error, tenant_id, portal))
        conn.commit()


def get_tenant_contact_info(postgres: PostgresResource, tenant_id: int, asignado_a_id: int = None) -> dict:
    """
    Get commercial contact info for a contact.
    Priority: assigned comercial > tenant defaults > env vars.
    """
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # First try: get assigned comercial's contact info
            if asignado_a_id:
                cur.execute("""
                    SELECT
                        tu.comercial_nombre,
                        tu.comercial_email,
                        tu.comercial_telefono,
                        u.first_name,
                        u.last_name,
                        u.email
                    FROM tenant_users tu
                    JOIN auth_user u ON tu.user_id = u.id
                    WHERE tu.user_id = %s AND tu.tenant_id = %s
                """, (asignado_a_id, tenant_id))
                row = cur.fetchone()

                if row:
                    comercial_nombre, comercial_email, comercial_telefono, first_name, last_name, user_email = row
                    # Use comercial fields, fallback to user fields
                    name = comercial_nombre or f"{first_name} {last_name}".strip() or 'Comercial'
                    email = comercial_email or user_email or ''
                    phone = comercial_telefono or ''

                    if name and email:  # Only use if we have at least name and email
                        return {'name': name, 'email': email, 'phone': phone}

            # Fallback: tenant defaults
            cur.execute("""
                SELECT comercial_nombre, comercial_email, comercial_telefono
                FROM tenants
                WHERE tenant_id = %s
            """, (tenant_id,))
            row = cur.fetchone()

            if row and (row[0] or row[1]):
                return {
                    'name': row[0] or os.environ.get('CONTACT_NAME', 'Interesado'),
                    'email': row[1] or os.environ.get('CONTACT_EMAIL', ''),
                    'phone': row[2] or os.environ.get('CONTACT_PHONE', '')
                }

    # Final fallback: env vars
    return {
        'name': os.environ.get('CONTACT_NAME', 'Interesado'),
        'email': os.environ.get('CONTACT_EMAIL', ''),
        'phone': os.environ.get('CONTACT_PHONE', '')
    }


def get_portal_session(postgres: PostgresResource, tenant_id: int, portal: str) -> Optional[dict]:
    """Get saved session cookies for a portal."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cookies, email, is_valid, last_used
                FROM leads_portal_session
                WHERE tenant_id = %s AND portal = %s AND is_valid = true
            """, (tenant_id, portal))
            row = cur.fetchone()
            if row:
                return {
                    'cookies': row[0],
                    'email': row[1],
                    'is_valid': row[2],
                    'last_used': row[3]
                }
            return None


def update_session_last_used(postgres: PostgresResource, tenant_id: int, portal: str):
    """Update last_used timestamp for session."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads_portal_session
                SET last_used = NOW(), updated_at = NOW()
                WHERE tenant_id = %s AND portal = %s
            """, (tenant_id, portal))
        conn.commit()


def invalidate_session(postgres: PostgresResource, tenant_id: int, portal: str):
    """Mark session as invalid (needs re-login)."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads_portal_session
                SET is_valid = false, updated_at = NOW()
                WHERE tenant_id = %s AND portal = %s
            """, (tenant_id, portal))
        conn.commit()


def save_session_cookies(postgres: PostgresResource, tenant_id: int, portal: str, email: str, cookies: list):
    """Save or update session cookies after successful login."""
    cookies_json = json.dumps(cookies)
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Upsert: insert or update
            cur.execute("""
                INSERT INTO leads_portal_session (tenant_id, portal, email, cookies, is_valid, last_used, created_at, updated_at)
                VALUES (%s, %s, %s, %s, true, NOW(), NOW(), NOW())
                ON CONFLICT (tenant_id, portal)
                DO UPDATE SET
                    cookies = EXCLUDED.cookies,
                    email = EXCLUDED.email,
                    is_valid = true,
                    last_used = NOW(),
                    updated_at = NOW()
            """, (tenant_id, portal, email, cookies_json))
        conn.commit()


async def process_fotocasa_contact(
    contact: dict,
    session: Optional[dict],
    context: AssetExecutionContext,
    credentials: tuple = (None, None),
    postgres: PostgresResource = None,
    tenant_id: int = None
) -> dict:
    """Process a single Fotocasa contact using Playwright."""
    from scrapers.contact_automation.fotocasa_contact import FotocasaContact

    result = {
        'success': False,
        'phone': None,
        'message_sent': False,
        'error': None
    }

    # Use passed credentials or fallback to env vars
    email, password = credentials
    if not email or not password:
        email = os.environ.get('FOTOCASA_EMAIL')
        password = os.environ.get('FOTOCASA_PASSWORD')

    automation = FotocasaContact(headless=True, email=email, password=password)

    try:
        await automation.setup_browser()

        # Load cookies from DB if available
        if session and session.get('cookies'):
            cookies = session['cookies']
            if isinstance(cookies, str):
                cookies = json.loads(cookies)
            await automation.context.add_cookies(cookies)
            context.log.info(f"Loaded {len(cookies)} cookies from DB session")

        # Check if logged in, login if needed
        if not await automation.is_logged_in():
            context.log.info("Session expired or no session, attempting login...")
            if email and password:
                if not await automation.login(email, password):
                    result['error'] = 'Login failed'
                    return result
                context.log.info("Login successful")
                # Save session cookies for future use
                if postgres and tenant_id:
                    cookies = await automation.context.cookies()
                    save_session_cookies(postgres, tenant_id, 'fotocasa', email, cookies)
                    context.log.info(f"Saved {len(cookies)} cookies to DB")
            else:
                result['error'] = 'No credentials for auto-login'
                return result

        # Contact the lead
        contact_result = await automation.contact_lead(
            lead_id=contact['lead_id'],
            listing_url=contact['listing_url'],
            message=contact['mensaje']
        )

        result['success'] = contact_result.success
        result['phone'] = contact_result.phone_extracted
        result['message_sent'] = contact_result.message_sent
        result['error'] = contact_result.error

    except Exception as e:
        result['error'] = str(e)
        context.log.error(f"Error processing Fotocasa contact: {e}")

    finally:
        await automation.close()

    return result


async def process_habitaclia_contact(
    contact: dict,
    session: Optional[dict],
    context: AssetExecutionContext,
    contact_info: dict = None
) -> dict:
    """Process a single Habitaclia contact (with 2Captcha support)."""
    from scrapers.contact_automation.habitaclia_contact import HabitacliaContact

    result = {
        'success': False,
        'phone': None,
        'message_sent': False,
        'error': None
    }

    captcha_api_key = os.environ.get('CAPTCHA_API_KEY')
    if not captcha_api_key:
        result['error'] = 'CAPTCHA_API_KEY not configured'
        context.log.warning("CAPTCHA_API_KEY not set, skipping Habitaclia contact")
        return result

    # Use tenant contact info or defaults
    contact_info = contact_info or {}
    automation = HabitacliaContact(
        headless=True,
        captcha_api_key=captcha_api_key,
        contact_name=contact_info.get('name'),
        contact_email=contact_info.get('email'),
        contact_phone=contact_info.get('phone')
    )

    try:
        await automation.setup_browser()

        # Load cookies from DB if available
        if session and session.get('cookies'):
            cookies = session['cookies']
            if isinstance(cookies, str):
                cookies = json.loads(cookies)
            await automation.context.add_cookies(cookies)
            context.log.info(f"Loaded {len(cookies)} cookies from DB session")

        # Contact the lead
        contact_result = await automation.contact_lead(
            lead_id=contact['lead_id'],
            listing_url=contact['listing_url'],
            message=contact['mensaje']
        )

        result['success'] = contact_result.success
        result['phone'] = contact_result.phone_extracted
        result['message_sent'] = contact_result.message_sent
        result['error'] = contact_result.error

    except Exception as e:
        result['error'] = str(e)
        context.log.error(f"Error processing Habitaclia contact: {e}")

    finally:
        await automation.close()

    return result


async def process_milanuncios_contact(
    contact: dict,
    session: Optional[dict],
    context: AssetExecutionContext,
    credentials: tuple = (None, None),
    postgres: PostgresResource = None,
    tenant_id: int = None
) -> dict:
    """Process a single Milanuncios contact using internal chat."""
    from scrapers.contact_automation.milanuncios_contact import MilanunciosContact

    result = {
        'success': False,
        'phone': None,
        'message_sent': False,
        'error': None
    }

    # Use passed credentials or fallback to env vars
    email, password = credentials
    if not email or not password:
        email = os.environ.get('MILANUNCIOS_EMAIL')
        password = os.environ.get('MILANUNCIOS_PASSWORD')

    if not email or not password:
        result['error'] = 'MILANUNCIOS credentials not configured (tenant or env vars)'
        context.log.warning("Milanuncios credentials not set, skipping contact")
        return result

    automation = MilanunciosContact(headless=True, email=email, password=password)

    try:
        await automation.setup_browser()

        # Load cookies from DB if available
        if session and session.get('cookies'):
            cookies = session['cookies']
            if isinstance(cookies, str):
                cookies = json.loads(cookies)
            await automation.context.add_cookies(cookies)
            context.log.info(f"Loaded {len(cookies)} cookies from DB session")

        # Check if logged in, login if needed
        if not await automation.is_logged_in():
            context.log.info("Session expired, attempting login...")
            if not await automation.login():
                result['error'] = 'Login failed'
                return result
            context.log.info("Login successful")
            # Save session cookies for future use
            if postgres and tenant_id:
                cookies = await automation.context.cookies()
                save_session_cookies(postgres, tenant_id, 'milanuncios', email, cookies)
                context.log.info(f"Saved {len(cookies)} cookies to DB")

        # Contact the lead
        contact_result = await automation.contact_lead(
            lead_id=contact['lead_id'],
            listing_url=contact['listing_url'],
            message=contact['mensaje']
        )

        result['success'] = contact_result.success
        result['phone'] = contact_result.phone_extracted
        result['message_sent'] = contact_result.message_sent
        result['error'] = contact_result.error

    except Exception as e:
        result['error'] = str(e)
        context.log.error(f"Error processing Milanuncios contact: {e}")

    finally:
        await automation.close()

    return result


async def process_idealista_contact(
    contact: dict,
    session: Optional[dict],
    context: AssetExecutionContext,
    credentials: tuple = (None, None),
    postgres: PostgresResource = None,
    tenant_id: int = None
) -> dict:
    """Process a single Idealista contact (with DataDome handling via 2Captcha)."""
    from scrapers.contact_automation.idealista_contact import IdealistaContact

    result = {
        'success': False,
        'phone': None,
        'message_sent': False,
        'error': None
    }

    # Check for captcha API key (global, not per-tenant)
    captcha_api_key = os.environ.get('CAPTCHA_API_KEY')
    if not captcha_api_key:
        result['error'] = 'CAPTCHA_API_KEY not configured (required for DataDome)'
        context.log.warning("CAPTCHA_API_KEY not set, skipping Idealista contact")
        return result

    # Use passed credentials or fallback to env vars
    email, password = credentials
    if not email or not password:
        email = os.environ.get('IDEALISTA_EMAIL')
        password = os.environ.get('IDEALISTA_PASSWORD')

    if not email or not password:
        result['error'] = 'IDEALISTA credentials not configured (tenant or env vars)'
        context.log.warning("Idealista credentials not set, skipping contact")
        return result

    automation = IdealistaContact(headless=True, captcha_api_key=captcha_api_key, email=email, password=password)

    try:
        await automation.setup_browser()

        # Load cookies from DB if available
        if session and session.get('cookies'):
            cookies = session['cookies']
            if isinstance(cookies, str):
                cookies = json.loads(cookies)
            await automation.context.add_cookies(cookies)
            context.log.info(f"Loaded {len(cookies)} cookies from DB session")

        # Check if logged in, login if needed
        if not await automation.is_logged_in():
            context.log.info("Session expired, attempting login...")
            if not await automation.login():
                result['error'] = 'Login failed (possibly DataDome blocked)'
                return result
            context.log.info("Login successful")
            # Save session cookies for future use
            if postgres and tenant_id:
                cookies = await automation.context.cookies()
                save_session_cookies(postgres, tenant_id, 'idealista', email, cookies)
                context.log.info(f"Saved {len(cookies)} cookies to DB")

        # Contact the lead
        contact_result = await automation.contact_lead(
            lead_id=contact['lead_id'],
            listing_url=contact['listing_url'],
            message=contact['mensaje']
        )

        result['success'] = contact_result.success
        result['phone'] = contact_result.phone_extracted
        result['message_sent'] = contact_result.message_sent
        result['error'] = contact_result.error

    except Exception as e:
        result['error'] = str(e)
        context.log.error(f"Error processing Idealista contact: {e}")

    finally:
        await automation.close()

    return result


@asset(
    description="Procesa la cola de contactos automaticos",
    compute_kind="playwright",
    group_name="contact",
)
def process_contact_queue(
    context: AssetExecutionContext,
    postgres: PostgresResource
) -> Output[Dict[str, Any]]:
    """
    Process pending contacts from the queue.

    - Max 5 contacts per run (conservative limit)
    - Uses saved sessions from portal_sessions table
    - Updates contact status after each attempt
    """
    context.log.info("Starting contact queue processing...")

    # Get pending contacts (max 5 per day)
    pending = get_pending_contacts(postgres, limit=5)

    if not pending:
        context.log.info("No pending contacts in queue")
        return Output(
            value={'status': 'no_pending', 'processed': 0},
            metadata={'processed': MetadataValue.int(0)}
        )

    context.log.info(f"Found {len(pending)} pending contacts")

    results = {
        'status': 'completed',
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'phones_extracted': 0,
        'messages_sent': 0,
        'details': []
    }

    # Process contacts by portal
    for contact in pending:
        contact_id = contact['id']
        portal = contact['portal']
        tenant_id = contact['tenant_id']

        context.log.info(f"Processing contact {contact_id}: {portal} - {contact['listing_url'][:50]}...")

        # Mark as in progress
        update_contact_status(postgres, contact_id, 'EN_PROCESO')

        # Get session for this portal
        session = get_portal_session(postgres, tenant_id, portal)

        # Get credentials for this tenant/portal (with fallback to env vars)
        credentials = get_portal_credentials(postgres, tenant_id, portal)

        # Get tenant contact info (for filling contact forms)
        # Priority: assigned comercial > tenant defaults > env vars
        asignado_a_id = contact.get('asignado_a_id')
        contact_info = get_tenant_contact_info(postgres, tenant_id, asignado_a_id)

        if not session:
            context.log.warning(f"No valid session for {portal} (tenant {tenant_id})")
            # All portals can try auto-login if credentials are available
            # Only fail if no session AND no credentials
            if credentials == (None, None):
                # Habitaclia doesn't need credentials (uses CAPTCHA), but needs session
                if portal == 'habitaclia':
                    update_contact_status(
                        postgres, contact_id, 'FALLIDO',
                        error=f'No valid session for {portal}'
                    )
                    results['failed'] += 1
                    continue
                # Fotocasa/Milanuncios/Idealista need credentials for auto-login
                elif portal in ('fotocasa', 'milanuncios', 'idealista'):
                    update_contact_status(
                        postgres, contact_id, 'FALLIDO',
                        error=f'No credentials configured for {portal}'
                    )
                    results['failed'] += 1
                    continue

        # Check credentials for portals that need them (when session exists but may be expired)
        if portal in ('milanuncios', 'idealista') and credentials == (None, None):
            context.log.warning(f"No credentials for {portal} (tenant {tenant_id})")
            update_contact_status(
                postgres, contact_id, 'FALLIDO',
                error=f'No credentials configured for {portal}'
            )
            update_credential_error(postgres, tenant_id, portal, 'No credentials configured')
            results['failed'] += 1
            continue

        # Process based on portal (pass credentials and contact info)
        if portal == 'fotocasa':
            result = asyncio.run(process_fotocasa_contact(contact, session, context, credentials, postgres, tenant_id))
        elif portal == 'habitaclia':
            result = asyncio.run(process_habitaclia_contact(contact, session, context, contact_info))
        elif portal == 'milanuncios':
            result = asyncio.run(process_milanuncios_contact(contact, session, context, credentials, postgres, tenant_id))
        elif portal == 'idealista':
            result = asyncio.run(process_idealista_contact(contact, session, context, credentials, postgres, tenant_id))
        else:
            result = {'success': False, 'error': f'Portal not supported for contact: {portal}'}

        # Update status
        if result['success']:
            update_contact_status(
                postgres, contact_id, 'COMPLETADO',
                telefono=result.get('phone'),
                mensaje_enviado=result.get('message_sent', False)
            )
            update_session_last_used(postgres, tenant_id, portal)
            update_credential_last_used(postgres, tenant_id, portal)
            results['successful'] += 1
            if result.get('phone'):
                results['phones_extracted'] += 1
            if result.get('message_sent'):
                results['messages_sent'] += 1
        else:
            update_contact_status(
                postgres, contact_id, 'FALLIDO',
                error=result.get('error')
            )
            results['failed'] += 1

            # Update credential error
            if result.get('error'):
                update_credential_error(postgres, tenant_id, portal, result['error'])

            # Invalidate session if auth error
            if result.get('error') and 'session' in result['error'].lower():
                invalidate_session(postgres, tenant_id, portal)
                context.log.warning(f"Invalidated session for {portal}")

        results['processed'] += 1
        results['details'].append({
            'contact_id': contact_id,
            'portal': portal,
            'success': result['success'],
            'phone': result.get('phone'),
            'message_sent': result.get('message_sent'),
            'error': result.get('error')
        })

        # Small delay between contacts
        if results['processed'] < len(pending):
            context.log.info("Waiting 30s before next contact...")
            asyncio.run(asyncio.sleep(30))

    # Send alert on failures
    if results['failed'] > 0:
        # Build detailed failure info
        failed_details = [
            f"• {d['portal']}: {d['error']}"
            for d in results['details']
            if not d['success']
        ]
        send_alert(
            title="Contact automation completed with failures",
            message=f"{results['failed']}/{results['processed']} contacts failed",
            severity=AlertSeverity.WARNING,
            details={
                'successful': results['successful'],
                'failed': results['failed'],
                'phones_extracted': results['phones_extracted'],
                'errors': '\n'.join(failed_details) if failed_details else 'Unknown'
            }
        )

    context.log.info(f"Contact processing complete: {results['successful']} OK, {results['failed']} failed")

    return Output(
        value=results,
        metadata={
            'processed': MetadataValue.int(results['processed']),
            'successful': MetadataValue.int(results['successful']),
            'failed': MetadataValue.int(results['failed']),
            'phones_extracted': MetadataValue.int(results['phones_extracted']),
            'messages_sent': MetadataValue.int(results['messages_sent']),
        }
    )

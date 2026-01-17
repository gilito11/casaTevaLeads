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
            cur.execute("""
                SELECT
                    id, tenant_id, lead_id, portal, listing_url,
                    titulo, mensaje, prioridad
                FROM leads_contact_queue
                WHERE estado = 'PENDIENTE'
                ORDER BY prioridad DESC, created_at ASC
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


async def process_fotocasa_contact(
    contact: dict,
    session: Optional[dict],
    context: AssetExecutionContext
) -> dict:
    """Process a single Fotocasa contact using Playwright."""
    from scrapers.contact_automation.fotocasa_contact import FotocasaContact

    result = {
        'success': False,
        'phone': None,
        'message_sent': False,
        'error': None
    }

    automation = FotocasaContact(headless=True)

    try:
        await automation.setup_browser()

        # Load cookies from DB if available
        if session and session.get('cookies'):
            cookies = session['cookies']
            if isinstance(cookies, str):
                cookies = json.loads(cookies)
            await automation.context.add_cookies(cookies)
            context.log.info(f"Loaded {len(cookies)} cookies from DB session")

        # Check if logged in
        if not await automation.is_logged_in():
            context.log.warning("Session expired or invalid")
            result['error'] = 'Session expired - need re-login'
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
    context: AssetExecutionContext
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

    automation = HabitacliaContact(headless=True, captcha_api_key=captcha_api_key)

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

        if not session:
            context.log.warning(f"No valid session for {portal} (tenant {tenant_id})")
            update_contact_status(
                postgres, contact_id, 'FALLIDO',
                error=f'No valid session for {portal}'
            )
            results['failed'] += 1
            continue

        # Process based on portal
        if portal == 'fotocasa':
            result = asyncio.run(process_fotocasa_contact(contact, session, context))
        elif portal == 'habitaclia':
            result = asyncio.run(process_habitaclia_contact(contact, session, context))
        else:
            result = {'success': False, 'error': f'Unknown portal: {portal}'}

        # Update status
        if result['success']:
            update_contact_status(
                postgres, contact_id, 'COMPLETADO',
                telefono=result.get('phone'),
                mensaje_enviado=result.get('message_sent', False)
            )
            update_session_last_used(postgres, tenant_id, portal)
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
        send_alert(
            title="Contact automation completed with failures",
            message=f"{results['failed']}/{results['processed']} contacts failed",
            severity=AlertSeverity.WARNING,
            details={
                'successful': results['successful'],
                'failed': results['failed'],
                'phones_extracted': results['phones_extracted']
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

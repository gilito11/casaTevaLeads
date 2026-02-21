#!/usr/bin/env python3
"""
Process contact queue - Standalone script for GitHub Actions.

Reads pending contacts from ContactQueue and processes them using
the contact automation scrapers (Playwright-based).

Usage:
    python scripts/process_contact_queue.py

Requires:
    - DATABASE_URL environment variable (Neon)
    - FOTOCASA_EMAIL, FOTOCASA_PASSWORD (for Fotocasa)
    - MILANUNCIOS_EMAIL, MILANUNCIOS_PASSWORD (for Milanuncios)
    - IDEALISTA_EMAIL, IDEALISTA_PASSWORD (for Idealista)
    - CAPTCHA_API_KEY (for Habitaclia/Idealista)
    - DATADOME_PROXY (for Idealista - IPRoyal residential proxy)
    - CONTACT_NAME, CONTACT_EMAIL, CONTACT_PHONE (for forms)
    - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional, for alerts)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_connection():
    """Get database connection from DATABASE_URL."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    return psycopg2.connect(database_url)


def get_pending_contacts(limit: int = 5) -> list:
    """Get pending contacts from queue."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    cq.id, cq.tenant_id, cq.lead_id, cq.portal, cq.listing_url,
                    cq.titulo, cq.mensaje, cq.prioridad
                FROM leads_contact_queue cq
                WHERE cq.estado = 'PENDIENTE'
                ORDER BY cq.prioridad DESC, cq.created_at ASC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]


def update_contact_status(
    contact_id: int,
    estado: str,
    telefono: Optional[str] = None,
    mensaje_enviado: bool = False,
    error: Optional[str] = None
):
    """Update contact queue item status."""
    with get_connection() as conn:
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


def send_telegram_alert(message: str):
    """Send Telegram notification."""
    import requests

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        logger.warning("Telegram not configured, skipping alert")
        return

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, json={
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        logger.info("Telegram alert sent")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


async def process_fotocasa(contact: dict) -> dict:
    """Process Fotocasa contact."""
    from scrapers.contact_automation.fotocasa_contact import FotocasaContact

    result = {'success': False, 'phone': None, 'message_sent': False, 'error': None}

    email = os.environ.get('FOTOCASA_EMAIL')
    password = os.environ.get('FOTOCASA_PASSWORD')

    if not email or not password:
        result['error'] = 'FOTOCASA credentials not configured'
        return result

    automation = FotocasaContact(headless=True, email=email, password=password)

    try:
        await automation.setup_browser()

        if not await automation.is_logged_in():
            logger.info("Logging in to Fotocasa...")
            if not await automation.login(email, password):
                result['error'] = 'Login failed'
                return result

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
        logger.error(f"Fotocasa error: {e}")
    finally:
        await automation.close()

    return result


async def process_habitaclia(contact: dict) -> dict:
    """Process Habitaclia contact."""
    from scrapers.contact_automation.habitaclia_contact import HabitacliaContact

    result = {'success': False, 'phone': None, 'message_sent': False, 'error': None}

    captcha_key = os.environ.get('CAPTCHA_API_KEY')
    if not captcha_key:
        result['error'] = 'CAPTCHA_API_KEY not configured'
        return result

    automation = HabitacliaContact(
        headless=True,
        captcha_api_key=captcha_key,
        contact_name=os.environ.get('CONTACT_NAME', 'Interesado'),
        contact_email=os.environ.get('CONTACT_EMAIL', ''),
        contact_phone=os.environ.get('CONTACT_PHONE', '')
    )

    try:
        await automation.setup_browser()

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
        logger.error(f"Habitaclia error: {e}")
    finally:
        await automation.close()

    return result


async def process_milanuncios(contact: dict) -> dict:
    """Process Milanuncios contact."""
    from scrapers.contact_automation.milanuncios_contact import MilanunciosContact

    result = {'success': False, 'phone': None, 'message_sent': False, 'error': None}

    email = os.environ.get('MILANUNCIOS_EMAIL')
    password = os.environ.get('MILANUNCIOS_PASSWORD')

    if not email or not password:
        result['error'] = 'MILANUNCIOS credentials not configured'
        return result

    automation = MilanunciosContact(headless=True, email=email, password=password)

    try:
        await automation.setup_browser()

        if not await automation.is_logged_in():
            logger.info("Logging in to Milanuncios...")
            if not await automation.login(email, password):
                result['error'] = 'Login failed'
                return result

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
        logger.error(f"Milanuncios error: {e}")
    finally:
        await automation.close()

    return result


async def process_idealista(contact: dict) -> dict:
    """Process Idealista contact."""
    from scrapers.contact_automation.idealista_contact import IdealistaContact

    result = {'success': False, 'phone': None, 'message_sent': False, 'error': None}

    email = os.environ.get('IDEALISTA_EMAIL')
    password = os.environ.get('IDEALISTA_PASSWORD')
    captcha_key = os.environ.get('CAPTCHA_API_KEY')
    proxy = os.environ.get('DATADOME_PROXY')

    if not email or not password:
        result['error'] = 'IDEALISTA credentials not configured'
        return result

    if not proxy:
        result['error'] = 'DATADOME_PROXY not configured (required for Idealista)'
        return result

    automation = IdealistaContact(
        headless=True,
        captcha_api_key=captcha_key,
        email=email,
        password=password,
        proxy=proxy
    )

    try:
        await automation.setup_browser()

        if not await automation.is_logged_in():
            logger.info("Logging in to Idealista...")
            if not await automation.login(email, password):
                result['error'] = 'Login failed'
                return result

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
        logger.error(f"Idealista error: {e}")
    finally:
        await automation.close()

    return result


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description='Process contact queue')
    parser.add_argument('--max-contacts', type=int, default=5, help='Max contacts to process')
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Contact Queue Processor")
    logger.info("=" * 50)

    # Get pending contacts
    pending = get_pending_contacts(limit=args.max_contacts)

    if not pending:
        logger.info("No pending contacts")
        print("::notice::No pending contacts in queue")
        return 0

    logger.info(f"Found {len(pending)} pending contacts")

    results = {
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'details': []
    }

    for contact in pending:
        contact_id = contact['id']
        portal = contact['portal']

        logger.info(f"Processing {portal}: {contact['listing_url'][:60]}...")

        # Mark as in progress
        update_contact_status(contact_id, 'EN_PROCESO')

        # Process based on portal
        if portal == 'fotocasa':
            result = asyncio.run(process_fotocasa(contact))
        elif portal == 'habitaclia':
            result = asyncio.run(process_habitaclia(contact))
        elif portal == 'milanuncios':
            result = asyncio.run(process_milanuncios(contact))
        elif portal == 'idealista':
            result = asyncio.run(process_idealista(contact))
        else:
            result = {'success': False, 'error': f'Portal not supported: {portal}'}

        # Update status
        if result['success']:
            update_contact_status(
                contact_id, 'COMPLETADO',
                telefono=result.get('phone'),
                mensaje_enviado=result.get('message_sent', False)
            )
            results['successful'] += 1
            logger.info(f"  ✓ Success (phone: {result.get('phone')}, sent: {result.get('message_sent')})")
        else:
            update_contact_status(
                contact_id, 'FALLIDO',
                error=result.get('error')
            )
            results['failed'] += 1
            logger.error(f"  ✗ Failed: {result.get('error')}")

        results['processed'] += 1
        results['details'].append({
            'portal': portal,
            'success': result['success'],
            'error': result.get('error')
        })

        # Delay between contacts
        if results['processed'] < len(pending):
            logger.info("Waiting 30s before next contact...")
            asyncio.run(asyncio.sleep(30))

    # Summary
    logger.info("=" * 50)
    logger.info(f"Processed: {results['processed']}")
    logger.info(f"Successful: {results['successful']}")
    logger.info(f"Failed: {results['failed']}")

    # Telegram notification
    if results['processed'] > 0:
        emoji = "✅" if results['failed'] == 0 else "⚠️"
        message = f"""{emoji} <b>Contact Queue Processed</b>

Processed: {results['processed']}
Successful: {results['successful']}
Failed: {results['failed']}

{datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        send_telegram_alert(message)

    # GitHub Actions output
    print(f"::set-output name=processed::{results['processed']}")
    print(f"::set-output name=successful::{results['successful']}")
    print(f"::set-output name=failed::{results['failed']}")

    return 0 if results['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

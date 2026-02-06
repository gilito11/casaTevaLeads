#!/usr/bin/env python3
"""
Post-scrape auto-queue: detect new listings and enqueue for contact.

Runs after dbt in scrape-neon.yml workflow.
Reads AutoContactConfig from DB to determine what to auto-queue.
Uses weighted random template selection for A/B testing.
"""

import os
import sys
import random
import logging
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


def get_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def get_auto_contact_configs(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT acc.*
            FROM leads_auto_contact_config acc
            WHERE acc.habilitado = TRUE
        """)
        return cur.fetchall()


def get_new_listings(conn, tenant_id, hours_back=4):
    """Get leads captured in the last N hours that aren't already queued."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                l.lead_id,
                l.source_portal,
                l.listing_url,
                l.titulo,
                l.zona_clasificada,
                l.tipo_propiedad,
                l.precio,
                l.es_particular,
                l.lead_score,
                l.telefono_norm
            FROM public_marts.dim_leads l
            WHERE l.tenant_id = %s
              AND l.fecha_primera_captura >= NOW() - INTERVAL '%s hours'
              AND l.listing_url IS NOT NULL
              AND l.listing_url != ''
              AND NOT EXISTS (
                  SELECT 1 FROM leads_contact_queue cq
                  WHERE cq.lead_id = l.lead_id AND cq.tenant_id::TEXT = %s::TEXT
              )
        """, (tenant_id, hours_back, tenant_id))
        return cur.fetchall()


def get_templates(conn, tenant_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, nombre, cuerpo, peso
            FROM leads_message_template
            WHERE tenant_id = %s AND activa = TRUE AND canal = 'portal'
            ORDER BY peso DESC
        """, (tenant_id,))
        return cur.fetchall()


def select_template_weighted(templates):
    if not templates:
        return None
    weights = [t['peso'] for t in templates]
    return random.choices(templates, weights=weights, k=1)[0]


def render_message(template_body, listing):
    context = {
        'nombre_zona': listing.get('zona_clasificada') or '',
        'tipo_propiedad': listing.get('tipo_propiedad') or 'vivienda',
        'precio': f"{listing['precio']:,.0f}" if listing.get('precio') else '',
        'portal': (listing.get('source_portal') or '').capitalize(),
        'url_anuncio': listing.get('listing_url') or '',
    }
    body = template_body
    for key, val in context.items():
        body = body.replace(f'{{{key}}}', str(val))
    return body


def count_contacts_today(conn, tenant_id, portal=None):
    with conn.cursor() as cur:
        sql = """
            SELECT COUNT(*) FROM leads_contact_queue
            WHERE tenant_id = %s AND DATE(created_at) = CURRENT_DATE
        """
        params = [tenant_id]
        if portal:
            sql += " AND portal = %s"
            params.append(portal)
        cur.execute(sql, params)
        return cur.fetchone()[0]


def enqueue_lead(conn, tenant_id, listing, message, template_id, priority=0):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO leads_contact_queue
                (tenant_id, lead_id, portal, listing_url, titulo, mensaje,
                 estado, prioridad, template_id, mensaje_enviado, respondio,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE', %s, %s, FALSE, FALSE, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """, (
            tenant_id, listing['lead_id'], listing['source_portal'],
            listing['listing_url'], (listing.get('titulo') or '')[:500],
            message, priority, template_id
        ))
    conn.commit()


def send_telegram_summary(total_queued, by_portal):
    try:
        from scrapers.utils.telegram_alerts import send_telegram_alert
    except ImportError:
        logger.warning("Could not import telegram_alerts")
        return

    if total_queued == 0:
        return

    lines = [
        f"<b>Auto-Queue</b>",
        f"",
        f"{total_queued} nuevos leads encolados",
    ]

    if by_portal:
        lines.append("")
        for portal, count in sorted(by_portal.items()):
            lines.append(f"  {portal}: {count}")

    lines.append(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    send_telegram_alert("\n".join(lines))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    conn = get_connection()
    configs = get_auto_contact_configs(conn)

    if not configs:
        logger.info("No active auto-contact configs found")
        conn.close()
        return 0

    total_queued = 0
    by_portal = {}

    for config in configs:
        tenant_id = config['tenant_id']
        logger.info(f"Processing tenant {tenant_id}")

        new_listings = get_new_listings(conn, tenant_id)
        logger.info(f"  Found {len(new_listings)} new listings")

        if not new_listings:
            continue

        templates = get_templates(conn, tenant_id)
        if not templates:
            logger.warning(f"  No active templates for tenant {tenant_id}")

        contacts_today = count_contacts_today(conn, tenant_id)
        remaining = config['max_contactos_dia'] - contacts_today

        if remaining <= 0:
            logger.info(f"  Daily limit reached ({config['max_contactos_dia']})")
            continue

        queued = 0
        for listing in new_listings:
            if queued >= remaining:
                break

            portal = listing['source_portal']

            # Check portal enabled
            portal_flag = f"contactar_{portal}"
            if not config.get(portal_flag, False):
                continue

            # Check portal daily limit
            portal_today = count_contacts_today(conn, tenant_id, portal)
            if portal_today >= config['max_contactos_portal_dia']:
                continue

            # Check particular filter
            if config['solo_particulares'] and not listing.get('es_particular', True):
                continue

            # Check price range
            precio = listing.get('precio')
            if precio:
                precio_f = float(precio)
                if config['precio_minimo'] and precio_f < float(config['precio_minimo']):
                    continue
                if config['precio_maximo'] and precio_f > float(config['precio_maximo']):
                    continue

            # Check score minimum
            if (listing.get('lead_score') or 0) < config['score_minimo']:
                continue

            # Select template (A/B test)
            template = select_template_weighted(templates) if templates else None

            if template:
                message = render_message(template['cuerpo'], listing)
                template_id = template['id']
            else:
                message = (
                    f"Hola, he visto su anuncio en {portal.capitalize()} "
                    f"y me interesa. Podriamos hablar?"
                )
                template_id = None

            # Enqueue with lead_score as priority
            priority = listing.get('lead_score') or 0
            enqueue_lead(conn, tenant_id, listing, message, template_id, priority)
            queued += 1

            # Track by portal
            by_portal[portal] = by_portal.get(portal, 0) + 1

            # Increment template usage counter
            if template_id:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE leads_message_template SET veces_usada = veces_usada + 1 WHERE id = %s",
                        (template_id,)
                    )
                conn.commit()

        total_queued += queued
        logger.info(f"  Queued {queued} leads for auto-contact")

    # Telegram summary
    send_telegram_summary(total_queued, by_portal)

    conn.close()
    logger.info(f"Total queued: {total_queued}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

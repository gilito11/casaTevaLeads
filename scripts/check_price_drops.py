#!/usr/bin/env python3
"""
Post-scrape price drop alerts (Telegram).

Detecta bajadas de precio >= 5% cuyo nuevo precio se vio POR PRIMERA VEZ en las
ultimas N horas (fila mas reciente de raw.listing_price_history), asi cada
bajada se alerta una sola vez con el cron diario. Solo alerta leads presentes
en dim_leads (particulares en zonas activas).
"""

import os
import sys
import logging

import psycopg2

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scrapers.utils.telegram_alerts import send_price_drop_alert, send_telegram_alert

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DROP_THRESHOLD_PCT = 5.0
HOURS_BACK = 26  # cron diario + margen
MAX_ALERTS = 10


def get_fresh_drops(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ranked AS (
                SELECT tenant_id, portal, anuncio_id, precio, fecha_captura,
                       LAG(precio) OVER (
                           PARTITION BY tenant_id, portal, anuncio_id
                           ORDER BY fecha_captura
                       ) AS precio_anterior,
                       ROW_NUMBER() OVER (
                           PARTITION BY tenant_id, portal, anuncio_id
                           ORDER BY fecha_captura DESC
                       ) AS rn
                FROM raw.listing_price_history
            ),
            drops AS (
                SELECT tenant_id, portal, anuncio_id, precio, precio_anterior
                FROM ranked
                WHERE rn = 1
                  AND precio_anterior > 0
                  AND precio < precio_anterior
                  AND fecha_captura >= NOW() - INTERVAL '%s hours'
                  AND (precio_anterior - precio) / precio_anterior * 100 >= %s
            )
            SELECT d.titulo, d.source_portal, d.zona_clasificada,
                   dr.precio_anterior, dr.precio, d.listing_url
            FROM drops dr
            JOIN raw.raw_listings r
              ON r.tenant_id::text = dr.tenant_id::text
             AND r.portal = dr.portal
             AND r.raw_data->>'anuncio_id' = dr.anuncio_id
            JOIN public_marts.dim_leads d
              ON d.source_listing_id = r.id
             AND d.tenant_id::text = dr.tenant_id::text
            ORDER BY (dr.precio_anterior - dr.precio) / dr.precio_anterior DESC
            """,
            (HOURS_BACK, DROP_THRESHOLD_PCT),
        )
        return cur.fetchall()


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        drops = get_fresh_drops(conn)
    finally:
        conn.close()

    if not drops:
        logger.info("Sin bajadas de precio nuevas")
        return

    logger.info("%d bajadas de precio detectadas", len(drops))
    for titulo, portal, zona, precio_ant, precio, url in drops[:MAX_ALERTS]:
        send_price_drop_alert(
            titulo=(titulo or "")[:120],
            portal=portal,
            zona=zona or "?",
            precio_anterior=float(precio_ant),
            precio_nuevo=float(precio),
            url=url or "",
        )

    if len(drops) > MAX_ALERTS:
        send_telegram_alert(
            f"...y {len(drops) - MAX_ALERTS} bajadas de precio mas (>{DROP_THRESHOLD_PCT:.0f}%) hoy"
        )


if __name__ == "__main__":
    main()

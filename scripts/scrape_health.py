"""
Checks de salud del scraping contra la BD (sin parsear logs) + aviso in-app.

Fuente: raw.scraper_zone_runs (una fila por portal+zona y run, la escribe
record_zone_metrics) y raw.raw_listings.created_at (primera captura).
Cada problema es un string "<portal>: <motivo>".

Por que existe: habitaclia devolvio found=0 en todas las zonas del 15 Sep al
6 Oct 2026 con el paso de GitHub en "success" y errors=0, y wallapop paso 10
dias sin un lead nuevo; nada de eso llego a nadie.
"""
from datetime import datetime, timezone

# Dias sin NINGUN raw nuevo (created_at) a partir de los cuales es problema.
# Sacado de huecos maximos en periodos sanos (Jul-Oct 2026, sin contar la
# caida del token BD 27 Ago-15 Sep): fotocasa 4d, milanuncios 5d, wallapop 5d,
# habitaclia 11d (~1 nuevo cada 2-3 dias pese a ~200 vistos/dia).
MAX_DAYS_WITHOUT_NEW = {
    'fotocasa': 5,
    'milanuncios': 6,
    'wallapop': 8,
    'habitaclia': 14,
    'idealista': 30,
}
DEFAULT_MAX_DAYS_WITHOUT_NEW = 7

# Caida brusca: found del run < DROP_RATIO * media diaria de los 7 dias previos.
DROP_RATIO = 0.3
DROP_MIN_AVG = 20


def check_portals(conn, portals, tenant_id=1, window_hours=3):
    """Devuelve (stats por portal, lista de problemas)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT portal, COUNT(*), COALESCE(SUM(found), 0), COALESCE(SUM(errors), 0)
        FROM raw.scraper_zone_runs
        WHERE scraped_at > NOW() - make_interval(hours => %s)
        GROUP BY portal
        """,
        [window_hours],
    )
    runs = {r[0]: {'zones': r[1], 'found': int(r[2]), 'errors': int(r[3])} for r in cur.fetchall()}

    cur.execute(
        """
        SELECT portal, AVG(found_day)
        FROM (
            SELECT portal, date_trunc('day', scraped_at) d, SUM(found) found_day
            FROM raw.scraper_zone_runs
            WHERE scraped_at > NOW() - make_interval(hours => %s) - INTERVAL '7 days'
              AND scraped_at <= NOW() - make_interval(hours => %s)
            GROUP BY 1, 2
        ) t
        GROUP BY portal
        """,
        [window_hours, window_hours],
    )
    avg7 = {r[0]: float(r[1] or 0) for r in cur.fetchall()}

    cur.execute(
        """
        SELECT portal, MAX(created_at)
        FROM raw.raw_listings
        WHERE tenant_id = %s
          -- wallapop guarda tambien las agencias descartadas (para no repagar
          -- el detalle): no cuentan como lead nuevo.
          AND raw_data->>'es_particular' IS DISTINCT FROM 'false'
        GROUP BY portal
        """,
        [tenant_id],
    )
    last_new = {r[0]: r[1] for r in cur.fetchall()}
    cur.close()

    now = datetime.now(timezone.utc)
    stats, problems = {}, []
    for p in portals:
        run = runs.get(p)
        last = last_new.get(p)
        days = (now - last).days if last else None
        limit = MAX_DAYS_WITHOUT_NEW.get(p, DEFAULT_MAX_DAYS_WITHOUT_NEW)
        stats[p] = {
            'zone_runs': run['zones'] if run else 0,
            'found': run['found'] if run else 0,
            'found_avg_7d': round(avg7.get(p, 0)),
            'days_without_new': days,
            'max_days_without_new': limit,
        }
        if not run:
            problems.append(f"{p}: sin filas en scraper_zone_runs en {window_hours}h (no corrio o peto antes de la 1a zona)")
        elif run['found'] == 0:
            problems.append(f"{p}: found=0 en {run['zones']} zonas (errors={run['errors']}), parser o bloqueo")
        elif avg7.get(p, 0) >= DROP_MIN_AVG and run['found'] < DROP_RATIO * avg7[p]:
            problems.append(f"{p}: caida de anuncios vistos, found={run['found']} vs media 7d {avg7[p]:.0f}")
        if days is None or days >= limit:
            problems.append(f"{p}: 0 leads nuevos en {days if days is not None else '?'} dias (umbral {limit})")
    return stats, problems


def notify_admins(conn, problems, run_url='', dedupe_hours=20, dry_run=False):
    """Notificacion in-app (campana del navbar) a cada superusuario activo.

    Una notificacion por portal (los problemas del mismo portal van juntos en
    el mensaje). Dedupe: si el usuario ya tiene un aviso de ese portal en
    `dedupe_hours`, no se repite (cron diario -> max 1/dia por portal aunque
    cambien los numeros). Devuelve [(user_id, titulo)] creados (o que se
    crearian en dry_run).
    """
    grouped = {}
    for problem in problems:
        grouped.setdefault(problem.split(':', 1)[0], []).append(problem)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.id, COALESCE(MIN(tu.tenant_id), 1)
        FROM auth_user u
        LEFT JOIN tenant_users tu ON tu.user_id = u.id
        WHERE u.is_superuser AND u.is_active
        GROUP BY u.id
        """
    )
    admins = cur.fetchall()
    created = []
    for key, items in grouped.items():
        prefix = f"Scraping {key}:"
        titulo = f"Scraping {items[0]}"[:200]
        mensaje = "\n".join(items) + "\nDetectado por scrape-neon.yml (publish_scrape_status.py)."
        for user_id, tenant_id in admins:
            cur.execute(
                """
                SELECT 1 FROM notifications_notification
                WHERE user_id = %s AND left(titulo, %s) = %s
                  AND created_at > NOW() - make_interval(hours => %s)
                LIMIT 1
                """,
                [user_id, len(prefix), prefix, dedupe_hours],
            )
            if cur.fetchone():
                continue
            created.append((user_id, titulo))
            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO notifications_notification
                        (tenant_id, user_id, tipo, titulo, mensaje, url, is_read, created_at)
                    VALUES (%s, %s, 'sistema', %s, %s, %s, false, NOW())
                    """,
                    [tenant_id, user_id, titulo, mensaje, run_url[:500]],
                )
    if not dry_run:
        conn.commit()
    cur.close()
    return created

#!/usr/bin/env python3
"""
Escribe scrape_status.json con el resultado del run (paso por portal +
anuncios vistos/nuevos en Neon en las ultimas 3h). El workflow lo publica en
la rama `ops-status` (un solo commit, force-push) y la rutina cloud de
Claude Code lo lee para decidir si hay que investigar. Sin secretos fuera
del workflow: la rutina solo necesita leer la rama.

Ademas de seen/new 3h aplica los checks de scrape_health (found=0 aunque
errors=0, N dias sin leads nuevos, caida vs media 7d) y crea una notificacion
in-app para los superusuarios (dedupe 1/dia por problema): Telegram no lo mira
nadie y habitaclia estuvo 3 semanas a 0 sin que se enterase nadie.

Env: DATABASE_URL, RUN_ID, PORTALS, JOB_STATUS, STEP_BD, STEP_<PORTAL>.
--dry-run: no escribe el JSON ni crea notificaciones (solo imprime).
--window-hours N: ventana del run (por defecto 3).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import psycopg2

from scrape_health import check_portals, notify_admins


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--window-hours", type=int, default=3)
    args = ap.parse_args()
    tenant_id = int(os.environ.get("TENANT_ID", "1"))
    portals = [p.strip() for p in os.environ.get("PORTALS", "").split(",") if p.strip()]
    status = {
        "run_id": os.environ.get("RUN_ID", ""),
        "run_url": os.environ.get("RUN_URL", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "job_status": os.environ.get("JOB_STATUS", ""),
        "bd_token": os.environ.get("STEP_BD", ""),
        "portals": {},
    }
    counts, health, health_problems, conn = {}, {}, [], None
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(
            """
            SELECT portal,
                   COUNT(*) FILTER (WHERE scraping_timestamp > NOW() - make_interval(hours => %s)),
                   COUNT(*) FILTER (WHERE created_at > NOW() - make_interval(hours => %s))
            FROM raw.raw_listings
            WHERE tenant_id = %s
            GROUP BY portal
            """,
            [args.window_hours, args.window_hours, tenant_id],
        )
        counts = {r[0]: {"seen_3h": r[1], "new_3h": r[2]} for r in cur.fetchall()}
        cur.close()
        health, health_problems = check_portals(conn, portals, tenant_id, args.window_hours)
    except Exception as e:  # el JSON debe salir siempre
        status["db_error"] = str(e)[:200]
    for p in portals:
        status["portals"][p] = {
            "step": os.environ.get(f"STEP_{p.upper()}", "not_run"),
            **counts.get(p, {"seen_3h": 0, "new_3h": 0}),
            **health.get(p, {}),
        }
    bad = []
    for p, v in status["portals"].items():
        if v["step"] not in ("success", "skipped"):
            bad.append(f"{p}: paso GitHub '{v['step']}'")
        elif v["seen_3h"] == 0 and not any(x.startswith(f"{p}:") for x in health_problems):
            bad.append(f"{p}: 0 anuncios vistos en raw_listings en {args.window_hours}h")
    bad += health_problems
    if status["bd_token"] not in ("", "success"):
        bad.append("brightdata_token: check_brightdata.py fallo (token caducado?)")
    if status["job_status"] not in ("", "success"):
        bad.append(f"job: {status['job_status']}")
    if "db_error" in status:
        bad.append(f"db: {status['db_error']}")
    status["ok"] = not bad
    status["problems"] = bad

    if conn is not None:
        try:
            created = notify_admins(conn, bad, status["run_url"], dry_run=args.dry_run)
            status["notified"] = len(created)
        except Exception as e:
            status["notify_error"] = str(e)[:200]
        conn.close()

    out = json.dumps(status, indent=2, ensure_ascii=False)
    if not args.dry_run:
        with open("scrape_status.json", "w", encoding="utf-8") as f:
            f.write(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

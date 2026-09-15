#!/usr/bin/env python3
"""
Escribe scrape_status.json con el resultado del run (paso por portal +
anuncios vistos/nuevos en Neon en las ultimas 3h). El workflow lo publica en
la rama `ops-status` (un solo commit, force-push) y la rutina cloud de
Claude Code lo lee para decidir si hay que investigar. Sin secretos fuera
del workflow: la rutina solo necesita leer la rama.

Env: DATABASE_URL, RUN_ID, PORTALS, JOB_STATUS, STEP_BD, STEP_<PORTAL>.
"""
import json
import os
import sys
from datetime import datetime, timezone

import psycopg2


def main() -> int:
    portals = [p.strip() for p in os.environ.get("PORTALS", "").split(",") if p.strip()]
    status = {
        "run_id": os.environ.get("RUN_ID", ""),
        "run_url": os.environ.get("RUN_URL", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "job_status": os.environ.get("JOB_STATUS", ""),
        "bd_token": os.environ.get("STEP_BD", ""),
        "portals": {},
    }
    counts = {}
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(
            """
            SELECT portal,
                   COUNT(*) FILTER (WHERE scraping_timestamp > NOW() - INTERVAL '3 hours'),
                   COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '3 hours')
            FROM raw.raw_listings
            GROUP BY portal
            """
        )
        counts = {r[0]: {"seen_3h": r[1], "new_3h": r[2]} for r in cur.fetchall()}
        conn.close()
    except Exception as e:  # el JSON debe salir siempre
        status["db_error"] = str(e)[:200]
    for p in portals:
        status["portals"][p] = {
            "step": os.environ.get(f"STEP_{p.upper()}", "not_run"),
            **counts.get(p, {"seen_3h": 0, "new_3h": 0}),
        }
    bad = [p for p, v in status["portals"].items()
           if v["step"] not in ("success", "skipped") or v["seen_3h"] == 0]
    if status["bd_token"] not in ("", "success"):
        bad.append("brightdata_token")
    if status["job_status"] not in ("", "success"):
        bad.append("job")
    status["ok"] = not bad
    status["problems"] = bad
    with open("scrape_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

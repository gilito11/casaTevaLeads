"""
Audit data quality of Scrapling-saved rows in raw.raw_listings.

Reports per portal/tenant:
- Total rows + recent rows
- Field completeness (% with non-empty/non-null values)
- Distribution: precio buckets, fotos count, descripcion length
- Particular vs Profesional ratio
- Sample 5 rows per portal for manual eyeball

Usage:
    python scripts/audit_scrapling_quality.py
    python scripts/audit_scrapling_quality.py --since 1h
    python scripts/audit_scrapling_quality.py --tenant 1 --portal idealista
"""
import argparse
import json
import os
import sys
from urllib.parse import urlparse

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, "backend", ".env"), override=False)
load_dotenv(os.path.join(ROOT, ".env"), override=False)


def connect():
    p = urlparse(os.environ["DATABASE_URL"])
    return psycopg2.connect(
        host=p.hostname,
        port=p.port or 5432,
        database=p.path.lstrip("/").split("?")[0],
        user=p.username,
        password=p.password,
        sslmode="require",
    )


FIELDS = [
    ("anuncio_id", "REQ"),
    ("titulo", "REQ"),
    ("precio", "REQ"),
    ("descripcion", "OPT"),
    ("habitaciones", "OPT"),
    ("metros", "OPT"),
    ("ubicacion", "OPT"),
    ("vendedor", "OPT"),
    ("telefono", "OPT"),
    ("fotos", "OPT"),
    ("zona_busqueda", "REQ"),
    ("url", "REQ"),
]


def stats_for(conn, portal: str, tenant_id: int, since: str):
    cur = conn.cursor()
    where = """
        WHERE portal = %s AND tenant_id = %s
          AND raw_data->>'scraper_type' = 'scrapling'
          AND scraping_timestamp > NOW() - INTERVAL %s
    """
    args = [portal, tenant_id, since]

    cur.execute(f"SELECT COUNT(*) FROM raw.raw_listings {where}", args)
    total = cur.fetchone()[0]
    if total == 0:
        cur.close()
        return {"total": 0}

    completeness = {}
    for field, _ in FIELDS:
        if field == "fotos":
            cur.execute(
                f"SELECT COUNT(*) FROM raw.raw_listings {where} "
                f"AND jsonb_array_length(COALESCE(raw_data->'fotos','[]'::jsonb)) > 0",
                args,
            )
        else:
            cur.execute(
                f"SELECT COUNT(*) FROM raw.raw_listings {where} "
                f"AND COALESCE(raw_data->>'{field}','')<>'' AND raw_data->>'{field}'<>'null'",
                args,
            )
        completeness[field] = cur.fetchone()[0]

    cur.execute(
        f"SELECT raw_data->>'es_particular', COUNT(*) FROM raw.raw_listings {where} GROUP BY 1",
        args,
    )
    es_part = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute(
        f"""
        SELECT
          MIN((raw_data->>'precio')::float),
          AVG((raw_data->>'precio')::float),
          MAX((raw_data->>'precio')::float),
          AVG(LENGTH(COALESCE(raw_data->>'descripcion',''))),
          AVG(jsonb_array_length(COALESCE(raw_data->'fotos','[]'::jsonb)))
        FROM raw.raw_listings {where}
        AND raw_data->>'precio' IS NOT NULL
        AND raw_data->>'precio' != ''
        AND raw_data->>'precio' ~ '^[0-9]+(\\.[0-9]+)?$'
        """,
        args,
    )
    precio_min, precio_avg, precio_max, desc_avg, fotos_avg = cur.fetchone() or (
        None, None, None, None, None,
    )

    cur.execute(
        f"""
        SELECT raw_data->>'anuncio_id', raw_data->>'titulo',
               raw_data->>'precio', raw_data->>'es_particular',
               raw_data->>'habitaciones', raw_data->>'metros',
               LENGTH(COALESCE(raw_data->>'descripcion','')),
               jsonb_array_length(COALESCE(raw_data->'fotos','[]'::jsonb)),
               raw_data->>'telefono', raw_data->>'vendedor', raw_data->>'ubicacion'
        FROM raw.raw_listings {where}
        ORDER BY scraping_timestamp DESC LIMIT 5
        """,
        args,
    )
    samples = []
    for r in cur.fetchall():
        samples.append({
            "anuncio_id": r[0],
            "titulo": (r[1] or "")[:60],
            "precio": r[2],
            "es_particular": r[3],
            "habitaciones": r[4],
            "metros": r[5],
            "descripcion_len": r[6],
            "fotos_count": r[7],
            "telefono": r[8] or "",
            "vendedor": (r[9] or "")[:40],
            "ubicacion": (r[10] or "")[:40],
        })

    cur.close()
    return {
        "total": total,
        "completeness_pct": {f: round(100 * completeness[f] / total, 1) for f, _ in FIELDS},
        "es_particular": es_part,
        "precio": {
            "min": precio_min,
            "avg": round(precio_avg, 0) if precio_avg else None,
            "max": precio_max,
        },
        "descripcion_avg_chars": round(desc_avg, 0) if desc_avg else None,
        "fotos_avg": round(fotos_avg, 1) if fotos_avg else None,
        "samples": samples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2 hours", help="Postgres interval, e.g. '30 minutes', '1 hour', '2 days'")
    ap.add_argument("--tenant", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--portal", nargs="+", default=["idealista", "fotocasa", "habitaclia", "milanuncios"])
    args = ap.parse_args()

    conn = connect()
    report = {}
    for tenant in args.tenant:
        report[f"tenant_{tenant}"] = {}
        for portal in args.portal:
            report[f"tenant_{tenant}"][portal] = stats_for(conn, portal, tenant, args.since)
    conn.close()

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

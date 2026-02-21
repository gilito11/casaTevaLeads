#!/usr/bin/env python3
"""Quick test: enqueue one milanuncios lead + process it to test login."""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def main():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])

    # 1. Check auto_contact_config
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM leads_auto_contact_config WHERE tenant_id = 1")
        config = cur.fetchone()
        if config:
            print(f"Config: contactar_milanuncios={config.get('contactar_milanuncios')}, "
                  f"solo_particulares={config.get('solo_particulares')}, "
                  f"score_minimo={config.get('score_minimo')}")
        else:
            print("No auto_contact_config for tenant 1!")

    # 2. Find a milanuncios lead to test with
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT lead_id, source_portal, listing_url, titulo, lead_score, es_particular
            FROM public_marts.dim_leads
            WHERE tenant_id = 1
              AND source_portal = 'milanuncios'
              AND listing_url IS NOT NULL
              AND listing_url != ''
              AND NOT EXISTS (
                  SELECT 1 FROM leads_contact_queue cq
                  WHERE cq.lead_id = lead_id AND cq.tenant_id = 1
              )
            ORDER BY lead_score DESC NULLS LAST
            LIMIT 5
        """)
        leads = cur.fetchall()
        print(f"\nAvailable milanuncios leads: {len(leads)}")
        for l in leads:
            print(f"  {l['lead_id']} score={l.get('lead_score')} particular={l.get('es_particular')} - {l.get('titulo','')[:60]}")

    if not leads:
        print("No milanuncios leads available to test!")
        conn.close()
        return 1

    # 3. Enqueue first lead
    lead = leads[0]
    message = "Hola, he visto su anuncio y me interesa. Podriamos hablar?"
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO leads_contact_queue
                (tenant_id, lead_id, portal, listing_url, titulo, mensaje,
                 estado, prioridad, mensaje_enviado, respondio, created_at, updated_at)
            VALUES (1, %s, 'milanuncios', %s, %s, %s, 'PENDIENTE', 0, FALSE, FALSE, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """, (lead['lead_id'], lead['listing_url'], (lead.get('titulo') or '')[:500], message))
    conn.commit()
    print(f"\nEnqueued lead {lead['lead_id']} for milanuncios contact test")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Quick test: diagnose milanuncios leads + enqueue one for contact test."""
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

    # 2. Diagnostic: count milanuncios leads in dim_leads
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE es_particular = TRUE) as particulares,
                   COUNT(*) FILTER (WHERE es_particular = FALSE) as profesionales,
                   COUNT(*) FILTER (WHERE es_particular IS NULL) as null_particular,
                   COUNT(*) FILTER (WHERE lead_score >= 30) as score_30plus,
                   AVG(lead_score) as avg_score
            FROM public_marts.dim_leads
            WHERE tenant_id = 1 AND source_portal = 'milanuncios'
        """)
        stats = cur.fetchone()
        print(f"\nMilanuncios leads in dim_leads:")
        print(f"  Total: {stats['total']}")
        print(f"  Particulares: {stats['particulares']}")
        print(f"  Profesionales: {stats['profesionales']}")
        print(f"  NULL particular: {stats['null_particular']}")
        print(f"  Score >= 30: {stats['score_30plus']}")
        print(f"  Avg score: {stats['avg_score']}")

    # 3. Check how many already in contact queue
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM leads_contact_queue
            WHERE tenant_id = 1 AND portal = 'milanuncios'
        """)
        queued = cur.fetchone()[0]
        print(f"  Already in contact queue: {queued}")

    # 4. Find ANY milanuncios lead (even already queued) to test with
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # First try: not already queued
        cur.execute("""
            SELECT lead_id, source_portal, listing_url, titulo, lead_score, es_particular
            FROM public_marts.dim_leads
            WHERE tenant_id = 1
              AND source_portal = 'milanuncios'
              AND listing_url IS NOT NULL AND listing_url != ''
              AND NOT EXISTS (
                  SELECT 1 FROM leads_contact_queue cq
                  WHERE cq.lead_id = lead_id AND cq.tenant_id = 1
              )
            ORDER BY lead_score DESC NULLS LAST
            LIMIT 3
        """)
        leads = cur.fetchall()

        if not leads:
            # Fallback: any milanuncios lead, even if already queued
            print("\nNo un-queued leads, trying any milanuncios lead...")
            cur.execute("""
                SELECT lead_id, source_portal, listing_url, titulo, lead_score, es_particular
                FROM public_marts.dim_leads
                WHERE tenant_id = 1
                  AND source_portal = 'milanuncios'
                  AND listing_url IS NOT NULL AND listing_url != ''
                ORDER BY lead_score DESC NULLS LAST
                LIMIT 3
            """)
            leads = cur.fetchall()

        print(f"\nCandidate leads: {len(leads)}")
        for l in leads:
            print(f"  {l['lead_id']} score={l.get('lead_score')} particular={l.get('es_particular')} - {(l.get('titulo') or '')[:60]}")

    if not leads:
        print("\nNO milanuncios leads at all in dim_leads! Check dbt model.")
        conn.close()
        return 0  # Don't fail workflow

    # 5. Enqueue first lead (delete old entry if exists)
    lead = leads[0]
    message = "Hola, he visto su anuncio y me interesa. Podriamos hablar?"
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM leads_contact_queue
            WHERE lead_id = %s AND tenant_id = 1 AND portal = 'milanuncios'
        """, (lead['lead_id'],))
        cur.execute("""
            INSERT INTO leads_contact_queue
                (tenant_id, lead_id, portal, listing_url, titulo, mensaje,
                 estado, prioridad, mensaje_enviado, respondio, created_at, updated_at)
            VALUES (1, %s, 'milanuncios', %s, %s, %s, 'PENDIENTE', 0, FALSE, FALSE, NOW(), NOW())
        """, (lead['lead_id'], lead['listing_url'], (lead.get('titulo') or '')[:500], message))
    conn.commit()
    print(f"\nEnqueued lead {lead['lead_id']} for milanuncios contact test")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

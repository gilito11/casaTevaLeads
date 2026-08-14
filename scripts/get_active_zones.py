#!/usr/bin/env python3
"""Imprime la lista de zonas activas (slugs de scraper) para un portal.

Fuente de verdad: tabla zonas_geograficas (activa=True + scrapear_<portal>).
La usa scrape-neon.yml para construir --zones del cron diario; activar una
zona desde el dashboard la mete aqui sin tocar el workflow.

Salida: slugs separados por coma en stdout (una linea). Si la BD no responde
o no hay filas, cae a la lista historica hardcodeada para no dejar el cron
sin zonas.

Uso: python scripts/get_active_zones.py --portal habitaclia [--tenant 1]
"""

import argparse
import os
import sys

# Lista del cron previa a la tabla (Lleida <=20km). Solo fallback.
FALLBACK_ZONES = (
    "lleida,alpicat,alcarras,torrefarrera,bell_lloc,termens,juneda,almacelles,"
    "almenar,mollerussa,mollerussa_rural,albatarrec,torre_serona,"
    "montoliu_de_lleida,alcoletge,sudanell,benavent_de_segria,rossello,"
    "artesa_de_lleida,corbins,vilanova_de_segria,alfes,sunyer,"
    "vilanova_de_la_barca,puigverd_de_lleida,torres_de_segre,alguaire,aspa,"
    "soses,menarguens,bellvis,sidamon,sarroca_de_lleida,aitona,fondarella,"
    "torrebesses,miralcamp,vallfogona_balaguer,gimenells"
)

PORTALES = ('habitaclia', 'fotocasa', 'milanuncios', 'idealista', 'wallapop')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--portal', required=True, choices=PORTALES)
    parser.add_argument('--tenant', type=int, default=int(os.environ.get('TENANT_ID', 1)))
    args = parser.parse_args()

    try:
        import psycopg2
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT slug FROM zonas_geograficas
                WHERE tenant_id = %s AND activa = TRUE AND scrapear_{args.portal} = TRUE
                ORDER BY slug
                """,
                (args.tenant,),
            )
            zones = [r[0] for r in cur.fetchall()]
        conn.close()
        if not zones:
            raise RuntimeError('zonas_geograficas sin filas activas para el tenant')
        print(','.join(zones))
    except Exception as e:
        print(f"get_active_zones: fallback por error BD: {e}", file=sys.stderr)
        print(FALLBACK_ZONES)


if __name__ == '__main__':
    main()

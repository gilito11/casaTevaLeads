#!/usr/bin/env python
"""
Script para ejecutar el scraper de Habitaclia.

Uses Camoufox (anti-detect Firefox) to bypass Imperva bot protection.
Falls back to Botasaurus Chrome if Camoufox is not available.

Uso:
    python run_habitaclia_scraper.py [--zones ZONE1 ZONE2] [--postgres] [--tenant-id=1]

Ejemplos:
    python run_habitaclia_scraper.py --zones salou --postgres
    python run_habitaclia_scraper.py --zones costa_daurada --postgres
    python run_habitaclia_scraper.py --zones baix_camp tarragones --postgres
"""

import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from scrapers.botasaurus_habitaclia import ZONAS_GEOGRAFICAS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Ejecutar scraper de Habitaclia',
    )
    parser.add_argument(
        '--zones',
        nargs='+',
        default=['tarragona_provincia'],
        help='Zonas a scrapear'
    )
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='ID del tenant (default: 1)'
    )
    parser.add_argument(
        '--postgres',
        action='store_true',
        help='Habilitar guardado en PostgreSQL'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Ejecutar en modo headless (default: True)'
    )
    parser.add_argument(
        '--list-zones',
        action='store_true',
        help='Listar zonas disponibles y salir'
    )
    parser.add_argument(
        '--botasaurus',
        action='store_true',
        help='Forzar uso de Botasaurus en vez de Camoufox'
    )

    args = parser.parse_args()

    if args.list_zones:
        print("\nZonas disponibles en Habitaclia:")
        print("-" * 50)
        print("\nPROVINCIAS:")
        for key, zona in ZONAS_GEOGRAFICAS.items():
            if zona.get('is_province'):
                print(f"  {key:25} - {zona['nombre']}")
        print("\nCOMARCAS:")
        for key, zona in ZONAS_GEOGRAFICAS.items():
            if 'composite' in zona:
                cities = ', '.join(zona['composite'][:3])
                if len(zona['composite']) > 3:
                    cities += '...'
                print(f"  {key:25} - {zona['nombre']} [{cities}]")
        print("\nCIUDADES:")
        for key, zona in ZONAS_GEOGRAFICAS.items():
            if 'url_slug' in zona and not zona.get('is_province'):
                print(f"  {key:25} - {zona['nombre']}")
        return

    # Validate zones
    for zone in args.zones:
        if zone not in ZONAS_GEOGRAFICAS:
            print(f"ERROR: Zona desconocida: {zone}")
            print(f"Usa --list-zones para ver zonas disponibles")
            sys.exit(1)

    # Choose scraper: Camoufox (default) or Botasaurus (fallback)
    use_camoufox = not args.botasaurus
    if use_camoufox:
        try:
            from scrapers.camoufox_habitaclia import CamoufoxHabitaclia
            scraper_name = "Camoufox"
        except ImportError:
            use_camoufox = False

    if not use_camoufox:
        scraper_name = "Botasaurus"

    print(f"\n{'='*60}")
    print(f"SCRAPER DE HABITACLIA ({scraper_name})")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"Zonas: {', '.join(args.zones)}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"{'='*60}\n")

    if use_camoufox:
        scraper = CamoufoxHabitaclia(
            zones=args.zones,
            tenant_id=args.tenant_id,
            headless=args.headless,
        )
        stats = scraper.scrape()
        print(f"\n{'='*60}")
        print("RESULTADOS")
        print(f"{'='*60}")
        print(f"Total anuncios encontrados: {stats['total_listings']}")
        print(f"Guardados: {stats['saved']}")
        print(f"Duplicados: {stats['duplicates']}")
        print(f"Errores: {stats['errors']}")
    else:
        # Botasaurus fallback
        from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia
        postgres_config = None
        if args.postgres:
            db_url = os.environ.get('DATABASE_URL', '')
            if db_url:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                is_remote = parsed.hostname and parsed.hostname != 'localhost'
                postgres_config = {
                    'host': parsed.hostname,
                    'port': parsed.port or 5432,
                    'database': parsed.path.lstrip('/'),
                    'user': parsed.username,
                    'password': parsed.password,
                    'sslmode': 'require' if is_remote else 'prefer'
                }
            else:
                postgres_config = {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'casa_teva_db',
                    'user': 'casa_teva',
                    'password': '',
                }

        with BotasaurusHabitaclia(
            tenant_id=args.tenant_id,
            zones=args.zones,
            postgres_config=postgres_config,
            headless=args.headless,
        ) as scraper:
            if args.postgres:
                stats = scraper.scrape_and_save()
                print(f"\n{'='*60}")
                print("RESULTADOS")
                print(f"{'='*60}")
                print(f"Total anuncios encontrados: {stats['total_listings']}")
                print(f"Filtrados (agencias): {stats['filtered_out']}")
                print(f"Guardados: {stats['saved']}")
                print(f"Errores: {stats['errors']}")
            else:
                listings = scraper.scrape()
                print(f"\nEncontrados {len(listings)} anuncios")
                for l in listings[:5]:
                    print(f"  - {l.get('titulo', 'N/A')[:50]}... | {l.get('precio')}€")


if __name__ == '__main__':
    main()

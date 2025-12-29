#!/usr/bin/env python
"""
Script para ejecutar el scraper de Pisos.com con Botasaurus.

Uso:
    python run_pisos_scraper.py [--zones ZONE1 ZONE2] [--postgres] [--tenant-id=1]

Ejemplos:
    python run_pisos_scraper.py --zones salou
    python run_pisos_scraper.py --zones tarragona_capital --postgres
    python run_pisos_scraper.py --zones salou cambrils reus --postgres
"""

import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.botasaurus_pisos import (
    BotasaurusPisos,
    ZONAS_GEOGRAFICAS,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Ejecutar scraper de Pisos.com (Botasaurus)',
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

    args = parser.parse_args()

    if args.list_zones:
        print("\nZonas disponibles en Pisos.com:")
        print("-" * 50)
        print("\nPROVINCIAS:")
        for key, zona in ZONAS_GEOGRAFICAS.items():
            if 'provincia' in key:
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
            if 'url_path' in zona and 'provincia' not in key:
                print(f"  {key:25} - {zona['nombre']}")
        return

    # Validate zones
    for zone in args.zones:
        if zone not in ZONAS_GEOGRAFICAS:
            print(f"ERROR: Zona desconocida: {zone}")
            print(f"Usa --list-zones para ver zonas disponibles")
            sys.exit(1)

    # PostgreSQL config
    postgres_config = None
    if args.postgres:
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url and 'azure' in db_url:
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            postgres_config = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path.lstrip('/'),
                'user': parsed.username,
                'password': parsed.password,
                'sslmode': 'require'
            }
        else:
            pg_host = 'postgres' if os.environ.get('DATABASE_URL') else 'localhost'
            postgres_config = {
                'host': pg_host,
                'port': 5432,
                'database': 'casa_teva_db',
                'user': 'casa_teva',
                'password': 'casateva2024'
            }

    print(f"\n{'='*60}")
    print("SCRAPER DE PISOS.COM (Botasaurus)")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"Zonas: {', '.join(args.zones)}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"{'='*60}\n")

    with BotasaurusPisos(
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
            print(f"{stats['saved']} leads guardados en PostgreSQL")
        else:
            listings = scraper.scrape()
            print(f"\nEncontrados {len(listings)} anuncios")
            for l in listings[:5]:
                print(f"  - {l.get('titulo', 'N/A')[:50]}... | {l.get('precio')}€")


if __name__ == '__main__':
    main()

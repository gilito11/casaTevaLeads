#!/usr/bin/env python
"""
Script para ejecutar el scraper de Wallapop Inmobiliaria.

Incluye sistema de blacklist para filtrar inmobiliarias encubiertas.

Uso:
    python run_wallapop_scraper.py [opciones]

Ejemplos:
    # Scrapear Barcelona (default)
    python run_wallapop_scraper.py

    # Scrapear Lleida y Tarragona
    python run_wallapop_scraper.py --zones lleida tarragona

    # Con radio de 50km
    python run_wallapop_scraper.py --zones salou --distance 50

    # Añadir usuario a blacklist
    python run_wallapop_scraper.py --blacklist "InmobiliariaX" "OtroUsuario"
"""

import argparse
import os
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scrapers.wallapop_scraper import WallapopScraper, ZONAS_WALLAPOP, USUARIOS_BLACKLIST_INICIAL


def main():
    parser = argparse.ArgumentParser(
        description='Ejecutar scraper de Wallapop Inmobiliaria',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--zones',
        nargs='+',
        default=['barcelona'],
        help='Zonas a scrapear (default: barcelona). Use --list-zones para ver disponibles.'
    )
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='ID del tenant (default: 1)'
    )
    parser.add_argument(
        '--precio-min',
        type=int,
        default=5000,
        help='Precio mínimo en euros (default: 5000)'
    )
    parser.add_argument(
        '--distance',
        type=int,
        default=30,
        help='Radio de búsqueda en km (default: 30)'
    )
    parser.add_argument(
        '--blacklist',
        nargs='+',
        default=[],
        help='Usuarios adicionales a añadir a la blacklist'
    )
    parser.add_argument(
        '--minio',
        action='store_true',
        help='Habilitar guardado en MinIO'
    )
    parser.add_argument(
        '--postgres',
        action='store_true',
        help='Habilitar guardado en PostgreSQL'
    )
    parser.add_argument(
        '--list-zones',
        action='store_true',
        help='Listar zonas disponibles'
    )
    parser.add_argument(
        '--show-blacklist',
        action='store_true',
        help='Mostrar usuarios en blacklist inicial'
    )

    args = parser.parse_args()

    if args.list_zones:
        print("\nZonas disponibles para Wallapop:")
        print("-" * 40)
        for key, zona in ZONAS_WALLAPOP.items():
            print(f"  {key:15} - {zona['nombre']}")
        return

    if args.show_blacklist:
        print("\nUsuarios en blacklist inicial:")
        print("-" * 40)
        for usuario in USUARIOS_BLACKLIST_INICIAL:
            print(f"  - {usuario}")
        print(f"\nTotal: {len(USUARIOS_BLACKLIST_INICIAL)} usuarios")
        return

    # Validar zonas
    zonas_validas = []
    for zona in args.zones:
        if zona in ZONAS_WALLAPOP:
            zonas_validas.append(zona)
        else:
            print(f"ADVERTENCIA: Zona '{zona}' no encontrada para Wallapop, ignorando...")

    if not zonas_validas:
        print("ERROR: Ninguna zona válida especificada.")
        print(f"Zonas disponibles: {', '.join(sorted(ZONAS_WALLAPOP.keys()))}")
        return

    args.zones = zonas_validas

    # Configuración
    filters = {'precio_min': args.precio_min}

    minio_config = None
    if args.minio:
        minio_config = {
            'endpoint': 'localhost:9000',
            'access_key': 'minioadmin',
            'secret_key': 'minioadmin',
            'secure': False
        }

    postgres_config = None
    if args.postgres:
        db_url = os.environ.get('DATABASE_URL', '')
        pg_host = 'postgres' if '@postgres' in db_url else 'localhost'
        postgres_config = {
            'host': pg_host,
            'port': 5432,
            'database': 'casa_teva_db',
            'user': 'casa_teva',
            'password': 'casateva2024'
        }

    # Mostrar configuración
    print(f"\n{'='*60}")
    print("SCRAPER DE WALLAPOP INMOBILIARIA")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"Zonas a scrapear:")
    for zona_key in args.zones:
        zona_info = ZONAS_WALLAPOP.get(zona_key, {})
        print(f"  - {zona_info.get('nombre', zona_key)}")
    print(f"Radio de búsqueda: {args.distance} km")
    print(f"Precio mínimo: {args.precio_min:,} €")
    print(f"Blacklist usuarios extra: {args.blacklist if args.blacklist else 'Ninguno'}")
    print(f"MinIO: {'Habilitado' if args.minio else 'Deshabilitado'}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"{'='*60}\n")

    # Ejecutar
    process = CrawlerProcess(get_project_settings())
    process.crawl(
        WallapopScraper,
        tenant_id=args.tenant_id,
        zones=args.zones,
        filters=filters,
        distance_km=args.distance,
        usuarios_blacklist_extra=args.blacklist,
        minio_config=minio_config,
        postgres_config=postgres_config
    )
    process.start()


if __name__ == '__main__':
    main()

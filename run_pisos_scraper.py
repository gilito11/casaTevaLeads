#!/usr/bin/env python
"""
Script para ejecutar el scraper de Pisos.com.

Uso:
    python run_pisos_scraper.py [--tenant-id=1] [--zones=tarragona_capital] [--postgres]

Ejemplos:
    # Ejecutar sin guardar (solo logs)
    python run_pisos_scraper.py

    # Ejecutar para Tarragona capital
    python run_pisos_scraper.py --zones=tarragona_capital

    # Ejecutar para múltiples zonas
    python run_pisos_scraper.py --zones=salou,cambrils,reus

    # Ejecutar con PostgreSQL
    python run_pisos_scraper.py --postgres

Zonas disponibles:
    lleida_capital, lleida_provincia, tarragona_capital, tarragona_provincia,
    salou, cambrils, reus, vendrell, calafell, torredembarra, altafulla, valls,
    tortosa, amposta, barcelona_capital
"""

import sys
import os
import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scrapers.pisos_scraper import PisosScraper, ZONAS_PISOS


def main():
    """Función principal para ejecutar el scraper"""

    # Parsear argumentos
    parser = argparse.ArgumentParser(
        description='Ejecutar scraper de Pisos.com',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Zonas disponibles:
  lleida_capital     - Lleida Capital
  lleida_provincia   - Lleida Provincia
  tarragona_capital  - Tarragona Capital
  tarragona_provincia - Tarragona Provincia
  salou              - Salou
  cambrils           - Cambrils
  reus               - Reus
  vendrell           - El Vendrell
  calafell           - Calafell
  torredembarra      - Torredembarra
  valls              - Valls
  tortosa            - Tortosa
  amposta            - Amposta

Ejemplos:
  python run_pisos_scraper.py --zones salou cambrils
  python run_pisos_scraper.py --zones tarragona_capital --postgres
        """
    )

    parser.add_argument(
        '--zones',
        nargs='+',
        default=['tarragona_capital'],
        help='Zonas a scrapear (default: tarragona_capital)'
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
        default=None,
        help='Precio mínimo en euros'
    )
    parser.add_argument(
        '--precio-max',
        type=int,
        default=None,
        help='Precio máximo en euros'
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
        help='Listar todas las zonas disponibles y salir'
    )

    args = parser.parse_args()

    # Si piden listar zonas, mostrar y salir
    if args.list_zones:
        print("\nZonas geográficas disponibles para Pisos.com:")
        print("-" * 50)
        for key, zona in ZONAS_PISOS.items():
            print(f"  {key:20} - {zona['nombre']}")
        print()
        return

    # Validar zonas
    for zone in args.zones:
        if zone not in ZONAS_PISOS:
            print(f"ERROR: Zona desconocida: {zone}")
            print(f"Zonas disponibles: {', '.join(ZONAS_PISOS.keys())}")
            sys.exit(1)

    # Configuración de filtros
    filters = {}
    if args.precio_min:
        filters['precio_min'] = args.precio_min
    if args.precio_max:
        filters['precio_max'] = args.precio_max

    # Configuración de MinIO (si está habilitado)
    minio_config = None
    if args.minio:
        minio_config = {
            'endpoint': 'localhost:9000',
            'access_key': 'minioadmin',
            'secret_key': 'minioadmin',
            'secure': False
        }

    # Configuración de PostgreSQL (si está habilitado)
    # Usa DATABASE_URL si está disponible (Azure), sino usa config local (Docker)
    postgres_config = None
    if args.postgres:
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url and 'azure' in db_url:
            # Parsear DATABASE_URL de Azure
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
            # Config local (Docker)
            pg_host = 'postgres' if db_url and '@postgres' in db_url else 'localhost'
            postgres_config = {
                'host': pg_host,
                'port': 5432,
                'database': 'casa_teva_db',
                'user': 'casa_teva',
                'password': 'casateva2024'
            }

    # Mostrar configuración
    print(f"\n{'='*60}")
    print("SCRAPER DE PISOS.COM")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"Zonas a scrapear:")
    for zona_key in args.zones:
        zona_info = ZONAS_PISOS.get(zona_key, {})
        print(f"  - {zona_info.get('nombre', zona_key)}")
    if filters:
        if filters.get('precio_min'):
            print(f"Precio mínimo: {filters['precio_min']:,} €")
        if filters.get('precio_max'):
            print(f"Precio máximo: {filters['precio_max']:,} €")
    print(f"MinIO: {'Habilitado' if args.minio else 'Deshabilitado'}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"{'='*60}\n")

    # Configurar Scrapy
    process = CrawlerProcess(get_project_settings())

    # Ejecutar spider
    process.crawl(
        PisosScraper,
        tenant_id=args.tenant_id,
        zones=args.zones,
        filters=filters,
        minio_config=minio_config,
        postgres_config=postgres_config
    )

    process.start()


if __name__ == '__main__':
    main()

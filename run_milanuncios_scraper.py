#!/usr/bin/env python
"""
Script para ejecutar el scraper de Milanuncios.

Uso:
    python run_milanuncios_scraper.py [opciones]

Zonas disponibles:
    - la_bordeta: La Bordeta, Lleida
    - lleida_ciudad: Lleida capital
    - tarragona_ciudad: Tarragona capital
    - salou: Salou
    - cambrils: Cambrils
    - costa_dorada: Costa Dorada (Salou centro)
    - reus: Reus

Ejemplos:
    # Scrapear La Bordeta (default)
    python run_milanuncios_scraper.py

    # Scrapear Salou y Tarragona
    python run_milanuncios_scraper.py --zones salou tarragona_ciudad

    # Scrapear con filtro de precio y radio de 15km
    python run_milanuncios_scraper.py --zones salou --precio-min 50000 --precio-max 200000 --distance 15000

    # Scrapear todas las zonas de Tarragona
    python run_milanuncios_scraper.py --zones salou cambrils tarragona_ciudad reus

    # Guardar en MinIO y PostgreSQL
    python run_milanuncios_scraper.py --zones la_bordeta --minio --postgres
"""

import argparse
import os
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scrapers.milanuncios_scraper import MilanunciosScraper, ZONAS_GEOGRAFICAS


def main():
    """Función principal para ejecutar el scraper"""

    # Parsear argumentos
    parser = argparse.ArgumentParser(
        description='Ejecutar scraper de Milanuncios',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Zonas disponibles:
  la_bordeta      - La Bordeta, Lleida
  lleida_ciudad   - Lleida capital
  tarragona_ciudad - Tarragona capital
  salou           - Salou
  cambrils        - Cambrils
  costa_dorada    - Costa Dorada (Salou centro)
  reus            - Reus

Ejemplos:
  python run_milanuncios_scraper.py --zones salou tarragona_ciudad
  python run_milanuncios_scraper.py --zones la_bordeta --precio-min 50000 --distance 15000
        """
    )

    parser.add_argument(
        '--zones',
        nargs='+',
        default=['la_bordeta'],
        choices=list(ZONAS_GEOGRAFICAS.keys()),
        help='Zonas a scrapear (default: la_bordeta)'
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
        '--precio-max',
        type=int,
        default=None,
        help='Precio máximo en euros (default: sin límite)'
    )
    parser.add_argument(
        '--distance',
        type=int,
        default=20000,
        help='Radio de búsqueda en metros (default: 20000 = 20km)'
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
        print("\nZonas geográficas disponibles:")
        print("-" * 50)
        for key, zona in ZONAS_GEOGRAFICAS.items():
            print(f"  {key:18} - {zona['nombre']}")
            print(f"                     Coords: ({zona['latitude']}, {zona['longitude']})")
            print(f"                     Provincia ID: {zona['geoProvinceId']}")
        print()
        return

    # Configuración de filtros
    filters = {
        'precio_min': args.precio_min,
    }
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
    # Usa 'postgres' como host si DATABASE_URL contiene @postgres (Docker)
    # o 'localhost' para desarrollo local
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
    print("SCRAPER DE MILANUNCIOS")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"Zonas a scrapear:")
    for zona_key in args.zones:
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
        print(f"  - {zona_info.get('nombre', zona_key)}")
    print(f"Radio de búsqueda: {args.distance / 1000:.1f} km")
    print(f"Precio mínimo: {args.precio_min:,} €")
    print(f"Precio máximo: {args.precio_max:,} €" if args.precio_max else "Precio máximo: Sin límite")
    print(f"MinIO: {'Habilitado' if args.minio else 'Deshabilitado'}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"{'='*60}\n")

    # Configurar Scrapy
    process = CrawlerProcess(get_project_settings())

    # Ejecutar spider
    process.crawl(
        MilanunciosScraper,
        tenant_id=args.tenant_id,
        zones=args.zones,
        filters=filters,
        distance=args.distance,
        minio_config=minio_config,
        postgres_config=postgres_config
    )

    process.start()


if __name__ == '__main__':
    main()

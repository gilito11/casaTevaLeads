#!/usr/bin/env python
"""
Script para ejecutar todos los scrapers en todas las zonas configuradas.

Uso:
    python run_all_scrapers.py [--minio] [--postgres]

Ejemplos:
    # Ejecutar sin guardar (solo logs)
    python run_all_scrapers.py

    # Ejecutar guardando en PostgreSQL
    python run_all_scrapers.py --postgres

    # Ejecutar guardando en MinIO y PostgreSQL
    python run_all_scrapers.py --minio --postgres
"""

import sys
import argparse
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scrapers.milanuncios_scraper import MilanunciosScraper, ZONAS_GEOGRAFICAS

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Zonas por defecto para scrapear (las más comunes en Cataluña)
ZONAS_DEFAULT = [
    'tarragona_ciudad',
    'tarragona_provincia',
    'reus',
    'salou',
    'cambrils',
    'lleida_ciudad',
]


def main():
    """Función principal para ejecutar todos los scrapers"""

    parser = argparse.ArgumentParser(description='Ejecutar todos los scrapers')
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='ID del tenant (default: 1)'
    )
    parser.add_argument(
        '--zones',
        type=str,
        default=None,
        help='Zonas específicas separadas por coma (default: todas las zonas por defecto)'
    )
    parser.add_argument(
        '--all-zones',
        action='store_true',
        help='Scrapear TODAS las zonas disponibles'
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
        help='Listar zonas disponibles y salir'
    )

    args = parser.parse_args()

    # Listar zonas disponibles
    if args.list_zones:
        print("\n=== Zonas disponibles para Milanuncios ===\n")
        for key, config in ZONAS_GEOGRAFICAS.items():
            print(f"  {key:25} -> {config['nombre']}")
        print(f"\n=== Zonas por defecto ===\n")
        for z in ZONAS_DEFAULT:
            if z in ZONAS_GEOGRAFICAS:
                print(f"  {z}")
        sys.exit(0)

    # Determinar zonas a scrapear
    if args.all_zones:
        zones = list(ZONAS_GEOGRAFICAS.keys())
    elif args.zones:
        zones = [z.strip() for z in args.zones.split(',')]
        # Validar zonas
        for zone in zones:
            if zone not in ZONAS_GEOGRAFICAS:
                print(f"ERROR: Zona desconocida: {zone}")
                print(f"Usa --list-zones para ver las zonas disponibles")
                sys.exit(1)
    else:
        zones = ZONAS_DEFAULT

    # Filtros de precio
    filters = {
        "filtros_precio": {
            "min": 5000,
            "max": 2000000
        }
    }

    # Configuración de MinIO y PostgreSQL
    minio_config = None
    postgres_config = None

    if args.minio:
        import os
        minio_config = {
            'endpoint': os.environ.get('MINIO_ENDPOINT', 'localhost:9000'),
            'access_key': os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
            'secret_key': os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
            'bucket': os.environ.get('MINIO_BUCKET', 'raw-scraping'),
        }

    if args.postgres:
        import os
        postgres_config = {
            'host': os.environ.get('POSTGRES_HOST', 'localhost'),
            'port': os.environ.get('POSTGRES_PORT', '5432'),
            'dbname': os.environ.get('POSTGRES_DB', 'casa_teva'),
            'user': os.environ.get('POSTGRES_USER', 'postgres'),
            'password': os.environ.get('POSTGRES_PASSWORD', ''),
        }

    # Mostrar configuración
    zone_names = [ZONAS_GEOGRAFICAS.get(z, {}).get('nombre', z) for z in zones]
    print(f"\n{'='*60}")
    print(f"SCRAPING MASIVO - {len(zones)} zonas")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"MinIO: {'Habilitado' if args.minio else 'Deshabilitado'}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"\nZonas a scrapear:")
    for i, z in enumerate(zone_names, 1):
        print(f"  {i}. {z}")
    print(f"{'='*60}\n")

    # Obtener settings de Scrapy
    settings = get_project_settings()

    # Aumentar delay para evitar bloqueos
    settings['DOWNLOAD_DELAY'] = 7  # 7 segundos entre requests

    # Crear proceso de Scrapy
    process = CrawlerProcess(settings)

    # Solo Milanuncios por ahora (los otros están bloqueados)
    process.crawl(
        MilanunciosScraper,
        tenant_id=args.tenant_id,
        zones=zones,
        filters=filters,
        minio_config=minio_config,
        postgres_config=postgres_config,
    )

    # Ejecutar
    logger.info("Iniciando scraping masivo...")
    process.start()

    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETADO")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

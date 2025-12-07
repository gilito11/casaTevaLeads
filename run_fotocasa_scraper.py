#!/usr/bin/env python
"""
Script para ejecutar el scraper de Fotocasa.

Uso:
    python run_fotocasa_scraper.py [--tenant-id=1] [--minio] [--postgres]

Ejemplos:
    # Ejecutar sin guardar (solo logs)
    python run_fotocasa_scraper.py

    # Ejecutar con MinIO y PostgreSQL
    python run_fotocasa_scraper.py --minio --postgres

    # Ejecutar para un tenant específico
    python run_fotocasa_scraper.py --tenant-id=2 --minio --postgres
"""

import sys
import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scrapers.fotocasa_scraper import FotocasaScraper


def main():
    """Función principal para ejecutar el scraper"""

    # Parsear argumentos
    parser = argparse.ArgumentParser(description='Ejecutar scraper de Fotocasa')
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='ID del tenant (default: 1)'
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

    args = parser.parse_args()

    # Configuración de zonas y filtros
    zones = {
        "lleida_ciudad": {
            "enabled": True,
            "codigos_postales": ["25001", "25002", "25003", "25004", "25005", "25006", "25007", "25008"]
        }
    }

    filters = {
        "filtros_precio": {
            "min": 50000,
            "max": 1000000
        }
    }

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
    postgres_config = None
    if args.postgres:
        postgres_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'casa_teva_db',
            'user': 'casa_teva',
            'password': 'casateva2024'
        }

    # Configurar Scrapy
    process = CrawlerProcess(get_project_settings())

    # Ejecutar spider
    process.crawl(
        FotocasaScraper,
        tenant_id=args.tenant_id,
        zones=zones,
        filters=filters,
        minio_config=minio_config,
        postgres_config=postgres_config
    )

    print(f"\n{'='*60}")
    print(f"Iniciando scraper de Fotocasa")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"MinIO: {'Habilitado' if args.minio else 'Deshabilitado'}")
    print(f"PostgreSQL: {'Habilitado' if args.postgres else 'Deshabilitado'}")
    print(f"{'='*60}\n")

    process.start()


if __name__ == '__main__':
    main()

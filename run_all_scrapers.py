#!/usr/bin/env python
"""
Script para ejecutar todos los scrapers en todas las zonas configuradas.

Uso:
    python run_all_scrapers.py [--postgres] [--zones ZONAS]

Ejemplos:
    # Ejecutar sin guardar (solo logs)
    python run_all_scrapers.py

    # Ejecutar guardando en PostgreSQL
    python run_all_scrapers.py --postgres

    # Ejecutar zonas específicas
    python run_all_scrapers.py --zones salou,cambrils --postgres
"""

import sys
import argparse
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from scrapers.milanuncios_scraper import MilanunciosScraper, ZONAS_GEOGRAFICAS
from scrapers.pisos_scraper import PisosScraper, ZONAS_PISOS

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Zonas por defecto para scrapear (las más comunes en Cataluña)
ZONAS_DEFAULT = [
    'tarragona_ciudad',
    'tarragona_30km',  # Cubre área amplia alrededor de Tarragona
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

    # Configuración de PostgreSQL
    postgres_config = None

    if args.postgres:
        import os
        postgres_config = {
            'host': os.environ.get('POSTGRES_HOST', 'localhost'),
            'port': os.environ.get('POSTGRES_PORT', '5432'),
            'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
            'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
            'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
        }

    # Mostrar configuración
    zone_names = [ZONAS_GEOGRAFICAS.get(z, {}).get('nombre', z) for z in zones]
    print(f"\n{'='*60}")
    print(f"SCRAPING MASIVO - {len(zones)} zonas")
    print(f"{'='*60}")
    print(f"Tenant ID: {args.tenant_id}")
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

    # Milanuncios
    process.crawl(
        MilanunciosScraper,
        tenant_id=args.tenant_id,
        zones=zones,
        filters=filters,
        postgres_config=postgres_config,
    )

    # Pisos.com - mapear zonas de Milanuncios a zonas de Pisos
    # Solo ejecutar si hay zonas equivalentes en Pisos.com
    zona_mapping = {
        'tarragona_ciudad': 'tarragona_capital',
        'tarragona_30km': 'tarragona_provincia',
        'reus': 'reus',
        'salou': 'salou',
        'cambrils': 'cambrils',
        'lleida_ciudad': 'lleida_capital',
    }
    pisos_zones = []
    for z in zones:
        if z in zona_mapping and zona_mapping[z] in ZONAS_PISOS:
            pisos_zones.append(zona_mapping[z])

    if pisos_zones:
        logger.info(f"Ejecutando Pisos.com en zonas: {pisos_zones}")
        process.crawl(
            PisosScraper,
            tenant_id=args.tenant_id,
            zones=pisos_zones,
            filters={},
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

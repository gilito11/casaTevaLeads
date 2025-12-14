"""
Assets de Dagster para el proceso de scraping de portales inmobiliarios.

Define los assets para:
- Scraping de portales (Fotocasa, Milanuncios, Wallapop)
- Carga en Data Lake (MinIO)
- Carga en PostgreSQL (raw layer)
"""

import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Any

from dagster import asset, AssetExecutionContext, MetadataValue, Output

from casa_teva_pipeline.resources.minio_resource import MinIOResource
from casa_teva_pipeline.resources.postgres_resource import PostgresResource


logger = logging.getLogger(__name__)


@asset(
    description="Ejecuta scraper de Fotocasa y guarda listings en Data Lake (MinIO)",
    compute_kind="python",
    group_name="scraping",
)
def bronze_fotocasa_listings(
    context: AssetExecutionContext,
    minio: MinIOResource
) -> Output[Dict[str, Any]]:
    """
    Ejecuta el scraper de Fotocasa y guarda los resultados en MinIO.

    Este asset:
    1. Ejecuta FotocasaScraper usando Scrapy
    2. Guarda JSONs de listings en bronze/tenant_1/fotocasa/{fecha}/
    3. Retorna metadata con número de listings y paths

    Returns:
        Dict con metadata del scraping
    """
    context.log.info("Iniciando scraping de Fotocasa...")

    # Configuración del tenant
    tenant_id = 1
    fecha = datetime.now().strftime('%Y-%m-%d')

    try:
        # Ejecutar scraper de Fotocasa usando subprocess
        # NOTA: Esto ejecuta el scraper y guarda directamente en MinIO
        result = subprocess.run(
            [
                'python',
                'run_fotocasa_scraper.py',
                f'--tenant-id={tenant_id}',
                '--minio',
            ],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hora timeout
        )

        if result.returncode != 0:
            context.log.error(f"Error en scraper: {result.stderr}")
            raise Exception(f"Scraper falló con código {result.returncode}")

        context.log.info("Scraping completado exitosamente")

        # Listar archivos creados en MinIO
        prefix = f"bronze/tenant_{tenant_id}/fotocasa/{fecha}/"
        files = minio.list_files(prefix=prefix)

        num_listings = len(files)

        context.log.info(f"Scrapeados {num_listings} listings de Fotocasa")

        # Preparar metadata
        metadata = {
            'tenant_id': tenant_id,
            'portal': 'fotocasa',
            'fecha': fecha,
            'num_listings': num_listings,
            'paths': files,
            'prefix': prefix,
        }

        return Output(
            value=metadata,
            metadata={
                'num_listings': MetadataValue.int(num_listings),
                'portal': MetadataValue.text('fotocasa'),
                'fecha': MetadataValue.text(fecha),
                'paths_sample': MetadataValue.text('\n'.join(files[:5])),  # Primeros 5
            }
        )

    except subprocess.TimeoutExpired:
        context.log.error("Scraper excedió el timeout de 1 hora")
        raise

    except Exception as e:
        context.log.error(f"Error ejecutando scraper: {e}")
        raise


@asset(
    description="Carga listings desde MinIO a PostgreSQL raw.raw_listings",
    compute_kind="python",
    group_name="scraping",
)
def raw_postgres_listings(
    context: AssetExecutionContext,
    minio: MinIOResource,
    postgres: PostgresResource,
    bronze_fotocasa_listings: Dict[str, Any]
) -> Output[int]:
    """
    Lee JSONs de MinIO y los carga en PostgreSQL raw.raw_listings.

    Este asset:
    1. Lee todos los JSONs del prefijo en MinIO
    2. Los inserta en raw.raw_listings usando bulk insert
    3. Retorna número de registros cargados

    Args:
        bronze_fotocasa_listings: Metadata del asset upstream

    Returns:
        Número de registros insertados
    """
    context.log.info("Iniciando carga a PostgreSQL...")

    tenant_id = bronze_fotocasa_listings['tenant_id']
    portal = bronze_fotocasa_listings['portal']
    paths = bronze_fotocasa_listings['paths']

    if not paths:
        context.log.warning("No hay listings para cargar")
        return Output(value=0, metadata={'num_loaded': MetadataValue.int(0)})

    # Preparar datos para bulk insert
    listings_to_insert = []

    for path in paths:
        try:
            # Leer JSON de MinIO
            raw_data = minio.read_json(path)

            if raw_data:
                listings_to_insert.append({
                    'tenant_id': tenant_id,
                    'portal': portal,
                    'data_lake_path': path,
                    'raw_data': raw_data
                })

        except Exception as e:
            context.log.error(f"Error leyendo {path}: {e}")

    # Insertar en PostgreSQL usando bulk insert
    num_loaded = postgres.bulk_insert_raw_listings(listings_to_insert)

    context.log.info(f"Cargados {num_loaded} listings en PostgreSQL")

    return Output(
        value=num_loaded,
        metadata={
            'num_loaded': MetadataValue.int(num_loaded),
            'num_errors': MetadataValue.int(len(paths) - num_loaded),
            'portal': MetadataValue.text(portal),
        }
    )


@asset(
    description="Scraping de Milanuncios (placeholder)",
    compute_kind="python",
    group_name="scraping",
)
def bronze_milanuncios_listings(
    context: AssetExecutionContext
) -> Output[Dict[str, Any]]:
    """
    Placeholder para scraper de Milanuncios.

    TODO: Implementar cuando el scraper esté listo.
    """
    context.log.info("Scraper de Milanuncios - Por implementar")

    metadata = {
        'tenant_id': 1,
        'portal': 'milanuncios',
        'num_listings': 0,
        'paths': [],
    }

    return Output(
        value=metadata,
        metadata={
            'status': MetadataValue.text('Not implemented'),
        }
    )


@asset(
    description="Scraping de Wallapop (placeholder)",
    compute_kind="python",
    group_name="scraping",
)
def bronze_wallapop_listings(
    context: AssetExecutionContext
) -> Output[Dict[str, Any]]:
    """
    Placeholder para scraper de Wallapop.

    TODO: Implementar cuando el scraper esté listo.
    """
    context.log.info("Scraper de Wallapop - Por implementar")

    metadata = {
        'tenant_id': 1,
        'portal': 'wallapop',
        'num_listings': 0,
        'paths': [],
    }

    return Output(
        value=metadata,
        metadata={
            'status': MetadataValue.text('Not implemented'),
        }
    )


@asset(
    description="Estadísticas de scraping consolidadas",
    compute_kind="python",
    group_name="reporting",
)
def scraping_stats(
    context: AssetExecutionContext,
    postgres: PostgresResource,
    bronze_fotocasa_listings: Dict[str, Any],
    raw_postgres_listings: int
) -> Output[Dict[str, Any]]:
    """
    Genera estadísticas consolidadas del proceso de scraping.

    Args:
        bronze_fotocasa_listings: Metadata de Fotocasa
        raw_postgres_listings: Número de registros cargados

    Returns:
        Dict con estadísticas consolidadas
    """
    context.log.info("Generando estadísticas de scraping...")

    # Obtener último timestamp
    tenant_id = bronze_fotocasa_listings['tenant_id']
    portal = bronze_fotocasa_listings['portal']

    last_scraping = postgres.get_latest_scraping_timestamp(tenant_id, portal)

    stats = {
        'fecha': bronze_fotocasa_listings['fecha'],
        'portales': {
            'fotocasa': {
                'scrapeados': bronze_fotocasa_listings['num_listings'],
                'cargados': raw_postgres_listings,
            }
        },
        'total_scrapeados': bronze_fotocasa_listings['num_listings'],
        'total_cargados': raw_postgres_listings,
        'ultimo_scraping': last_scraping,
    }

    return Output(
        value=stats,
        metadata={
            'total_scrapeados': MetadataValue.int(stats['total_scrapeados']),
            'total_cargados': MetadataValue.int(stats['total_cargados']),
            'ultimo_scraping': MetadataValue.text(last_scraping or 'N/A'),
        }
    )

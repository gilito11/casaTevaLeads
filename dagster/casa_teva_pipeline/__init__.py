"""
Pipeline de Dagster para Casa Teva.

Define todos los assets, resources, schedules y jobs del sistema.
"""
import os

from dagster import (
    Definitions,
    define_asset_job,
    AssetSelection,
    load_assets_from_modules,
    ScheduleDefinition,
    DefaultScheduleStatus,
)

from casa_teva_pipeline.assets import scraping_assets
from casa_teva_pipeline.resources.minio_resource import MinIOResource
from casa_teva_pipeline.resources.postgres_resource import PostgresResource


# Cargar todos los assets del módulo scraping_assets
all_assets = load_assets_from_modules([scraping_assets])

# Definir job para scraping completo
scraping_job = define_asset_job(
    name="scraping_job",
    description="Job completo de scraping: extrae datos de portales y carga en Data Lake y PostgreSQL",
    selection=AssetSelection.all(),
    tags={
        "team": "data-engineering",
        "priority": "high",
    }
)

# Definir job solo para Fotocasa
fotocasa_job = define_asset_job(
    name="fotocasa_job",
    description="Job de scraping solo para Fotocasa",
    selection=AssetSelection.assets(
        scraping_assets.bronze_fotocasa_listings,
        scraping_assets.raw_postgres_listings,
        scraping_assets.scraping_stats,
    ),
    tags={
        "portal": "fotocasa",
    }
)

# Definir schedules - usando el job directamente
scraping_schedule = ScheduleDefinition(
    name="scraping_schedule",
    cron_schedule="0 */6 * * *",  # Cada 6 horas
    job=scraping_job,
    default_status=DefaultScheduleStatus.STOPPED,  # Empezar parado
    description="Ejecuta scrapers de portales inmobiliarios cada 6 horas",
)

scraping_schedule_daily = ScheduleDefinition(
    name="scraping_schedule_daily",
    cron_schedule="0 2 * * *",  # Diario a las 2 AM
    job=scraping_job,
    default_status=DefaultScheduleStatus.STOPPED,
    description="Ejecuta scrapers diariamente a las 2 AM",
)

# Definir resources usando variables de entorno
resources = {
    "minio": MinIOResource(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        bucket_name="casa-teva-data-lake",
        secure=False,
    ),
    "postgres": PostgresResource(
        host=os.getenv("DAGSTER_POSTGRES_HOST", "localhost"),
        port=5432,
        database=os.getenv("DAGSTER_POSTGRES_DB", "casa_teva_db"),
        user=os.getenv("DAGSTER_POSTGRES_USER", "casa_teva"),
        password=os.getenv("DAGSTER_POSTGRES_PASSWORD", "casateva2024"),
    ),
}

# Crear Definitions que exporta todo
defs = Definitions(
    assets=all_assets,
    jobs=[scraping_job, fotocasa_job],
    schedules=[scraping_schedule, scraping_schedule_daily],
    resources=resources,
)

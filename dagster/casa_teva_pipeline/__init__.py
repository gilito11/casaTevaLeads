"""
Pipeline de Dagster para Casa Teva.

Define todos los assets, resources, schedules y jobs del sistema.
"""

from dagster import (
    Definitions,
    define_asset_job,
    AssetSelection,
    load_assets_from_modules,
)

from casa_teva_pipeline.assets import scraping_assets
from casa_teva_pipeline.resources.minio_resource import MinIOResource
from casa_teva_pipeline.resources.postgres_resource import PostgresResource
from casa_teva_pipeline.schedules import scraping_schedules


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

# Definir resources
resources = {
    "minio": MinIOResource(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="casa-teva-data-lake",
        secure=False,
    ),
    "postgres": PostgresResource(
        host="localhost",
        port=5432,
        database="casa_teva_db",
        user="casa_teva",
        password="casateva2024",
    ),
}

# Definir schedules
schedules = [
    scraping_schedules.scraping_schedule,
    scraping_schedules.scraping_schedule_hourly,
    scraping_schedules.scraping_schedule_daily,
    scraping_schedules.scraping_schedule_custom,
]

# Crear Definitions que exporta todo
defs = Definitions(
    assets=all_assets,
    jobs=[scraping_job, fotocasa_job],
    schedules=schedules,
    resources=resources,
)

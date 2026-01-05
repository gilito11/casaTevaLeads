"""
Pipeline de Dagster para Casa Teva.

Define todos los assets, resources, schedules y jobs del sistema.

Schedules configurados:
- scraping_schedule_spanish: 9:00, 11:00, 13:00, 15:00, 17:00, 19:00 hora española
- scraping_schedule_daily: 2:00 AM diario (backup)
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
from casa_teva_pipeline.resources.postgres_resource import PostgresResource


# Cargar todos los assets del módulo scraping_assets
all_assets = load_assets_from_modules([scraping_assets])

# Job principal de scraping
scraping_job = define_asset_job(
    name="scraping_job",
    description="Ejecuta scraping de todos los portales para las zonas activas",
    selection=AssetSelection.all(),
    tags={
        "team": "data-engineering",
        "priority": "high",
    }
)

# Schedule principal: 9, 11, 13, 15, 17, 19 hora española
# Cron: minuto hora día mes día_semana
# 0 9,11,13,15,17,19 * * * = A las 9:00, 11:00, 13:00, 15:00, 17:00, 19:00
scraping_schedule_spanish = ScheduleDefinition(
    name="scraping_schedule_spanish",
    cron_schedule="0 9,11,13,15,17,19 * * *",
    job=scraping_job,
    execution_timezone="Europe/Madrid",
    default_status=DefaultScheduleStatus.STOPPED,  # PAUSADO hasta definir horario óptimo
    description="Scraping cada 2 horas en horario laboral español (9-11-13-15-17-19)",
)

# Schedule de backup: 2 AM diario
scraping_schedule_daily = ScheduleDefinition(
    name="scraping_schedule_daily",
    cron_schedule="0 2 * * *",
    job=scraping_job,
    execution_timezone="Europe/Madrid",
    default_status=DefaultScheduleStatus.STOPPED,  # Desactivado por defecto
    description="Scraping diario a las 2 AM (backup)",
)

# Determinar configuración de PostgreSQL según entorno
# Para Azure: usar DATABASE_URL o variables individuales con SSL
def get_postgres_config():
    """Obtiene la configuración de PostgreSQL desde variables de entorno."""
    db_url = os.getenv("DATABASE_URL", "")

    # Si es Azure (tiene 'azure' en la URL)
    if "azure" in db_url:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip('/'),
            "user": parsed.username,
            "password": parsed.password,
            "sslmode": "require",
        }

    # Configuración por defecto (local/Docker)
    return {
        "host": os.getenv("DAGSTER_POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("DAGSTER_POSTGRES_PORT", "5432")),
        "database": os.getenv("DAGSTER_POSTGRES_DB", "casa_teva_db"),
        "user": os.getenv("DAGSTER_POSTGRES_USER", "casa_teva"),
        "password": os.getenv("DAGSTER_POSTGRES_PASSWORD", "casateva2024"),
        "sslmode": os.getenv("DAGSTER_POSTGRES_SSLMODE", "prefer"),
    }


pg_config = get_postgres_config()

resources = {
    "postgres": PostgresResource(
        host=pg_config["host"],
        port=pg_config["port"],
        database=pg_config["database"],
        user=pg_config["user"],
        password=pg_config["password"],
        sslmode=pg_config["sslmode"],
    ),
}

# Crear Definitions que exporta todo
defs = Definitions(
    assets=all_assets,
    jobs=[scraping_job],
    schedules=[scraping_schedule_spanish, scraping_schedule_daily],
    resources=resources,
)

"""
Pipeline de Dagster para Casa Teva.

Define todos los assets, resources, schedules y jobs del sistema.

Schedules configurados:
- scraping_schedule_optimized: 12:00, 18:00 hora española (basado en análisis de 220 anuncios)
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

from casa_teva_pipeline.assets import scraping_assets, image_assets, contact_assets
from casa_teva_pipeline.resources.postgres_resource import PostgresResource


# Cargar todos los assets de los módulos
all_assets = load_assets_from_modules([scraping_assets, image_assets, contact_assets])

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

# Schedule TEMPORAL: L-X-V a las 12:00 (1 vez/día)
# NOTA: Cuando el usuario avise, volver a: 0 12,18 * * * (12:00 y 18:00 diario)
# Cron: 0 12 * * 1,3,5 = A las 12:00 hora española, solo Lunes-Miércoles-Viernes
scraping_schedule_optimized = ScheduleDefinition(
    name="scraping_schedule_optimized",
    cron_schedule="0 12 * * 1,3,5",
    job=scraping_job,
    execution_timezone="Europe/Madrid",
    default_status=DefaultScheduleStatus.RUNNING,  # ACTIVO - horario temporal L-X-V
    description="Scraping temporal: 12:00 solo L-X-V (hasta nuevo aviso)",
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

# Job de contacto automatico
contact_job = define_asset_job(
    name="contact_job",
    description="Procesa la cola de contactos automaticos (max 5/dia)",
    selection=AssetSelection.assets(contact_assets.process_contact_queue),
    tags={
        "team": "data-engineering",
        "priority": "medium",
    }
)

# Schedule de contacto: 10 AM diario (horario laboral)
contact_schedule = ScheduleDefinition(
    name="contact_schedule",
    cron_schedule="0 10 * * 1-5",  # 10:00 AM, lunes a viernes
    job=contact_job,
    execution_timezone="Europe/Madrid",
    default_status=DefaultScheduleStatus.STOPPED,  # Desactivado hasta configurar sesiones
    description="Contacto automatico: 10:00 AM L-V (max 5 contactos/dia)",
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
    jobs=[scraping_job, contact_job],
    schedules=[scraping_schedule_optimized, scraping_schedule_daily, contact_schedule],
    resources=resources,
)

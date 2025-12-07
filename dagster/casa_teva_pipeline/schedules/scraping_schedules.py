"""
Schedules de Dagster para el sistema de scraping.

Define schedules para ejecutar los scrapers de forma automática.
"""

from dagster import (
    ScheduleDefinition,
    DefaultScheduleStatus,
    RunRequest,
    ScheduleEvaluationContext,
)


# Schedule principal: ejecuta scraping cada 6 horas
scraping_schedule = ScheduleDefinition(
    name="scraping_schedule",
    cron_schedule="0 */6 * * *",  # Cada 6 horas (00:00, 06:00, 12:00, 18:00)
    job_name="scraping_job",  # Referenciado en Definitions
    default_status=DefaultScheduleStatus.RUNNING,
    description="Ejecuta scrapers de portales inmobiliarios cada 6 horas",
    timezone="Europe/Madrid",
)


# Schedule de prueba: ejecuta cada hora (útil para testing)
scraping_schedule_hourly = ScheduleDefinition(
    name="scraping_schedule_hourly",
    cron_schedule="0 * * * *",  # Cada hora en el minuto 0
    job_name="scraping_job",
    default_status=DefaultScheduleStatus.STOPPED,  # Desactivado por defecto
    description="Schedule de prueba - ejecuta cada hora (desactivado por defecto)",
    timezone="Europe/Madrid",
)


# Schedule diario: ejecuta una vez al día a las 2 AM
scraping_schedule_daily = ScheduleDefinition(
    name="scraping_schedule_daily",
    cron_schedule="0 2 * * *",  # Diario a las 2 AM
    job_name="scraping_job",
    default_status=DefaultScheduleStatus.STOPPED,
    description="Ejecuta scrapers diariamente a las 2 AM (desactivado por defecto)",
    timezone="Europe/Madrid",
)


# Schedule con evaluación custom para control más fino
def scraping_schedule_custom_eval(context: ScheduleEvaluationContext):
    """
    Evaluación custom del schedule para decidir si ejecutar y con qué config.

    Permite lógica condicional basada en:
    - Día de la semana
    - Hora del día
    - Resultados previos
    - Configuración dinámica
    """
    from datetime import datetime

    now = datetime.now()

    # Ejemplo: Solo ejecutar en días laborables
    if now.weekday() >= 5:  # Sábado (5) o Domingo (6)
        # No ejecutar en fin de semana
        return []

    # Ejemplo: Ejecutar con config diferente según hora
    if now.hour < 12:
        # Mañana: scraping completo
        run_config = {
            "ops": {
                "bronze_fotocasa_listings": {
                    "config": {"full_scrape": True}
                }
            }
        }
    else:
        # Tarde: scraping incremental
        run_config = {
            "ops": {
                "bronze_fotocasa_listings": {
                    "config": {"full_scrape": False}
                }
            }
        }

    return RunRequest(
        run_key=f"scraping_{now.strftime('%Y%m%d_%H%M')}",
        run_config=run_config,
        tags={
            "dia_semana": now.strftime('%A'),
            "hora": str(now.hour),
        }
    )


scraping_schedule_custom = ScheduleDefinition(
    name="scraping_schedule_custom",
    job_name="scraping_job",
    evaluation_fn=scraping_schedule_custom_eval,
    cron_schedule="0 */6 * * *",  # Cada 6 horas
    default_status=DefaultScheduleStatus.STOPPED,
    description="Schedule con lógica custom (solo días laborables)",
    timezone="Europe/Madrid",
)

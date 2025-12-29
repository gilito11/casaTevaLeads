"""
Assets de Dagster para el proceso de scraping de portales inmobiliarios.

Lee las zonas activas de la base de datos y ejecuta los scrapers correspondientes.
Los scrapers guardan directamente en PostgreSQL.
"""

import subprocess
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

from dagster import asset, AssetExecutionContext, MetadataValue, Output

from casa_teva_pipeline.resources.postgres_resource import PostgresResource


logger = logging.getLogger(__name__)

# Mapeo de zonas de BD a zonas de cada scraper
# Todas las zonas disponibles en el scraper de Milanuncios
ZONA_MAPPING_MILANUNCIOS = {
    # Lleida
    'lleida_ciudad': 'lleida_ciudad',
    'lleida_20km': 'lleida_20km',
    'lleida_30km': 'lleida_30km',
    'lleida_40km': 'lleida_40km',
    'lleida_50km': 'lleida_50km',
    'la_bordeta': 'la_bordeta',
    'balaguer': 'balaguer',
    'mollerussa': 'mollerussa',
    'tremp': 'tremp',
    'tarrega': 'tarrega',
    # Tarragona
    'tarragona_ciudad': 'tarragona_ciudad',
    'tarragona_20km': 'tarragona_20km',
    'tarragona_30km': 'tarragona_30km',
    'tarragona_40km': 'tarragona_40km',
    'tarragona_50km': 'tarragona_50km',
    # Costa Daurada - Costeros
    'salou': 'salou',
    'cambrils': 'cambrils',
    'reus': 'reus',
    'vendrell': 'vendrell',
    'altafulla': 'altafulla',
    'torredembarra': 'torredembarra',
    'miami_platja': 'miami_platja',
    'hospitalet_infant': 'hospitalet_infant',
    'calafell': 'calafell',
    'coma_ruga': 'coma_ruga',
    # Costa Daurada - Interior
    'valls': 'valls',
    'montblanc': 'montblanc',
    'vila_seca': 'vila_seca',
    # Terres de l'Ebre
    'tortosa': 'tortosa',
    'amposta': 'amposta',
    'deltebre': 'deltebre',
    'ametlla_mar': 'ametlla_mar',
    'sant_carles_rapita': 'sant_carles_rapita',
}

ZONA_MAPPING_PISOS = {
    # Lleida
    'lleida_ciudad': 'lleida_capital',
    'lleida_20km': 'lleida_provincia',
    'lleida_30km': 'lleida_provincia',
    'lleida_40km': 'lleida_provincia',
    'lleida_50km': 'lleida_provincia',
    'la_bordeta': 'lleida_capital',
    'mollerussa': 'lleida_provincia',
    'tremp': 'lleida_provincia',
    'tarrega': 'lleida_provincia',
    'balaguer': 'lleida_provincia',
    # Tarragona
    'tarragona_ciudad': 'tarragona_capital',
    'tarragona_20km': 'tarragona_provincia',
    'tarragona_30km': 'tarragona_provincia',
    'tarragona_40km': 'tarragona_provincia',
    'tarragona_50km': 'tarragona_provincia',
    # Costa Daurada
    'salou': 'salou',
    'cambrils': 'cambrils',
    'reus': 'reus',
    'vendrell': 'vendrell',
    'calafell': 'calafell',
    'torredembarra': 'torredembarra',
    'altafulla': 'altafulla',
    'miami_platja': 'tarragona_provincia',
    'vila_seca': 'tarragona_provincia',
    'valls': 'valls',
    'montblanc': 'tarragona_provincia',
    # Terres de l'Ebre
    'tortosa': 'tortosa',
    'amposta': 'amposta',
    'sant_carles_rapita': 'tarragona_provincia',
}

# Mapping para Habitaclia (Botasaurus)
ZONA_MAPPING_HABITACLIA = {
    # Lleida
    'lleida_ciudad': 'lleida',
    'lleida_20km': 'lleida_provincia',
    'lleida_30km': 'lleida_provincia',
    'lleida_40km': 'lleida_provincia',
    'lleida_50km': 'lleida_provincia',
    'balaguer': 'balaguer',
    'mollerussa': 'mollerussa',
    'tarrega': 'tarrega',
    # Tarragona
    'tarragona_ciudad': 'tarragona',
    'tarragona_20km': 'tarragona_provincia',
    'tarragona_30km': 'tarragona_provincia',
    'tarragona_40km': 'tarragona_provincia',
    'tarragona_50km': 'tarragona_provincia',
    # Costa Daurada
    'salou': 'salou',
    'cambrils': 'cambrils',
    'reus': 'reus',
    'vendrell': 'vendrell',
    'calafell': 'calafell',
    'torredembarra': 'torredembarra',
    'altafulla': 'altafulla',
    'miami_platja': 'miami_platja',
    'vila_seca': 'vila-seca',
    'valls': 'valls',
    'montblanc': 'montblanc',
    # Terres de l'Ebre
    'tortosa': 'tortosa',
    'amposta': 'amposta',
    'sant_carles_rapita': 'sant_carles_de_la_rapita',
}

# Mapping para Fotocasa (Botasaurus)
ZONA_MAPPING_FOTOCASA = {
    # Lleida
    'lleida_ciudad': 'lleida',
    'lleida_20km': 'lleida_provincia',
    'lleida_30km': 'lleida_provincia',
    'lleida_40km': 'lleida_provincia',
    'lleida_50km': 'lleida_provincia',
    'balaguer': 'balaguer',
    'mollerussa': 'mollerussa',
    'tarrega': 'tarrega',
    'tremp': 'tremp',
    # Tarragona
    'tarragona_ciudad': 'tarragona',
    'tarragona_20km': 'tarragona_provincia',
    'tarragona_30km': 'tarragona_provincia',
    'tarragona_40km': 'tarragona_provincia',
    'tarragona_50km': 'tarragona_provincia',
    # Costa Daurada
    'salou': 'salou',
    'cambrils': 'cambrils',
    'reus': 'reus',
    'vendrell': 'vendrell',
    'calafell': 'calafell',
    'torredembarra': 'torredembarra',
    'altafulla': 'altafulla',
    'miami_platja': 'miami_platja',
    'vila_seca': 'vila_seca',
    'valls': 'valls',
    'montblanc': 'montblanc',
    # Terres de l'Ebre
    'tortosa': 'tortosa',
    'amposta': 'amposta',
    'deltebre': 'deltebre',
    'ametlla_mar': 'ametlla_mar',
    'sant_carles_rapita': 'sant_carles_rapita',
}


def get_project_root() -> str:
    """Obtiene el directorio raíz del proyecto."""
    # Dagster corre desde /app/dagster, el proyecto está en /app
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # assets -> casa_teva_pipeline -> dagster -> app
    return os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))


def run_scraper(
    context: AssetExecutionContext,
    scraper_name: str,
    zones: List[str],
    tenant_id: int = 1
) -> Dict[str, Any]:
    """
    Ejecuta un scraper específico para las zonas dadas.

    Args:
        context: Contexto de ejecución de Dagster
        scraper_name: Nombre del scraper (milanuncios, pisos)
        zones: Lista de zonas a scrapear
        tenant_id: ID del tenant

    Returns:
        Dict con resultados del scraping
    """
    project_root = get_project_root()
    script_path = os.path.join(project_root, f'run_{scraper_name}_scraper.py')

    if not os.path.exists(script_path):
        context.log.warning(f"Script no encontrado: {script_path}")
        return {
            'scraper': scraper_name,
            'status': 'skipped',
            'reason': f'Script not found: {script_path}',
            'zones': zones,
            'leads_found': 0,
        }

    if not zones:
        context.log.info(f"No hay zonas para {scraper_name}")
        return {
            'scraper': scraper_name,
            'status': 'skipped',
            'reason': 'No zones configured',
            'zones': [],
            'leads_found': 0,
        }

    zones_str = ','.join(zones)
    context.log.info(f"Ejecutando {scraper_name} para zonas: {zones_str}")

    try:
        # Configurar entorno con PLAYWRIGHT_BROWSERS_PATH
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root
        env['PLAYWRIGHT_BROWSERS_PATH'] = os.environ.get(
            'PLAYWRIGHT_BROWSERS_PATH', '/opt/playwright'
        )

        # Construir comando con zonas como argumentos separados
        # argparse espera: --zones zone1 zone2 zone3 (no comma-separated)
        cmd = [
            sys.executable,
            script_path,
            '--zones',
        ] + zones + [
            '--postgres',
            f'--tenant-id={tenant_id}',
        ]

        # Ejecutar scraper
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2700,  # 45 minutos timeout (Botasaurus con --single-process es más lento)
            cwd=project_root,
            env=env,
        )

        if result.returncode != 0:
            # Capture last 2000 chars of both stderr and stdout for debugging
            error_msg = result.stderr[-2000:] if result.stderr else ''
            stdout_msg = result.stdout[-1000:] if result.stdout else ''
            context.log.error(f"Error en {scraper_name} (returncode={result.returncode})")
            context.log.error(f"STDERR: {error_msg}")
            if stdout_msg:
                context.log.error(f"STDOUT (last 1000): {stdout_msg}")
            return {
                'scraper': scraper_name,
                'status': 'error',
                'error': error_msg,
                'zones': zones,
                'leads_found': 0,
            }

        context.log.info(f"{scraper_name} completado exitosamente")

        # Intentar extraer número de leads del output
        leads_found = 0
        if 'leads guardados' in result.stdout.lower():
            # Buscar patrón como "X leads guardados"
            import re
            match = re.search(r'(\d+)\s+leads?\s+guardad', result.stdout.lower())
            if match:
                leads_found = int(match.group(1))

        return {
            'scraper': scraper_name,
            'status': 'completed',
            'zones': zones,
            'leads_found': leads_found,
            'output': result.stdout[-1000:] if result.stdout else '',
        }

    except subprocess.TimeoutExpired:
        context.log.error(f"{scraper_name} excedió el timeout")
        return {
            'scraper': scraper_name,
            'status': 'timeout',
            'zones': zones,
            'leads_found': 0,
        }

    except Exception as e:
        context.log.error(f"Error ejecutando {scraper_name}: {e}")
        return {
            'scraper': scraper_name,
            'status': 'error',
            'error': str(e),
            'zones': zones,
            'leads_found': 0,
        }


@asset(
    description="Ejecuta todos los scrapers para las zonas activas en la BD",
    compute_kind="python",
    group_name="scraping",
)
def scraping_all_portals(
    context: AssetExecutionContext,
    postgres: PostgresResource
) -> Output[Dict[str, Any]]:
    """
    Asset principal de scraping.

    1. Lee las zonas activas de la base de datos
    2. Mapea las zonas a cada scraper
    3. Ejecuta los scrapers
    4. Retorna estadísticas
    """
    context.log.info("Iniciando scraping de todos los portales...")
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Obtener zonas activas de la BD
    zones = postgres.get_active_zones()

    if not zones:
        context.log.warning("No hay zonas activas configuradas")
        return Output(
            value={
                'fecha': fecha,
                'status': 'no_zones',
                'message': 'No hay zonas activas configuradas',
                'scrapers': [],
            },
            metadata={
                'status': MetadataValue.text('No zones configured'),
            }
        )

    context.log.info(f"Zonas activas encontradas: {len(zones)}")
    for zone in zones:
        context.log.info(f"  - {zone['nombre']} ({zone['slug']}) - Tenant: {zone['tenant_nombre']}")

    # Agrupar zonas por tenant
    zones_by_tenant = {}
    for zone in zones:
        tid = zone['tenant_id']
        if tid not in zones_by_tenant:
            zones_by_tenant[tid] = []
        zones_by_tenant[tid].append(zone['slug'])

    # Ejecutar scrapers para cada tenant
    all_results = []
    total_leads = 0

    for tenant_id, zone_slugs in zones_by_tenant.items():
        context.log.info(f"Procesando tenant {tenant_id} con {len(zone_slugs)} zonas")

        # Mapear zonas para Milanuncios
        milanuncios_zones = []
        for slug in zone_slugs:
            if slug in ZONA_MAPPING_MILANUNCIOS:
                mapped = ZONA_MAPPING_MILANUNCIOS[slug]
                if mapped not in milanuncios_zones:
                    milanuncios_zones.append(mapped)

        # Mapear zonas para Pisos.com
        pisos_zones = []
        for slug in zone_slugs:
            if slug in ZONA_MAPPING_PISOS:
                mapped = ZONA_MAPPING_PISOS[slug]
                if mapped not in pisos_zones:
                    pisos_zones.append(mapped)

        # Ejecutar Milanuncios
        if milanuncios_zones:
            result = run_scraper(context, 'milanuncios', milanuncios_zones, tenant_id)
            all_results.append(result)
            total_leads += result.get('leads_found', 0)

        # Ejecutar Pisos.com
        if pisos_zones:
            result = run_scraper(context, 'pisos', pisos_zones, tenant_id)
            all_results.append(result)
            total_leads += result.get('leads_found', 0)

        # Mapear zonas para Habitaclia (Botasaurus)
        habitaclia_zones = []
        for slug in zone_slugs:
            if slug in ZONA_MAPPING_HABITACLIA:
                mapped = ZONA_MAPPING_HABITACLIA[slug]
                if mapped not in habitaclia_zones:
                    habitaclia_zones.append(mapped)

        # Ejecutar Habitaclia
        if habitaclia_zones:
            result = run_scraper(context, 'habitaclia', habitaclia_zones, tenant_id)
            all_results.append(result)
            total_leads += result.get('leads_found', 0)

        # Mapear zonas para Fotocasa (Botasaurus)
        fotocasa_zones = []
        for slug in zone_slugs:
            if slug in ZONA_MAPPING_FOTOCASA:
                mapped = ZONA_MAPPING_FOTOCASA[slug]
                if mapped not in fotocasa_zones:
                    fotocasa_zones.append(mapped)

        # Ejecutar Fotocasa
        if fotocasa_zones:
            result = run_scraper(context, 'fotocasa', fotocasa_zones, tenant_id)
            all_results.append(result)
            total_leads += result.get('leads_found', 0)

    # Preparar resumen
    completed = sum(1 for r in all_results if r['status'] == 'completed')
    errors = sum(1 for r in all_results if r['status'] == 'error')
    skipped = sum(1 for r in all_results if r['status'] == 'skipped')

    summary = {
        'fecha': fecha,
        'status': 'completed',
        'zonas_activas': len(zones),
        'scrapers_ejecutados': len(all_results),
        'scrapers_completados': completed,
        'scrapers_con_error': errors,
        'scrapers_omitidos': skipped,
        'total_leads_encontrados': total_leads,
        'resultados': all_results,
    }

    context.log.info(f"Scraping completado: {completed} OK, {errors} errores, {skipped} omitidos")
    context.log.info(f"Total leads encontrados: {total_leads}")

    return Output(
        value=summary,
        metadata={
            'fecha': MetadataValue.text(fecha),
            'zonas_activas': MetadataValue.int(len(zones)),
            'scrapers_ejecutados': MetadataValue.int(len(all_results)),
            'scrapers_completados': MetadataValue.int(completed),
            'scrapers_con_error': MetadataValue.int(errors),
            'total_leads': MetadataValue.int(total_leads),
        }
    )


@asset(
    description="Ejecuta dbt para transformar raw -> staging -> marts",
    compute_kind="dbt",
    group_name="transform",
    deps=["scraping_all_portals"],
)
def dbt_transform(
    context: AssetExecutionContext,
) -> Output[Dict[str, Any]]:
    """
    Ejecuta dbt run para transformar los datos de raw a marts.

    Flujo: raw.raw_listings -> staging.stg_* -> marts.dim_leads
    """
    context.log.info("Iniciando transformación dbt...")

    # Parse DATABASE_URL para obtener credenciales
    database_url = os.environ.get('DATABASE_URL', '')

    dbt_env = os.environ.copy()

    if database_url and 'azure' in database_url:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        dbt_env['DBT_HOST'] = parsed.hostname or 'localhost'
        dbt_env['DBT_PORT'] = str(parsed.port or 5432)
        dbt_env['DBT_USER'] = parsed.username or ''
        dbt_env['DBT_PASSWORD'] = parsed.password or ''
        dbt_env['DBT_DATABASE'] = parsed.path.lstrip('/') if parsed.path else ''
        dbt_env['DBT_SSLMODE'] = 'require'
        context.log.info(f"Configurado para Azure: {dbt_env['DBT_HOST']}")
    else:
        # Local/Docker config
        dbt_env['DBT_HOST'] = os.environ.get('POSTGRES_HOST', 'postgres')
        dbt_env['DBT_PORT'] = os.environ.get('POSTGRES_PORT', '5432')
        dbt_env['DBT_USER'] = os.environ.get('POSTGRES_USER', 'casa_teva')
        dbt_env['DBT_PASSWORD'] = os.environ.get('POSTGRES_PASSWORD', 'casateva2024')
        dbt_env['DBT_DATABASE'] = os.environ.get('POSTGRES_DB', 'casa_teva_db')
        dbt_env['DBT_SSLMODE'] = 'prefer'
        context.log.info(f"Configurado para local: {dbt_env['DBT_HOST']}")

    # Ejecutar dbt run
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    dbt_project_dir = os.path.join(project_root, 'dbt_project')

    try:
        result = subprocess.run(
            [
                sys.executable, '-m', 'dbt', 'run',
                '--project-dir', dbt_project_dir,
                '--profiles-dir', dbt_project_dir,
                '--target', 'prod',
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutos
            env=dbt_env,
            cwd=dbt_project_dir,
        )

        if result.returncode != 0:
            context.log.error(f"dbt run falló: {result.stderr[-1000:]}")
            return Output(
                value={
                    'status': 'error',
                    'error': result.stderr[-500:],
                    'stdout': result.stdout[-500:],
                },
                metadata={
                    'status': MetadataValue.text('ERROR'),
                }
            )

        context.log.info("dbt run completado exitosamente")
        context.log.info(result.stdout[-1000:] if result.stdout else "No output")

        return Output(
            value={
                'status': 'success',
                'output': result.stdout[-1000:] if result.stdout else '',
            },
            metadata={
                'status': MetadataValue.text('SUCCESS'),
            }
        )

    except subprocess.TimeoutExpired:
        context.log.error("dbt run excedió el timeout")
        return Output(
            value={'status': 'timeout'},
            metadata={'status': MetadataValue.text('TIMEOUT')}
        )
    except Exception as e:
        context.log.error(f"Error ejecutando dbt: {e}")
        return Output(
            value={'status': 'error', 'error': str(e)},
            metadata={'status': MetadataValue.text('ERROR')}
        )


@asset(
    description="Estadísticas del último scraping",
    compute_kind="python",
    group_name="reporting",
    deps=["dbt_transform"],
)
def scraping_stats(
    context: AssetExecutionContext,
    postgres: PostgresResource,
) -> Output[Dict[str, Any]]:
    """
    Genera estadísticas después del scraping.
    """
    context.log.info("Generando estadísticas de scraping...")

    stats = postgres.get_scraping_stats()

    context.log.info(f"Total leads en BD: {stats['total_leads']}")
    context.log.info(f"Último scraping: {stats['ultimo_scraping']}")

    return Output(
        value=stats,
        metadata={
            'total_leads': MetadataValue.int(stats['total_leads']),
            'portales_activos': MetadataValue.int(stats['portales_activos']),
            'ultimo_scraping': MetadataValue.text(stats['ultimo_scraping'] or 'N/A'),
        }
    )

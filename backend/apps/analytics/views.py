import json
import logging
import re
import unicodedata
import traceback
from dataclasses import asdict

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from decimal import Decimal

from core.models import ZONAS_PREESTABLECIDAS
from .services import calcular_acm, acm_para_lead, generar_pdf_valoracion, generar_pdf_lead


logger = logging.getLogger(__name__)


def normalize_zone_name(name):
    """Normalize zone name for matching: remove accents, lowercase, simplify."""
    if not name:
        return ''
    # Remove accents
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Lowercase and remove extra spaces
    name = name.lower().strip()
    # Remove common prefixes/suffixes
    name = re.sub(r'^(costa dorada|costa daurada|terres ebre|provincia de|tarragona)\s*[-:]\s*', '', name)
    name = re.sub(r'\s*\(.*?\)\s*', '', name)  # Remove parenthetical content
    return name


def find_zone_coords(zona_nombre):
    """Find coordinates for a zone name using fuzzy matching."""
    if not zona_nombre:
        return None

    normalized_input = normalize_zone_name(zona_nombre)

    # First pass: exact match on normalized name
    for slug, zona_data in ZONAS_PREESTABLECIDAS.items():
        normalized_preset = normalize_zone_name(zona_data['nombre'])
        if normalized_input == normalized_preset:
            return {
                'lat': zona_data['lat'],
                'lon': zona_data['lon'],
                'region': zona_data.get('region_nombre', ''),
            }

    # Second pass: one contains the other
    for slug, zona_data in ZONAS_PREESTABLECIDAS.items():
        normalized_preset = normalize_zone_name(zona_data['nombre'])
        if normalized_preset in normalized_input or normalized_input in normalized_preset:
            return {
                'lat': zona_data['lat'],
                'lon': zona_data['lon'],
                'region': zona_data.get('region_nombre', ''),
            }

    # Third pass: slug match
    for slug, zona_data in ZONAS_PREESTABLECIDAS.items():
        slug_normalized = slug.replace('_', ' ')
        if slug_normalized in normalized_input:
            return {
                'lat': zona_data['lat'],
                'lon': zona_data['lon'],
                'region': zona_data.get('region_nombre', ''),
            }

    return None


def convert_decimals(obj):
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj


def dict_fetchall(cursor):
    """Return all rows from a cursor as a list of dicts with Decimals converted."""
    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return convert_decimals(rows)


def dict_fetchone(cursor):
    """Return one row from a cursor as a dict with Decimals converted."""
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    result = dict(zip(columns, row)) if row else {}
    return convert_decimals(result)


@login_required
def analytics_dashboard_view(request):
    """Dashboard de analytics con KPIs, gráficos y métricas.

    NOTA: Las vistas de analytics no existen aún, así que usamos queries directas
    que combinan public_marts.dim_leads con leads_lead_estado para obtener estados reales.
    """
    tenant_id = request.session.get('tenant_id', 1)

    # Filtros desde GET params
    filtro_portal = request.GET.get('portal', '')
    filtro_zona = request.GET.get('zona', '')
    filtro_dias = request.GET.get('dias', '')  # 7, 30, 90

    # Construir WHERE clause para filtros
    filtros_sql = []
    filtros_params = [tenant_id]
    if filtro_portal:
        filtros_sql.append("l.source_portal = %s")
        filtros_params.append(filtro_portal)
    if filtro_zona:
        filtros_sql.append("l.zona_clasificada = %s")
        filtros_params.append(filtro_zona)
    if filtro_dias and filtro_dias.isdigit():
        filtros_sql.append(f"l.fecha_primera_captura >= CURRENT_DATE - INTERVAL '{int(filtro_dias)} days'")

    filtros_where = " AND " + " AND ".join(filtros_sql) if filtros_sql else ""

    context = {
        'kpis': {},
        'embudo': [],
        'leads_por_dia': [],
        'evolucion_precios': [],
        'comparativa_portales': [],
        'precios_por_zona': [],
        'tipologia_inmuebles': [],
        'ultimos_leads': [],
        'filtro_portal': filtro_portal,
        'filtro_zona': filtro_zona,
        'filtro_dias': filtro_dias,
        'portales_disponibles': [],
        'zonas_disponibles': [],
    }

    with connection.cursor() as cursor:
        # Obtener opciones para filtros
        try:
            cursor.execute("""
                SELECT DISTINCT source_portal FROM public_marts.dim_leads
                WHERE tenant_id = %s AND source_portal IS NOT NULL ORDER BY source_portal
            """, [tenant_id])
            context['portales_disponibles'] = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
                SELECT DISTINCT zona_clasificada FROM public_marts.dim_leads
                WHERE tenant_id = %s AND zona_clasificada IS NOT NULL AND zona_clasificada != ''
                ORDER BY zona_clasificada
            """, [tenant_id])
            context['zonas_disponibles'] = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching filter options: {e}")

        # KPIs principales - query directa combinando leads con estados
        try:
            cursor.execute(f"""
                WITH lead_con_estado AS (
                    SELECT
                        l.*,
                        COALESCE(e.estado, 'NUEVO') as estado_real,
                        e.fecha_primer_contacto
                    FROM public_marts.dim_leads l
                    LEFT JOIN leads_lead_estado e ON l.lead_id = e.lead_id
                    WHERE l.tenant_id = %s {filtros_where}
                )
                SELECT
                    COUNT(*) as total_leads,
                    COUNT(*) FILTER (WHERE estado_real = 'NUEVO') as leads_nuevos,
                    COUNT(*) FILTER (WHERE estado_real = 'EN_PROCESO') as leads_en_proceso,
                    COUNT(*) FILTER (WHERE estado_real = 'INTERESADO') as leads_interesados,
                    COUNT(*) FILTER (WHERE estado_real = 'CLIENTE') as leads_convertidos,
                    COUNT(*) FILTER (WHERE estado_real IN ('NO_INTERESADO', 'NO_CONTACTAR', 'YA_VENDIDO')) as leads_descartados,
                    COUNT(*) FILTER (WHERE estado_real = 'CONTACTADO_SIN_RESPUESTA') as leads_contactados,
                    COUNT(*) FILTER (WHERE estado_real = 'EN_ESPERA') as leads_en_espera,
                    ROUND(
                        CASE WHEN COUNT(*) > 0
                        THEN 100.0 * COUNT(*) FILTER (WHERE estado_real = 'CLIENTE') / COUNT(*)
                        ELSE 0 END, 1
                    ) as tasa_conversion,
                    COALESCE(SUM(precio) FILTER (WHERE estado_real NOT IN ('NO_INTERESADO', 'NO_CONTACTAR', 'YA_VENDIDO')), 0) as valor_pipeline,
                    COUNT(*) FILTER (WHERE fecha_primera_captura >= CURRENT_DATE - INTERVAL '7 days') as leads_ultima_semana,
                    COUNT(*) FILTER (WHERE fecha_primera_captura >= DATE_TRUNC('month', CURRENT_DATE)) as leads_este_mes,
                    COALESCE(AVG(lead_score), 0)::INTEGER as score_medio,
                    COALESCE(AVG(
                        CASE WHEN fecha_primer_contacto IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (fecha_primer_contacto - fecha_primera_captura)) / 86400
                        END
                    ), 0)::NUMERIC(5,1) as dias_medio_primer_contacto
                FROM lead_con_estado
            """, filtros_params)
            context['kpis'] = dict_fetchone(cursor)
        except Exception as e:
            logger.error(f"Error fetching KPIs: {e}")
            context['kpis'] = {
                'total_leads': 0, 'leads_nuevos': 0, 'leads_en_proceso': 0,
                'leads_interesados': 0, 'leads_convertidos': 0, 'tasa_conversion': 0,
                'valor_pipeline': 0, 'leads_ultima_semana': 0, 'leads_contactados': 0,
                'leads_en_espera': 0, 'leads_descartados': 0, 'leads_este_mes': 0,
                'score_medio': 0, 'dias_medio_primer_contacto': 0
            }

        # Embudo de conversión - estados ordenados
        try:
            cursor.execute("""
                WITH lead_con_estado AS (
                    SELECT
                        COALESCE(e.estado, 'NUEVO') as estado_real,
                        l.precio
                    FROM public_marts.dim_leads l
                    LEFT JOIN leads_lead_estado e ON l.lead_id = e.lead_id
                    WHERE l.tenant_id = %s
                ),
                total AS (SELECT COUNT(*) as cnt FROM lead_con_estado),
                estados AS (
                    SELECT
                        estado_real as estado,
                        COUNT(*) as total_leads,
                        COALESCE(AVG(precio), 0) as precio_medio,
                        CASE estado_real
                            WHEN 'NUEVO' THEN 1
                            WHEN 'EN_PROCESO' THEN 2
                            WHEN 'CONTACTADO_SIN_RESPUESTA' THEN 3
                            WHEN 'EN_ESPERA' THEN 4
                            WHEN 'INTERESADO' THEN 5
                            WHEN 'CLIENTE' THEN 6
                            WHEN 'NO_INTERESADO' THEN 7
                            WHEN 'YA_VENDIDO' THEN 8
                            WHEN 'NO_CONTACTAR' THEN 9
                            ELSE 10
                        END as orden_embudo
                    FROM lead_con_estado
                    GROUP BY estado_real
                )
                SELECT
                    e.estado,
                    e.total_leads,
                    ROUND(e.precio_medio::numeric, 0) as precio_medio,
                    ROUND(100.0 * e.total_leads / GREATEST(t.cnt, 1), 1) as porcentaje,
                    e.orden_embudo
                FROM estados e, total t
                ORDER BY orden_embudo
            """, [tenant_id])
            context['embudo'] = dict_fetchall(cursor)
        except Exception as e:
            logger.error(f"Error fetching embudo: {e}")

        # Leads por día (últimos 30 días)
        try:
            cursor.execute("""
                SELECT
                    DATE(fecha_primera_captura) as fecha,
                    COUNT(*) as leads_captados,
                    COUNT(DISTINCT telefono_norm) as leads_unicos,
                    COALESCE(AVG(precio), 0) as precio_medio
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND fecha_primera_captura >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(fecha_primera_captura)
                ORDER BY fecha
            """, [tenant_id])
            rows = dict_fetchall(cursor)
            for row in rows:
                row['fecha'] = row['fecha'].strftime('%Y-%m-%d') if row['fecha'] else ''
                row['precio_medio'] = float(row['precio_medio']) if row['precio_medio'] else 0
            context['leads_por_dia'] = rows
        except Exception as e:
            logger.error(f"Error fetching leads por dia: {e}")

        # Evolución de precios (últimas 12 semanas)
        try:
            cursor.execute("""
                SELECT
                    DATE_TRUNC('week', fecha_primera_captura)::date as semana,
                    COALESCE(AVG(precio), 0) as precio_medio,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio), 0) as precio_mediana,
                    COALESCE(MIN(precio), 0) as min_precio,
                    COALESCE(MAX(precio), 0) as max_precio
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND precio > 0
                  AND fecha_primera_captura >= CURRENT_DATE - INTERVAL '12 weeks'
                GROUP BY DATE_TRUNC('week', fecha_primera_captura)
                ORDER BY semana DESC
                LIMIT 12
            """, [tenant_id])
            rows = dict_fetchall(cursor)
            for row in rows:
                row['semana'] = row['semana'].strftime('%Y-%m-%d') if row['semana'] else ''
                row['precio_medio'] = float(row['precio_medio']) if row['precio_medio'] else 0
                row['precio_mediana'] = float(row['precio_mediana']) if row['precio_mediana'] else 0
                row['min_precio'] = float(row['min_precio']) if row['min_precio'] else 0
                row['max_precio'] = float(row['max_precio']) if row['max_precio'] else 0
            context['evolucion_precios'] = list(reversed(rows))
        except Exception as e:
            logger.error(f"Error fetching evolucion precios: {e}")

        # Comparativa de portales
        try:
            cursor.execute("""
                WITH lead_con_estado AS (
                    SELECT
                        l.source_portal as portal,
                        l.telefono_norm,
                        l.precio,
                        l.superficie_m2 as metros,
                        l.lead_score,
                        COALESCE(e.estado, 'NUEVO') as estado_real
                    FROM public_marts.dim_leads l
                    LEFT JOIN leads_lead_estado e ON l.lead_id = e.lead_id
                    WHERE l.tenant_id = %s
                )
                SELECT
                    portal,
                    COUNT(*) as total_leads,
                    COUNT(DISTINCT telefono_norm) as leads_unicos,
                    COUNT(*) FILTER (WHERE estado_real = 'CLIENTE') as convertidos,
                    ROUND(
                        CASE WHEN COUNT(*) > 0
                        THEN 100.0 * COUNT(*) FILTER (WHERE estado_real = 'CLIENTE') / COUNT(*)
                        ELSE 0 END, 1
                    ) as tasa_conversion,
                    COUNT(*) FILTER (WHERE estado_real IN ('CONTACTADO_SIN_RESPUESTA', 'INTERESADO', 'CLIENTE')) as contactados,
                    ROUND(
                        CASE WHEN COUNT(*) > 0
                        THEN 100.0 * COUNT(*) FILTER (WHERE estado_real IN ('CONTACTADO_SIN_RESPUESTA', 'INTERESADO', 'CLIENTE')) / COUNT(*)
                        ELSE 0 END, 1
                    ) as tasa_contacto,
                    COALESCE(AVG(lead_score), 0)::INTEGER as score_medio,
                    COALESCE(AVG(precio), 0) as precio_medio,
                    COALESCE(AVG(CASE WHEN metros > 0 THEN precio / metros ELSE NULL END), 0) as precio_m2_medio
                FROM lead_con_estado
                GROUP BY portal
                ORDER BY total_leads DESC
            """, [tenant_id])
            rows = dict_fetchall(cursor)
            for row in rows:
                row['precio_medio'] = float(row['precio_medio']) if row['precio_medio'] else 0
                row['precio_m2_medio'] = float(row['precio_m2_medio']) if row['precio_m2_medio'] else 0
            context['comparativa_portales'] = rows
        except Exception as e:
            logger.error(f"Error fetching comparativa portales: {e}")

        # Precios por zona (normalizado para encoding issues)
        try:
            cursor.execute("""
                SELECT
                    CASE
                        -- Fix encoding issues and normalize zone names
                        WHEN zona_clasificada ILIKE '%%trrega%%' OR zona_clasificada ILIKE '%%tàrrega%%' OR zona_clasificada ILIKE '%%tarrega%%' THEN 'Tàrrega'
                        WHEN zona_clasificada ILIKE '%%mollerussa%%' THEN 'Mollerussa'
                        WHEN zona_clasificada ILIKE '%%balaguer%%' THEN 'Balaguer'
                        WHEN zona_clasificada ILIKE '%%lleida%%' OR zona_clasificada ILIKE '%%lerida%%' THEN 'Lleida Ciudad'
                        WHEN zona_clasificada ILIKE '%%salou%%' THEN 'Salou'
                        WHEN zona_clasificada ILIKE '%%cambrils%%' THEN 'Cambrils'
                        WHEN zona_clasificada ILIKE '%%tarragona%%' THEN 'Tarragona Ciudad'
                        WHEN zona_clasificada ILIKE '%%reus%%' THEN 'Reus'
                        WHEN zona_clasificada ILIKE '%%vendrell%%' THEN 'El Vendrell'
                        WHEN zona_clasificada ILIKE '%%tortosa%%' THEN 'Tortosa'
                        WHEN zona_clasificada ILIKE '%%amposta%%' THEN 'Amposta'
                        WHEN zona_clasificada ILIKE '%%deltebre%%' THEN 'Deltebre'
                        WHEN zona_clasificada ILIKE '%%ametlla%%' THEN 'L''Ametlla de Mar'
                        WHEN zona_clasificada ILIKE '%%sant carles%%' OR zona_clasificada ILIKE '%%rapita%%' OR zona_clasificada ILIKE '%%ràpita%%' THEN 'Sant Carles de la Ràpita'
                        WHEN zona_clasificada ILIKE '%%miami%%' THEN 'Miami Platja'
                        WHEN zona_clasificada ILIKE '%%alpicat%%' THEN 'Alpicat'
                        WHEN zona_clasificada ILIKE '%%tremp%%' THEN 'Tremp'
                        ELSE zona_clasificada
                    END as zona_clasificada,
                    COALESCE(AVG(precio), 0) as precio_medio,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio), 0) as precio_mediana,
                    COALESCE(AVG(CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 ELSE NULL END), 0) as precio_m2_medio,
                    COUNT(*) as total_inmuebles
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND zona_clasificada IS NOT NULL
                  AND zona_clasificada != ''
                  AND precio > 0
                GROUP BY 1
                ORDER BY total_inmuebles DESC
                LIMIT 15
            """, [tenant_id])
            rows = dict_fetchall(cursor)
            for row in rows:
                row['precio_medio'] = float(row['precio_medio']) if row['precio_medio'] else 0
                row['precio_mediana'] = float(row['precio_mediana']) if row['precio_mediana'] else 0
                row['precio_m2_medio'] = float(row['precio_m2_medio']) if row['precio_m2_medio'] else 0
            context['precios_por_zona'] = rows
        except Exception as e:
            logger.error(f"Error fetching precios por zona: {e}")

        # Tipología de inmuebles (normalizado)
        try:
            cursor.execute("""
                SELECT
                    CASE
                        WHEN LOWER(tipo_propiedad) IN ('piso', 'pisos') THEN 'Piso'
                        WHEN LOWER(tipo_propiedad) IN ('apartamento', 'apartamentos') THEN 'Apartamento'
                        WHEN LOWER(tipo_propiedad) IN ('casa', 'casas', 'chalet', 'chalets') THEN 'Casa'
                        WHEN LOWER(tipo_propiedad) IN ('ático', 'atico', 'áticos', 'aticos') THEN 'Ático'
                        WHEN LOWER(tipo_propiedad) IN ('dúplex', 'duplex') THEN 'Dúplex'
                        WHEN LOWER(tipo_propiedad) IN ('estudio', 'estudios') THEN 'Estudio'
                        WHEN LOWER(tipo_propiedad) IN ('local', 'locales') THEN 'Local'
                        WHEN LOWER(tipo_propiedad) IN ('garaje', 'garajes', 'parking') THEN 'Garaje'
                        WHEN LOWER(tipo_propiedad) IN ('terreno', 'terrenos', 'parcela', 'parcelas') THEN 'Terreno'
                        WHEN LOWER(tipo_propiedad) IN ('finca', 'fincas') THEN 'Finca'
                        WHEN tipo_propiedad IS NULL THEN 'Sin especificar'
                        ELSE 'Otros'
                    END as tipo_propiedad,
                    COUNT(*) as total,
                    ROUND(100.0 * COUNT(*) / GREATEST((SELECT COUNT(*) FROM public_marts.dim_leads WHERE tenant_id = %s), 1), 1) as porcentaje,
                    COALESCE(AVG(precio), 0) as precio_medio,
                    COALESCE(AVG(CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 ELSE NULL END), 0) as precio_m2_medio
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                GROUP BY 1
                ORDER BY total DESC
            """, [tenant_id, tenant_id])
            rows = dict_fetchall(cursor)
            for row in rows:
                row['precio_medio'] = float(row['precio_medio']) if row['precio_medio'] else 0
                row['precio_m2_medio'] = float(row['precio_m2_medio']) if row['precio_m2_medio'] else 0
                row['porcentaje'] = float(row['porcentaje']) if row['porcentaje'] else 0
            context['tipologia_inmuebles'] = rows
        except Exception as e:
            logger.error(f"Error fetching tipologia: {e}")

        # Últimos leads captados (10 más recientes)
        try:
            cursor.execute(f"""
                SELECT
                    l.lead_id,
                    l.titulo,
                    l.precio,
                    l.source_portal as portal,
                    l.zona_clasificada as zona,
                    l.telefono_norm as telefono,
                    l.lead_score as score,
                    l.fecha_primera_captura,
                    COALESCE(e.estado, 'NUEVO') as estado
                FROM public_marts.dim_leads l
                LEFT JOIN leads_lead_estado e ON l.lead_id = e.lead_id
                WHERE l.tenant_id = %s {filtros_where}
                ORDER BY l.fecha_primera_captura DESC
                LIMIT 10
            """, filtros_params)
            rows = dict_fetchall(cursor)
            for row in rows:
                if row.get('fecha_primera_captura'):
                    row['fecha_primera_captura'] = row['fecha_primera_captura'].strftime('%d/%m %H:%M')
            context['ultimos_leads'] = rows
        except Exception as e:
            logger.error(f"Error fetching ultimos leads: {e}")

    # Proximas visitas (del usuario actual, próximos 7 días)
    from leads.models import Interaction
    try:
        from django.utils import timezone
        from datetime import timedelta
        proximas_visitas = Interaction.objects.filter(
            contact__tenant_id=tenant_id,
            tipo='visita',
            fecha__gte=timezone.now(),
            fecha__lte=timezone.now() + timedelta(days=7)
        ).select_related('contact').order_by('fecha')[:5]
        context['proximas_visitas'] = proximas_visitas
    except Exception as e:
        logger.error(f"Error fetching proximas visitas: {e}")
        context['proximas_visitas'] = []

    # Convert lists to JSON for JavaScript
    context['leads_por_dia_json'] = json.dumps(context['leads_por_dia'])
    context['evolucion_precios_json'] = json.dumps(context['evolucion_precios'])
    context['embudo_json'] = json.dumps(context['embudo'])
    context['precios_por_zona_json'] = json.dumps(context['precios_por_zona'])
    context['tipologia_json'] = json.dumps(context['tipologia_inmuebles'])

    return render(request, 'analytics/dashboard.html', context)


@login_required
def map_view(request):
    """Vista del mapa de leads por zona geográfica."""
    tenant_id = request.session.get('tenant_id', 1)

    # Get leads grouped by zona_clasificada
    zones_data = []

    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT
                    zona_clasificada,
                    COUNT(*) as total_leads,
                    COUNT(*) FILTER (WHERE precio > 0) as con_precio,
                    COALESCE(AVG(precio) FILTER (WHERE precio > 0), 0) as precio_medio,
                    COALESCE(MIN(precio) FILTER (WHERE precio > 0), 0) as precio_min,
                    COALESCE(MAX(precio) FILTER (WHERE precio > 0), 0) as precio_max
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND zona_clasificada IS NOT NULL
                  AND zona_clasificada != ''
                GROUP BY zona_clasificada
                ORDER BY total_leads DESC
            """, [tenant_id])
            rows = dict_fetchall(cursor)

            for row in rows:
                zona_nombre = row['zona_clasificada']

                # Try to find coordinates using improved matching
                coords = find_zone_coords(zona_nombre)

                if coords:
                    zones_data.append({
                        'nombre': zona_nombre,
                        'lat': coords['lat'],
                        'lon': coords['lon'],
                        'region': coords['region'],
                        'total_leads': row['total_leads'],
                        'precio_medio': round(float(row['precio_medio']), 0),
                        'precio_min': round(float(row['precio_min']), 0),
                        'precio_max': round(float(row['precio_max']), 0),
                    })
                else:
                    # Log unmatched zones for debugging
                    logger.debug(f"Map: Could not find coords for zone '{zona_nombre}'")

        except Exception as e:
            logger.error(f"Error fetching map data: {e}")

    # Calculate map center (average of all points)
    if zones_data:
        center_lat = sum(z['lat'] for z in zones_data) / len(zones_data)
        center_lon = sum(z['lon'] for z in zones_data) / len(zones_data)
    else:
        # Default to Tarragona area
        center_lat = 41.1189
        center_lon = 1.2445

    # Create map config as JSON to avoid locale issues with decimals
    map_config = {
        'center': [float(center_lat), float(center_lon)],
        'zones': zones_data,
    }

    context = {
        'zones_data': zones_data,
        'map_config_json': json.dumps(map_config),
        'total_leads': sum(z['total_leads'] for z in zones_data),
        'total_zones': len(zones_data),
    }

    return render(request, 'analytics/map.html', context)


@login_required
def map_data_api(request):
    """API endpoint para obtener datos del mapa (para actualizaciones AJAX)."""
    tenant_id = request.session.get('tenant_id', 1)

    zones_data = []

    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT
                    zona_clasificada,
                    source_portal as portal,
                    COUNT(*) as total_leads,
                    COALESCE(AVG(precio) FILTER (WHERE precio > 0), 0) as precio_medio
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND zona_clasificada IS NOT NULL
                  AND zona_clasificada != ''
                GROUP BY zona_clasificada, source_portal
                ORDER BY zona_clasificada, total_leads DESC
            """, [tenant_id])
            rows = dict_fetchall(cursor)

            # Group by zone
            zones_dict = {}
            for row in rows:
                zona = row['zona_clasificada']
                if zona not in zones_dict:
                    zones_dict[zona] = {
                        'nombre': zona,
                        'total_leads': 0,
                        'portales': {},
                        'coords': None,
                    }
                zones_dict[zona]['total_leads'] += row['total_leads']
                zones_dict[zona]['portales'][row['portal']] = {
                    'count': row['total_leads'],
                    'precio_medio': round(float(row['precio_medio']), 0),
                }

            # Add coordinates using improved matching
            for zona_nombre, zona_data in zones_dict.items():
                coords = find_zone_coords(zona_nombre)
                if coords:
                    zona_data['coords'] = {
                        'lat': coords['lat'],
                        'lon': coords['lon'],
                    }
                    zones_data.append(zona_data)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'zones': zones_data})


@login_required
def scrape_history_view(request):
    """
    Vista compacta del historial de scrapes.
    Agrupa por día/horario mostrando qué zonas se scrapearon.
    """
    tenant_id = request.session.get('tenant_id', 1)
    dias = int(request.GET.get('dias', 7))

    # Obtener datos de raw_listings agrupados por fecha y zona
    history = []

    with connection.cursor() as cursor:
        try:
            # Agrupar por día y franja horaria (mañana 12:00, tarde 18:00)
            cursor.execute("""
                WITH scrape_sessions AS (
                    SELECT
                        DATE(scraped_at) as fecha,
                        CASE
                            WHEN EXTRACT(HOUR FROM scraped_at) < 15 THEN '12:00'
                            ELSE '18:00'
                        END as franja,
                        raw_data->>'zona_geografica' as zona,
                        portal,
                        COUNT(*) as listings,
                        MIN(scraped_at) as start_time,
                        MAX(scraped_at) as end_time
                    FROM raw.raw_listings
                    WHERE tenant_id = %s
                      AND scraped_at >= CURRENT_DATE - INTERVAL '%s days'
                      AND raw_data->>'zona_geografica' IS NOT NULL
                    GROUP BY DATE(scraped_at),
                             CASE WHEN EXTRACT(HOUR FROM scraped_at) < 15 THEN '12:00' ELSE '18:00' END,
                             raw_data->>'zona_geografica',
                             portal
                )
                SELECT
                    fecha,
                    franja,
                    json_agg(json_build_object(
                        'zona', zona,
                        'portal', portal,
                        'listings', listings
                    ) ORDER BY zona, portal) as zonas
                FROM scrape_sessions
                GROUP BY fecha, franja
                ORDER BY fecha DESC, franja DESC
            """, [tenant_id, dias])

            rows = dict_fetchall(cursor)
            for row in rows:
                row['fecha'] = row['fecha'].strftime('%d/%m') if row['fecha'] else ''
            history = rows

        except Exception as e:
            logger.error(f"Error fetching scrape history: {e}\n{traceback.format_exc()}")

    context = {
        'history': history,
        'dias': dias,
    }

    return render(request, 'analytics/scrape_history.html', context)


@login_required
def zones_grid_view(request):
    """
    Vista tipo grid/casillas mostrando zonas y cuánto tiempo hace que no se scrapean.
    Colores: verde (reciente), amarillo (>3 días), rojo (>7 días).
    """
    tenant_id = request.session.get('tenant_id', 1)

    zones = []

    with connection.cursor() as cursor:
        try:
            # Obtener todas las zonas configuradas con su último scrape
            cursor.execute("""
                WITH ultimo_scrape AS (
                    SELECT
                        raw_data->>'zona_geografica' as zona,
                        portal,
                        MAX(scraped_at) as ultimo,
                        COUNT(*) as total_listings
                    FROM raw.raw_listings
                    WHERE tenant_id = %s
                      AND raw_data->>'zona_geografica' IS NOT NULL
                    GROUP BY raw_data->>'zona_geografica', portal
                ),
                zonas_config AS (
                    SELECT
                        nombre,
                        slug,
                        activa,
                        scrapear_milanuncios as ma,
                        scrapear_fotocasa as fc,
                        scrapear_habitaclia as ha,
                        scrapear_idealista as id
                    FROM core_zonageografica
                    WHERE tenant_id = %s
                )
                SELECT
                    z.nombre,
                    z.slug,
                    z.activa,
                    -- Por cada portal: último scrape y días desde entonces
                    MAX(CASE WHEN u.portal = 'milanuncios' THEN u.ultimo END) as ma_ultimo,
                    MAX(CASE WHEN u.portal = 'fotocasa' THEN u.ultimo END) as fc_ultimo,
                    MAX(CASE WHEN u.portal = 'habitaclia' THEN u.ultimo END) as ha_ultimo,
                    MAX(CASE WHEN u.portal = 'idealista' THEN u.ultimo END) as id_ultimo,
                    -- Días desde último scrape por portal
                    EXTRACT(DAY FROM NOW() - MAX(CASE WHEN u.portal = 'milanuncios' THEN u.ultimo END))::INT as ma_dias,
                    EXTRACT(DAY FROM NOW() - MAX(CASE WHEN u.portal = 'fotocasa' THEN u.ultimo END))::INT as fc_dias,
                    EXTRACT(DAY FROM NOW() - MAX(CASE WHEN u.portal = 'habitaclia' THEN u.ultimo END))::INT as ha_dias,
                    EXTRACT(DAY FROM NOW() - MAX(CASE WHEN u.portal = 'idealista' THEN u.ultimo END))::INT as id_dias,
                    -- Total listings por portal
                    SUM(CASE WHEN u.portal = 'milanuncios' THEN u.total_listings ELSE 0 END)::INT as ma_total,
                    SUM(CASE WHEN u.portal = 'fotocasa' THEN u.total_listings ELSE 0 END)::INT as fc_total,
                    SUM(CASE WHEN u.portal = 'habitaclia' THEN u.total_listings ELSE 0 END)::INT as ha_total,
                    SUM(CASE WHEN u.portal = 'idealista' THEN u.total_listings ELSE 0 END)::INT as id_total,
                    -- Portales activos
                    z.ma, z.fc, z.ha, z.id
                FROM zonas_config z
                LEFT JOIN ultimo_scrape u ON (
                    u.zona ILIKE '%%' || z.nombre || '%%'
                    OR u.zona ILIKE '%%' || z.slug || '%%'
                    OR z.nombre ILIKE '%%' || u.zona || '%%'
                )
                GROUP BY z.nombre, z.slug, z.activa, z.ma, z.fc, z.ha, z.id
                ORDER BY z.activa DESC, z.nombre
            """, [tenant_id, tenant_id])

            zones = dict_fetchall(cursor)

            # Añadir clase CSS según días
            for z in zones:
                for portal in ['ma', 'fc', 'ha', 'id']:
                    dias = z.get(f'{portal}_dias')
                    if dias is None:
                        z[f'{portal}_class'] = 'gray'  # Nunca scrapeado
                    elif dias <= 1:
                        z[f'{portal}_class'] = 'green'
                    elif dias <= 3:
                        z[f'{portal}_class'] = 'yellow'
                    elif dias <= 7:
                        z[f'{portal}_class'] = 'orange'
                    else:
                        z[f'{portal}_class'] = 'red'

        except Exception as e:
            logger.error(f"Error fetching zones grid: {e}\n{traceback.format_exc()}")

    context = {
        'zones': zones,
    }

    return render(request, 'analytics/zones_grid.html', context)


# ============================================================================
# ACM - Análisis Comparativo de Mercado
# ============================================================================

@login_required
def acm_view(request):
    """Vista principal del ACM con formulario."""
    tenant_id = request.session.get('tenant_id', 1)

    # Obtener zonas disponibles para el selector
    zonas = []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT zona_clasificada
            FROM public_marts.dim_leads
            WHERE tenant_id = %s AND zona_clasificada IS NOT NULL AND zona_clasificada != ''
            ORDER BY zona_clasificada
        """, [tenant_id])
        zonas = [row[0] for row in cursor.fetchall()]

    context = {
        'zonas': zonas,
        'tipos_inmueble': ['Piso', 'Casa', 'Apartamento', 'Ático', 'Dúplex', 'Estudio', 'Local', 'Terreno'],
    }

    return render(request, 'analytics/acm.html', context)


@login_required
@require_GET
def acm_calcular_api(request):
    """API para calcular ACM."""
    tenant_id = request.session.get('tenant_id', 1)

    zona = request.GET.get('zona', '')
    metros = request.GET.get('metros', '')
    tipo = request.GET.get('tipo', '')
    habitaciones = request.GET.get('habitaciones', '')

    if not zona or not metros:
        return JsonResponse({'error': 'Zona y metros son requeridos'}, status=400)

    try:
        metros_float = float(metros)
    except ValueError:
        return JsonResponse({'error': 'Metros debe ser un número'}, status=400)

    hab_int = None
    if habitaciones:
        try:
            hab_int = int(habitaciones)
        except ValueError:
            pass

    try:
        acm = calcular_acm(
            tenant_id=tenant_id,
            zona=zona,
            metros=metros_float,
            tipo_inmueble=tipo if tipo else None,
            habitaciones=hab_int
        )

        # Convertir dataclass a dict para JSON
        result = {
            'zona': acm.zona,
            'tipo_inmueble': acm.tipo_inmueble,
            'metros': acm.metros,
            'habitaciones': acm.habitaciones,
            'precio_estimado': acm.precio_estimado,
            'precio_min': acm.precio_min,
            'precio_max': acm.precio_max,
            'precio_mediana': acm.precio_mediana,
            'precio_m2_medio': acm.precio_m2_medio,
            'num_comparables': acm.num_comparables,
            'confianza': acm.confianza,
            'tendencia_precios': acm.tendencia_precios,
            'comparables': [
                {
                    'lead_id': c.lead_id,
                    'titulo': c.titulo,
                    'precio': c.precio,
                    'metros': c.metros,
                    'precio_m2': c.precio_m2,
                    'zona': c.zona,
                    'portal': c.portal,
                    'url': c.url,
                    'habitaciones': c.habitaciones,
                    'fecha_captura': c.fecha_captura,
                    'similitud': c.similitud,
                }
                for c in acm.comparables
            ]
        }

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error en ACM: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def acm_lead_api(request, lead_id):
    """API para obtener ACM de un lead específico."""
    tenant_id = request.session.get('tenant_id', 1)

    try:
        acm = acm_para_lead(tenant_id, lead_id)
        if not acm:
            return JsonResponse({'error': 'No se pudo calcular ACM para este lead'}, status=404)

        result = {
            'precio_estimado': acm.precio_estimado,
            'precio_min': acm.precio_min,
            'precio_max': acm.precio_max,
            'precio_m2_medio': acm.precio_m2_medio,
            'num_comparables': acm.num_comparables,
            'confianza': acm.confianza,
        }

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error en ACM para lead {lead_id}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# PDF de Valoración
# ============================================================================

@login_required
@require_GET
def pdf_valoracion_view(request):
    """Genera PDF de valoración desde parámetros."""
    tenant_id = request.session.get('tenant_id', 1)

    zona = request.GET.get('zona', '')
    metros = request.GET.get('metros', '')
    tipo = request.GET.get('tipo', '')
    habitaciones = request.GET.get('habitaciones', '')
    cliente = request.GET.get('cliente', '')

    if not zona or not metros:
        return HttpResponse('Zona y metros son requeridos', status=400)

    try:
        metros_float = float(metros)
    except ValueError:
        return HttpResponse('Metros debe ser un número', status=400)

    hab_int = None
    if habitaciones:
        try:
            hab_int = int(habitaciones)
        except ValueError:
            pass

    try:
        acm = calcular_acm(
            tenant_id=tenant_id,
            zona=zona,
            metros=metros_float,
            tipo_inmueble=tipo if tipo else None,
            habitaciones=hab_int
        )

        # Obtener nombre de inmobiliaria del tenant
        from core.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            nombre_inmobiliaria = tenant.nombre
        except Tenant.DoesNotExist:
            nombre_inmobiliaria = "Casa Teva"

        pdf_buffer = generar_pdf_valoracion(
            acm=acm,
            nombre_cliente=cliente if cliente else None,
            nombre_inmobiliaria=nombre_inmobiliaria
        )

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        filename = f"valoracion_{zona.replace(' ', '_')}_{metros}m2.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"Error generando PDF: {e}\n{traceback.format_exc()}")
        return HttpResponse(f'Error generando PDF: {str(e)}', status=500)


@login_required
@require_GET
def pdf_lead_view(request, lead_id):
    """Genera PDF de valoración para un lead específico."""
    tenant_id = request.session.get('tenant_id', 1)

    try:
        # Obtener nombre de inmobiliaria
        from core.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            nombre_inmobiliaria = tenant.nombre
        except Tenant.DoesNotExist:
            nombre_inmobiliaria = "Casa Teva"

        pdf_buffer = generar_pdf_lead(
            tenant_id=tenant_id,
            lead_id=lead_id,
            nombre_inmobiliaria=nombre_inmobiliaria
        )

        if not pdf_buffer:
            return HttpResponse('No se pudo generar el PDF para este lead', status=404)

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="valoracion_{lead_id}.pdf"'

        return response

    except Exception as e:
        logger.error(f"Error generando PDF para lead {lead_id}: {e}")
        return HttpResponse(f'Error: {str(e)}', status=500)

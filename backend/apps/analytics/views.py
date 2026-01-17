import json
import logging
import re
import unicodedata
import traceback

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from decimal import Decimal

from core.models import ZONAS_PREESTABLECIDAS


def debug_dashboard(request):
    """Endpoint de diagnóstico temporal - eliminar después de usar."""
    errors = []
    results = {}
    tenant_id = 1

    with connection.cursor() as cursor:
        # Test 1: Basic table access
        try:
            cursor.execute("SELECT COUNT(*) FROM public_marts.dim_leads WHERE tenant_id = %s", [tenant_id])
            results['dim_leads_count'] = cursor.fetchone()[0]
        except Exception as e:
            errors.append(f"dim_leads: {e}")

        # Test 2: Join with lead_estado
        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM public_marts.dim_leads l
                LEFT JOIN leads_lead_estado e ON l.lead_id = e.lead_id
                WHERE l.tenant_id = %s
            """, [tenant_id])
            results['join_count'] = cursor.fetchone()[0]
        except Exception as e:
            errors.append(f"join: {e}")

        # Test 3: Full KPIs query
        try:
            cursor.execute("""
                WITH lead_con_estado AS (
                    SELECT
                        l.*,
                        COALESCE(e.estado, 'NUEVO') as estado_real,
                        e.fecha_primer_contacto
                    FROM public_marts.dim_leads l
                    LEFT JOIN leads_lead_estado e ON l.lead_id = e.lead_id
                    WHERE l.tenant_id = %s
                )
                SELECT COUNT(*) FROM lead_con_estado
            """, [tenant_id])
            results['kpis_query'] = cursor.fetchone()[0]
        except Exception as e:
            errors.append(f"kpis: {e}\n{traceback.format_exc()}")

    # Test Interaction model
    try:
        from leads.models import Interaction
        results['interaction_model'] = 'OK'
    except Exception as e:
        errors.append(f"Interaction import: {e}")

    # Test 4: Check photos by portal
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT source_portal, COUNT(*) as total,
                       COUNT(*) FILTER (WHERE fotos_json IS NOT NULL AND fotos_json::text != 'null' AND fotos_json::text != '[]') as con_fotos
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                GROUP BY source_portal
                ORDER BY source_portal
            """, [tenant_id])
            results['photos_by_portal'] = {row[0]: {'total': row[1], 'con_fotos': row[2]} for row in cursor.fetchall()}
        except Exception as e:
            errors.append(f"photos: {e}")

        # Test 5: Sample Milanuncios photos
        try:
            cursor.execute("""
                SELECT lead_id, fotos_json::text, pg_typeof(fotos_json) as col_type
                FROM public_marts.dim_leads
                WHERE tenant_id = %s AND source_portal = 'milanuncios'
                LIMIT 3
            """, [tenant_id])
            results['milanuncios_sample'] = [{'lead_id': row[0], 'fotos': row[1][:200] if row[1] else None, 'type': row[2]} for row in cursor.fetchall()]
        except Exception as e:
            errors.append(f"milanuncios_sample: {e}")

        # Test 6: Check column type
        try:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public_marts' AND table_name = 'dim_leads' AND column_name = 'fotos_json'
            """)
            row = cursor.fetchone()
            results['fotos_column_type'] = row[1] if row else 'NOT FOUND'
        except Exception as e:
            errors.append(f"column_type: {e}")

    # Test 7: Check Django ORM parsing of fotos
    try:
        from leads.models import Lead
        lead_with_photos = Lead.objects.filter(portal='milanuncios').exclude(fotos__isnull=True).first()
        if lead_with_photos:
            results['django_fotos_test'] = {
                'lead_id': lead_with_photos.lead_id,
                'fotos_type': type(lead_with_photos.fotos).__name__,
                'fotos_length': len(lead_with_photos.fotos) if lead_with_photos.fotos else 0,
                'first_foto': lead_with_photos.fotos[0][:100] if lead_with_photos.fotos and len(lead_with_photos.fotos) > 0 else None
            }
        else:
            results['django_fotos_test'] = 'No milanuncios lead with photos found'
    except Exception as e:
        errors.append(f"django_fotos_test: {e}")

    return JsonResponse({
        'status': 'error' if errors else 'ok',
        'errors': errors,
        'results': results
    })

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

        # Precios por zona
        try:
            cursor.execute("""
                SELECT
                    zona_clasificada as zona_clasificada,
                    COALESCE(AVG(precio), 0) as precio_medio,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio), 0) as precio_mediana,
                    COALESCE(AVG(CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 ELSE NULL END), 0) as precio_m2_medio,
                    COUNT(*) as total_inmuebles
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND zona_clasificada IS NOT NULL
                  AND zona_clasificada != ''
                  AND precio > 0
                GROUP BY zona_clasificada
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

        # Tipología de inmuebles
        try:
            cursor.execute("""
                SELECT
                    COALESCE(tipo_propiedad, 'Sin especificar') as tipo_propiedad,
                    COUNT(*) as total,
                    ROUND(100.0 * COUNT(*) / GREATEST((SELECT COUNT(*) FROM public_marts.dim_leads WHERE tenant_id = %s), 1), 1) as porcentaje,
                    COALESCE(AVG(precio), 0) as precio_medio,
                    COALESCE(AVG(CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 ELSE NULL END), 0) as precio_m2_medio
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                GROUP BY tipo_propiedad
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

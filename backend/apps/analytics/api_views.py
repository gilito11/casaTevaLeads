"""
Analytics API endpoints with filter support.

All endpoints support the following query parameters:
- fecha_inicio: Start date (YYYY-MM-DD)
- fecha_fin: End date (YYYY-MM-DD)
- portal: Filter by source portal (pisos, habitaclia, fotocasa, milanuncios, idealista)
- zona: Filter by zona_geografica
- estado: Filter by lead estado
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import connection
from datetime import datetime, timedelta
from decimal import Decimal
import json


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
    """Return all rows from a cursor as a list of dicts."""
    columns = [col[0] for col in cursor.description]
    return convert_decimals([dict(zip(columns, row)) for row in cursor.fetchall()])


def dict_fetchone(cursor):
    """Return one row from a cursor as a dict."""
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return convert_decimals(dict(zip(columns, row)) if row else {})


def build_where_clause(request, table_alias='l'):
    """Build WHERE clause and params from request query parameters."""
    tenant_id = request.session.get('tenant_id', 1)
    conditions = [f"{table_alias}.tenant_id = %s"]
    params = [tenant_id]

    # Date range
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if fecha_inicio:
        conditions.append(f"DATE({table_alias}.updated_at) >= %s")
        params.append(fecha_inicio)
    if fecha_fin:
        conditions.append(f"DATE({table_alias}.updated_at) <= %s")
        params.append(fecha_fin)

    # Portal filter
    portal = request.GET.get('portal')
    if portal and portal != 'todos':
        conditions.append(f"{table_alias}.portal = %s")
        params.append(portal)

    # Zone filter
    zona = request.GET.get('zona')
    if zona and zona != 'todas':
        conditions.append(f"{table_alias}.zona_geografica = %s")
        params.append(zona)

    # Estado filter (requires join with lead_estado)
    estado = request.GET.get('estado')
    if estado and estado != 'todos':
        # Estado is handled in the query itself since it requires a join
        pass

    return ' AND '.join(conditions), params


def get_estado_filter(request):
    """Return estado filter value if specified."""
    estado = request.GET.get('estado')
    return estado if estado and estado != 'todos' else None


@login_required
def api_kpis(request):
    """
    GET /analytics/api/kpis/

    Returns main KPI metrics for the dashboard.
    """
    where_clause, params = build_where_clause(request)
    estado_filter = get_estado_filter(request)

    with connection.cursor() as cursor:
        # Build estado filter condition
        estado_condition = ""
        if estado_filter:
            estado_condition = f"AND COALESCE(e.estado, 'NUEVO') = %s"
            params.append(estado_filter)

        cursor.execute(f"""
            WITH lead_con_estado AS (
                SELECT
                    l.*,
                    COALESCE(l.estado, 'NUEVO') as estado_real
                FROM public_marts.dim_leads l
                WHERE {where_clause} {estado_condition}
            )
            SELECT
                COUNT(*) as total_leads,
                COUNT(*) FILTER (WHERE estado_real = 'NUEVO') as leads_nuevos,
                COUNT(*) FILTER (WHERE estado_real = 'EN_PROCESO') as leads_en_proceso,
                COUNT(*) FILTER (WHERE estado_real = 'INTERESADO') as leads_interesados,
                COUNT(*) FILTER (WHERE estado_real = 'CLIENTE') as leads_convertidos,
                COUNT(*) FILTER (WHERE estado_real IN ('NO_INTERESADO', 'NO_CONTACTAR', 'YA_VENDIDO')) as leads_descartados,
                ROUND(
                    CASE WHEN COUNT(*) > 0
                    THEN 100.0 * COUNT(*) FILTER (WHERE estado_real = 'CLIENTE') / COUNT(*)
                    ELSE 0 END, 1
                ) as tasa_conversion,
                COALESCE(SUM(precio) FILTER (WHERE estado_real NOT IN ('NO_INTERESADO', 'NO_CONTACTAR', 'YA_VENDIDO')), 0) as valor_pipeline,
                COUNT(*) FILTER (WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days') as leads_ultima_semana,
                COUNT(*) FILTER (WHERE updated_at >= DATE_TRUNC('month', CURRENT_DATE)) as leads_este_mes,
                COALESCE(AVG(precio), 0) as precio_medio,
                COUNT(DISTINCT portal) as portales_activos
            FROM lead_con_estado
        """, params)

        kpis = dict_fetchone(cursor)

    return JsonResponse({'data': kpis})


@login_required
def api_embudo(request):
    """
    GET /analytics/api/embudo/

    Returns conversion funnel data by estado.
    """
    where_clause, params = build_where_clause(request)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            WITH lead_con_estado AS (
                SELECT
                    COALESCE(l.estado, 'NUEVO') as estado_real,
                    l.precio
                FROM public_marts.dim_leads l
                WHERE {where_clause}
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
        """, params)

        embudo = dict_fetchall(cursor)

    return JsonResponse({'data': embudo})


@login_required
def api_leads_por_dia(request):
    """
    GET /analytics/api/leads-por-dia/

    Returns leads captured per day for the selected period.
    """
    where_clause, params = build_where_clause(request)
    estado_filter = get_estado_filter(request)

    # Default to last 30 days if no date range specified
    if not request.GET.get('fecha_inicio'):
        where_clause += " AND l.updated_at >= CURRENT_DATE - INTERVAL '30 days'"

    with connection.cursor() as cursor:
        estado_join = ""
        estado_condition = ""
        if estado_filter:
            estado_join = "LEFT JOIN leads_lead_estado e ON l.lead_id::text = e.lead_id"
            estado_condition = f"AND COALESCE(e.estado, 'NUEVO') = %s"
            params.append(estado_filter)

        cursor.execute(f"""
            SELECT
                DATE(l.updated_at) as fecha,
                COUNT(*) as leads_captados,
                COUNT(DISTINCT l.telefono_norm) as leads_unicos,
                COALESCE(AVG(l.precio), 0) as precio_medio
            FROM public_marts.dim_leads l
            {estado_join}
            WHERE {where_clause} {estado_condition}
            GROUP BY DATE(l.updated_at)
            ORDER BY fecha
        """, params)

        rows = dict_fetchall(cursor)
        for row in rows:
            row['fecha'] = row['fecha'].strftime('%Y-%m-%d') if row.get('fecha') else ''

    return JsonResponse({'data': rows})


@login_required
def api_evolucion_precios(request):
    """
    GET /analytics/api/evolucion-precios/

    Returns price evolution over time (weekly aggregation).
    """
    where_clause, params = build_where_clause(request)

    # Default to last 12 weeks if no date range specified
    if not request.GET.get('fecha_inicio'):
        where_clause += " AND l.updated_at >= CURRENT_DATE - INTERVAL '12 weeks'"

    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT
                DATE_TRUNC('week', l.updated_at)::date as semana,
                COALESCE(AVG(l.precio), 0) as precio_medio,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.precio), 0) as precio_mediana,
                COALESCE(MIN(l.precio), 0) as min_precio,
                COALESCE(MAX(l.precio), 0) as max_precio,
                COUNT(*) as total_inmuebles
            FROM public_marts.dim_leads l
            WHERE {where_clause} AND l.precio > 0
            GROUP BY DATE_TRUNC('week', l.updated_at)
            ORDER BY semana
        """, params)

        rows = dict_fetchall(cursor)
        for row in rows:
            row['semana'] = row['semana'].strftime('%Y-%m-%d') if row.get('semana') else ''

    return JsonResponse({'data': rows})


@login_required
def api_comparativa_portales(request):
    """
    GET /analytics/api/comparativa-portales/

    Returns comparative metrics by source portal.
    """
    where_clause, params = build_where_clause(request)
    estado_filter = get_estado_filter(request)

    with connection.cursor() as cursor:
        estado_condition = ""
        if estado_filter:
            estado_condition = f"AND COALESCE(e.estado, 'NUEVO') = %s"
            params.append(estado_filter)

        cursor.execute(f"""
            WITH lead_con_estado AS (
                SELECT
                    l.portal as portal,
                    l.telefono_norm,
                    l.precio,
                    l.metros,
                    COALESCE(e.estado, 'NUEVO') as estado_real
                FROM public_marts.dim_leads l
                LEFT JOIN leads_lead_estado e ON l.lead_id::text = e.lead_id
                WHERE {where_clause} {estado_condition}
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
                COALESCE(AVG(precio), 0) as precio_medio,
                COALESCE(AVG(CASE WHEN metros > 0 THEN precio / metros ELSE NULL END), 0) as precio_m2_medio
            FROM lead_con_estado
            GROUP BY portal
            ORDER BY total_leads DESC
        """, params)

        rows = dict_fetchall(cursor)

    return JsonResponse({'data': rows})


@login_required
def api_precios_por_zona(request):
    """
    GET /analytics/api/precios-por-zona/

    Returns price statistics grouped by zone.
    """
    where_clause, params = build_where_clause(request)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT
                l.zona_geografica,
                COALESCE(AVG(l.precio), 0) as precio_medio,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.precio), 0) as precio_mediana,
                COALESCE(AVG(CASE WHEN l.metros > 0 THEN l.precio / l.metros ELSE NULL END), 0) as precio_m2_medio,
                COUNT(*) as total_inmuebles,
                COALESCE(MIN(l.precio), 0) as precio_min,
                COALESCE(MAX(l.precio), 0) as precio_max
            FROM public_marts.dim_leads l
            WHERE {where_clause}
              AND l.zona_geografica IS NOT NULL
              AND l.zona_geografica != ''
              AND l.zona_geografica != 'Otros'
              AND l.precio > 0
            GROUP BY l.zona_geografica
            ORDER BY total_inmuebles DESC
            LIMIT 20
        """, params)

        rows = dict_fetchall(cursor)

    return JsonResponse({'data': rows})


@login_required
def api_tipologia(request):
    """
    GET /analytics/api/tipologia/

    Returns property type distribution.
    """
    where_clause, params = build_where_clause(request)
    tenant_id = request.session.get('tenant_id', 1)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT
                COALESCE(l.tipo_inmueble, 'Sin especificar') as tipo_inmueble,
                COUNT(*) as total,
                ROUND(100.0 * COUNT(*) / GREATEST(
                    (SELECT COUNT(*) FROM public_marts.dim_leads WHERE tenant_id = %s), 1
                ), 1) as porcentaje,
                COALESCE(AVG(l.precio), 0) as precio_medio,
                COALESCE(AVG(CASE WHEN l.metros > 0 THEN l.precio / l.metros ELSE NULL END), 0) as precio_m2_medio
            FROM public_marts.dim_leads l
            WHERE {where_clause}
            GROUP BY l.tipo_inmueble
            ORDER BY total DESC
        """, [tenant_id] + params)

        rows = dict_fetchall(cursor)

    return JsonResponse({'data': rows})


@login_required
def api_filter_options(request):
    """
    GET /analytics/api/filter-options/

    Returns available filter options (portales, zonas, estados).
    """
    tenant_id = request.session.get('tenant_id', 1)

    with connection.cursor() as cursor:
        # Get distinct portals
        cursor.execute("""
            SELECT DISTINCT portal
            FROM public_marts.dim_leads
            WHERE tenant_id = %s AND portal IS NOT NULL
            ORDER BY portal
        """, [tenant_id])
        portales = [row[0] for row in cursor.fetchall()]

        # Get distinct zones
        cursor.execute("""
            SELECT DISTINCT zona_geografica
            FROM public_marts.dim_leads
            WHERE tenant_id = %s
              AND zona_geografica IS NOT NULL
              AND zona_geografica != ''
              AND zona_geografica != 'Otros'
            ORDER BY zona_geografica
        """, [tenant_id])
        zonas = [row[0] for row in cursor.fetchall()]

        # Estados are fixed
        estados = [
            'NUEVO', 'EN_PROCESO', 'CONTACTADO_SIN_RESPUESTA',
            'EN_ESPERA', 'INTERESADO', 'NO_INTERESADO',
            'NO_CONTACTAR', 'CLIENTE', 'YA_VENDIDO'
        ]

    return JsonResponse({
        'portales': portales,
        'zonas': zonas,
        'estados': estados
    })


@login_required
def api_export_csv(request):
    """
    GET /analytics/api/export/

    Exports filtered data as CSV.
    """
    from django.http import HttpResponse
    import csv

    where_clause, params = build_where_clause(request)
    estado_filter = get_estado_filter(request)

    with connection.cursor() as cursor:
        estado_join = "LEFT JOIN leads_lead_estado e ON l.lead_id::text = e.lead_id"
        estado_condition = ""
        if estado_filter:
            estado_condition = f"AND COALESCE(e.estado, 'NUEVO') = %s"
            params.append(estado_filter)

        cursor.execute(f"""
            SELECT
                l.lead_id,
                l.telefono_norm,
                l.email,
                l.nombre,
                l.portal,
                l.zona_geografica,
                l.tipo_inmueble,
                l.precio,
                l.metros,
                l.habitaciones,
                COALESCE(e.estado, 'NUEVO') as estado,
                l.updated_at
            FROM public_marts.dim_leads l
            {estado_join}
            WHERE {where_clause} {estado_condition}
            ORDER BY l.updated_at DESC
            LIMIT 10000
        """, params)

        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'

    writer = csv.writer(response)
    writer.writerow(columns)
    writer.writerows(rows)

    return response

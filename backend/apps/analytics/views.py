from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import connection
import json


def dict_fetchall(cursor):
    """Return all rows from a cursor as a list of dicts."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dict_fetchone(cursor):
    """Return one row from a cursor as a dict."""
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else {}


@login_required
def analytics_dashboard_view(request):
    """Dashboard de analytics con KPIs, gráficos y métricas."""
    tenant_id = request.session.get('tenant_id', 1)

    context = {
        'kpis': {},
        'embudo': [],
        'leads_por_dia': [],
        'evolucion_precios': [],
        'comparativa_portales': [],
        'precios_por_zona': [],
        'tipologia_inmuebles': [],
    }

    with connection.cursor() as cursor:
        # KPIs principales
        try:
            cursor.execute("""
                SELECT
                    COALESCE(total_leads, 0) as total_leads,
                    COALESCE(leads_nuevos, 0) as leads_nuevos,
                    COALESCE(leads_en_proceso, 0) as leads_en_proceso,
                    COALESCE(leads_interesados, 0) as leads_interesados,
                    COALESCE(leads_convertidos, 0) as leads_convertidos,
                    COALESCE(leads_descartados, 0) as leads_descartados,
                    COALESCE(tasa_conversion, 0) as tasa_conversion,
                    COALESCE(tasa_descarte, 0) as tasa_descarte,
                    COALESCE(valor_pipeline, 0) as valor_pipeline,
                    COALESCE(valor_convertido, 0) as valor_convertido,
                    COALESCE(score_medio, 0) as score_medio,
                    COALESCE(dias_medio_primer_contacto, 0) as dias_medio_primer_contacto,
                    COALESCE(leads_ultima_semana, 0) as leads_ultima_semana,
                    COALESCE(leads_este_mes, 0) as leads_este_mes
                FROM analytics.analytics_kpis_tenant
                WHERE tenant_id = %s
            """, [tenant_id])
            context['kpis'] = dict_fetchone(cursor)
        except Exception as e:
            print(f"Error fetching KPIs: {e}")
            context['kpis'] = {
                'total_leads': 0, 'leads_nuevos': 0, 'leads_en_proceso': 0,
                'leads_interesados': 0, 'leads_convertidos': 0, 'tasa_conversion': 0,
                'valor_pipeline': 0, 'score_medio': 0, 'leads_ultima_semana': 0,
                'dias_medio_primer_contacto': 0
            }

        # Embudo de conversión
        try:
            cursor.execute("""
                SELECT
                    estado,
                    COALESCE(total_leads, 0) as total_leads,
                    COALESCE(score_medio, 0) as score_medio,
                    COALESCE(precio_medio, 0) as precio_medio,
                    COALESCE(porcentaje, 0) as porcentaje,
                    COALESCE(orden_embudo, 0) as orden_embudo
                FROM analytics.analytics_embudo_conversion
                WHERE tenant_id = %s
                ORDER BY orden_embudo
            """, [tenant_id])
            context['embudo'] = dict_fetchall(cursor)
        except Exception as e:
            print(f"Error fetching embudo: {e}")

        # Leads por día (últimos 30 días)
        try:
            cursor.execute("""
                SELECT
                    fecha,
                    COALESCE(SUM(leads_captados), 0) as leads_captados,
                    COALESCE(SUM(leads_unicos), 0) as leads_unicos,
                    COALESCE(AVG(precio_medio), 0) as precio_medio
                FROM analytics.analytics_leads_por_dia
                WHERE tenant_id = %s
                  AND fecha >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY fecha
                ORDER BY fecha
            """, [tenant_id])
            rows = dict_fetchall(cursor)
            # Convert dates to strings for JSON
            for row in rows:
                row['fecha'] = row['fecha'].strftime('%Y-%m-%d') if row['fecha'] else ''
            context['leads_por_dia'] = rows
        except Exception as e:
            print(f"Error fetching leads por dia: {e}")

        # Evolución de precios (últimas 12 semanas)
        try:
            cursor.execute("""
                SELECT
                    semana,
                    COALESCE(precio_medio, 0) as precio_medio,
                    COALESCE(precio_mediana, 0) as precio_mediana,
                    COALESCE(min_precio, 0) as min_precio,
                    COALESCE(max_precio, 0) as max_precio
                FROM analytics.analytics_evolucion_precios
                WHERE tenant_id = %s
                ORDER BY semana DESC
                LIMIT 12
            """, [tenant_id])
            rows = dict_fetchall(cursor)
            # Convert dates to strings and reverse order
            for row in rows:
                row['semana'] = row['semana'].strftime('%Y-%m-%d') if row['semana'] else ''
            context['evolucion_precios'] = list(reversed(rows))
        except Exception as e:
            print(f"Error fetching evolucion precios: {e}")

        # Comparativa de portales
        try:
            cursor.execute("""
                SELECT
                    portal,
                    COALESCE(total_leads, 0) as total_leads,
                    COALESCE(leads_unicos, 0) as leads_unicos,
                    COALESCE(convertidos, 0) as convertidos,
                    COALESCE(tasa_conversion, 0) as tasa_conversion,
                    COALESCE(contactados, 0) as contactados,
                    COALESCE(tasa_contacto, 0) as tasa_contacto,
                    COALESCE(score_medio, 0) as score_medio,
                    COALESCE(precio_medio, 0) as precio_medio,
                    COALESCE(precio_m2_medio, 0) as precio_m2_medio
                FROM analytics.analytics_comparativa_portales
                WHERE tenant_id = %s
                ORDER BY total_leads DESC
            """, [tenant_id])
            context['comparativa_portales'] = dict_fetchall(cursor)
        except Exception as e:
            print(f"Error fetching comparativa portales: {e}")

        # Precios por zona
        try:
            cursor.execute("""
                SELECT
                    zona_clasificada,
                    COALESCE(precio_medio, 0) as precio_medio,
                    COALESCE(precio_mediana, 0) as precio_mediana,
                    COALESCE(precio_m2_medio, 0) as precio_m2_medio,
                    COALESCE(total_inmuebles, 0) as total_inmuebles
                FROM analytics.analytics_precios_por_zona
                WHERE tenant_id = %s
                  AND zona_clasificada IS NOT NULL
                  AND zona_clasificada != ''
                ORDER BY total_inmuebles DESC
                LIMIT 15
            """, [tenant_id])
            context['precios_por_zona'] = dict_fetchall(cursor)
        except Exception as e:
            print(f"Error fetching precios por zona: {e}")

        # Tipología de inmuebles
        try:
            cursor.execute("""
                SELECT
                    tipo_propiedad,
                    COALESCE(total, 0) as total,
                    COALESCE(porcentaje, 0) as porcentaje,
                    COALESCE(precio_medio, 0) as precio_medio,
                    COALESCE(precio_m2_medio, 0) as precio_m2_medio
                FROM analytics.analytics_tipologia_inmuebles
                WHERE tenant_id = %s
                  AND tipo_propiedad IS NOT NULL
                ORDER BY total DESC
            """, [tenant_id])
            context['tipologia_inmuebles'] = dict_fetchall(cursor)
        except Exception as e:
            print(f"Error fetching tipologia: {e}")

    # Convert lists to JSON for JavaScript
    context['leads_por_dia_json'] = json.dumps(context['leads_por_dia'])
    context['evolucion_precios_json'] = json.dumps(context['evolucion_precios'])
    context['embudo_json'] = json.dumps(context['embudo'])
    context['precios_por_zona_json'] = json.dumps(context['precios_por_zona'])
    context['tipologia_json'] = json.dumps(context['tipologia_inmuebles'])

    return render(request, 'analytics/dashboard.html', context)

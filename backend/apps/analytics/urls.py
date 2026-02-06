from django.urls import path
from django.views.generic import RedirectView
from .views import (
    analytics_dashboard_view, map_view, map_data_api, scrape_history_view, zones_grid_view,
    acm_view, acm_calcular_api, acm_lead_api, pdf_valoracion_view, pdf_lead_view,
    realtime_dashboard_view,
)
from . import api_views

app_name = 'analytics'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='analytics:dashboard'), name='index'),
    path('dashboard/', analytics_dashboard_view, name='dashboard'),
    path('realtime/', realtime_dashboard_view, name='realtime_dashboard'),
    path('mapa/', map_view, name='map'),
    path('scrapes/', scrape_history_view, name='scrape_history'),
    path('zonas/', zones_grid_view, name='zones_grid'),
    path('api/map-data/', map_data_api, name='map_data_api'),

    # ACM - Análisis Comparativo de Mercado
    path('valoracion/', acm_view, name='acm'),
    path('api/acm/', acm_calcular_api, name='acm_calcular'),
    path('api/acm/<str:lead_id>/', acm_lead_api, name='acm_lead'),

    # PDF de Valoración
    path('pdf/valoracion/', pdf_valoracion_view, name='pdf_valoracion'),
    path('pdf/lead/<str:lead_id>/', pdf_lead_view, name='pdf_lead'),

    # API endpoints with filter support
    path('api/kpis/', api_views.api_kpis, name='api_kpis'),
    path('api/embudo/', api_views.api_embudo, name='api_embudo'),
    path('api/leads-por-dia/', api_views.api_leads_por_dia, name='api_leads_por_dia'),
    path('api/evolucion-precios/', api_views.api_evolucion_precios, name='api_evolucion_precios'),
    path('api/comparativa-portales/', api_views.api_comparativa_portales, name='api_comparativa_portales'),
    path('api/precios-por-zona/', api_views.api_precios_por_zona, name='api_precios_por_zona'),
    path('api/tipologia/', api_views.api_tipologia, name='api_tipologia'),
    path('api/filter-options/', api_views.api_filter_options, name='api_filter_options'),
    path('api/export/', api_views.api_export_csv, name='api_export'),
]

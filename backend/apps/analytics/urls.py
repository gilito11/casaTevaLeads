from django.urls import path
from django.views.generic import RedirectView
from .views import analytics_dashboard_view, map_view, map_data_api, debug_dashboard
from . import api_views

app_name = 'analytics'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='analytics:dashboard'), name='index'),
    path('dashboard/', analytics_dashboard_view, name='dashboard'),
    path('debug/', debug_dashboard, name='debug'),  # TEMP - remove after debugging
    path('mapa/', map_view, name='map'),
    path('api/map-data/', map_data_api, name='map_data_api'),

    # New API endpoints with filter support
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

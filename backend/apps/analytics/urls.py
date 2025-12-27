from django.urls import path
from .views import analytics_dashboard_view, map_view, map_data_api

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', analytics_dashboard_view, name='dashboard'),
    path('mapa/', map_view, name='map'),
    path('api/map-data/', map_data_api, name='map_data_api'),
]

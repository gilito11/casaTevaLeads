from django.urls import path
from django.views.generic import RedirectView
from .views import analytics_dashboard_view, map_view, map_data_api

app_name = 'analytics'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='analytics:dashboard'), name='index'),
    path('dashboard/', analytics_dashboard_view, name='dashboard'),
    path('mapa/', map_view, name='map'),
    path('api/map-data/', map_data_api, name='map_data_api'),
]

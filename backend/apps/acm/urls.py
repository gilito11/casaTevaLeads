from django.urls import path
from . import views

app_name = 'acm'

urlpatterns = [
    # API REST endpoints
    path('api/generate/<str:lead_id>/', views.generate_acm, name='api_generate'),
    path('api/report/<str:lead_id>/', views.get_acm_report, name='api_report'),

    # HTMX endpoints for lead detail page
    path('htmx/generate/<str:lead_id>/', views.htmx_generate_acm, name='htmx_generate'),
    path('htmx/get/<str:lead_id>/', views.htmx_get_acm, name='htmx_get'),
]

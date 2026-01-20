from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import (
    LeadListView, LeadDetailView,
    ZonaListView,
    WebhookListCreateView, WebhookDetailView
)

app_name = 'api_v1'

urlpatterns = [
    # Leads
    path('leads/', LeadListView.as_view(), name='lead-list'),
    path('leads/<str:lead_id>/', LeadDetailView.as_view(), name='lead-detail'),

    # Zones
    path('zones/', ZonaListView.as_view(), name='zone-list'),

    # Webhooks
    path('webhooks/', WebhookListCreateView.as_view(), name='webhook-list'),
    path('webhooks/<int:webhook_id>/', WebhookDetailView.as_view(), name='webhook-detail'),

    # Documentation
    path('schema/', SpectacularAPIView.as_view(urlconf='api_v1.urls'), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api_v1:schema'), name='swagger-ui'),
]

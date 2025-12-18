"""
URLs para la API REST de leads.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from leads.api_views import LeadViewSet

router = DefaultRouter()
router.register(r'', LeadViewSet, basename='lead')

urlpatterns = [
    path('', include(router.urls)),
]

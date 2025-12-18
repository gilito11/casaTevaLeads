"""
URLs para la API REST de core (zonas, blacklist).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.api_views import (
    ZonaGeograficaViewSet,
    UsuarioBlacklistViewSet,
    ContadorUsuarioPortalViewSet
)

router = DefaultRouter()
router.register(r'zonas', ZonaGeograficaViewSet, basename='zona')
router.register(r'blacklist', UsuarioBlacklistViewSet, basename='blacklist')
router.register(r'contadores', ContadorUsuarioPortalViewSet, basename='contador')

urlpatterns = [
    path('', include(router.urls)),
]

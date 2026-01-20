"""
URLs para la API REST de leads.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from leads.api_views import LeadViewSet, TaskViewSet

router = DefaultRouter()
router.register(r'', LeadViewSet, basename='lead')

# Task router separado para mantener compatibilidad con API existente
task_router = DefaultRouter()
task_router.register(r'', TaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
    path('tasks/', include(task_router.urls)),
]

"""
URL configuration for casa_teva project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

from core.views import (
    login_view, logout_view, dashboard_view, profile_view,
    scrapers_view, add_zona_view, remove_zona_view, run_scraper_view, scraper_status_view,
    run_all_scrapers_view, scraper_status_partial_view
)


def health_check(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Health check
    path('health/', health_check, name='health_check'),

    # Auth
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Frontend
    path('', dashboard_view, name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('leads/', include('leads.urls', namespace='leads')),

    # Scrapers
    path('scrapers/', scrapers_view, name='scrapers'),
    path('scrapers/add-zona/', add_zona_view, name='add_zona'),
    path('scrapers/remove-zona/<int:zona_id>/', remove_zona_view, name='remove_zona'),
    path('scrapers/run/', run_scraper_view, name='run_scraper'),
    path('scrapers/run-all/', run_all_scrapers_view, name='run_all_scrapers'),
    path('scrapers/status/', scraper_status_view, name='scraper_status'),
    path('scrapers/status-partial/', scraper_status_partial_view, name='scraper_status_partial'),

    # REST API
    path('api/leads/', include('leads.api_urls')),
    path('api/core/', include('core.api_urls')),
    path('api/analytics/', include('analytics.urls')),
]

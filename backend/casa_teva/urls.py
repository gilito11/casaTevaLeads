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
from django.http import JsonResponse, FileResponse
from django.db import connection
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import (
    login_view, logout_view, dashboard_view, profile_view,
    scrapers_view, add_zona_view, remove_zona_view, run_scraper_view, scraper_status_view,
    run_all_scrapers_view, scraper_status_partial_view,
    run_botasaurus_view, scraping_jobs_partial_view, scraping_job_detail_view,
    clear_scraping_jobs_view, update_zona_radio_view, toggle_zona_portal_view
)
from notifications.views import alert_settings_view


def health_check(request):
    """Health check endpoint with database connectivity verification."""
    health = {'status': 'ok', 'database': 'unknown'}
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        health['database'] = 'ok'
    except Exception as e:
        health['status'] = 'degraded'
        health['database'] = 'error'
        health['database_error'] = str(e)[:100]
        status_code = 503

    return JsonResponse(health, status=status_code)


def system_status(request):
    """Detailed system status for remote monitoring. Requires auth or API key."""
    from django.contrib.auth.decorators import login_required
    from datetime import datetime, timedelta
    import platform

    # Allow API key auth for CLI access
    api_key = request.headers.get('X-API-Key') or request.GET.get('key')
    if not request.user.is_authenticated and not api_key:
        return JsonResponse({'error': 'auth required'}, status=401)

    if api_key:
        from api_v1.models import APIKey
        if not APIKey.objects.filter(is_active=True).exists():
            return JsonResponse({'error': 'invalid key'}, status=403)
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if not APIKey.objects.filter(key_hash=key_hash, is_active=True).exists():
            return JsonResponse({'error': 'invalid key'}, status=403)

    status = {
        'server': {
            'platform': platform.platform(),
            'python': platform.python_version(),
            'time': datetime.now().isoformat(),
        },
        'database': {},
        'scraping': {},
        'leads': {},
    }

    try:
        with connection.cursor() as cursor:
            # DB connectivity
            cursor.execute('SELECT 1')
            status['database']['connected'] = True

            # Last scrape per portal
            cursor.execute("""
                SELECT source_portal,
                       COUNT(*) as total,
                       MAX(fecha_scraping) as last_scrape
                FROM public_marts.dim_leads
                GROUP BY source_portal
                ORDER BY source_portal
            """)
            for row in cursor.fetchall():
                status['scraping'][row[0] or 'unknown'] = {
                    'total_leads': row[1],
                    'last_scrape': row[2].isoformat() if row[2] else None,
                }

            # Total leads and recent activity
            cursor.execute("""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE fecha_scraping >= NOW() - INTERVAL '24 hours'),
                       COUNT(*) FILTER (WHERE fecha_scraping >= NOW() - INTERVAL '7 days')
                FROM public_marts.dim_leads
            """)
            row = cursor.fetchone()
            status['leads'] = {
                'total': row[0],
                'last_24h': row[1],
                'last_7d': row[2],
            }

            # Contact queue status
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM leads_contactqueue
                GROUP BY status
            """)
            status['contact_queue'] = {row[0]: row[1] for row in cursor.fetchall()}

    except Exception as e:
        status['database']['connected'] = False
        status['database']['error'] = str(e)[:200]

    return JsonResponse(status)


def service_worker(request):
    """Serve the service worker from root path for maximum scope."""
    sw_path = settings.BASE_DIR / 'static' / 'service-worker.js'
    return FileResponse(
        open(sw_path, 'rb'),
        content_type='application/javascript',
        headers={'Service-Worker-Allowed': '/'}
    )


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Health check & status
    path('health/', health_check, name='health_check'),
    path('status/', system_status, name='system_status'),

    # PWA Service Worker (must be at root for full scope)
    path('service-worker.js', service_worker, name='service_worker'),

    # Push notifications API
    path('api/push/', include('notifications.urls', namespace='notifications')),

    # Auth
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Frontend
    path('', dashboard_view, name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('settings/alerts/', alert_settings_view, name='alert_settings'),
    path('leads/', include('leads.urls', namespace='leads')),
    path('analytics/', include('analytics.urls', namespace='analytics')),

    # Scrapers
    path('scrapers/', scrapers_view, name='scrapers'),
    path('scrapers/add-zona/', add_zona_view, name='add_zona'),
    path('scrapers/remove-zona/<int:zona_id>/', remove_zona_view, name='remove_zona'),
    path('scrapers/zona/<int:zona_id>/radio/', update_zona_radio_view, name='update_zona_radio'),
    path('scrapers/zona/<int:zona_id>/portal/<str:portal>/', toggle_zona_portal_view, name='toggle_zona_portal'),
    path('scrapers/run/', run_scraper_view, name='run_scraper'),
    path('scrapers/run-all/', run_all_scrapers_view, name='run_all_scrapers'),
    path('scrapers/status/', scraper_status_view, name='scraper_status'),
    path('scrapers/status-partial/', scraper_status_partial_view, name='scraper_status_partial'),
    path('scrapers/botasaurus/', run_botasaurus_view, name='run_botasaurus'),
    path('scrapers/jobs/', scraping_jobs_partial_view, name='scraping_jobs_partial'),
    path('scrapers/jobs/<int:job_id>/', scraping_job_detail_view, name='scraping_job_detail'),
    path('scrapers/jobs/clear/', clear_scraping_jobs_view, name='clear_scraping_jobs'),

    # REST API
    path('api/leads/', include('leads.api_urls')),
    path('api/core/', include('core.api_urls')),

    # API v1 (para integraciones externas con API Key)
    path('api/v1/', include('api_v1.urls', namespace='api_v1')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Widget valorador embebible
    path('widget/', include('widget.urls', namespace='widget')),
    path('api/widget/', include(('widget.api_urls', 'widget_api'))),

    # ACM - Analisis Comparativo de Mercado
    path('acm/', include('acm.urls', namespace='acm')),
]

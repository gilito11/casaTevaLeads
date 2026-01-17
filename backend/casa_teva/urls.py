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
from django.db import connection
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import (
    login_view, logout_view, dashboard_view, profile_view,
    scrapers_view, add_zona_view, remove_zona_view, run_scraper_view, scraper_status_view,
    run_all_scrapers_view, scraper_status_partial_view,
    run_botasaurus_view, scraping_jobs_partial_view, scraping_job_detail_view,
    clear_scraping_jobs_view, update_zona_radio_view, toggle_zona_portal_view
)


def health_check(request):
    """Health check endpoint with database connectivity verification."""
    health = {'status': 'ok', 'database': 'unknown'}
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
            health['database'] = 'ok'

            # Check contact automation tables if ?tables=1
            if request.GET.get('tables'):
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_name IN ('leads_contact_queue', 'leads_portal_session')
                """)
                health['contact_tables'] = [r[0] for r in cursor.fetchall()]

            # Create contact tables if ?create_contact_tables=secret123
            if request.GET.get('create_contact_tables') == 'secret123':
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS leads_contact_queue (
                            id BIGSERIAL PRIMARY KEY,
                            lead_id VARCHAR(100) NOT NULL,
                            portal VARCHAR(50) NOT NULL,
                            listing_url TEXT NOT NULL,
                            titulo VARCHAR(500),
                            mensaje TEXT NOT NULL,
                            estado VARCHAR(20) DEFAULT 'PENDIENTE',
                            prioridad INTEGER DEFAULT 0,
                            telefono_extraido VARCHAR(20),
                            mensaje_enviado BOOLEAN DEFAULT FALSE,
                            error TEXT,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            processed_at TIMESTAMP WITH TIME ZONE,
                            tenant_id INTEGER NOT NULL REFERENCES core_tenant(tenant_id) ON DELETE CASCADE,
                            created_by_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL
                        )
                    """)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS leads_portal_session (
                            id BIGSERIAL PRIMARY KEY,
                            portal VARCHAR(50) NOT NULL,
                            email VARCHAR(254) NOT NULL,
                            cookies JSONB NOT NULL,
                            is_valid BOOLEAN DEFAULT TRUE,
                            last_used TIMESTAMP WITH TIME ZONE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            expires_at TIMESTAMP WITH TIME ZONE,
                            tenant_id INTEGER NOT NULL REFERENCES core_tenant(tenant_id) ON DELETE CASCADE,
                            UNIQUE(tenant_id, portal)
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('leads', '0006_contact_automation', NOW())
                        ON CONFLICT DO NOTHING
                    """)
                    health['tables_created'] = True
                except Exception as e:
                    health['tables_created'] = False
                    health['create_error'] = str(e)[:200]

    except Exception as e:
        health['status'] = 'degraded'
        health['database'] = 'error'
        health['database_error'] = str(e)[:100]
        status_code = 503

    return JsonResponse(health, status=status_code)


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

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

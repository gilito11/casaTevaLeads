"""
Vistas principales de la aplicacion Core.
Dashboard, login, perfil, scrapers, etc.
"""
import subprocess
import sys
import threading
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta

from core.models import Tenant, TenantUser, ZonaGeografica, ZONAS_PREESTABLECIDAS, ZONAS_POR_REGION, ScrapingJob
from leads.models import Lead


def login_view(request):
    """Vista de login"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Guardar tenant en sesion si el usuario tiene uno
            tenant_user = TenantUser.objects.filter(user=user).first()
            if tenant_user:
                request.session['tenant_id'] = tenant_user.tenant.tenant_id
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contrasena incorrectos')

    return render(request, 'auth/login.html')


def logout_view(request):
    """Vista de logout"""
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    """Vista del dashboard principal con KPIs"""
    # Obtener tenant del usuario
    tenant_id = request.session.get('tenant_id')
    if not tenant_id:
        tenant_user = TenantUser.objects.filter(user=request.user).first()
        if tenant_user:
            tenant_id = tenant_user.tenant.tenant_id
            request.session['tenant_id'] = tenant_id

    # Filtrar leads por tenant
    leads_qs = Lead.objects.all()
    if tenant_id:
        leads_qs = leads_qs.filter(tenant_id=tenant_id)

    # KPIs
    today = timezone.now().date()
    start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))

    # Conteos por estado
    stats = leads_qs.aggregate(
        total=Count('lead_id'),
        nuevos=Count('lead_id', filter=Q(estado='NUEVO')),
        en_proceso=Count('lead_id', filter=Q(estado='EN_PROCESO')),
        contactados=Count('lead_id', filter=Q(estado='CONTACTADO_SIN_RESPUESTA')),
        interesados=Count('lead_id', filter=Q(estado='INTERESADO')),
        no_interesados=Count('lead_id', filter=Q(estado='NO_INTERESADO')),
        en_espera=Count('lead_id', filter=Q(estado='EN_ESPERA')),
        clientes=Count('lead_id', filter=Q(estado='CLIENTE')),
        ya_vendidos=Count('lead_id', filter=Q(estado='YA_VENDIDO')),
        no_contactar=Count('lead_id', filter=Q(estado='NO_CONTACTAR')),
    )

    # Leads nuevos hoy
    leads_hoy = leads_qs.filter(fecha_scraping__gte=start_of_day).count()

    # Tasa de conversion
    total_procesados = stats['clientes'] + stats['no_interesados'] + stats['ya_vendidos']
    tasa_conversion = (stats['clientes'] / total_procesados * 100) if total_procesados > 0 else 0

    # Leads por portal
    leads_por_portal = list(leads_qs.values('portal').annotate(count=Count('lead_id')))

    # Ultimos leads
    ultimos_leads = leads_qs.order_by('-fecha_scraping')[:10]

    # Estados disponibles para el grafico
    estados_chart = [
        {'nombre': 'Nuevo', 'valor': stats['nuevos'], 'color': '#3B82F6'},
        {'nombre': 'En Proceso', 'valor': stats['en_proceso'], 'color': '#06B6D4'},
        {'nombre': 'Contactado', 'valor': stats['contactados'], 'color': '#F97316'},
        {'nombre': 'Interesado', 'valor': stats['interesados'], 'color': '#22C55E'},
        {'nombre': 'No Interesado', 'valor': stats['no_interesados'], 'color': '#EF4444'},
        {'nombre': 'En Espera', 'valor': stats['en_espera'], 'color': '#EAB308'},
        {'nombre': 'Cliente', 'valor': stats['clientes'], 'color': '#10B981'},
        {'nombre': 'Ya Vendido', 'valor': stats['ya_vendidos'], 'color': '#6B7280'},
        {'nombre': 'No Contactar', 'valor': stats['no_contactar'], 'color': '#DC2626'},
    ]

    context = {
        'stats': stats,
        'leads_hoy': leads_hoy,
        'tasa_conversion': round(tasa_conversion, 1),
        'leads_por_portal': leads_por_portal,
        'ultimos_leads': ultimos_leads,
        'estados_chart': estados_chart,
        'estados': Lead.ESTADO_CHOICES,
    }

    return render(request, 'dashboard/index.html', context)


@login_required
def profile_view(request):
    """Vista del perfil de usuario"""
    tenant_user = TenantUser.objects.filter(user=request.user).select_related('tenant').first()

    # Estadisticas del usuario
    user_stats = {}
    if tenant_user:
        leads_qs = Lead.objects.filter(tenant_id=tenant_user.tenant.tenant_id)
        user_stats = {
            'total_leads': leads_qs.count(),
            'leads_asignados': leads_qs.filter(asignado_a_id=request.user.id).count(),
            'clientes_convertidos': leads_qs.filter(
                asignado_a_id=request.user.id,
                estado='CLIENTE'
            ).count(),
        }

    context = {
        'tenant_user': tenant_user,
        'user_stats': user_stats,
    }

    return render(request, 'profile/index.html', context)


# Variable global para rastrear scrapers en ejecución
_running_scrapers = {}

# Mapeo de zonas de la BD a zonas de Pisos.com
ZONA_MAPPING_PISOS = {
    # Lleida
    'tarragona_ciudad': 'tarragona_capital',
    'tarragona_20km': 'tarragona_provincia',
    'tarragona_30km': 'tarragona_provincia',
    'tarragona_40km': 'tarragona_provincia',
    'tarragona_50km': 'tarragona_provincia',
    'lleida_ciudad': 'lleida_capital',
    'lleida_20km': 'lleida_provincia',
    'lleida_30km': 'lleida_provincia',
    'lleida_40km': 'lleida_provincia',
    'lleida_50km': 'lleida_provincia',
    'la_bordeta': 'lleida_capital',
    'balaguer': 'balaguer',
    'mollerussa': 'mollerussa',
    'tremp': 'tremp',
    'tarrega': 'tarrega',
    # Costa Daurada
    'salou': 'salou',
    'cambrils': 'cambrils',
    'reus': 'reus',
    'vendrell': 'vendrell',
    'calafell': 'calafell',
    'torredembarra': 'torredembarra',
    'altafulla': 'altafulla',
    'miami_platja': 'miami_platja',
    'hospitalet_infant': 'hospitalet_infant',
    'coma_ruga': 'coma_ruga',
    'valls': 'valls',
    'montblanc': 'montblanc',
    'vila_seca': 'vila_seca',
    # Terres de l'Ebre
    'tortosa': 'tortosa',
    'amposta': 'amposta',
    'deltebre': 'deltebre',
    'ametlla_mar': 'ametlla_mar',
    'sant_carles_rapita': 'sant_carles_rapita',
}


@login_required
def scrapers_view(request):
    """Vista para gestionar scrapers y zonas"""
    tenant_id = request.session.get('tenant_id')
    tenant = None
    zonas = []

    if tenant_id:
        tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
        if tenant:
            zonas = ZonaGeografica.objects.filter(tenant=tenant)

    # Zonas activas del tenant
    zonas_activas_slugs = [z.slug for z in zonas]

    # Zonas agrupadas por región
    zonas_por_region = []
    for region_key, region_data in ZONAS_POR_REGION.items():
        region_zonas = []
        for zona_slug, zona_data in region_data['zonas'].items():
            region_zonas.append({
                'slug': zona_slug,
                'nombre': zona_data['nombre'],
                'radio_default': zona_data.get('radio_default', 20),
                'activa': zona_slug in zonas_activas_slugs,
            })
        zonas_por_region.append({
            'key': region_key,
            'nombre': region_data['nombre'],
            'zonas': region_zonas,
        })

    # Scrapers disponibles (4 portales activos)
    scrapers = [
        {'id': 'habitaclia', 'nombre': 'Habitaclia', 'descripcion': 'Portal inmobiliario catalan (Botasaurus)'},
        {'id': 'fotocasa', 'nombre': 'Fotocasa', 'descripcion': 'Portal inmobiliario (Botasaurus)'},
        {'id': 'milanuncios', 'nombre': 'Milanuncios', 'descripcion': 'Anuncios clasificados (ScrapingBee)'},
        {'id': 'idealista', 'nombre': 'Idealista', 'descripcion': 'Portal inmobiliario (ScrapingBee)'},
    ]

    context = {
        'tenant': tenant,
        'zonas': zonas,
        'zonas_por_region': zonas_por_region,
        'scrapers': scrapers,
        'running_scrapers': _running_scrapers,
    }

    return render(request, 'scrapers/index.html', context)


@login_required
def add_zona_view(request):
    """Añadir una zona preestablecida al tenant"""
    is_htmx = request.headers.get('HX-Request') == 'true'

    if request.method == 'POST':
        zona_slug = request.POST.get('zona_slug')
        tenant_id = request.session.get('tenant_id')

        if tenant_id and zona_slug:
            tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
            if tenant:
                try:
                    # Verificar si ya existe
                    if not ZonaGeografica.objects.filter(tenant=tenant, slug=zona_slug).exists():
                        ZonaGeografica.crear_desde_preestablecida(tenant, zona_slug)
                        if not is_htmx:
                            messages.success(request, f'Zona "{zona_slug}" añadida correctamente')
                    else:
                        if not is_htmx:
                            messages.warning(request, f'La zona "{zona_slug}" ya está configurada')
                except ValueError as e:
                    if not is_htmx:
                        messages.error(request, str(e))

    # Para HTMX: devolver ambos paneles actualizados
    if is_htmx:
        return zonas_partial_view(request)

    return redirect('scrapers')


@login_required
def zonas_partial_view(request):
    """Vista parcial que devuelve ambos paneles de zonas (HTMX)."""
    tenant_id = request.session.get('tenant_id')
    tenant = None
    zonas = []

    if tenant_id:
        tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
        if tenant:
            zonas = ZonaGeografica.objects.filter(tenant=tenant)

    # Zonas activas del tenant
    zonas_activas_slugs = [z.slug for z in zonas]

    # Zonas agrupadas por región
    zonas_por_region = []
    for region_key, region_data in ZONAS_POR_REGION.items():
        region_zonas = []
        for zona_slug, zona_data in region_data['zonas'].items():
            region_zonas.append({
                'slug': zona_slug,
                'nombre': zona_data['nombre'],
                'radio_default': zona_data.get('radio_default', 20),
                'activa': zona_slug in zonas_activas_slugs,
            })
        zonas_por_region.append({
            'key': region_key,
            'nombre': region_data['nombre'],
            'zonas': region_zonas,
        })

    context = {
        'zonas': zonas,
        'zonas_por_region': zonas_por_region,
    }
    return render(request, 'scrapers/partials/zonas_panels.html', context)


@login_required
def remove_zona_view(request, zona_id):
    """Eliminar una zona del tenant"""
    is_htmx = request.headers.get('HX-Request') == 'true'
    tenant_id = request.session.get('tenant_id')

    if tenant_id:
        zona = get_object_or_404(ZonaGeografica, id=zona_id, tenant_id=tenant_id)
        nombre = zona.nombre
        zona.delete()
        if not is_htmx:
            messages.success(request, f'Zona "{nombre}" eliminada')

    # Para HTMX: devolver ambos paneles actualizados
    if is_htmx:
        return zonas_partial_view(request)

    return redirect('scrapers')


def _run_scraper_process(scraper_id, zona_slug, scraper_key):
    """Ejecuta el scraper en un proceso separado"""
    try:
        # Determinar el script a ejecutar
        # __file__ = backend/apps/core/views.py -> subir 4 niveles para llegar a project root
        current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/apps/core
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))  # casa-teva-lead-system
        script_path = os.path.join(project_root, f'run_{scraper_id}_scraper.py')

        if os.path.exists(script_path):
            # Mapear zona si es scraper de pisos
            actual_zona = zona_slug
            if scraper_id == 'pisos':
                actual_zona = ZONA_MAPPING_PISOS.get(zona_slug)
                if not actual_zona:
                    _running_scrapers[scraper_key] = {
                        'status': 'error',
                        'error': f'Zona "{zona_slug}" no disponible para Pisos.com',
                    }
                    return

            # Ejecutar el scraper usando sys.executable para asegurar el Python correcto
            # Incluir PLAYWRIGHT_BROWSERS_PATH para Azure
            scraper_env = {
                **os.environ,
                'PYTHONPATH': project_root,
                'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/home/playwright'),
            }
            result = subprocess.run(
                [sys.executable, script_path, '--zones', actual_zona, '--postgres'],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos timeout
                cwd=project_root,
                env=scraper_env
            )
            _running_scrapers[scraper_key] = {
                'status': 'completed' if result.returncode == 0 else 'error',
                'output': result.stdout[:1000] if result.stdout else '',
                'error': result.stderr[:500] if result.stderr else '',
                'returncode': result.returncode,
            }
        else:
            _running_scrapers[scraper_key] = {
                'status': 'error',
                'error': f'Script no encontrado: {script_path}',
            }
    except subprocess.TimeoutExpired:
        _running_scrapers[scraper_key] = {
            'status': 'timeout',
            'error': 'El scraper tardó demasiado tiempo',
        }
    except Exception as e:
        _running_scrapers[scraper_key] = {
            'status': 'error',
            'error': str(e),
        }


@login_required
def run_scraper_view(request):
    """Ejecutar un scraper para una zona específica"""
    if request.method == 'POST':
        scraper_id = request.POST.get('scraper_id')
        zona_slug = request.POST.get('zona_slug')

        if scraper_id and zona_slug:
            scraper_key = f'{scraper_id}_{zona_slug}'

            # Verificar si ya está corriendo
            if scraper_key in _running_scrapers and _running_scrapers[scraper_key].get('status') == 'running':
                messages.warning(request, f'El scraper {scraper_id} ya está ejecutándose para la zona {zona_slug}')
            else:
                # Marcar como corriendo
                _running_scrapers[scraper_key] = {'status': 'running', 'started': timezone.now().isoformat()}

                # Ejecutar en un thread separado
                thread = threading.Thread(
                    target=_run_scraper_process,
                    args=(scraper_id, zona_slug, scraper_key)
                )
                thread.daemon = True
                thread.start()

                messages.success(request, f'Scraper {scraper_id} iniciado para zona {zona_slug}')

    return redirect('scrapers')


@login_required
def scraper_status_view(request):
    """API para obtener el estado de los scrapers"""
    return JsonResponse(_running_scrapers)


@login_required
def scraper_status_partial_view(request):
    """Vista parcial para HTMX que devuelve el banner de estado"""
    context = {
        'running_scrapers': _running_scrapers,
    }
    return render(request, 'scrapers/partials/status_banner.html', context)


def _run_all_scrapers_process(tenant_id, zonas, scraper_key):
    """Ejecuta todos los scrapers para todas las zonas en un proceso separado"""
    try:
        # __file__ = backend/apps/core/views.py -> subir 4 niveles para llegar a project root
        current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/apps/core
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))  # casa-teva-lead-system
        script_path = os.path.join(project_root, 'run_all_scrapers.py')

        if os.path.exists(script_path):
            # Construir lista de zonas como string separado por comas
            zone_slugs = ','.join([z.slug for z in zonas])

            # Ejecutar el script de todos los scrapers
            # Incluir PLAYWRIGHT_BROWSERS_PATH para Azure
            scraper_env = {
                **os.environ,
                'PYTHONPATH': project_root,
                'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/home/playwright'),
            }
            result = subprocess.run(
                [sys.executable, script_path, '--zones', zone_slugs, '--postgres'],
                capture_output=True,
                text=True,
                timeout=2700,  # 45 minutos timeout (Botasaurus con --single-process es más lento)
                cwd=project_root,
                env=scraper_env
            )
            _running_scrapers[scraper_key] = {
                'status': 'completed' if result.returncode == 0 else 'error',
                'output': result.stdout[-2000:] if result.stdout else '',
                'error': result.stderr[-500:] if result.stderr else '',
                'returncode': result.returncode,
                'zonas_count': len(zonas),
            }
        else:
            _running_scrapers[scraper_key] = {
                'status': 'error',
                'error': f'Script no encontrado: {script_path}',
            }
    except subprocess.TimeoutExpired:
        _running_scrapers[scraper_key] = {
            'status': 'timeout',
            'error': 'El scraping masivo tardó demasiado tiempo (>30 min)',
        }
    except Exception as e:
        _running_scrapers[scraper_key] = {
            'status': 'error',
            'error': str(e),
        }


@login_required
def run_all_scrapers_view(request):
    """Ejecutar todos los scrapers para todas las zonas configuradas"""
    if request.method == 'POST':
        tenant_id = request.session.get('tenant_id')

        if tenant_id:
            tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
            if tenant:
                zonas = list(ZonaGeografica.objects.filter(tenant=tenant))

                if not zonas:
                    messages.warning(request, 'No hay zonas configuradas. Añade zonas primero.')
                    return redirect('scrapers')

                scraper_key = f'all_scrapers_{tenant_id}'

                # Verificar si ya está corriendo
                if scraper_key in _running_scrapers and _running_scrapers[scraper_key].get('status') == 'running':
                    messages.warning(request, 'Ya hay un scraping masivo en ejecución. Espera a que termine.')
                else:
                    # Marcar como corriendo
                    _running_scrapers[scraper_key] = {
                        'status': 'running',
                        'started': timezone.now().isoformat(),
                        'zonas_count': len(zonas),
                    }

                    # Ejecutar en un thread separado
                    thread = threading.Thread(
                        target=_run_all_scrapers_process,
                        args=(tenant_id, zonas, scraper_key)
                    )
                    thread.daemon = True
                    thread.start()

                    messages.success(
                        request,
                        f'Scraping masivo iniciado para {len(zonas)} zonas. Esto puede tardar varios minutos.'
                    )
        else:
            messages.error(request, 'No se encontró el tenant')

    return redirect('scrapers')


# ============================================================
# NUEVAS VISTAS: Scraping con Botasaurus y feedback de leads
# ============================================================

def _run_botasaurus_scraper(job_id, portal, zona_slug):
    """
    Ejecuta el scraper en background y actualiza el ScrapingJob.
    Soporta Botasaurus (habitaclia, fotocasa) y ScrapingBee (milanuncios, idealista).
    """
    import re as regex_module

    try:
        job = ScrapingJob.objects.get(id=job_id)
        job.mark_running()

        # Construir path al proyecto
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

        encontrados = 0
        guardados = 0
        filtrados = 0
        errors = []

        # Mapeo de portales a scripts
        BOTASAURUS_PORTALS = {'habitaclia', 'fotocasa'}
        SCRAPINGBEE_PORTALS = {'milanuncios', 'idealista'}

        # Determinar qué portales ejecutar
        if portal == 'all':
            portals_to_run = ['habitaclia', 'fotocasa', 'milanuncios', 'idealista']
        else:
            portals_to_run = [portal]

        # Preparar environment
        scraper_env = {
            **os.environ,
            'PYTHONPATH': project_root,
        }

        for p in portals_to_run:
            if p in BOTASAURUS_PORTALS:
                # Botasaurus scraper
                script_path = os.path.join(project_root, f'run_{p}_scraper.py')
                cmd = [sys.executable, script_path, '--zones', zona_slug, '--postgres']
            elif p in SCRAPINGBEE_PORTALS:
                # ScrapingBee scraper
                script_path = os.path.join(project_root, f'run_scrapingbee_{p}_scraper.py')
                cmd = [sys.executable, script_path, '--zones', zona_slug, '--postgres']
            else:
                continue

            if not os.path.exists(script_path):
                errors.append(f"{p}: script not found")
                continue

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutos por portal
                    cwd=project_root,
                    env=scraper_env
                )

                # Parsear output
                output = result.stdout or ''
                for line in output.split('\n'):
                    # Buscar líneas de estadísticas
                    match = regex_module.search(r'(\d+)\s+guardados?', line)
                    if match:
                        guardados += int(match.group(1))
                    match = regex_module.search(r'(\d+)\s+filtrados?', line)
                    if match:
                        filtrados += int(match.group(1))
                    match = regex_module.search(r'Found\s+(\d+)\s+listings?', line, regex_module.IGNORECASE)
                    if match:
                        encontrados += int(match.group(1))
                    match = regex_module.search(r'Scraped\s+(\d+)', line, regex_module.IGNORECASE)
                    if match:
                        encontrados += int(match.group(1))

                if result.returncode != 0:
                    errors.append(f"{p}: {result.stderr[-200:] if result.stderr else 'unknown error'}")

            except subprocess.TimeoutExpired:
                errors.append(f"{p}: timeout (>5min)")

        # Actualizar job
        if errors and not guardados:
            job.mark_error("; ".join(errors)[:500])
        else:
            job.mark_completed(
                encontrados=encontrados,
                guardados=guardados,
                filtrados=filtrados
            )
            if errors:
                job.error_message = "; ".join(errors)[:500]
                job.save(update_fields=['error_message'])

    except Exception as e:
        try:
            job = ScrapingJob.objects.get(id=job_id)
            job.mark_error(str(e)[:500])
        except:
            pass


@login_required
def run_botasaurus_view(request):
    """
    Ejecutar scraper Botasaurus para un portal y zona específicos.
    Crea un ScrapingJob y devuelve su ID para tracking.

    Supports HTMX requests - returns partial HTML instead of redirect.
    """
    is_htmx = request.headers.get('HX-Request') == 'true'

    if request.method == 'POST':
        portal = request.POST.get('portal', 'all')
        zona_id = request.POST.get('zona_id')

        # Obtener tenant
        tenant_id = request.session.get('tenant_id')
        if not tenant_id:
            if is_htmx:
                return render(request, 'scrapers/partials/jobs_status.html', {
                    'jobs': [],
                    'has_running': False,
                    'error_message': 'No se encontró el tenant',
                })
            messages.error(request, 'No se encontró el tenant')
            return redirect('scrapers')

        tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

        # Obtener zona
        zona = None
        zona_nombre = 'Todas las zonas'
        zona_slug = None

        if zona_id:
            zona = get_object_or_404(ZonaGeografica, id=zona_id, tenant=tenant)
            zona_nombre = zona.nombre
            zona_slug = zona.slug
        else:
            # Si no hay zona específica, usar todas las zonas activas
            zonas = ZonaGeografica.objects.filter(tenant=tenant, activa=True)
            if zonas.exists():
                zona_slug = ','.join([z.slug for z in zonas])
                zona_nombre = f"{zonas.count()} zonas"
            else:
                if is_htmx:
                    return render(request, 'scrapers/partials/jobs_status.html', {
                        'jobs': [],
                        'has_running': False,
                        'error_message': 'No hay zonas activas configuradas',
                    })
                messages.warning(request, 'No hay zonas activas configuradas')
                return redirect('scrapers')

        # Verificar si ya hay un job corriendo para este portal/zona
        running_job = ScrapingJob.objects.filter(
            tenant=tenant,
            portal=portal,
            status='running'
        ).first()

        if running_job:
            if is_htmx:
                # Return current jobs status showing the running job
                jobs = list(ScrapingJob.objects.filter(tenant_id=tenant_id).order_by('-created_at')[:5])
                return render(request, 'scrapers/partials/jobs_status.html', {
                    'jobs': jobs,
                    'has_running': True,
                    'warning_message': f'Ya hay un scraping en ejecución para {portal}',
                })
            messages.warning(request, f'Ya hay un scraping en ejecución para {portal}')
            return redirect('scrapers')

        # Crear el job
        job = ScrapingJob.objects.create(
            tenant=tenant,
            portal=portal,
            zona=zona,
            zona_nombre=zona_nombre,
            status='pending'
        )

        # Ejecutar en thread separado
        thread = threading.Thread(
            target=_run_botasaurus_scraper,
            args=(job.id, portal, zona_slug)
        )
        thread.daemon = True
        thread.start()

        # For HTMX: return updated jobs partial
        if is_htmx:
            jobs = list(ScrapingJob.objects.filter(tenant_id=tenant_id).order_by('-created_at')[:5])
            has_running = ScrapingJob.objects.filter(tenant_id=tenant_id, status__in=['pending', 'running']).exists()
            return render(request, 'scrapers/partials/jobs_status.html', {
                'jobs': jobs,
                'has_running': has_running,
                'success_message': f'Scraping iniciado para {portal} - {zona_nombre}',
            })

        messages.success(request, f'Scraping iniciado para {portal} - {zona_nombre}')

    return redirect('scrapers')


@login_required
def scraping_jobs_partial_view(request):
    """
    Vista HTMX que devuelve el estado de los últimos jobs de scraping.
    Se actualiza cada 3 segundos mientras hay jobs corriendo.
    """
    tenant_id = request.session.get('tenant_id')
    if not tenant_id:
        # Render empty state instead of error for better UX
        return render(request, 'scrapers/partials/jobs_status.html', {
            'jobs': [],
            'has_running': False,
        })

    # Base queryset
    jobs_qs = ScrapingJob.objects.filter(tenant_id=tenant_id).order_by('-created_at')

    # Verificar si hay alguno corriendo para auto-refresh (antes del slice)
    has_running = jobs_qs.filter(status__in=['pending', 'running']).exists()

    # Últimos 5 jobs (slice después de la verificación)
    jobs = list(jobs_qs[:5])

    context = {
        'jobs': jobs,
        'has_running': has_running,
    }
    return render(request, 'scrapers/partials/jobs_status.html', context)


@login_required
def scraping_job_detail_view(request, job_id):
    """API para obtener el detalle de un job específico."""
    tenant_id = request.session.get('tenant_id')
    job = get_object_or_404(ScrapingJob, id=job_id, tenant_id=tenant_id)

    return JsonResponse({
        'id': job.id,
        'portal': job.portal,
        'zona': job.zona_nombre,
        'status': job.status,
        'leads_encontrados': job.leads_encontrados,
        'leads_guardados': job.leads_guardados,
        'leads_filtrados': job.leads_filtrados,
        'error': job.error_message,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
    })


@login_required
def clear_scraping_jobs_view(request):
    """Limpiar trabajos de scraping completados o con error."""
    if request.method == 'POST':
        tenant_id = request.session.get('tenant_id')
        if tenant_id:
            # Eliminar jobs que no están en ejecución
            deleted_count, _ = ScrapingJob.objects.filter(
                tenant_id=tenant_id,
                status__in=['completed', 'error']
            ).delete()

    # Devolver el partial actualizado
    return scraping_jobs_partial_view(request)


@login_required
def update_zona_radio_view(request, zona_id):
    """Actualizar el radio de búsqueda de una zona (HTMX)."""
    if request.method == 'POST':
        tenant_id = request.session.get('tenant_id')
        if tenant_id:
            zona = get_object_or_404(ZonaGeografica, id=zona_id, tenant_id=tenant_id)
            try:
                radio_km = int(request.POST.get('radio_km', 20))
                if 5 <= radio_km <= 50:
                    zona.radio_km = radio_km
                    zona.save(update_fields=['radio_km'])
            except (ValueError, TypeError):
                pass

    # HTMX swap=none, just return 200
    from django.http import HttpResponse
    return HttpResponse(status=200)

"""
Vistas principales de la aplicacion Core.
Dashboard, login, perfil, scrapers, etc.
"""
import subprocess
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

from core.models import Tenant, TenantUser, ZonaGeografica, ZONAS_PREESTABLECIDAS
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
        leads_qs = Lead.objects.filter(tenant=tenant_user.tenant)
        user_stats = {
            'total_leads': leads_qs.count(),
            'leads_asignados': leads_qs.filter(asignado_a=request.user).count(),
            'clientes_convertidos': leads_qs.filter(
                asignado_a=request.user,
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

    # Zonas preestablecidas disponibles
    zonas_disponibles = []
    zonas_activas_slugs = [z.slug for z in zonas]
    for slug, data in ZONAS_PREESTABLECIDAS.items():
        zonas_disponibles.append({
            'slug': slug,
            'nombre': data['nombre'],
            'lat': data['lat'],
            'lon': data['lon'],
            'provincia_id': data.get('provincia_id'),
            'activa': slug in zonas_activas_slugs,
        })

    # Scrapers disponibles
    scrapers = [
        {'id': 'milanuncios', 'nombre': 'Milanuncios', 'descripcion': 'Portal de anuncios clasificados'},
        {'id': 'wallapop', 'nombre': 'Wallapop', 'descripcion': 'Marketplace de segunda mano'},
        {'id': 'fotocasa', 'nombre': 'Fotocasa', 'descripcion': 'Portal inmobiliario'},
    ]

    context = {
        'tenant': tenant,
        'zonas': zonas,
        'zonas_disponibles': zonas_disponibles,
        'scrapers': scrapers,
        'running_scrapers': _running_scrapers,
    }

    return render(request, 'scrapers/index.html', context)


@login_required
def add_zona_view(request):
    """Añadir una zona preestablecida al tenant"""
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
                        messages.success(request, f'Zona "{zona_slug}" añadida correctamente')
                    else:
                        messages.warning(request, f'La zona "{zona_slug}" ya está configurada')
                except ValueError as e:
                    messages.error(request, str(e))

    return redirect('scrapers')


@login_required
def remove_zona_view(request, zona_id):
    """Eliminar una zona del tenant"""
    tenant_id = request.session.get('tenant_id')
    if tenant_id:
        zona = get_object_or_404(ZonaGeografica, id=zona_id, tenant_id=tenant_id)
        nombre = zona.nombre
        zona.delete()
        messages.success(request, f'Zona "{nombre}" eliminada')

    return redirect('scrapers')


def _run_scraper_process(scraper_id, zona_slug, scraper_key):
    """Ejecuta el scraper en un proceso separado"""
    try:
        # Determinar el script a ejecutar
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        script_path = os.path.join(project_root, f'run_{scraper_id}_scraper.py')

        if os.path.exists(script_path):
            # Ejecutar el scraper
            result = subprocess.run(
                ['python', script_path, '--zones', zona_slug, '--max-items', '10'],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos timeout
                cwd=project_root
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
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        script_path = os.path.join(project_root, 'run_all_scrapers.py')

        if os.path.exists(script_path):
            # Construir lista de zonas como string separado por comas
            zone_slugs = ','.join([z.slug for z in zonas])

            # Ejecutar el script de todos los scrapers
            result = subprocess.run(
                ['python', script_path, '--zones', zone_slugs, '--postgres'],
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutos timeout para todas las zonas
                cwd=project_root
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

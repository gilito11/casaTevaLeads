"""
Vistas principales de la aplicacion Core.
Dashboard, login, perfil, etc.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from core.models import Tenant, TenantUser
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

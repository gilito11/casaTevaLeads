"""
Vistas para la gestion de Leads.
Lista, detalle, cambio de estado, notas, etc.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q

from leads.models import Lead, Nota, LeadEstado
from core.models import TenantUser, Tenant


def get_user_tenant(request):
    """Obtiene el tenant del usuario actual"""
    tenant_id = request.session.get('tenant_id')
    if not tenant_id:
        tenant_user = TenantUser.objects.filter(user=request.user).first()
        if tenant_user:
            tenant_id = tenant_user.tenant.tenant_id
            request.session['tenant_id'] = tenant_id
    return tenant_id


@login_required
def lead_list_view(request):
    """Vista de lista de leads con filtros y paginacion"""
    tenant_id = get_user_tenant(request)

    # Base queryset
    leads_qs = Lead.objects.all()
    if tenant_id:
        leads_qs = leads_qs.filter(tenant_id=tenant_id)

    # Filtros
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    portal = request.GET.get('portal', '')
    zona = request.GET.get('zona', '')

    if q:
        leads_qs = leads_qs.filter(
            Q(telefono_norm__icontains=q) |
            Q(nombre__icontains=q) |
            Q(direccion__icontains=q) |
            Q(zona_geografica__icontains=q)
        )

    if portal:
        leads_qs = leads_qs.filter(portal=portal)

    if zona:
        leads_qs = leads_qs.filter(zona_geografica=zona)

    # Ordenar
    leads_qs = leads_qs.order_by('-fecha_scraping')

    # Paginacion
    paginator = Paginator(leads_qs, 25)
    page = request.GET.get('page', 1)
    leads = paginator.get_page(page)

    # Obtener estados de LeadEstado para todos los leads de la página
    lead_ids = [str(lead.lead_id) for lead in leads]
    lead_estados = {
        le.lead_id: le.estado
        for le in LeadEstado.objects.filter(lead_id__in=lead_ids)
    }

    # Añadir estado_actual a cada lead
    for lead in leads:
        lead.estado_actual = lead_estados.get(str(lead.lead_id), lead.estado)

    # Filtrar por estado después de obtener estados reales
    if estado:
        # Filtrar leads cuyo estado_actual coincida
        leads_filtered = [l for l in leads if l.estado_actual == estado]
        # Recalcular total para el filtro de estado
        # Nota: Este filtro es aproximado, idealmente se haría en la query

    # Zonas para filtro
    zonas = Lead.objects.values_list('zona_geografica', flat=True).distinct()

    context = {
        'leads': leads,
        'total_leads': paginator.count,
        'estados': Lead.ESTADO_CHOICES,
        'zonas': zonas,
    }

    # Si es peticion HTMX, devolver solo la tabla
    if request.headers.get('HX-Request'):
        return render(request, 'leads/partials/lead_table.html', context)

    return render(request, 'leads/list.html', context)


@login_required
def lead_detail_view(request, lead_id):
    """Vista de detalle de un lead"""
    tenant_id = get_user_tenant(request)

    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Verificar que el lead pertenece al tenant del usuario
    if tenant_id and lead.tenant_id != tenant_id:
        return redirect('leads:list')

    # Obtener notas del lead
    notas = lead.notas.select_related('autor').all()

    # Obtener estado de LeadEstado (tabla gestionada por Django)
    lead_estado = LeadEstado.objects.filter(lead_id=str(lead.lead_id)).first()
    estado_actual = lead_estado.estado if lead_estado else lead.estado

    context = {
        'lead': lead,
        'notas': notas,
        'estados': Lead.ESTADO_CHOICES,
        'estado_actual': estado_actual,
        'lead_estado': lead_estado,
    }

    return render(request, 'leads/detail.html', context)


@login_required
def change_status_view(request, lead_id):
    """Vista para cambiar el estado de un lead (HTMX)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Verificar que el lead pertenece al tenant del usuario
    if tenant_id and lead.tenant_id != tenant_id:
        return HttpResponse(status=403)

    nuevo_estado = request.POST.get('estado')
    if nuevo_estado and nuevo_estado in dict(Lead.ESTADO_CHOICES):
        # Usar LeadEstado para guardar el estado (tabla gestionada por Django)
        # El Lead apunta a una VIEW de dbt que es read-only
        lead_estado, created = LeadEstado.objects.get_or_create(
            lead_id=str(lead.lead_id),
            defaults={
                'tenant_id': lead.tenant_id,
                'telefono_norm': lead.telefono_norm,
                'estado': nuevo_estado,
            }
        )

        lead_estado.estado = nuevo_estado
        lead_estado.fecha_cambio_estado = timezone.now()

        # Si es el primer contacto
        if nuevo_estado in ['CONTACTADO_SIN_RESPUESTA', 'INTERESADO', 'NO_INTERESADO']:
            if not lead_estado.fecha_primer_contacto:
                lead_estado.fecha_primer_contacto = timezone.now()
            lead_estado.fecha_ultimo_contacto = timezone.now()
            lead_estado.numero_intentos += 1

        lead_estado.save()

    # Si viene del detalle, recargar toda la pagina
    if request.headers.get('HX-Target') == 'body':
        return redirect('leads:detail', lead_id=lead_id)

    # Obtener estado actual de LeadEstado
    lead_estado = LeadEstado.objects.filter(lead_id=str(lead.lead_id)).first()
    current_estado = lead_estado.estado if lead_estado else lead.estado

    # Si viene de la tabla, devolver solo la fila actualizada
    context = {
        'lead': lead,
        'lead_estado': current_estado,
        'estados': Lead.ESTADO_CHOICES,
    }

    html = render_to_string('leads/partials/lead_row.html', context, request)
    return HttpResponse(html)


@login_required
def add_note_view(request, lead_id):
    """Vista para agregar una nota a un lead (HTMX)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Verificar que el lead pertenece al tenant del usuario
    if tenant_id and lead.tenant_id != tenant_id:
        return HttpResponse(status=403)

    texto = request.POST.get('texto', '').strip()
    if texto:
        nota = Nota.objects.create(
            lead=lead,
            autor=request.user,
            texto=texto
        )

        # Devolver HTML de la nota creada
        context = {'nota': nota}
        html = render_to_string('leads/partials/note_item.html', context, request)
        return HttpResponse(html)

    return HttpResponse(status=400)

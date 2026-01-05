"""
Vistas para la gestion de Leads.
Lista, detalle, cambio de estado, notas, etc.
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q
from django.db import connection
from django.views.decorators.http import require_POST

from leads.models import Lead, Nota, LeadEstado, AnuncioBlacklist
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

    # Ordenamiento
    orden = request.GET.get('orden', '')
    if orden == '-lead_score':
        leads_qs = leads_qs.order_by('-lead_score', '-fecha_scraping')
    elif orden == 'lead_score':
        leads_qs = leads_qs.order_by('lead_score', '-fecha_scraping')

    # Filtrar por estado usando LeadEstado
    if estado:
        # Obtener lead_ids que tienen el estado especificado en LeadEstado
        lead_ids_with_estado = LeadEstado.objects.filter(
            estado=estado
        ).values_list('lead_id', flat=True)

        if estado == 'NUEVO':
            # Para estado NUEVO: leads que no tienen LeadEstado O tienen estado NUEVO
            leads_qs = leads_qs.filter(
                Q(lead_id__in=[lid for lid in lead_ids_with_estado]) |
                ~Q(lead_id__in=LeadEstado.objects.values_list('lead_id', flat=True))
            )
        else:
            # Para otros estados: solo los que tienen ese estado en LeadEstado
            leads_qs = leads_qs.filter(lead_id__in=[lid for lid in lead_ids_with_estado])

    # Ordenar por defecto si no hay orden especificado
    if not orden:
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

    # Zonas para filtro - obtener zonas únicas no vacías
    zonas = (Lead.objects
             .exclude(zona_geografica__isnull=True)
             .exclude(zona_geografica='')
             .values_list('zona_geografica', flat=True)
             .distinct()
             .order_by('zona_geografica'))

    context = {
        'leads': leads,
        'total_leads': paginator.count,
        'estados': Lead.ESTADO_CHOICES,
        'zonas': list(zonas),
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

    # Si viene del detalle, usar HX-Redirect para recargar la pagina completa
    if request.headers.get('HX-Target') == 'body':
        from django.urls import reverse
        response = HttpResponse()
        response['HX-Redirect'] = reverse('leads:detail', kwargs={'lead_id': lead_id})
        return response

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


@login_required
def delete_lead_view(request, lead_id):
    """Vista para eliminar un lead (HTMX)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Verificar que el lead pertenece al tenant del usuario
    if tenant_id and lead.tenant_id != tenant_id:
        return HttpResponse(status=403)

    # Eliminar el estado del lead si existe
    LeadEstado.objects.filter(lead_id=str(lead.lead_id)).delete()

    # Eliminar notas asociadas usando SQL directo (el FK apunta a una vista con lead_id tipo texto)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM leads_nota WHERE lead_id = %s", [lead_id])

    # Eliminar el lead de la tabla public_marts.dim_leads
    with connection.cursor() as cursor:
        cursor.execute("""
            DELETE FROM public_marts.dim_leads
            WHERE lead_id = %s
        """, [lead_id])

    # Devolver respuesta vacía para que HTMX elimine la fila
    return HttpResponse("")


@login_required
@require_POST
def bulk_change_status_view(request):
    """Vista para cambiar el estado de múltiples leads a la vez"""
    try:
        data = json.loads(request.body)
        lead_ids = data.get('lead_ids', [])
        nuevo_estado = data.get('estado')

        if not lead_ids or not nuevo_estado:
            return JsonResponse({'error': 'Faltan parámetros'}, status=400)

        if nuevo_estado not in dict(Lead.ESTADO_CHOICES):
            return JsonResponse({'error': 'Estado inválido'}, status=400)

        tenant_id = get_user_tenant(request)
        updated_count = 0

        for lead_id in lead_ids:
            try:
                lead = Lead.objects.get(lead_id=lead_id)

                # Verificar que el lead pertenece al tenant
                if tenant_id and lead.tenant_id != tenant_id:
                    continue

                # Usar LeadEstado para guardar el estado
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

                if nuevo_estado in ['CONTACTADO_SIN_RESPUESTA', 'INTERESADO', 'NO_INTERESADO']:
                    if not lead_estado.fecha_primer_contacto:
                        lead_estado.fecha_primer_contacto = timezone.now()
                    lead_estado.fecha_ultimo_contacto = timezone.now()
                    lead_estado.numero_intentos += 1

                lead_estado.save()
                updated_count += 1

            except Lead.DoesNotExist:
                continue

        return JsonResponse({'updated': updated_count})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)


@login_required
@require_POST
def bulk_delete_view(request):
    """Vista para eliminar múltiples leads a la vez, opcionalmente añadiéndolos a blacklist"""
    try:
        data = json.loads(request.body)
        leads_info = data.get('leads_info', [])
        add_to_blacklist = data.get('add_to_blacklist', False)

        if not leads_info:
            return JsonResponse({'error': 'No se especificaron leads'}, status=400)

        tenant_id = get_user_tenant(request)
        deleted_count = 0
        blacklisted_count = 0

        for info in leads_info:
            lead_id = info.get('lead_id')
            anuncio_id = info.get('anuncio_id', '')
            portal = info.get('portal', '')

            if not lead_id:
                continue

            try:
                lead = Lead.objects.get(lead_id=lead_id)

                # Verificar que el lead pertenece al tenant
                if tenant_id and lead.tenant_id != tenant_id:
                    continue

                # Si hay que añadir a blacklist y tenemos la info necesaria
                if add_to_blacklist and portal:
                    # Usar anuncio_id si está disponible, sino usar el lead_id
                    blacklist_id = anuncio_id if anuncio_id else lead_id
                    try:
                        tenant = Tenant.objects.get(tenant_id=tenant_id)
                        AnuncioBlacklist.objects.get_or_create(
                            tenant=tenant,
                            portal=portal,
                            anuncio_id=blacklist_id,
                            defaults={
                                'url_anuncio': lead.url_anuncio,
                                'titulo': lead.direccion or lead.descripcion[:200] if lead.descripcion else '',
                                'motivo': 'Eliminado por el usuario y marcado para no volver a scrapear',
                                'created_by': request.user,
                            }
                        )
                        blacklisted_count += 1
                    except Exception:
                        pass  # Si falla el blacklist, continuamos con el delete

                # Eliminar estado del lead
                LeadEstado.objects.filter(lead_id=str(lead_id)).delete()

                # Eliminar notas
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM leads_nota WHERE lead_id = %s", [lead_id])

                # Eliminar de public_marts.dim_leads
                with connection.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM public_marts.dim_leads
                        WHERE lead_id = %s
                    """, [lead_id])

                deleted_count += 1

            except Lead.DoesNotExist:
                continue

        return JsonResponse({
            'deleted': deleted_count,
            'blacklisted': blacklisted_count
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

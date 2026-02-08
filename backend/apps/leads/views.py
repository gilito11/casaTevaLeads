"""
Vistas para la gestion de Leads.
Lista, detalle, cambio de estado, notas, etc.
"""
import csv
import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q
from django.db import connection, models, IntegrityError
from django.views.decorators.http import require_POST

from leads.models import Lead, Nota, LeadEstado, AnuncioBlacklist, Contact, Interaction, Task
from core.models import TenantUser, Tenant

logger = logging.getLogger(__name__)


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
    asignado = request.GET.get('asignado', '')  # 'me' para mis leads, user_id, o '' para todos

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

    # Filtrar por asignacion
    if asignado:
        if asignado == 'me':
            # Mis leads (asignados al usuario actual)
            lead_ids_asignados = LeadEstado.objects.filter(
                asignado_a=request.user
            ).values_list('lead_id', flat=True)
            leads_qs = leads_qs.filter(lead_id__in=[lid for lid in lead_ids_asignados])
        elif asignado == 'unassigned':
            # Leads sin asignar
            lead_ids_asignados = LeadEstado.objects.exclude(
                asignado_a__isnull=True
            ).values_list('lead_id', flat=True)
            leads_qs = leads_qs.exclude(lead_id__in=[lid for lid in lead_ids_asignados])
        else:
            # Leads asignados a un usuario especifico
            lead_ids_asignados = LeadEstado.objects.filter(
                asignado_a_id=asignado
            ).values_list('lead_id', flat=True)
            leads_qs = leads_qs.filter(lead_id__in=[lid for lid in lead_ids_asignados])

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

    # Obtener nombres de Contact editados por el usuario
    telefono_list = [lead.telefono_norm for lead in leads if lead.telefono_norm]
    contact_nombres = {
        c.telefono: c.nombre
        for c in Contact.objects.filter(tenant_id=tenant_id, telefono__in=telefono_list)
        if c.nombre  # Solo si tiene nombre editado
    }

    # Obtener asignaciones de LeadEstado
    lead_asignaciones = {
        le.lead_id: le.asignado_a
        for le in LeadEstado.objects.filter(lead_id__in=lead_ids).select_related('asignado_a')
    }

    # Añadir estado_actual, nombre de contacto y asignado_a a cada lead
    for lead in leads:
        lead.estado_actual = lead_estados.get(str(lead.lead_id), lead.estado)
        lead.asignado_a_user = lead_asignaciones.get(str(lead.lead_id))
        # Usar nombre de Contact si está editado, sino el original
        contact_nombre = contact_nombres.get(lead.telefono_norm)
        if contact_nombre:
            lead.nombre = contact_nombre

    # Obtener usuarios del tenant para dropdown de asignacion
    team_users = get_tenant_users(tenant_id)

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
        'team_users': team_users,
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

    # Notas asociadas al lead (evaluate eagerly to catch DB errors)
    try:
        notas = list(Nota.objects.filter(lead_id=str(lead.lead_id)).order_by('-created_at'))
    except Exception:
        notas = []

    # Obtener estado de LeadEstado (tabla gestionada por Django)
    lead_estado = LeadEstado.objects.filter(lead_id=str(lead.lead_id)).first()
    estado_actual = lead_estado.estado if lead_estado else lead.estado

    # Obtener nombre de Contact si está editado
    contact = Contact.objects.filter(
        tenant_id=tenant_id,
        telefono=lead.telefono_norm
    ).first()
    if contact and contact.nombre:
        lead.nombre = contact.nombre

    # Obtener usuarios del tenant para dropdown de asignacion
    team_users = get_tenant_users(tenant_id)

    # Verificar duplicados cross-portal
    duplicate_info = None
    duplicate_leads = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT duplicate_group_id, num_portales, portales, match_type, num_leads_grupo
                FROM public_marts.dim_lead_duplicates
                WHERE lead_id = %s AND tenant_id = %s
            """, [str(lead.lead_id), tenant_id])
            row = cursor.fetchone()
            if row:
                duplicate_info = {
                    'group_id': row[0],
                    'num_portales': row[1],
                    'portales': row[2],
                    'match_type': row[3],
                    'num_leads': row[4],
                }
                # Obtener otros leads del mismo grupo
                cursor.execute("""
                    SELECT d.lead_id, l.portal, l.precio, l.superficie_m2, l.titulo, l.url_anuncio
                    FROM public_marts.dim_lead_duplicates d
                    JOIN public_marts.dim_leads l ON d.lead_id = l.lead_id AND d.tenant_id = l.tenant_id
                    WHERE d.duplicate_group_id = %s
                      AND d.tenant_id = %s
                      AND d.lead_id != %s
                    ORDER BY l.portal
                """, [row[0], tenant_id, str(lead.lead_id)])
                for dup_row in cursor.fetchall():
                    duplicate_leads.append({
                        'lead_id': dup_row[0],
                        'portal': dup_row[1],
                        'precio': dup_row[2],
                        'metros': dup_row[3],
                        'titulo': dup_row[4],
                        'url': dup_row[5],
                    })
    except Exception:
        pass  # Tabla puede no existir aun

    # Obtener tareas asociadas a este lead
    lead_tasks = Task.objects.filter(
        tenant_id=tenant_id,
        lead_id=str(lead.lead_id)
    ).order_by('completada', 'fecha_vencimiento')

    context = {
        'lead': lead,
        'notas': notas,
        'estados': Lead.ESTADO_CHOICES,
        'estado_actual': estado_actual,
        'lead_estado': lead_estado,
        'team_users': team_users,
        'duplicate_info': duplicate_info,
        'duplicate_leads': duplicate_leads,
        'lead_tasks': lead_tasks,
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

    # Obtener nombre de Contact si está editado
    contact = Contact.objects.filter(
        tenant_id=tenant_id,
        telefono=lead.telefono_norm
    ).first()
    if contact and contact.nombre:
        lead.nombre = contact.nombre

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

    # Delete from raw_listings (source of truth) - dbt view will update on next run
    with connection.cursor() as cursor:
        cursor.execute("""
            DELETE FROM raw.raw_listings
            WHERE (raw_data->>'anuncio_id') IN (
                SELECT source_listing_id FROM public_marts.dim_leads WHERE lead_id = %s
            )
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
        failed_ids = []

        for lead_id in lead_ids:
            try:
                lead = Lead.objects.get(lead_id=lead_id)

                # Verificar que el lead pertenece al tenant
                if tenant_id and lead.tenant_id != tenant_id:
                    failed_ids.append({'id': lead_id, 'reason': 'tenant_mismatch'})
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
                failed_ids.append({'id': lead_id, 'reason': 'not_found'})

        response = {'updated': updated_count}
        if failed_ids:
            response['failed'] = failed_ids
        return JsonResponse(response)

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
        failed_ids = []

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
                    failed_ids.append({'id': lead_id, 'reason': 'tenant_mismatch'})
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
                    except (Tenant.DoesNotExist, IntegrityError) as e:
                        logger.warning(f"Could not add lead {lead_id} to blacklist: {e}")

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
                failed_ids.append({'id': lead_id, 'reason': 'not_found'})

        response = {
            'deleted': deleted_count,
            'blacklisted': blacklisted_count
        }
        if failed_ids:
            response['failed'] = failed_ids
        return JsonResponse(response)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)


# ============================================================
# CONTACT MANAGEMENT VIEWS
# ============================================================

@login_required
def contact_list_view(request):
    """Vista de lista de contactos con sus propiedades agrupadas"""
    tenant_id = get_user_tenant(request)

    # Base queryset
    contacts_qs = Contact.objects.filter(tenant_id=tenant_id).order_by('-updated_at')

    # Filtros
    q = request.GET.get('q', '').strip()
    if q:
        contacts_qs = contacts_qs.filter(
            Q(telefono__icontains=q) |
            Q(nombre__icontains=q) |
            Q(email__icontains=q)
        )

    # Paginacion
    paginator = Paginator(contacts_qs, 25)
    page = request.GET.get('page', 1)
    contacts = paginator.get_page(page)

    context = {
        'contacts': contacts,
        'total_contacts': paginator.count,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'contacts/partials/contact_table.html', context)

    return render(request, 'contacts/list.html', context)


@login_required
def contact_detail_view(request, contact_id):
    """Vista de detalle de un contacto con sus propiedades e interacciones"""
    tenant_id = get_user_tenant(request)
    contact = get_object_or_404(Contact, id=contact_id, tenant_id=tenant_id)

    # Obtener leads/propiedades del contacto
    leads = contact.get_leads()

    # Obtener estados de LeadEstado para los leads
    lead_ids = [str(lead.lead_id) for lead in leads]
    lead_estados = {
        le.lead_id: le.estado
        for le in LeadEstado.objects.filter(lead_id__in=lead_ids)
    }

    # Añadir estado_actual a cada lead
    for lead in leads:
        lead.estado_actual = lead_estados.get(str(lead.lead_id), lead.estado)

    # Interacciones
    interactions = contact.interactions.select_related('usuario').all()

    context = {
        'contact': contact,
        'leads': leads,
        'interactions': interactions,
        'interaction_tipos': Interaction.TIPO_CHOICES,
        'estados': Lead.ESTADO_CHOICES,
    }

    return render(request, 'contacts/detail.html', context)


@login_required
def contact_from_lead_view(request, lead_id):
    """Crea o redirige al contacto asociado a un lead"""
    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    if tenant_id and lead.tenant_id != tenant_id:
        return redirect('leads:list')

    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

    # Buscar o crear contacto
    contact, created = Contact.objects.get_or_create(
        tenant=tenant,
        telefono=lead.telefono_norm,
        defaults={
            'nombre': lead.nombre,
            'email': lead.email,
        }
    )

    return redirect('leads:contact_detail', contact_id=contact.id)


@login_required
@require_POST
def contact_update_view(request, contact_id):
    """Actualizar informacion de un contacto (HTMX)"""
    tenant_id = get_user_tenant(request)
    contact = get_object_or_404(Contact, id=contact_id, tenant_id=tenant_id)

    # Actualizar campos
    contact.nombre = request.POST.get('nombre', '').strip() or None
    contact.telefono2 = request.POST.get('telefono2', '').strip() or None
    contact.email = request.POST.get('email', '').strip() or None
    contact.notas = request.POST.get('notas', '').strip() or None
    contact.save()

    # Si es HTMX, devolver el partial actualizado
    if request.headers.get('HX-Request'):
        context = {'contact': contact}
        return render(request, 'contacts/partials/contact_info.html', context)

    return redirect('leads:contact_detail', contact_id=contact.id)


@login_required
@require_POST
def add_interaction_view(request, contact_id):
    """Agregar una interaccion a un contacto (HTMX)"""
    tenant_id = get_user_tenant(request)
    contact = get_object_or_404(Contact, id=contact_id, tenant_id=tenant_id)

    tipo = request.POST.get('tipo', 'nota')
    descripcion = request.POST.get('descripcion', '').strip()
    fecha_str = request.POST.get('fecha', '')

    # Validar tipo contra TIPO_CHOICES
    tipos_validos = [choice[0] for choice in Interaction.TIPO_CHOICES]
    if tipo not in tipos_validos:
        tipo = 'nota'

    if descripcion:
        # Parsear fecha si se proporciona
        fecha = None
        if fecha_str:
            try:
                from datetime import datetime
                fecha = timezone.make_aware(datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M'))
            except ValueError:
                fecha = timezone.now()
        else:
            fecha = timezone.now()

        interaction = Interaction.objects.create(
            contact=contact,
            tipo=tipo,
            descripcion=descripcion,
            fecha=fecha,
            usuario=request.user
        )

        # Devolver HTML de la interaccion creada
        if request.headers.get('HX-Request'):
            context = {'interaction': interaction}
            return render(request, 'contacts/partials/interaction_item.html', context)

    return redirect('leads:contact_detail', contact_id=contact.id)


@login_required
@require_POST
def delete_interaction_view(request, interaction_id):
    """Eliminar una interaccion (HTMX)"""
    tenant_id = get_user_tenant(request)
    interaction = get_object_or_404(
        Interaction,
        id=interaction_id,
        contact__tenant_id=tenant_id
    )

    interaction.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')

    return redirect('leads:contact_detail', contact_id=interaction.contact_id)


# ============================================================
# LEAD ASSIGNMENT VIEWS
# ============================================================

def get_tenant_users(tenant_id):
    """Obtiene los usuarios del tenant para asignacion (excluye admins)"""
    from django.contrib.auth.models import User
    user_ids = TenantUser.objects.filter(
        tenant_id=tenant_id
    ).values_list('user_id', flat=True)
    return User.objects.filter(id__in=user_ids).exclude(
        is_superuser=True
    ).exclude(
        is_staff=True
    ).order_by('first_name', 'username')


@login_required
@require_POST
def assign_lead_view(request, lead_id):
    """Asignar un lead a un usuario del tenant (HTMX)"""
    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    if tenant_id and lead.tenant_id != tenant_id:
        return HttpResponse(status=403)

    user_id = request.POST.get('user_id')

    # Obtener o crear LeadEstado
    lead_estado, created = LeadEstado.objects.get_or_create(
        lead_id=str(lead.lead_id),
        defaults={
            'tenant_id': lead.tenant_id,
            'telefono_norm': lead.telefono_norm,
            'estado': 'NUEVO',
        }
    )

    # Asignar usuario (o None si se deselecciona)
    from django.contrib.auth.models import User
    if user_id:
        lead_estado.asignado_a = User.objects.filter(id=user_id).first()
    else:
        lead_estado.asignado_a = None
    lead_estado.save()

    # Si es HTMX, devolver partial actualizado
    if request.headers.get('HX-Request'):
        team_users = get_tenant_users(tenant_id)
        context = {
            'lead': lead,
            'lead_estado': lead_estado,
            'team_users': team_users,
        }
        return render(request, 'leads/partials/assign_section.html', context)

    return redirect('leads:detail', lead_id=lead_id)


@login_required
@require_POST
def bulk_assign_view(request):
    """Asignar multiples leads a un usuario"""
    try:
        data = json.loads(request.body)
        lead_ids = data.get('lead_ids', [])
        user_id = data.get('user_id')  # None para desasignar

        if not lead_ids:
            return JsonResponse({'error': 'No se especificaron leads'}, status=400)

        tenant_id = get_user_tenant(request)
        from django.contrib.auth.models import User
        assigned_user = User.objects.filter(id=user_id).first() if user_id else None

        updated_count = 0
        for lead_id in lead_ids:
            try:
                lead = Lead.objects.get(lead_id=lead_id)
                if tenant_id and lead.tenant_id != tenant_id:
                    continue

                lead_estado, created = LeadEstado.objects.get_or_create(
                    lead_id=str(lead.lead_id),
                    defaults={
                        'tenant_id': lead.tenant_id,
                        'telefono_norm': lead.telefono_norm,
                        'estado': 'NUEVO',
                    }
                )
                lead_estado.asignado_a = assigned_user
                lead_estado.save()
                updated_count += 1
            except Lead.DoesNotExist:
                continue

        return JsonResponse({'updated': updated_count})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)


# ============================================================
# CALENDAR VIEWS
# ============================================================

@login_required
def calendar_view(request):
    """Vista de calendario con visitas programadas"""
    from datetime import datetime, timedelta
    import calendar as cal

    tenant_id = get_user_tenant(request)
    view_type = request.GET.get('view', 'week')  # week o month

    # Fecha actual o navegada
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))
    week = int(request.GET.get('week', datetime.now().isocalendar()[1]))

    today = datetime.now().date()

    if view_type == 'month':
        # Vista mensual
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        # Ajustar para incluir dias de semanas completas
        start_weekday = first_day.weekday()  # 0=Lunes
        start_date = first_day - timedelta(days=start_weekday)
        end_weekday = last_day.weekday()
        end_date = last_day + timedelta(days=6 - end_weekday)

        # Navegacion
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1

        nav_context = {
            'prev_url': f'?view=month&year={prev_year}&month={prev_month}',
            'next_url': f'?view=month&year={next_year}&month={next_month}',
            'title': f'{cal.month_name[month]} {year}',
        }
    else:
        # Vista semanal
        # Encontrar lunes de la semana
        iso_year, iso_week, _ = today.isocalendar()
        if request.GET.get('week'):
            iso_week = week
        if request.GET.get('year'):
            iso_year = year

        # Calcular fecha del lunes de esa semana ISO
        jan4 = datetime(iso_year, 1, 4)
        start_of_week1 = jan4 - timedelta(days=jan4.weekday())
        start_date = start_of_week1 + timedelta(weeks=iso_week - 1)
        end_date = start_date + timedelta(days=6)

        # Navegacion
        prev_week = iso_week - 1 if iso_week > 1 else 52
        prev_year = iso_year if iso_week > 1 else iso_year - 1
        next_week = iso_week + 1 if iso_week < 52 else 1
        next_year = iso_year if iso_week < 52 else iso_year + 1

        nav_context = {
            'prev_url': f'?view=week&year={prev_year}&week={prev_week}',
            'next_url': f'?view=week&year={next_year}&week={next_week}',
            'title': f'Semana {iso_week}, {iso_year}',
        }

    # Obtener visitas del rango
    visitas = Interaction.objects.filter(
        contact__tenant_id=tenant_id,
        tipo='visita',
        fecha__date__gte=start_date.date() if hasattr(start_date, 'date') else start_date,
        fecha__date__lte=end_date.date() if hasattr(end_date, 'date') else end_date,
    ).select_related('contact', 'usuario').order_by('fecha')

    # Agrupar visitas por dia
    visitas_por_dia = {}
    for visita in visitas:
        dia = visita.fecha.date()
        if dia not in visitas_por_dia:
            visitas_por_dia[dia] = []
        visitas_por_dia[dia].append(visita)

    # Generar dias del calendario
    if view_type == 'month':
        # Generar semanas del mes
        weeks = []
        current = start_date if isinstance(start_date, datetime) else datetime.combine(start_date, datetime.min.time())
        while current.date() <= (end_date.date() if hasattr(end_date, 'date') else end_date):
            week_days = []
            for _ in range(7):
                day_date = current.date()
                week_days.append({
                    'date': day_date,
                    'day': day_date.day,
                    'is_today': day_date == today,
                    'is_current_month': day_date.month == month,
                    'visitas': visitas_por_dia.get(day_date, []),
                })
                current += timedelta(days=1)
            weeks.append(week_days)
        calendar_data = {'weeks': weeks}
    else:
        # Generar dias de la semana
        days = []
        current = start_date if isinstance(start_date, datetime) else datetime.combine(start_date, datetime.min.time())
        day_names = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
        for i in range(7):
            day_date = current.date()
            days.append({
                'date': day_date,
                'name': day_names[i],
                'day': day_date.day,
                'is_today': day_date == today,
                'visitas': visitas_por_dia.get(day_date, []),
            })
            current += timedelta(days=1)
        calendar_data = {'days': days}

    context = {
        'view_type': view_type,
        'nav': nav_context,
        'calendar': calendar_data,
        'today': today,
    }

    # Si es HTMX, devolver solo el partial del calendario
    if request.headers.get('HX-Request'):
        template = f'leads/partials/calendar_{view_type}.html'
        return render(request, template, context)

    return render(request, 'leads/calendar.html', context)


# ============================================================
# CONTACT QUEUE VIEWS (Auto-contact via Dagster)
# ============================================================

@login_required
@require_POST
def enqueue_contact_view(request, lead_id):
    """Encolar un lead para contacto automatico (HTMX)"""
    from leads.models import ContactQueue

    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    if tenant_id and lead.tenant_id != tenant_id:
        return HttpResponse(status=403)

    # Verificar que el portal soporta contacto automatico
    portal = lead.portal
    supported_portals = ['fotocasa', 'habitaclia', 'milanuncios', 'idealista']
    if portal not in supported_portals:
        return JsonResponse({
            'error': f'Contacto automatico no soportado para {portal}. Soportados: {", ".join(supported_portals)}'
        }, status=400)

    # Verificar que tiene URL
    if not lead.url_anuncio:
        return JsonResponse({
            'error': 'Lead sin URL de anuncio'
        }, status=400)

    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

    # Mensaje por defecto
    mensaje = request.POST.get('mensaje', '').strip()
    if not mensaje:
        mensaje = (
            f"Hola, he visto su anuncio en {portal.capitalize()} "
            "y me interesa. ¿Podriamos hablar?"
        )

    # Crear entrada en cola
    try:
        queue_item, created = ContactQueue.objects.get_or_create(
            tenant=tenant,
            lead_id=str(lead.lead_id),
            portal=portal,
            defaults={
                'listing_url': lead.url_anuncio,
                'titulo': lead.titulo or lead.direccion,
                'mensaje': mensaje,
                'prioridad': int(request.POST.get('prioridad', 0)),
                'created_by': request.user,
            }
        )

        if not created:
            # Ya existe en cola
            return JsonResponse({
                'status': 'already_queued',
                'message': 'Este lead ya esta en la cola de contacto',
                'estado': queue_item.estado
            })

        return JsonResponse({
            'status': 'queued',
            'message': 'Lead encolado para contacto automatico',
            'queue_id': queue_item.id
        })

    except Exception as e:
        logger.error(f"Error enqueueing lead {lead_id}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def bulk_enqueue_view(request):
    """Encolar multiples leads para contacto automatico"""
    from leads.models import ContactQueue

    try:
        data = json.loads(request.body)
        lead_ids = data.get('lead_ids', [])
        mensaje = data.get('mensaje', '').strip()
        prioridad = int(data.get('prioridad', 0))

        if not lead_ids:
            return JsonResponse({'error': 'No se especificaron leads'}, status=400)

        tenant_id = get_user_tenant(request)
        tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

        queued = 0
        skipped = 0
        errors = []

        for lead_id in lead_ids:
            try:
                lead = Lead.objects.get(lead_id=lead_id)

                if tenant_id and lead.tenant_id != tenant_id:
                    errors.append({'id': lead_id, 'reason': 'tenant_mismatch'})
                    continue

                portal = lead.portal
                if portal not in ['fotocasa', 'habitaclia', 'milanuncios', 'idealista']:
                    skipped += 1
                    continue

                if not lead.url_anuncio:
                    skipped += 1
                    continue

                msg = mensaje or (
                    f"Hola, he visto su anuncio en {portal.capitalize()} "
                    "y me interesa. ¿Podriamos hablar?"
                )

                _, created = ContactQueue.objects.get_or_create(
                    tenant=tenant,
                    lead_id=str(lead.lead_id),
                    portal=portal,
                    defaults={
                        'listing_url': lead.url_anuncio,
                        'titulo': lead.titulo or lead.direccion,
                        'mensaje': msg,
                        'prioridad': prioridad,
                        'created_by': request.user,
                    }
                )

                if created:
                    queued += 1
                else:
                    skipped += 1

            except Lead.DoesNotExist:
                errors.append({'id': lead_id, 'reason': 'not_found'})

        response = {'queued': queued, 'skipped': skipped}
        if errors:
            response['errors'] = errors
        return JsonResponse(response)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)


@login_required
def contact_queue_view(request):
    """Vista de la cola de contactos pendientes"""
    from leads.models import ContactQueue

    tenant_id = get_user_tenant(request)

    queue_items = ContactQueue.objects.filter(
        tenant_id=tenant_id
    ).order_by('-prioridad', 'created_at')

    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado:
        queue_items = queue_items.filter(estado=estado)

    # Paginacion
    paginator = Paginator(queue_items, 25)
    page = request.GET.get('page', 1)
    items = paginator.get_page(page)

    context = {
        'queue_items': items,
        'total_items': paginator.count,
        'estado_choices': ContactQueue.ESTADO_QUEUE_CHOICES,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'leads/partials/contact_queue_table.html', context)

    return render(request, 'leads/contact_queue.html', context)


@login_required
@require_POST
def cancel_queued_contact_view(request, queue_id):
    """Cancelar un contacto pendiente en la cola"""
    from leads.models import ContactQueue

    tenant_id = get_user_tenant(request)
    item = get_object_or_404(ContactQueue, id=queue_id, tenant_id=tenant_id)

    if item.estado == 'PENDIENTE':
        item.estado = 'CANCELADO'
        item.save()
        return JsonResponse({'status': 'cancelled'})
    else:
        return JsonResponse({
            'error': f'No se puede cancelar item en estado {item.estado}'
        }, status=400)


@login_required
@require_POST
def retry_queued_contact_view(request, queue_id):
    """Reintentar un contacto fallido"""
    from leads.models import ContactQueue

    tenant_id = get_user_tenant(request)
    item = get_object_or_404(ContactQueue, id=queue_id, tenant_id=tenant_id)

    if item.estado == 'FALLIDO':
        item.estado = 'PENDIENTE'
        item.error = None
        item.save()

        if request.headers.get('HX-Request'):
            # Trigger HTMX page refresh
            response = HttpResponse(status=200)
            response['HX-Refresh'] = 'true'
            return response
        return JsonResponse({'status': 'requeued', 'id': item.id})
    else:
        return JsonResponse({
            'error': f'Solo se puede reintentar items con estado FALLIDO (actual: {item.estado})'
        }, status=400)


@login_required
@require_POST
def mark_contact_responded_view(request, queue_id):
    """Marcar un contacto como respondido (actualiza metricas A/B del template)"""
    from leads.models import ContactQueue, MessageTemplate

    tenant_id = get_user_tenant(request)
    item = get_object_or_404(ContactQueue, id=queue_id, tenant_id=tenant_id)

    if item.estado == 'COMPLETADO' and not item.respondio:
        item.respondio = True
        item.fecha_respuesta = timezone.now()
        item.save(update_fields=['respondio', 'fecha_respuesta', 'updated_at'])

        # Update template A/B metrics
        if item.template_id:
            MessageTemplate.objects.filter(id=item.template_id).update(
                veces_respondida=models.F('veces_respondida') + 1
            )

        if request.headers.get('HX-Request'):
            response = HttpResponse(status=200)
            response['HX-Refresh'] = 'true'
            return response
        return JsonResponse({'status': 'marked_responded', 'id': item.id})
    else:
        return JsonResponse({
            'error': 'Solo se puede marcar como respondido items COMPLETADOS no marcados previamente'
        }, status=400)


# ============================================================================
# Agenda / Tareas
# ============================================================================

@login_required
def task_list_view(request):
    """Vista de lista de tareas con filtros"""
    from leads.models import Task
    from datetime import timedelta

    tenant_id = get_user_tenant(request)

    # Filtros
    filtro = request.GET.get('filtro', 'pendientes')  # pendientes, hoy, semana, todas, completadas
    filtro_tipo = request.GET.get('tipo', '')

    tasks_qs = Task.objects.filter(tenant_id=tenant_id)

    # Filtrar por usuario (solo sus tareas asignadas)
    if not request.user.is_staff:
        tasks_qs = tasks_qs.filter(asignado_a=request.user)

    # Aplicar filtro de tiempo
    hoy = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if filtro == 'pendientes':
        tasks_qs = tasks_qs.filter(completada=False)
    elif filtro == 'hoy':
        tasks_qs = tasks_qs.filter(
            completada=False,
            fecha_vencimiento__date=hoy.date()
        )
    elif filtro == 'semana':
        fin_semana = hoy + timedelta(days=7)
        tasks_qs = tasks_qs.filter(
            completada=False,
            fecha_vencimiento__lte=fin_semana
        )
    elif filtro == 'vencidas':
        tasks_qs = tasks_qs.filter(
            completada=False,
            fecha_vencimiento__lt=hoy
        )
    elif filtro == 'completadas':
        tasks_qs = tasks_qs.filter(completada=True)

    if filtro_tipo:
        tasks_qs = tasks_qs.filter(tipo=filtro_tipo)

    tasks_qs = tasks_qs.order_by('completada', 'fecha_vencimiento', '-prioridad')

    # Estadísticas
    stats = {
        'pendientes': Task.objects.filter(tenant_id=tenant_id, completada=False).count(),
        'hoy': Task.objects.filter(
            tenant_id=tenant_id, completada=False, fecha_vencimiento__date=hoy.date()
        ).count(),
        'vencidas': Task.objects.filter(
            tenant_id=tenant_id, completada=False, fecha_vencimiento__lt=hoy
        ).count(),
    }

    context = {
        'tasks': tasks_qs,
        'filtro': filtro,
        'filtro_tipo': filtro_tipo,
        'tipos_tarea': Task.TIPO_CHOICES,
        'stats': stats,
    }

    return render(request, 'leads/task_list.html', context)


@login_required
def task_create_view(request):
    """Crear nueva tarea"""
    from leads.models import Task
    from datetime import timedelta

    tenant_id = get_user_tenant(request)

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo = request.POST.get('tipo', 'seguimiento')
        prioridad = request.POST.get('prioridad', 'media')
        fecha_vencimiento = request.POST.get('fecha_vencimiento', '')
        lead_id = request.POST.get('lead_id', '')

        if not titulo:
            return JsonResponse({'error': 'El titulo es requerido'}, status=400)

        # Fecha por defecto: mañana a las 10:00
        if not fecha_vencimiento:
            fecha_vencimiento = (timezone.now() + timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )
        else:
            from django.utils.dateparse import parse_datetime
            fecha_vencimiento = parse_datetime(fecha_vencimiento)
            if not fecha_vencimiento:
                return JsonResponse({'error': 'Fecha invalida'}, status=400)

        task = Task.objects.create(
            tenant_id=tenant_id,
            titulo=titulo,
            descripcion=descripcion,
            tipo=tipo,
            prioridad=prioridad,
            fecha_vencimiento=fecha_vencimiento,
            lead_id=lead_id if lead_id else None,
            asignado_a=request.user,
            created_by=request.user,
        )

        if request.headers.get('HX-Request'):
            return HttpResponse(status=204, headers={'HX-Refresh': 'true'})

        return JsonResponse({'status': 'created', 'id': task.id})

    # GET: redirect to agenda (form is in the modal on task_list.html)
    from django.shortcuts import redirect
    return redirect('leads:agenda')


@login_required
@require_POST
def task_complete_view(request, task_id):
    """Marcar tarea como completada"""
    from leads.models import Task

    tenant_id = get_user_tenant(request)
    task = get_object_or_404(Task, id=task_id, tenant_id=tenant_id)

    task.marcar_completada()

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Refresh': 'true'})

    return JsonResponse({'status': 'completed', 'id': task.id})


@login_required
@require_POST
def task_delete_view(request, task_id):
    """Eliminar tarea"""
    from leads.models import Task

    tenant_id = get_user_tenant(request)
    task = get_object_or_404(Task, id=task_id, tenant_id=tenant_id)

    task.delete()

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Refresh': 'true'})

    return JsonResponse({'status': 'deleted'})


# ============================================================================
# PDF Valuation Report
# ============================================================================

@login_required
def valuation_pdf_view(request, lead_id):
    """
    Generate and download a PDF valuation report for a lead.
    GET /leads/<lead_id>/valuation-pdf/
    """
    from leads.pdf_service import generate_valuation_pdf

    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    # Verify lead belongs to user's tenant
    if tenant_id and lead.tenant_id != tenant_id:
        return HttpResponse(status=403)

    tenant = get_object_or_404(Tenant, tenant_id=tenant_id)

    try:
        pdf_bytes = generate_valuation_pdf(lead, tenant)

        # Generate filename
        zona = lead.zona_geografica or 'desconocida'
        zona_slug = zona.lower().replace(' ', '_')[:20]
        fecha = timezone.now().strftime('%Y%m%d')
        filename = f"valoracion_{zona_slug}_{fecha}.pdf"

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Error generating PDF for lead {lead_id}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


class Echo:
    """An object that implements just the write method of the file-like interface."""
    def write(self, value):
        return value


@login_required
def export_csv_view(request):
    """
    Exportar leads filtrados a CSV usando StreamingHttpResponse.
    Respeta los mismos filtros que lead_list_view (q, estado, portal, zona).
    """
    tenant_id = get_user_tenant(request)

    # Base queryset
    leads_qs = Lead.objects.all()
    if tenant_id:
        leads_qs = leads_qs.filter(tenant_id=tenant_id)

    # Filtros (misma logica que lead_list_view)
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

    # Filtrar por estado usando LeadEstado
    if estado:
        lead_ids_with_estado = LeadEstado.objects.filter(
            estado=estado
        ).values_list('lead_id', flat=True)

        if estado == 'NUEVO':
            leads_qs = leads_qs.filter(
                Q(lead_id__in=[lid for lid in lead_ids_with_estado]) |
                ~Q(lead_id__in=LeadEstado.objects.values_list('lead_id', flat=True))
            )
        else:
            leads_qs = leads_qs.filter(lead_id__in=[lid for lid in lead_ids_with_estado])

    leads_qs = leads_qs.order_by('-fecha_scraping')

    # Obtener estados de LeadEstado para los leads
    lead_ids = list(leads_qs.values_list('lead_id', flat=True))
    lead_estados = {
        le.lead_id: le.estado
        for le in LeadEstado.objects.filter(lead_id__in=[str(lid) for lid in lead_ids])
    }

    def generate_csv():
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        # Headers en espanol
        yield writer.writerow([
            'Telefono',
            'Titulo',
            'Precio',
            'Portal',
            'Zona',
            'Estado',
            'URL Anuncio',
            'Fecha Scraping'
        ])

        # Iterar en batches para memoria eficiente
        for lead in leads_qs.iterator(chunk_size=500):
            estado_actual = lead_estados.get(str(lead.lead_id), lead.estado or 'NUEVO')
            fecha = lead.fecha_scraping.strftime('%Y-%m-%d %H:%M') if lead.fecha_scraping else ''

            yield writer.writerow([
                lead.telefono_norm or '',
                lead.titulo or lead.direccion or '',
                lead.precio or '',
                lead.portal or '',
                lead.zona_geografica or '',
                estado_actual,
                lead.url_anuncio or '',
                fecha
            ])

    response = StreamingHttpResponse(
        generate_csv(),
        content_type='text/csv; charset=utf-8'
    )
    fecha_export = timezone.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="leads_{fecha_export}.csv"'

    return response


# ============================================================================
# Price History API
# ============================================================================

@login_required
def price_history_view(request, lead_id):
    """
    Fetch price history for a lead from raw.listing_price_history.
    Returns JSON for Chart.js rendering.
    """
    tenant_id = get_user_tenant(request)
    lead = get_object_or_404(Lead, lead_id=lead_id)

    if tenant_id and lead.tenant_id != tenant_id:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Get the source listing ID and portal from the lead
    anuncio_id = lead.anuncio_id
    portal = lead.portal

    if not anuncio_id or not portal:
        # No price history available without listing ID
        return JsonResponse({
            'has_history': False,
            'current_price': float(lead.precio) if lead.precio else None,
            'message': 'No hay historial de precios disponible'
        })

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT precio, fecha_captura
                FROM raw.listing_price_history
                WHERE tenant_id = %s
                  AND portal = %s
                  AND anuncio_id = %s
                ORDER BY fecha_captura ASC
            """, [tenant_id, portal, anuncio_id])
            rows = cursor.fetchall()

        if not rows:
            # No history, return current price only
            return JsonResponse({
                'has_history': False,
                'current_price': float(lead.precio) if lead.precio else None,
                'message': 'Sin historial de cambios de precio'
            })

        # Build data for Chart.js
        labels = []
        prices = []
        for precio, fecha in rows:
            labels.append(fecha.strftime('%d/%m/%Y'))
            prices.append(float(precio) if precio else None)

        # Calculate price change
        first_price = prices[0] if prices else None
        last_price = prices[-1] if prices else None
        change_pct = None
        if first_price and last_price and first_price > 0:
            change_pct = round(((last_price - first_price) / first_price) * 100, 1)

        return JsonResponse({
            'has_history': True,
            'labels': labels,
            'prices': prices,
            'current_price': float(lead.precio) if lead.precio else last_price,
            'first_price': first_price,
            'change_pct': change_pct,
            'num_changes': len(prices)
        })

    except Exception as e:
        logger.error(f"Error fetching price history for lead {lead_id}: {e}")
        return JsonResponse({
            'has_history': False,
            'current_price': float(lead.precio) if lead.precio else None,
            'error': str(e)
        })


def image_proxy_view(request):
    """
    Proxy para servir imágenes de portales inmobiliarios.
    Evita bloqueo por hotlink protection (habitaclia, fotocasa, etc.)

    Query params:
        url: URL de imagen codificada en base64 (urlsafe, sin padding)
    """
    import base64
    import requests
    from urllib.parse import urlparse

    url_b64 = request.GET.get('url', '')
    if not url_b64:
        return HttpResponse(status=400)

    try:
        # Add padding if needed (base64 requires length multiple of 4)
        padding = 4 - len(url_b64) % 4
        if padding != 4:
            url_b64 += '=' * padding
        url = base64.urlsafe_b64decode(url_b64.encode()).decode('utf-8')
    except Exception as e:
        logger.warning(f"Image proxy decode error: {e}")
        return HttpResponse(status=400)

    # Fix known URL issues before proxying
    import re as _re
    # Habitaclia: XL_XXL/M_M/L_L suffixes get 502, but base URL works
    if 'images.habimg.com' in url:
        url = _re.sub(r'(XL_XXL|L_L|M_M|S_S)\.jpg', '.jpg', url)
    # Milanuncios: images-re domain returns 404, images works
    url = url.replace('images-re.milanuncios.com', 'images.milanuncios.com')
    # Milanuncios: ensure https:// prefix
    if url.startswith('images.milanuncios.com'):
        url = 'https://' + url

    # Validate URL domain
    parsed = urlparse(url)
    allowed_domains = [
        'images.habimg.com',        # habitaclia
        'static.fotocasa.es',       # fotocasa
        'img3.idealista.com',       # idealista
        'img4.idealista.com',       # idealista
        'images.milanuncios.com',   # milanuncios
    ]
    if parsed.netloc not in allowed_domains:
        return HttpResponse(status=403)

    # Determine referer based on domain
    referers = {
        'images.habimg.com': 'https://www.habitaclia.com/',
        'static.fotocasa.es': 'https://www.fotocasa.es/',
        'img3.idealista.com': 'https://www.idealista.com/',
        'img4.idealista.com': 'https://www.idealista.com/',
        'images.milanuncios.com': 'https://www.milanuncios.com/',
    }
    referer = referers.get(parsed.netloc, '')

    try:
        resp = requests.get(
            url,
            headers={
                'Referer': referer,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            timeout=10,
            stream=True,
        )
        if resp.status_code != 200:
            return HttpResponse(status=resp.status_code)

        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        response = HttpResponse(resp.content, content_type=content_type)
        response['Cache-Control'] = 'public, max-age=86400'  # Cache 1 day
        return response
    except requests.RequestException as e:
        logger.warning(f"Image proxy error: {e}")
        return HttpResponse(status=502)


@login_required
@require_POST
def analyze_lead_images_view(request, lead_id):
    """HTMX endpoint: analyze lead images with Ollama Vision and return updated score."""
    import sys
    from pathlib import Path

    PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    lead = get_object_or_404(Lead, lead_id=lead_id)

    fotos = lead.fotos_list
    if not fotos:
        return HttpResponse(
            '<span class="text-sm text-red-500">No hay fotos para analizar</span>')

    try:
        from ai_agents.vision_analyzer import (
            check_ollama_installed,
            check_model_available,
            analyze_property_images,
        )

        if not check_ollama_installed() or not check_model_available():
            return HttpResponse(
                '<span class="text-sm text-red-500">Ollama no disponible</span>')

        result = analyze_property_images(fotos[:3], max_images=3)
        image_score = result.get('total_image_score', 0)
        images_analyzed = result.get('images_analyzed', 0)

        # Save to DB
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public.lead_image_scores (
                    lead_id VARCHAR(100) PRIMARY KEY,
                    image_score INTEGER NOT NULL DEFAULT 0,
                    images_analyzed INTEGER NOT NULL DEFAULT 0,
                    analysis_json JSONB,
                    analyzed_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                INSERT INTO public.lead_image_scores (lead_id, image_score, images_analyzed, analysis_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (lead_id) DO UPDATE SET
                    image_score = EXCLUDED.image_score,
                    images_analyzed = EXCLUDED.images_analyzed,
                    analysis_json = EXCLUDED.analysis_json,
                    analyzed_at = NOW()
            """, [lead_id, image_score, images_analyzed, json.dumps(result)])

        # Build response HTML
        details = result.get('individual_results', [])
        detail_html = ""
        for d in details:
            if 'raw_response' not in d:
                detail_html += (
                    f'<div class="text-xs text-gray-500 dark:text-gray-400">'
                    f'{d.get("tipo_estancia", "?")} - '
                    f'conservacion:{d.get("estado_conservacion", 0)} '
                    f'foto:{d.get("calidad_foto", 0)} '
                    f'atractivo:{d.get("atractivo_visual", 0)}'
                    f'</div>'
                )

        color = "green" if image_score >= 20 else "yellow" if image_score >= 10 else "red"
        html = (
            f'<div class="space-y-1">'
            f'<div class="flex items-center space-x-2">'
            f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs '
            f'font-semibold bg-{color}-100 text-{color}-800 '
            f'dark:bg-{color}-900/30 dark:text-{color}-300">'
            f'AI Score: {image_score}/30</span>'
            f'<span class="text-xs text-gray-500">({images_analyzed} fotos analizadas)</span>'
            f'</div>'
            f'{detail_html}'
            f'</div>'
        )
        return HttpResponse(html)

    except ImportError:
        return HttpResponse(
            '<span class="text-sm text-red-500">ai_agents no disponible</span>')
    except Exception as e:
        logger.error(f"Image analysis error for {lead_id}: {e}")
        return HttpResponse(
            f'<span class="text-sm text-red-500">Error: {str(e)[:100]}</span>')

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter

from leads.models import LeadEstado
from core.models import ZonaGeografica

from .authentication import APIKeyAuthentication
from .throttling import TenantRateThrottle, TenantBurstThrottle
from .serializers import (
    LeadListSerializer, LeadDetailSerializer, LeadUpdateSerializer,
    ZonaSerializer, WebhookSerializer, WebhookCreateSerializer,
    ErrorSerializer
)
from .models import Webhook


class HasAPIKey(BasePermission):
    """Permiso que requiere API key valida."""
    def has_permission(self, request, view):
        return request.auth is not None and hasattr(request.auth, 'tenant')


class CanReadLeads(BasePermission):
    """Permiso para leer leads."""
    def has_permission(self, request, view):
        if not request.auth:
            return False
        return request.auth.can_read_leads


class CanWriteLeads(BasePermission):
    """Permiso para escribir leads."""
    def has_permission(self, request, view):
        if not request.auth:
            return False
        return request.auth.can_write_leads


class CanManageWebhooks(BasePermission):
    """Permiso para gestionar webhooks."""
    def has_permission(self, request, view):
        if not request.auth:
            return False
        return request.auth.can_manage_webhooks


class APIv1Mixin:
    """Mixin con configuracion comun para vistas API v1."""
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    throttle_classes = [TenantRateThrottle, TenantBurstThrottle]

    def get_tenant(self):
        """Obtiene el tenant de la API key autenticada."""
        return self.request.auth.tenant


class LeadListView(APIv1Mixin, APIView):
    """Listado de leads del tenant."""
    permission_classes = [HasAPIKey, CanReadLeads]

    @extend_schema(
        summary="Listar leads",
        description="Obtiene leads del tenant con filtros opcionales",
        parameters=[
            OpenApiParameter(
                name='portal',
                type=str,
                description='Filtrar por portal (habitaclia, fotocasa, milanuncios, idealista)'
            ),
            OpenApiParameter(
                name='zona',
                type=str,
                description='Filtrar por zona geografica'
            ),
            OpenApiParameter(
                name='estado',
                type=str,
                description='Filtrar por estado CRM'
            ),
            OpenApiParameter(
                name='precio_min',
                type=int,
                description='Precio minimo'
            ),
            OpenApiParameter(
                name='precio_max',
                type=int,
                description='Precio maximo'
            ),
            OpenApiParameter(
                name='page',
                type=int,
                description='Numero de pagina (default 1)'
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                description='Leads por pagina (default 25, max 100)'
            ),
        ],
        responses={
            200: LeadListSerializer(many=True),
            401: ErrorSerializer,
            429: ErrorSerializer,
        }
    )
    def get(self, request):
        tenant = self.get_tenant()

        # Parametros de filtro
        portal = request.query_params.get('portal')
        zona = request.query_params.get('zona')
        estado = request.query_params.get('estado')
        precio_min = request.query_params.get('precio_min')
        precio_max = request.query_params.get('precio_max')

        # Paginacion
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 25)), 100)
        except ValueError:
            page, page_size = 1, 25

        offset = (page - 1) * page_size

        # Query SQL directa a dim_leads (vista dbt)
        where_clauses = ["tenant_id = %s"]
        params = [tenant.tenant_id]

        if portal:
            where_clauses.append("source_portal = %s")
            params.append(portal)
        if zona:
            where_clauses.append("zona_clasificada = %s")
            params.append(zona)
        if estado:
            where_clauses.append("estado = %s")
            params.append(estado)
        if precio_min:
            where_clauses.append("precio >= %s")
            params.append(int(precio_min))
        if precio_max:
            where_clauses.append("precio <= %s")
            params.append(int(precio_max))

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_sql = f"SELECT COUNT(*) FROM public_marts.dim_leads WHERE {where_sql}"

        # Query con paginacion
        query_sql = f"""
            SELECT
                lead_id, titulo, precio, superficie_m2, habitaciones,
                source_portal, zona_clasificada, estado, telefono_norm,
                listing_url, fecha_primera_captura, lead_score
            FROM public_marts.dim_leads
            WHERE {where_sql}
            ORDER BY fecha_primera_captura DESC
            LIMIT %s OFFSET %s
        """
        params_paginated = params + [page_size, offset]

        with connection.cursor() as cursor:
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            cursor.execute(query_sql, params_paginated)
            columns = [col[0] for col in cursor.description]
            leads = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size,
            'results': leads
        })


class LeadDetailView(APIv1Mixin, APIView):
    """Detalle y actualizacion de lead."""
    permission_classes = [HasAPIKey, CanReadLeads]

    @extend_schema(
        summary="Detalle de lead",
        description="Obtiene informacion completa de un lead",
        responses={
            200: LeadDetailSerializer,
            404: ErrorSerializer,
        }
    )
    def get(self, request, lead_id):
        tenant = self.get_tenant()

        query_sql = """
            SELECT
                l.*,
                d.num_portales,
                d.portales
            FROM public_marts.dim_leads l
            LEFT JOIN public_marts.dim_lead_duplicates d
                ON l.lead_id = d.lead_id
            WHERE l.lead_id = %s AND l.tenant_id = %s
        """

        with connection.cursor() as cursor:
            cursor.execute(query_sql, [lead_id, tenant.tenant_id])
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()

        if not row:
            return Response(
                {'detail': 'Lead no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        lead = dict(zip(columns, row))
        return Response(lead)

    @extend_schema(
        summary="Actualizar lead",
        description="Actualiza el estado CRM de un lead",
        request=LeadUpdateSerializer,
        responses={
            200: LeadDetailSerializer,
            400: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    )
    def patch(self, request, lead_id):
        # Verificar permiso de escritura
        if not request.auth.can_write_leads:
            return Response(
                {'detail': 'No tiene permiso para modificar leads'},
                status=status.HTTP_403_FORBIDDEN
            )

        tenant = self.get_tenant()

        # Verificar que el lead existe
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT telefono_norm FROM public_marts.dim_leads WHERE lead_id = %s AND tenant_id = %s",
                [lead_id, tenant.tenant_id]
            )
            row = cursor.fetchone()

        if not row:
            return Response(
                {'detail': 'Lead no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        telefono_norm = row[0]

        serializer = LeadUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Actualizar en LeadEstado
        lead_estado, created = LeadEstado.objects.get_or_create(
            lead_id=lead_id,
            defaults={
                'tenant': tenant,
                'telefono_norm': telefono_norm,
            }
        )

        updated_fields = []
        if 'estado' in serializer.validated_data:
            old_estado = lead_estado.estado
            new_estado = serializer.validated_data['estado']
            lead_estado.estado = new_estado
            lead_estado.fecha_cambio_estado = timezone.now()
            updated_fields.extend(['estado', 'fecha_cambio_estado'])

            # Disparar webhook de cambio de estado
            if old_estado != new_estado:
                from .signals import trigger_status_change_webhook
                trigger_status_change_webhook(
                    tenant, lead_id, old_estado, new_estado
                )

        if 'asignado_a_id' in serializer.validated_data:
            lead_estado.asignado_a_id = serializer.validated_data['asignado_a_id']
            updated_fields.append('asignado_a_id')

        if updated_fields:
            lead_estado.save(update_fields=updated_fields + ['updated_at'])

        # Retornar lead actualizado
        return self.get(request, lead_id)


class ZonaListView(APIv1Mixin, APIView):
    """Listado de zonas del tenant."""

    @extend_schema(
        summary="Listar zonas",
        description="Obtiene zonas geograficas configuradas para el tenant",
        responses={
            200: ZonaSerializer(many=True),
        }
    )
    def get(self, request):
        tenant = self.get_tenant()
        zonas = ZonaGeografica.objects.filter(tenant=tenant).order_by('nombre')
        serializer = ZonaSerializer(zonas, many=True)
        return Response(serializer.data)


class WebhookListCreateView(APIv1Mixin, APIView):
    """Listado y creacion de webhooks."""
    permission_classes = [HasAPIKey, CanManageWebhooks]

    @extend_schema(
        summary="Listar webhooks",
        description="Obtiene webhooks configurados para el tenant",
        responses={
            200: WebhookSerializer(many=True),
        }
    )
    def get(self, request):
        tenant = self.get_tenant()
        webhooks = Webhook.objects.filter(tenant=tenant).order_by('-created_at')
        serializer = WebhookSerializer(webhooks, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Crear webhook",
        description="Configura un nuevo webhook para recibir eventos",
        request=WebhookCreateSerializer,
        responses={
            201: WebhookSerializer,
            400: ErrorSerializer,
        }
    )
    def post(self, request):
        tenant = self.get_tenant()
        serializer = WebhookCreateSerializer(
            data=request.data,
            context={'tenant': tenant}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        webhook = serializer.save()
        return Response(
            WebhookSerializer(webhook).data,
            status=status.HTTP_201_CREATED
        )


class WebhookDetailView(APIv1Mixin, APIView):
    """Detalle, actualizacion y eliminacion de webhook."""
    permission_classes = [HasAPIKey, CanManageWebhooks]

    def get_webhook(self, webhook_id):
        tenant = self.get_tenant()
        try:
            return Webhook.objects.get(id=webhook_id, tenant=tenant)
        except Webhook.DoesNotExist:
            return None

    @extend_schema(
        summary="Detalle de webhook",
        responses={
            200: WebhookSerializer,
            404: ErrorSerializer,
        }
    )
    def get(self, request, webhook_id):
        webhook = self.get_webhook(webhook_id)
        if not webhook:
            return Response(
                {'detail': 'Webhook no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(WebhookSerializer(webhook).data)

    @extend_schema(
        summary="Actualizar webhook",
        request=WebhookCreateSerializer,
        responses={
            200: WebhookSerializer,
            404: ErrorSerializer,
        }
    )
    def patch(self, request, webhook_id):
        webhook = self.get_webhook(webhook_id)
        if not webhook:
            return Response(
                {'detail': 'Webhook no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if 'url' in request.data:
            webhook.url = request.data['url']
        if 'is_active' in request.data:
            webhook.is_active = request.data['is_active']

        webhook.save()
        return Response(WebhookSerializer(webhook).data)

    @extend_schema(
        summary="Eliminar webhook",
        responses={
            204: None,
            404: ErrorSerializer,
        }
    )
    def delete(self, request, webhook_id):
        webhook = self.get_webhook(webhook_id)
        if not webhook:
            return Response(
                {'detail': 'Webhook no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        webhook.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

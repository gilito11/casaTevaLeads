"""
API ViewSets para leads usando Django REST Framework.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from leads.models import Lead, Nota
from leads.serializers import (
    LeadListSerializer,
    LeadDetailSerializer,
    LeadUpdateSerializer,
    NotaSerializer
)
from core.models import TenantUser


class LeadViewSet(viewsets.ModelViewSet):
    """
    API ViewSet para gestionar leads.

    list: Lista todos los leads del tenant
    retrieve: Obtiene detalle de un lead
    update/partial_update: Actualiza estado y asignacion
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'portal', 'zona_geografica']
    search_fields = ['telefono_norm', 'nombre', 'direccion']
    ordering_fields = ['fecha_scraping', 'precio', 'created_at']
    ordering = ['-fecha_scraping']

    def get_queryset(self):
        """Filtra leads por tenant del usuario"""
        user = self.request.user
        tenant_id = self.request.session.get('tenant_id')

        if not tenant_id:
            tenant_user = TenantUser.objects.filter(user=user).first()
            if tenant_user:
                tenant_id = tenant_user.tenant.tenant_id

        queryset = Lead.objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        return queryset

    def get_serializer_class(self):
        """Usa diferentes serializers segun la accion"""
        if self.action == 'list':
            return LeadListSerializer
        elif self.action in ['update', 'partial_update']:
            return LeadUpdateSerializer
        return LeadDetailSerializer

    def perform_update(self, serializer):
        """Actualiza timestamps al cambiar estado"""
        instance = serializer.instance
        nuevo_estado = serializer.validated_data.get('estado')

        if nuevo_estado and nuevo_estado != instance.estado:
            serializer.validated_data['fecha_cambio_estado'] = timezone.now()

            # Si es primer contacto
            if nuevo_estado in ['CONTACTADO_SIN_RESPUESTA', 'INTERESADO', 'NO_INTERESADO']:
                if not instance.fecha_primer_contacto:
                    serializer.validated_data['fecha_primer_contacto'] = timezone.now()
                serializer.validated_data['fecha_ultimo_contacto'] = timezone.now()

        serializer.save()

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """
        Endpoint para cambiar estado de un lead.
        POST /api/leads/{id}/cambiar_estado/
        Body: {"estado": "EN_PROCESO"}
        """
        lead = self.get_object()
        nuevo_estado = request.data.get('estado')

        if not nuevo_estado:
            return Response(
                {'error': 'Se requiere el campo estado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        estados_validos = dict(Lead.ESTADO_CHOICES)
        if nuevo_estado not in estados_validos:
            return Response(
                {'error': f'Estado invalido. Opciones: {list(estados_validos.keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_estado = lead.estado
        lead.estado = nuevo_estado
        lead.fecha_cambio_estado = timezone.now()

        if nuevo_estado in ['CONTACTADO_SIN_RESPUESTA', 'INTERESADO', 'NO_INTERESADO']:
            if not lead.fecha_primer_contacto:
                lead.fecha_primer_contacto = timezone.now()
            lead.fecha_ultimo_contacto = timezone.now()
            lead.numero_intentos += 1

        lead.save()

        return Response({
            'lead_id': lead.lead_id,
            'estado_anterior': old_estado,
            'estado_nuevo': nuevo_estado,
            'fecha_cambio': lead.fecha_cambio_estado
        })

    @action(detail=True, methods=['get', 'post'])
    def notas(self, request, pk=None):
        """
        GET: Lista notas del lead
        POST: Crea una nueva nota
        """
        lead = self.get_object()

        if request.method == 'GET':
            notas = lead.notas.select_related('autor').all()
            serializer = NotaSerializer(notas, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            texto = request.data.get('texto', '').strip()
            if not texto:
                return Response(
                    {'error': 'Se requiere el campo texto'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            nota = Nota.objects.create(
                lead=lead,
                autor=request.user,
                texto=texto
            )
            serializer = NotaSerializer(nota)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadisticas de leads.
        GET /api/leads/stats/
        """
        queryset = self.get_queryset()

        from django.db.models import Count, Q

        stats = queryset.aggregate(
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

        # Leads por portal
        por_portal = list(
            queryset.values('portal').annotate(count=Count('lead_id'))
        )

        # Leads por zona
        por_zona = list(
            queryset.values('zona_geografica').annotate(count=Count('lead_id'))
        )

        return Response({
            'estados': stats,
            'por_portal': por_portal,
            'por_zona': por_zona,
        })

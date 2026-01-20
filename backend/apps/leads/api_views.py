"""
API ViewSets para leads usando Django REST Framework.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from leads.models import Lead, Nota, Task
from leads.serializers import (
    LeadListSerializer,
    LeadDetailSerializer,
    LeadUpdateSerializer,
    NotaSerializer,
    TaskSerializer,
    TaskCreateSerializer
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


class TaskViewSet(viewsets.ModelViewSet):
    """
    API ViewSet para gestionar tareas/agenda.

    list: Lista todas las tareas del tenant
    retrieve: Obtiene detalle de una tarea
    create: Crea una nueva tarea
    update/partial_update: Actualiza una tarea
    destroy: Elimina una tarea
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'prioridad', 'completada', 'lead_id', 'asignado_a']
    search_fields = ['titulo', 'descripcion']
    ordering_fields = ['fecha_vencimiento', 'prioridad', 'created_at']
    ordering = ['completada', 'fecha_vencimiento']

    def get_tenant_id(self):
        """Obtiene el tenant_id del usuario actual"""
        user = self.request.user
        tenant_id = self.request.session.get('tenant_id')

        if not tenant_id:
            tenant_user = TenantUser.objects.filter(user=user).first()
            if tenant_user:
                tenant_id = tenant_user.tenant.tenant_id

        return tenant_id

    def get_queryset(self):
        """Filtra tareas por tenant del usuario"""
        tenant_id = self.get_tenant_id()

        queryset = Task.objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Filtro opcional por fecha
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')

        if fecha_desde:
            queryset = queryset.filter(fecha_vencimiento__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_vencimiento__lte=fecha_hasta)

        # Filtro para tareas de hoy
        hoy = self.request.query_params.get('hoy')
        if hoy and hoy.lower() == 'true':
            from datetime import date
            queryset = queryset.filter(
                fecha_vencimiento__date=date.today(),
                completada=False
            )

        # Filtro para tareas vencidas
        vencidas = self.request.query_params.get('vencidas')
        if vencidas and vencidas.lower() == 'true':
            queryset = queryset.filter(
                fecha_vencimiento__lt=timezone.now(),
                completada=False
            )

        return queryset

    def get_serializer_class(self):
        """Usa diferentes serializers segun la accion"""
        if self.action == 'create':
            return TaskCreateSerializer
        return TaskSerializer

    def get_serializer_context(self):
        """Agrega tenant_id al contexto del serializer"""
        context = super().get_serializer_context()
        context['tenant_id'] = self.get_tenant_id()
        return context

    @action(detail=True, methods=['post'])
    def completar(self, request, pk=None):
        """
        Marca una tarea como completada.
        POST /api/tasks/{id}/completar/
        """
        task = self.get_object()
        task.marcar_completada()

        serializer = TaskSerializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reabrir(self, request, pk=None):
        """
        Reabre una tarea completada.
        POST /api/tasks/{id}/reabrir/
        """
        task = self.get_object()
        task.completada = False
        task.fecha_completada = None
        task.save(update_fields=['completada', 'fecha_completada', 'updated_at'])

        serializer = TaskSerializer(task)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadisticas de tareas.
        GET /api/tasks/stats/
        """
        queryset = self.get_queryset()
        from django.db.models import Count, Q
        from datetime import date, timedelta

        hoy = date.today()
        fin_semana = hoy + timedelta(days=7)

        stats = queryset.aggregate(
            total=Count('id'),
            pendientes=Count('id', filter=Q(completada=False)),
            completadas=Count('id', filter=Q(completada=True)),
            hoy=Count('id', filter=Q(fecha_vencimiento__date=hoy, completada=False)),
            semana=Count('id', filter=Q(
                fecha_vencimiento__date__lte=fin_semana,
                completada=False
            )),
            vencidas=Count('id', filter=Q(
                fecha_vencimiento__lt=timezone.now(),
                completada=False
            )),
            urgentes=Count('id', filter=Q(prioridad='urgente', completada=False)),
        )

        # Tareas por tipo
        por_tipo = list(
            queryset.filter(completada=False)
            .values('tipo')
            .annotate(count=Count('id'))
        )

        return Response({
            'contadores': stats,
            'por_tipo': por_tipo,
        })

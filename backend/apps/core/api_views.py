"""
API ViewSets para core (zonas, blacklist) usando Django REST Framework.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from core.models import (
    Tenant, TenantUser, ZonaGeografica, UsuarioBlacklist,
    ContadorUsuarioPortal, ZONAS_PREESTABLECIDAS
)
from core.serializers import (
    TenantSerializer,
    ZonaGeograficaSerializer,
    ZonaGeograficaCreateSerializer,
    UsuarioBlacklistSerializer,
    UsuarioBlacklistCreateSerializer,
    ContadorUsuarioPortalSerializer,
)


def get_user_tenant(request):
    """Obtiene el tenant del usuario actual"""
    tenant_id = request.session.get('tenant_id')
    if not tenant_id:
        tenant_user = TenantUser.objects.filter(user=request.user).first()
        if tenant_user:
            tenant_id = tenant_user.tenant.tenant_id
            request.session['tenant_id'] = tenant_id
    return tenant_id


class ZonaGeograficaViewSet(viewsets.ModelViewSet):
    """
    API ViewSet para gestionar zonas geograficas.

    list: Lista todas las zonas del tenant
    retrieve: Obtiene detalle de una zona
    create: Crea una nueva zona
    update/partial_update: Actualiza una zona
    destroy: Elimina una zona
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ZonaGeograficaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['activa', 'tipo', 'scrapear_milanuncios', 'scrapear_fotocasa', 'scrapear_habitaclia', 'scrapear_idealista']
    search_fields = ['nombre', 'slug']

    def get_queryset(self):
        """Filtra zonas por tenant del usuario"""
        tenant_id = get_user_tenant(self.request)
        queryset = ZonaGeografica.objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.select_related('tenant')

    def perform_create(self, serializer):
        """Asigna el tenant del usuario al crear una zona"""
        tenant_id = get_user_tenant(self.request)
        if tenant_id:
            tenant = Tenant.objects.get(tenant_id=tenant_id)
            serializer.save(tenant=tenant)
        else:
            serializer.save()

    @action(detail=False, methods=['get'])
    def preestablecidas(self, request):
        """
        Lista zonas preestablecidas disponibles.
        GET /api/zonas/preestablecidas/
        """
        zonas = []
        for key, data in ZONAS_PREESTABLECIDAS.items():
            zonas.append({
                'key': key,
                'nombre': data['nombre'],
                'latitud': data['lat'],
                'longitud': data['lon'],
                'provincia_id': data.get('provincia_id'),
            })
        return Response(zonas)

    @action(detail=False, methods=['post'])
    def crear_desde_preestablecida(self, request):
        """
        Crea una zona a partir de una zona preestablecida.
        POST /api/zonas/crear_desde_preestablecida/
        Body: {"zona_key": "la_bordeta", "radio_km": 20, "precio_minimo": 5000}
        """
        serializer = ZonaGeograficaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        zona_key = serializer.validated_data['zona_key']
        radio_km = serializer.validated_data.get('radio_km', 20)
        precio_minimo = serializer.validated_data.get('precio_minimo', 5000)

        tenant_id = get_user_tenant(request)
        if not tenant_id:
            return Response(
                {'error': 'Usuario no tiene tenant asignado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant = Tenant.objects.get(tenant_id=tenant_id)

        # Verificar si ya existe
        if ZonaGeografica.objects.filter(tenant=tenant, slug=zona_key).exists():
            return Response(
                {'error': f'Ya existe la zona {zona_key} para este tenant'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            zona = ZonaGeografica.crear_desde_preestablecida(tenant, zona_key)
            zona.radio_km = radio_km
            zona.precio_minimo = precio_minimo
            zona.save()

            return Response(
                ZonaGeograficaSerializer(zona).data,
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def toggle_portal(self, request, pk=None):
        """
        Activa/desactiva un portal para la zona.
        POST /api/zonas/{id}/toggle_portal/
        Body: {"portal": "milanuncios", "activo": true}
        """
        zona = self.get_object()
        portal = request.data.get('portal')
        activo = request.data.get('activo', True)

        portales_validos = ['milanuncios', 'fotocasa', 'habitaclia', 'idealista']
        if portal not in portales_validos:
            return Response(
                {'error': f'Portal invalido. Opciones: {portales_validos}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        campo = f'scrapear_{portal}'
        setattr(zona, campo, activo)
        zona.save()

        return Response({
            'zona': zona.nombre,
            'portal': portal,
            'activo': activo
        })


class UsuarioBlacklistViewSet(viewsets.ModelViewSet):
    """
    API ViewSet para gestionar usuarios en blacklist.

    list: Lista usuarios blacklisteados (globales + del tenant)
    retrieve: Obtiene detalle de un usuario
    create: Agrega usuario a blacklist
    destroy: Elimina de blacklist (o desactiva)
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['portal', 'motivo', 'activo']
    search_fields = ['nombre_usuario', 'usuario_id']

    def get_queryset(self):
        """Filtra blacklist por tenant del usuario (incluye globales)"""
        tenant_id = get_user_tenant(self.request)

        queryset = UsuarioBlacklist.objects.all()
        if tenant_id:
            # Incluir globales (tenant=NULL) y del tenant especifico
            queryset = queryset.filter(
                Q(tenant__isnull=True) | Q(tenant_id=tenant_id)
            )

        return queryset.select_related('tenant').order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UsuarioBlacklistCreateSerializer
        return UsuarioBlacklistSerializer

    def perform_create(self, serializer):
        """Asigna el tenant del usuario si no se especifica"""
        tenant = serializer.validated_data.get('tenant')
        if tenant is None:
            tenant_id = get_user_tenant(self.request)
            if tenant_id:
                tenant = Tenant.objects.get(tenant_id=tenant_id)
                serializer.save(tenant=tenant)
                return
        serializer.save()

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Estadisticas de blacklist.
        GET /api/blacklist/stats/
        """
        queryset = self.get_queryset()

        from django.db.models import Count

        stats = {
            'total': queryset.filter(activo=True).count(),
            'por_portal': list(
                queryset.filter(activo=True)
                .values('portal')
                .annotate(count=Count('id'))
            ),
            'por_motivo': list(
                queryset.filter(activo=True)
                .values('motivo')
                .annotate(count=Count('id'))
            ),
            'globales': queryset.filter(tenant__isnull=True, activo=True).count(),
        }

        return Response(stats)

    @action(detail=False, methods=['post'])
    def verificar(self, request):
        """
        Verifica si un usuario esta en blacklist.
        POST /api/blacklist/verificar/
        Body: {"portal": "wallapop", "usuario_id": "123456"}
        """
        portal = request.data.get('portal')
        usuario_id = request.data.get('usuario_id')

        if not portal or not usuario_id:
            return Response(
                {'error': 'Se requieren portal y usuario_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant_id = get_user_tenant(request)
        tenant = Tenant.objects.filter(tenant_id=tenant_id).first() if tenant_id else None

        en_blacklist = UsuarioBlacklist.esta_en_blacklist(portal, usuario_id, tenant)

        return Response({
            'portal': portal,
            'usuario_id': usuario_id,
            'en_blacklist': en_blacklist
        })

    @action(detail=True, methods=['post'])
    def toggle_activo(self, request, pk=None):
        """
        Activa/desactiva un usuario en blacklist.
        POST /api/blacklist/{id}/toggle_activo/
        """
        usuario = self.get_object()
        usuario.activo = not usuario.activo
        usuario.save()

        return Response({
            'id': usuario.id,
            'nombre_usuario': usuario.nombre_usuario,
            'activo': usuario.activo
        })


class ContadorUsuarioPortalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API ViewSet de solo lectura para contadores de usuarios por portal.
    Util para ver usuarios que estan cerca del umbral de blacklist.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ContadorUsuarioPortalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['portal']
    search_fields = ['nombre_usuario']
    ordering_fields = ['num_anuncios', 'ultima_deteccion']
    ordering = ['-num_anuncios']

    def get_queryset(self):
        return ContadorUsuarioPortal.objects.all()

    @action(detail=False, methods=['get'])
    def cerca_umbral(self, request):
        """
        Lista usuarios cerca del umbral de blacklist.
        GET /api/contadores/cerca_umbral/
        """
        umbral = ContadorUsuarioPortal.UMBRAL_BLACKLIST
        usuarios = ContadorUsuarioPortal.objects.filter(
            num_anuncios__gte=umbral - 2,
            num_anuncios__lt=umbral
        ).order_by('-num_anuncios')

        serializer = self.get_serializer(usuarios, many=True)
        return Response({
            'umbral': umbral,
            'usuarios': serializer.data
        })

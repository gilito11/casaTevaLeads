"""
Serializers para la API REST de core (zonas, blacklist, tenants).
"""
from rest_framework import serializers
from core.models import Tenant, ZonaGeografica, UsuarioBlacklist, ContadorUsuarioPortal, ZONAS_PREESTABLECIDAS


class TenantSerializer(serializers.ModelSerializer):
    """Serializer para tenants"""

    class Meta:
        model = Tenant
        fields = [
            'tenant_id', 'nombre', 'slug', 'email_contacto', 'telefono',
            'activo', 'fecha_alta', 'max_leads_mes'
        ]
        read_only_fields = ['tenant_id', 'slug', 'fecha_alta']


class ZonaGeograficaSerializer(serializers.ModelSerializer):
    """Serializer para zonas geograficas"""
    tenant_nombre = serializers.CharField(source='tenant.nombre', read_only=True)

    class Meta:
        model = ZonaGeografica
        fields = [
            'id', 'tenant', 'tenant_nombre', 'nombre', 'slug', 'tipo',
            'latitud', 'longitud', 'radio_km', 'provincia_id',
            'activa', 'precio_minimo',
            'scrapear_milanuncios', 'scrapear_fotocasa', 'scrapear_habitaclia', 'scrapear_idealista',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ZonaGeograficaCreateSerializer(serializers.Serializer):
    """Serializer para crear zonas desde zonas preestablecidas"""
    zona_key = serializers.ChoiceField(
        choices=list(ZONAS_PREESTABLECIDAS.keys()),
        help_text="Clave de zona preestablecida"
    )
    radio_km = serializers.IntegerField(default=20, min_value=1, max_value=100)
    precio_minimo = serializers.IntegerField(default=5000, min_value=0)


class UsuarioBlacklistSerializer(serializers.ModelSerializer):
    """Serializer para usuarios en blacklist"""
    tenant_nombre = serializers.CharField(source='tenant.nombre', read_only=True, allow_null=True)
    es_global = serializers.SerializerMethodField()

    class Meta:
        model = UsuarioBlacklist
        fields = [
            'id', 'portal', 'usuario_id', 'nombre_usuario',
            'tenant', 'tenant_nombre', 'es_global',
            'motivo', 'num_anuncios_detectados', 'notas',
            'activo', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_es_global(self, obj):
        return obj.tenant is None


class UsuarioBlacklistCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar usuarios en blacklist"""

    class Meta:
        model = UsuarioBlacklist
        fields = [
            'portal', 'usuario_id', 'nombre_usuario',
            'tenant', 'motivo', 'notas'
        ]


class ContadorUsuarioPortalSerializer(serializers.ModelSerializer):
    """Serializer para contadores de usuarios por portal"""

    class Meta:
        model = ContadorUsuarioPortal
        fields = [
            'id', 'portal', 'usuario_id', 'nombre_usuario',
            'num_anuncios', 'ultimo_anuncio_url',
            'primera_deteccion', 'ultima_deteccion'
        ]
        read_only_fields = ['id', 'primera_deteccion', 'ultima_deteccion']


class ZonasPreestablecidasSerializer(serializers.Serializer):
    """Serializer para listar zonas preestablecidas disponibles"""
    key = serializers.CharField()
    nombre = serializers.CharField()
    latitud = serializers.FloatField()
    longitud = serializers.FloatField()
    provincia_id = serializers.IntegerField()

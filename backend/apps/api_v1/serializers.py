from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from leads.models import Lead, LeadEstado
from core.models import ZonaGeografica
from .models import Webhook


class LeadListSerializer(serializers.Serializer):
    """Serializer para listado de leads (campos resumidos)."""
    lead_id = serializers.CharField(read_only=True)
    titulo = serializers.CharField(read_only=True)
    precio = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    metros = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True,
        source='superficie_m2'
    )
    habitaciones = serializers.IntegerField(read_only=True)
    portal = serializers.CharField(source='source_portal', read_only=True)
    zona = serializers.CharField(source='zona_clasificada', read_only=True)
    estado = serializers.CharField(read_only=True)
    telefono = serializers.CharField(source='telefono_norm', read_only=True)
    url_anuncio = serializers.CharField(source='listing_url', read_only=True)
    fecha_scraping = serializers.DateTimeField(
        source='fecha_primera_captura', read_only=True
    )
    lead_score = serializers.IntegerField(read_only=True)


class LeadDetailSerializer(serializers.Serializer):
    """Serializer para detalle completo de lead."""
    lead_id = serializers.CharField(read_only=True)
    titulo = serializers.CharField(read_only=True)
    descripcion = serializers.CharField(read_only=True)
    precio = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    precio_anterior = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True
    )
    precio_cambio_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True, allow_null=True
    )
    metros = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True,
        source='superficie_m2'
    )
    habitaciones = serializers.IntegerField(read_only=True)
    banos = serializers.IntegerField(read_only=True)
    tipo_inmueble = serializers.CharField(source='tipo_propiedad', read_only=True)
    direccion = serializers.CharField(source='ubicacion', read_only=True)
    zona = serializers.CharField(source='zona_clasificada', read_only=True)

    portal = serializers.CharField(source='source_portal', read_only=True)
    url_anuncio = serializers.CharField(source='listing_url', read_only=True)
    anuncio_id = serializers.CharField(source='source_listing_id', read_only=True)

    telefono = serializers.CharField(source='telefono_norm', read_only=True)
    email = serializers.EmailField(read_only=True)
    nombre_contacto = serializers.CharField(read_only=True)

    estado = serializers.CharField(read_only=True)
    asignado_a_id = serializers.IntegerField(source='asignado_a', read_only=True)
    numero_intentos = serializers.IntegerField(source='num_contactos', read_only=True)

    fotos = serializers.JSONField(source='fotos_json', read_only=True)
    lead_score = serializers.IntegerField(read_only=True)
    dias_en_mercado = serializers.IntegerField(read_only=True)
    es_particular = serializers.BooleanField(read_only=True)

    fecha_scraping = serializers.DateTimeField(
        source='fecha_primera_captura', read_only=True
    )
    fecha_primer_contacto = serializers.DateTimeField(read_only=True)
    fecha_ultimo_contacto = serializers.DateTimeField(read_only=True)
    ultima_actualizacion = serializers.DateTimeField(read_only=True)

    # Duplicados cross-portal
    num_portales = serializers.IntegerField(read_only=True, allow_null=True)
    portales = serializers.CharField(read_only=True, allow_null=True)


class LeadUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar estado de lead."""
    estado = serializers.ChoiceField(
        choices=Lead.ESTADO_CHOICES,
        required=False
    )
    asignado_a_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_estado(self, value):
        valid_states = [choice[0] for choice in Lead.ESTADO_CHOICES]
        if value and value not in valid_states:
            raise serializers.ValidationError(
                f"Estado invalido. Valores permitidos: {', '.join(valid_states)}"
            )
        return value


class ZonaSerializer(serializers.ModelSerializer):
    """Serializer para zonas geograficas."""
    portales_activos = serializers.SerializerMethodField()

    class Meta:
        model = ZonaGeografica
        fields = [
            'id', 'nombre', 'slug', 'tipo',
            'latitud', 'longitud', 'radio_km',
            'activa', 'precio_minimo',
            'portales_activos',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_portales_activos(self, obj) -> list:
        portales = []
        if obj.scrapear_milanuncios:
            portales.append('milanuncios')
        if obj.scrapear_fotocasa:
            portales.append('fotocasa')
        if obj.scrapear_habitaclia:
            portales.append('habitaclia')
        if obj.scrapear_idealista:
            portales.append('idealista')
        return portales


class WebhookSerializer(serializers.ModelSerializer):
    """Serializer para webhooks."""
    secret = serializers.CharField(read_only=True)

    class Meta:
        model = Webhook
        fields = [
            'id', 'url', 'event_type', 'secret',
            'is_active', 'last_triggered', 'last_status_code',
            'failure_count', 'created_at'
        ]
        read_only_fields = [
            'id', 'secret', 'last_triggered',
            'last_status_code', 'failure_count', 'created_at'
        ]


class WebhookCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear webhooks."""
    class Meta:
        model = Webhook
        fields = ['url', 'event_type']

    def create(self, validated_data):
        validated_data['secret'] = Webhook.generate_secret()
        validated_data['tenant'] = self.context['tenant']
        return super().create(validated_data)


class APIKeySerializer(serializers.Serializer):
    """Serializer para mostrar info de API key (sin el key plain)."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    prefix = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    rate_limit_per_hour = serializers.IntegerField(read_only=True)
    request_count = serializers.IntegerField(read_only=True)
    last_used = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class ErrorSerializer(serializers.Serializer):
    """Serializer para errores de API."""
    detail = serializers.CharField()
    code = serializers.CharField(required=False)

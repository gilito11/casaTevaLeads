"""
Serializers para la API REST de leads.
"""
from rest_framework import serializers
from leads.models import Lead, Nota


class NotaSerializer(serializers.ModelSerializer):
    """Serializer para notas de leads"""
    autor_nombre = serializers.CharField(source='autor.username', read_only=True)

    class Meta:
        model = Nota
        fields = ['id', 'lead', 'autor', 'autor_nombre', 'texto', 'created_at']
        read_only_fields = ['autor', 'created_at']


class LeadListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados de leads"""

    class Meta:
        model = Lead
        fields = [
            'lead_id', 'tenant_id', 'telefono_norm', 'nombre', 'direccion',
            'zona_geografica', 'precio', 'portal', 'estado', 'fecha_scraping',
            'created_at'
        ]


class LeadDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de lead"""
    notas = NotaSerializer(many=True, read_only=True)
    asignado_a_nombre = serializers.CharField(source='asignado_a.username', read_only=True)

    class Meta:
        model = Lead
        fields = [
            'lead_id', 'tenant_id', 'telefono_norm', 'email', 'nombre',
            'direccion', 'zona_geografica', 'codigo_postal', 'tipo_inmueble',
            'precio', 'habitaciones', 'metros', 'descripcion', 'fotos',
            'portal', 'url_anuncio', 'data_lake_reference', 'estado',
            'asignado_a', 'asignado_a_nombre', 'numero_intentos',
            'fecha_scraping', 'fecha_primer_contacto', 'fecha_ultimo_contacto',
            'fecha_cambio_estado', 'created_at', 'updated_at', 'notas'
        ]


class LeadUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar leads (solo campos editables)"""

    class Meta:
        model = Lead
        fields = ['estado', 'asignado_a', 'numero_intentos',
                  'fecha_primer_contacto', 'fecha_ultimo_contacto']

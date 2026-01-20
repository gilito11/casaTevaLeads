"""
Serializers para la API REST de leads.
"""
from rest_framework import serializers
from leads.models import Lead, Nota, Task


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
            'updated_at'
        ]


class LeadDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de lead"""
    notas = NotaSerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            'lead_id', 'tenant_id', 'telefono_norm', 'email', 'nombre',
            'direccion', 'zona_geografica', 'tipo_inmueble',
            'precio', 'habitaciones', 'banos', 'metros', 'titulo', 'descripcion',
            'portal', 'url_anuncio', 'data_lake_reference', 'estado',
            'asignado_a_id', 'numero_intentos',
            'fecha_scraping', 'fecha_primer_contacto', 'fecha_ultimo_contacto',
            'updated_at', 'es_particular', 'lead_score', 'fecha_publicacion', 'notas'
        ]


class LeadUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar leads (solo campos editables)"""

    class Meta:
        model = Lead
        fields = ['estado', 'asignado_a_id', 'numero_intentos',
                  'fecha_primer_contacto', 'fecha_ultimo_contacto']


class TaskSerializer(serializers.ModelSerializer):
    """Serializer para tareas/agenda"""
    asignado_a_nombre = serializers.CharField(source='asignado_a.username', read_only=True)
    created_by_nombre = serializers.CharField(source='created_by.username', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_para_vencer = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'tenant', 'lead_id', 'contact',
            'titulo', 'descripcion', 'tipo', 'tipo_display',
            'prioridad', 'prioridad_display',
            'fecha_vencimiento', 'completada', 'fecha_completada',
            'asignado_a', 'asignado_a_nombre',
            'created_by', 'created_by_nombre',
            'created_at', 'updated_at',
            'esta_vencida', 'dias_para_vencer'
        ]
        read_only_fields = ['tenant', 'created_by', 'created_at', 'updated_at', 'fecha_completada']


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear tareas"""

    class Meta:
        model = Task
        fields = [
            'lead_id', 'contact', 'titulo', 'descripcion',
            'tipo', 'prioridad', 'fecha_vencimiento', 'asignado_a'
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        tenant_id = self.context.get('tenant_id')

        validated_data['tenant_id'] = tenant_id
        validated_data['created_by'] = request.user

        if not validated_data.get('asignado_a'):
            validated_data['asignado_a'] = request.user

        return super().create(validated_data)

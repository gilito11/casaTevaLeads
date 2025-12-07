from django.contrib import admin
from .models import Lead, Nota


class NotaInline(admin.TabularInline):
    model = Nota
    extra = 1
    fields = ['autor', 'texto', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'lead_id', 'tenant', 'telefono_norm', 'nombre', 'direccion',
        'zona_geografica', 'precio', 'estado', 'asignado_a',
        'fecha_scraping', 'portal'
    ]
    list_filter = [
        'estado', 'portal', 'tenant', 'zona_geografica',
        'tipo_inmueble', 'fecha_scraping', 'asignado_a'
    ]
    search_fields = [
        'telefono_norm', 'email', 'nombre', 'direccion',
        'zona_geografica', 'codigo_postal', 'descripcion'
    ]
    readonly_fields = [
        'lead_id', 'created_at', 'updated_at', 'fecha_scraping',
        'data_lake_reference'
    ]
    autocomplete_fields = ['tenant', 'asignado_a']
    inlines = [NotaInline]

    fieldsets = (
        ('Información del Lead', {
            'fields': ('lead_id', 'tenant', 'telefono_norm', 'email', 'nombre')
        }),
        ('Propiedad', {
            'fields': (
                'direccion', 'zona_geografica', 'codigo_postal',
                'tipo_inmueble', 'precio', 'habitaciones', 'metros',
                'descripcion', 'fotos'
            )
        }),
        ('Origen', {
            'fields': ('portal', 'url_anuncio', 'data_lake_reference', 'fecha_scraping')
        }),
        ('Gestión', {
            'fields': (
                'estado', 'asignado_a', 'numero_intentos',
                'fecha_primer_contacto', 'fecha_ultimo_contacto',
                'fecha_cambio_estado'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ['lead', 'autor', 'texto', 'created_at']
    list_filter = ['created_at', 'autor']
    search_fields = ['texto', 'lead__telefono_norm', 'lead__nombre']
    readonly_fields = ['created_at']
    autocomplete_fields = ['lead', 'autor']

from django.contrib import admin
from .models import ACMReport


@admin.register(ACMReport)
class ACMReportAdmin(admin.ModelAdmin):
    list_display = ['lead_id', 'zona', 'valoracion_media', 'num_comparables', 'confianza', 'created_at']
    list_filter = ['metodologia', 'zona', 'tenant', 'created_at']
    search_fields = ['lead_id', 'zona']
    readonly_fields = ['created_at', 'comparables', 'ajustes']
    ordering = ['-created_at']

    fieldsets = (
        ('Lead', {
            'fields': ('tenant', 'lead_id')
        }),
        ('Valoracion', {
            'fields': ('valoracion_min', 'valoracion_max', 'valoracion_media',
                       'precio_m2_min', 'precio_m2_max', 'precio_m2_medio')
        }),
        ('Propiedad Analizada', {
            'fields': ('zona', 'tipo_propiedad', 'superficie_m2', 'habitaciones', 'precio_anuncio')
        }),
        ('Metodologia', {
            'fields': ('metodologia', 'num_comparables', 'confianza', 'ajustes')
        }),
        ('Comparables', {
            'fields': ('comparables',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by')
        }),
    )

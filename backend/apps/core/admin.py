from django.contrib import admin
from django.contrib import messages
from .models import Tenant, TenantUser, ZonaGeografica


@admin.action(description="Activar zonas seleccionadas")
def activar_zonas(modeladmin, request, queryset):
    updated = queryset.update(activa=True)
    messages.success(request, f"{updated} zonas activadas")


@admin.action(description="Desactivar zonas seleccionadas")
def desactivar_zonas(modeladmin, request, queryset):
    updated = queryset.update(activa=False)
    messages.success(request, f"{updated} zonas desactivadas")


@admin.action(description="Eliminar zonas (sin confirmación)")
def eliminar_zonas_rapido(modeladmin, request, queryset):
    count = queryset.count()
    queryset.delete()
    messages.success(request, f"{count} zonas eliminadas")


@admin.register(ZonaGeografica)
class ZonaGeograficaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'slug', 'tenant', 'activa', 'radio_km', 'get_portales']
    list_filter = ['activa', 'tenant', 'tipo']
    search_fields = ['nombre', 'slug']
    list_editable = ['activa']
    actions = [activar_zonas, desactivar_zonas, eliminar_zonas_rapido]
    ordering = ['tenant', 'nombre']

    def get_portales(self, obj):
        portales = []
        if obj.scrapear_milanuncios: portales.append('MA')
        if obj.scrapear_fotocasa: portales.append('FC')
        if obj.scrapear_habitaclia: portales.append('HA')
        if obj.scrapear_idealista: portales.append('ID')
        return ', '.join(portales)
    get_portales.short_description = 'Portales'


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['tenant_id', 'nombre', 'slug', 'email_contacto', 'activo', 'fecha_alta']
    list_filter = ['activo', 'fecha_alta']
    search_fields = ['nombre', 'slug', 'email_contacto', 'telefono']
    prepopulated_fields = {'slug': ('nombre',)}
    readonly_fields = ['tenant_id', 'fecha_alta']
    ordering = ['nombre']
    fieldsets = (
        ('Información básica', {
            'fields': ('tenant_id', 'nombre', 'slug', 'email_contacto', 'telefono')
        }),
        ('Contacto por defecto (fallback si comercial no tiene datos)', {
            'fields': ('comercial_nombre', 'comercial_email', 'comercial_telefono'),
            'description': 'Datos usados en formularios de contacto si el comercial asignado no tiene datos propios.'
        }),
        ('Configuración', {
            'fields': ('config_scraping', 'max_leads_mes', 'activo')
        }),
        ('Fechas', {
            'fields': ('fecha_alta',)
        }),
    )


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant', 'rol', 'comercial_email', 'comercial_telefono']
    list_filter = ['rol', 'tenant']
    search_fields = ['user__username', 'user__email', 'tenant__nombre', 'comercial_email']
    autocomplete_fields = ['user', 'tenant']
    fieldsets = (
        ('Usuario y Rol', {
            'fields': ('user', 'tenant', 'rol')
        }),
        ('Datos de Contacto del Comercial', {
            'fields': ('comercial_nombre', 'comercial_email', 'comercial_telefono'),
            'description': 'Datos usados en formularios de contacto automático. Si vacíos, usa datos del User.'
        }),
    )

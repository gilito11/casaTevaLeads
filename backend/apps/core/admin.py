from django.contrib import admin
from .models import Tenant, TenantUser


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['tenant_id', 'nombre', 'slug', 'email_contacto', 'telefono', 'activo', 'fecha_alta', 'max_leads_mes']
    list_filter = ['activo', 'fecha_alta']
    search_fields = ['nombre', 'slug', 'email_contacto', 'telefono']
    prepopulated_fields = {'slug': ('nombre',)}
    readonly_fields = ['tenant_id', 'fecha_alta']
    ordering = ['nombre']
    fieldsets = (
        ('Información básica', {
            'fields': ('tenant_id', 'nombre', 'slug', 'email_contacto', 'telefono')
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
    list_display = ['user', 'tenant', 'rol']
    list_filter = ['rol', 'tenant']
    search_fields = ['user__username', 'user__email', 'tenant__nombre']
    autocomplete_fields = ['user', 'tenant']

from django.contrib import admin
from django import forms
from .models import (
    Lead, Nota, LeadEstado, PortalCredential, ContactQueue,
    MessageTemplate, AutoContactConfig,
)


class NotaInline(admin.TabularInline):
    model = Nota
    extra = 1
    fields = ['autor', 'texto', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'lead_id', 'tenant_id', 'telefono_norm', 'nombre', 'direccion',
        'zona_geografica', 'precio', 'estado',
        'fecha_scraping', 'portal'
    ]
    list_filter = [
        'estado', 'portal', 'zona_geografica',
        'tipo_inmueble', 'fecha_scraping'
    ]
    search_fields = [
        'telefono_norm', 'email', 'nombre', 'direccion',
        'zona_geografica', 'descripcion'
    ]
    readonly_fields = [
        'lead_id', 'updated_at', 'fecha_scraping',
        'data_lake_reference'
    ]
    inlines = [NotaInline]

    fieldsets = (
        ('Información del Lead', {
            'fields': ('lead_id', 'tenant_id', 'telefono_norm', 'email', 'nombre')
        }),
        ('Propiedad', {
            'fields': (
                'direccion', 'zona_geografica',
                'tipo_inmueble', 'precio', 'habitaciones', 'banos', 'metros',
                'titulo', 'descripcion'
            )
        }),
        ('Origen', {
            'fields': ('portal', 'url_anuncio', 'data_lake_reference', 'fecha_scraping')
        }),
        ('Gestión', {
            'fields': (
                'estado', 'asignado_a_id', 'numero_intentos',
                'fecha_primer_contacto', 'fecha_ultimo_contacto'
            )
        }),
        ('Metadata', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(LeadEstado)
class LeadEstadoAdmin(admin.ModelAdmin):
    list_display = ['lead_id', 'telefono_norm', 'estado', 'numero_intentos', 'fecha_cambio_estado']
    list_filter = ['estado', 'tenant']
    search_fields = ['lead_id', 'telefono_norm']
    readonly_fields = ['lead_id', 'created_at', 'updated_at']


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ['lead', 'autor', 'texto', 'created_at']
    list_filter = ['created_at', 'autor']
    search_fields = ['texto', 'lead__telefono_norm']
    readonly_fields = ['created_at']
    autocomplete_fields = ['autor']


class PortalCredentialForm(forms.ModelForm):
    """Formulario especial para manejar password cifrada."""
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Dejar en blanco para mantener la password actual"
    )

    class Meta:
        model = PortalCredential
        fields = ['tenant', 'portal', 'email', 'password', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.password_encrypted:
            self.fields['password'].initial = '********'

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password and password != '********':
            instance.set_password(password)
        if commit:
            instance.save()
        return instance


@admin.register(PortalCredential)
class PortalCredentialAdmin(admin.ModelAdmin):
    form = PortalCredentialForm
    list_display = ['tenant', 'portal', 'email', 'is_active', 'last_used', 'updated_at']
    list_filter = ['portal', 'is_active', 'tenant']
    search_fields = ['email', 'tenant__nombre']
    readonly_fields = ['last_used', 'last_error', 'created_at', 'updated_at']

    fieldsets = (
        ('Credenciales', {
            'fields': ('tenant', 'portal', 'email', 'password', 'is_active')
        }),
        ('Estado', {
            'fields': ('last_used', 'last_error'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactQueue)
class ContactQueueAdmin(admin.ModelAdmin):
    list_display = ['lead_id', 'portal', 'tenant', 'estado', 'prioridad', 'respondio', 'template', 'created_at', 'processed_at']
    list_filter = ['estado', 'portal', 'tenant', 'respondio']
    search_fields = ['lead_id', 'titulo']
    readonly_fields = ['created_at', 'updated_at', 'processed_at']


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'canal', 'tenant', 'activa', 'peso', 'veces_usada', 'tasa_respuesta_display']
    list_filter = ['canal', 'activa', 'tenant']
    search_fields = ['nombre', 'cuerpo']
    list_editable = ['activa', 'peso']
    readonly_fields = ['veces_usada', 'veces_respondida', 'created_at', 'updated_at']

    def tasa_respuesta_display(self, obj):
        if obj.veces_usada == 0:
            return '-'
        return f"{obj.tasa_respuesta:.1%}"
    tasa_respuesta_display.short_description = 'Tasa Respuesta'


@admin.register(AutoContactConfig)
class AutoContactConfigAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'habilitado', 'solo_particulares', 'max_contactos_dia', 'max_contactos_portal_dia']
    list_filter = ['habilitado']

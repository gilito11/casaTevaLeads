from django.contrib import admin
from django.utils.html import format_html
from .models import APIKey, Webhook, WebhookDelivery


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'prefix_display', 'is_active', 'rate_limit_per_hour', 'request_count', 'last_used']
    list_filter = ['is_active', 'tenant']
    search_fields = ['name', 'tenant__nombre']
    readonly_fields = ['prefix', 'key_hash', 'request_count', 'last_used', 'created_at']

    fieldsets = (
        (None, {
            'fields': ('tenant', 'name')
        }),
        ('Permisos', {
            'fields': ('can_read_leads', 'can_write_leads', 'can_manage_webhooks')
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_per_hour',)
        }),
        ('Estado', {
            'fields': ('is_active', 'expires_at')
        }),
        ('Info (solo lectura)', {
            'fields': ('prefix', 'request_count', 'last_used', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def prefix_display(self, obj):
        return f"{obj.prefix}..."
    prefix_display.short_description = 'Key Prefix'

    def save_model(self, request, obj, form, change):
        if not change:  # Nueva key
            api_key, plain_key = APIKey.create_for_tenant(
                tenant=obj.tenant,
                name=obj.name,
                can_read_leads=obj.can_read_leads,
                can_write_leads=obj.can_write_leads,
                can_manage_webhooks=obj.can_manage_webhooks,
                rate_limit_per_hour=obj.rate_limit_per_hour,
                expires_at=obj.expires_at,
            )
            # Mostrar la key solo una vez
            self.message_user(
                request,
                f"API Key creada. COPIA AHORA (no se mostrara de nuevo): {plain_key}",
                level='WARNING'
            )
            return
        super().save_model(request, obj, form, change)


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'event_type', 'url_truncated', 'is_active', 'failure_count', 'last_triggered']
    list_filter = ['is_active', 'event_type', 'tenant']
    search_fields = ['url', 'tenant__nombre']
    readonly_fields = ['secret', 'last_triggered', 'last_status_code', 'failure_count', 'created_at']

    def url_truncated(self, obj):
        if len(obj.url) > 50:
            return f"{obj.url[:50]}..."
        return obj.url
    url_truncated.short_description = 'URL'

    def save_model(self, request, obj, form, change):
        if not change:  # Nuevo webhook
            obj.secret = Webhook.generate_secret()
        super().save_model(request, obj, form, change)


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ['webhook', 'event_type', 'success_badge', 'status_code', 'duration_ms', 'created_at']
    list_filter = ['success', 'event_type', 'webhook__tenant']
    readonly_fields = ['webhook', 'event_type', 'payload', 'status_code', 'response_body', 'success', 'error', 'duration_ms', 'created_at']
    ordering = ['-created_at']

    def success_badge(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">OK</span>')
        return format_html('<span style="color: red;">FAIL</span>')
    success_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

from django.contrib import admin
from .models import PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'endpoint')
    readonly_fields = ('endpoint', 'p256dh', 'auth', 'created_at', 'updated_at')
    ordering = ('-created_at',)

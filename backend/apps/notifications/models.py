from django.db import models
from django.conf import settings


class NotificationManager(models.Manager):
    def unread_for_user(self, user, tenant_id=None):
        qs = self.filter(is_read=False).filter(
            models.Q(user=user) | models.Q(user__isnull=True)
        )
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs.order_by('-created_at')


class Notification(models.Model):
    TIPO_CHOICES = [
        ('nueva_lead', 'Nuevo Lead'),
        ('bajada_precio', 'Bajada de Precio'),
        ('tarea', 'Tarea'),
        ('contacto', 'Contacto'),
        ('sistema', 'Sistema'),
    ]

    tenant = models.ForeignKey(
        'core.Tenant', on_delete=models.CASCADE,
        related_name='notifications', db_column='tenant_id'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', null=True, blank=True,
        help_text="Null = broadcast to all tenant users"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='sistema')
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True, default='')
    url = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationManager()

    class Meta:
        db_table = 'notifications_notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.tipo}] {self.titulo}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


class AlertPreferences(models.Model):
    """User preferences for Telegram and push notifications."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alert_preferences'
    )

    # Daily summary
    daily_summary_enabled = models.BooleanField(default=True)
    daily_summary_hour = models.IntegerField(default=9, help_text="Hora del dia (0-23)")

    # Price drop alerts
    price_drop_enabled = models.BooleanField(default=True)
    price_drop_threshold = models.IntegerField(
        default=5,
        help_text="Porcentaje minimo de bajada para alertar"
    )

    # New leads alerts
    new_leads_enabled = models.BooleanField(default=True)
    new_leads_min_score = models.IntegerField(
        default=0,
        help_text="Score minimo del lead para alertar (0-100)"
    )

    # Error alerts (for admins)
    error_alerts_enabled = models.BooleanField(default=False)

    # Task reminders
    task_reminders_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications_alert_preferences'
        verbose_name = 'Alert Preferences'
        verbose_name_plural = 'Alert Preferences'

    def __str__(self):
        return f"Alert prefs for {self.user.username}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create preferences for a user."""
        prefs, _ = cls.objects.get_or_create(user=user)
        return prefs


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'notifications_push_subscription'
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'

    def __str__(self):
        return f"{self.user.username} - {self.endpoint[:50]}..."

    def get_subscription_info(self):
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh,
                "auth": self.auth
            }
        }

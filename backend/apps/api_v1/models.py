import secrets
import hashlib
from django.db import models
from django.utils import timezone
from core.models import Tenant


class APIKey(models.Model):
    """
    API Keys para autenticacion de integraciones externas.
    Cada key esta vinculada a un tenant y tiene permisos configurables.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    name = models.CharField(
        max_length=100,
        help_text="Nombre descriptivo para identificar la key"
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA256 hash de la API key"
    )
    prefix = models.CharField(
        max_length=8,
        help_text="Prefijo visible de la key (para identificacion)"
    )

    # Permisos
    can_read_leads = models.BooleanField(default=True)
    can_write_leads = models.BooleanField(default=True)
    can_manage_webhooks = models.BooleanField(default=True)

    # Estado
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    request_count = models.IntegerField(default=0)

    # Rate limiting
    rate_limit_per_hour = models.IntegerField(
        default=100,
        help_text="Requests permitidos por hora"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Si es null, no expira"
    )

    class Meta:
        db_table = 'api_keys'
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @classmethod
    def generate_key(cls):
        """Genera una nueva API key segura."""
        return f"ctv_{secrets.token_urlsafe(32)}"

    @classmethod
    def hash_key(cls, key: str) -> str:
        """Genera el hash SHA256 de una key."""
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create_for_tenant(cls, tenant: Tenant, name: str, **kwargs):
        """
        Crea una nueva API key para un tenant.
        Retorna tuple (APIKey, plain_key) - plain_key solo se muestra una vez.
        """
        plain_key = cls.generate_key()
        key_hash = cls.hash_key(plain_key)
        prefix = plain_key[:8]

        api_key = cls.objects.create(
            tenant=tenant,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            **kwargs
        )
        return api_key, plain_key

    @classmethod
    def get_by_key(cls, key: str):
        """Busca una API key por su valor plain."""
        key_hash = cls.hash_key(key)
        try:
            api_key = cls.objects.select_related('tenant').get(
                key_hash=key_hash,
                is_active=True
            )
            # Verificar expiracion
            if api_key.expires_at and api_key.expires_at < timezone.now():
                return None
            return api_key
        except cls.DoesNotExist:
            return None

    def record_usage(self):
        """Registra uso de la API key."""
        self.last_used = timezone.now()
        self.request_count += 1
        self.save(update_fields=['last_used', 'request_count'])


class Webhook(models.Model):
    """
    Configuracion de webhooks para notificaciones de eventos.
    """
    EVENT_TYPES = [
        ('new_lead', 'Nuevo Lead'),
        ('status_change', 'Cambio de Estado'),
        ('price_drop', 'Bajada de Precio'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    url = models.URLField(
        max_length=500,
        help_text="URL donde se enviaran los eventos"
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES
    )
    secret = models.CharField(
        max_length=64,
        help_text="Secret para firma HMAC-SHA256"
    )

    # Estado
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_status_code = models.IntegerField(null=True, blank=True)
    failure_count = models.IntegerField(default=0)

    # Si falla muchas veces, se desactiva automaticamente
    max_failures = models.IntegerField(
        default=5,
        help_text="Desactivar tras N fallos consecutivos"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'api_webhooks'
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
        unique_together = ['tenant', 'url', 'event_type']

    def __str__(self):
        status = "activo" if self.is_active else "inactivo"
        return f"{self.get_event_type_display()} -> {self.url[:50]}... ({status})"

    @classmethod
    def generate_secret(cls) -> str:
        """Genera un secret para firmar webhooks."""
        return secrets.token_hex(32)

    def record_success(self, status_code: int):
        """Registra envio exitoso."""
        self.last_triggered = timezone.now()
        self.last_status_code = status_code
        self.failure_count = 0
        self.save(update_fields=['last_triggered', 'last_status_code', 'failure_count'])

    def record_failure(self, status_code: int = None):
        """Registra fallo y desactiva si supera max_failures."""
        self.last_triggered = timezone.now()
        self.last_status_code = status_code
        self.failure_count += 1

        if self.failure_count >= self.max_failures:
            self.is_active = False

        self.save(update_fields=['last_triggered', 'last_status_code', 'failure_count', 'is_active'])


class WebhookDelivery(models.Model):
    """
    Log de entregas de webhooks para debugging.
    """
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    event_type = models.CharField(max_length=20)
    payload = models.JSONField()

    # Respuesta
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'api_webhook_deliveries'
        verbose_name = 'Webhook Delivery'
        verbose_name_plural = 'Webhook Deliveries'
        ordering = ['-created_at']

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.event_type} -> {self.webhook.url[:30]}... [{status}]"

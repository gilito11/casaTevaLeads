from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Tenant


class Lead(models.Model):
    """
    Modelo para gestionar leads inmobiliarios - Vista desde public_marts.dim_leads
    Los campos Django se mapean a las columnas reales de dbt via db_column.
    """

    ESTADO_CHOICES = [
        ('NUEVO', 'Nuevo'),
        ('EN_PROCESO', 'En proceso'),
        ('CONTACTADO_SIN_RESPUESTA', 'Contactado sin respuesta'),
        ('INTERESADO', 'Interesado'),
        ('NO_INTERESADO', 'No interesado'),
        ('EN_ESPERA', 'En espera'),
        ('NO_CONTACTAR', 'No contactar'),
        ('CLIENTE', 'Cliente'),
        ('YA_VENDIDO', 'Ya vendido'),
    ]

    # Columnas que existen en public_marts.dim_leads (dbt)
    lead_id = models.CharField(max_length=100, primary_key=True)
    tenant_id = models.IntegerField()
    telefono_norm = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    nombre = models.CharField(max_length=255, blank=True, null=True, db_column='nombre_contacto')
    direccion = models.TextField(null=True, blank=True, db_column='ubicacion')
    zona_geografica = models.CharField(max_length=100, null=True, blank=True, db_column='zona_clasificada')
    tipo_inmueble = models.CharField(max_length=50, blank=True, null=True, db_column='tipo_propiedad')
    precio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    habitaciones = models.IntegerField(null=True, blank=True)
    banos = models.IntegerField(null=True, blank=True)
    metros = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, db_column='superficie_m2')
    titulo = models.TextField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    portal = models.CharField(max_length=50, null=True, blank=True, db_column='source_portal')
    url_anuncio = models.TextField(null=True, blank=True, db_column='listing_url')
    data_lake_reference = models.TextField(blank=True, null=True, db_column='data_lake_path')
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='NUEVO')
    numero_intentos = models.IntegerField(default=0, db_column='num_contactos')
    fecha_scraping = models.DateTimeField(null=True, blank=True, db_column='fecha_primera_captura')
    fecha_primer_contacto = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_contacto = models.DateTimeField(null=True, blank=True)
    asignado_a_id = models.IntegerField(null=True, blank=True, db_column='asignado_a')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='ultima_actualizacion')
    anuncio_id = models.CharField(max_length=255, blank=True, null=True, db_column='source_listing_id')
    # Additional dbt columns
    es_particular = models.BooleanField(null=True, blank=True)
    lead_score = models.IntegerField(null=True, blank=True)
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    fotos = models.JSONField(null=True, blank=True, db_column='fotos_json')

    class Meta:
        db_table = '"public_marts"."dim_leads"'
        managed = False
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-fecha_scraping']

    def __str__(self):
        return f"{self.telefono_norm} - {self.direccion} ({self.estado})"

    @property
    def fotos_list(self):
        """Return photos as list, handling JSON string if needed."""
        import json
        if not self.fotos:
            return []
        if isinstance(self.fotos, str):
            try:
                return json.loads(self.fotos)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(self.fotos, list):
            return self.fotos
        return []

    @property
    def fotos_proxied(self):
        """Return photo URLs through proxy to avoid hotlink protection."""
        import base64

        fotos = self.fotos_list
        if not fotos:
            return []

        proxied = []
        for url in fotos:
            # Use urlsafe base64 without padding for cleaner URLs
            url_b64 = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
            proxy_url = f"/leads/img/?url={url_b64}"
            proxied.append(proxy_url)
        return proxied


class LeadEstado(models.Model):
    """
    Tabla separada para gestionar el estado CRM de los leads.
    Esta tabla es gestionada por Django (managed=True) y permite
    actualizar el estado independientemente del modelo dbt.
    """
    ESTADO_CHOICES = Lead.ESTADO_CHOICES

    lead_id = models.CharField(max_length=100, primary_key=True)  # MD5 hash del lead
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='lead_estados')
    telefono_norm = models.CharField(max_length=20, db_index=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='NUEVO')
    asignado_a = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_estado_asignados'
    )
    numero_intentos = models.IntegerField(default=0)
    fecha_primer_contacto = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_contacto = models.DateTimeField(null=True, blank=True)
    fecha_cambio_estado = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_lead_estado'
        verbose_name = 'Estado de Lead'
        verbose_name_plural = 'Estados de Leads'

    def __str__(self):
        return f"{self.telefono_norm} - {self.estado}"


class Nota(models.Model):
    """Modelo para notas asociadas a leads"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notas')
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='notas')
    texto = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'

    def __str__(self):
        return f"Nota de {self.autor} - {self.lead} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class Contact(models.Model):
    """
    Modelo para gestionar contactos de forma separada de los leads.
    Un contacto puede tener multiples propiedades/leads asociados.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='contacts')
    telefono = models.CharField(max_length=20, db_index=True)
    telefono2 = models.CharField(max_length=20, blank=True, null=True)
    nombre = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_contact'
        verbose_name = 'Contacto'
        verbose_name_plural = 'Contactos'
        unique_together = ['tenant', 'telefono']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.nombre or 'Sin nombre'} ({self.telefono})"

    def get_leads(self):
        """Obtiene todos los leads asociados a este contacto por telefono."""
        return Lead.objects.filter(
            tenant_id=self.tenant_id,
            telefono_norm=self.telefono
        ).order_by('-fecha_scraping')

    @property
    def leads_count(self):
        """Numero de propiedades/leads asociados."""
        return self.get_leads().count()


class Interaction(models.Model):
    """
    Modelo para registrar interacciones con contactos.
    Incluye llamadas, emails, notas, etc.
    """
    TIPO_CHOICES = [
        ('llamada', 'Llamada'),
        ('email', 'Email'),
        ('nota', 'Nota'),
        ('visita', 'Visita'),
        ('whatsapp', 'WhatsApp'),
        ('otro', 'Otro'),
    ]

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interactions')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='nota')
    descripcion = models.TextField()
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='interactions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'leads_interaction'
        verbose_name = 'Interaccion'
        verbose_name_plural = 'Interacciones'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        fecha_str = self.fecha.strftime('%d/%m/%Y') if self.fecha else 'Sin fecha'
        return f"{self.get_tipo_display()} - {self.contact} ({fecha_str})"


class AnuncioBlacklist(models.Model):
    """
    Modelo para almacenar anuncios que no deben volver a scrapearse.
    Cuando un usuario elimina un lead con la opcion "no volver a scrapear",
    se guarda aqui para que los scrapers lo ignoren en futuras ejecuciones.
    """
    PORTAL_CHOICES = [
        ('milanuncios', 'Milanuncios'),
        ('fotocasa', 'Fotocasa'),
        ('habitaclia', 'Habitaclia'),
        ('idealista', 'Idealista'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='anuncios_blacklist'
    )
    portal = models.CharField(max_length=50, choices=PORTAL_CHOICES)
    anuncio_id = models.CharField(
        max_length=255,
        help_text="ID unico del anuncio en el portal"
    )
    url_anuncio = models.TextField(blank=True, null=True)
    titulo = models.CharField(max_length=500, blank=True, null=True)
    motivo = models.TextField(
        blank=True,
        null=True,
        help_text="Motivo por el que se añadio a blacklist"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='anuncios_blacklist_creados'
    )

    class Meta:
        db_table = 'leads_anuncio_blacklist'
        verbose_name = 'Anuncio en Blacklist'
        verbose_name_plural = 'Anuncios en Blacklist'
        unique_together = ['tenant', 'portal', 'anuncio_id']
        indexes = [
            models.Index(fields=['portal', 'anuncio_id']),
        ]

    def __str__(self):
        return f"{self.portal}: {self.anuncio_id}"

    @classmethod
    def esta_en_blacklist(cls, tenant_id, portal, anuncio_id):
        """Verifica si un anuncio esta en blacklist"""
        return cls.objects.filter(
            tenant_id=tenant_id,
            portal=portal,
            anuncio_id=anuncio_id
        ).exists()


class ContactQueue(models.Model):
    """
    Cola de leads pendientes de contactar automaticamente.
    El CRM encola leads aqui y Dagster los procesa diariamente.
    """
    ESTADO_QUEUE_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROCESO', 'En proceso'),
        ('COMPLETADO', 'Completado'),
        ('FALLIDO', 'Fallido'),
        ('CANCELADO', 'Cancelado'),
    ]

    PORTAL_CHOICES = [
        ('fotocasa', 'Fotocasa'),
        ('habitaclia', 'Habitaclia'),
        ('milanuncios', 'Milanuncios'),
        ('idealista', 'Idealista'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='contact_queue')
    lead_id = models.CharField(max_length=100)
    portal = models.CharField(max_length=50, choices=PORTAL_CHOICES)
    listing_url = models.TextField()
    titulo = models.CharField(max_length=500, blank=True, null=True)
    mensaje = models.TextField(help_text="Mensaje a enviar al vendedor")
    estado = models.CharField(max_length=20, choices=ESTADO_QUEUE_CHOICES, default='PENDIENTE')
    prioridad = models.IntegerField(default=0, help_text="Mayor numero = mayor prioridad")

    # Resultado del contacto
    telefono_extraido = models.CharField(max_length=20, blank=True, null=True)
    mensaje_enviado = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # Usuario que encolo
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contacts_encolados'
    )

    class Meta:
        db_table = 'leads_contact_queue'
        verbose_name = 'Cola de Contacto'
        verbose_name_plural = 'Cola de Contactos'
        ordering = ['-prioridad', 'created_at']
        indexes = [
            models.Index(fields=['estado', 'portal']),
            models.Index(fields=['tenant', 'estado']),
        ]

    def __str__(self):
        return f"{self.portal}: {self.lead_id} ({self.estado})"


class PortalSession(models.Model):
    """
    Sesiones de portales (cookies) para automatizacion.
    Almacena cookies de login para evitar autenticacion repetida.
    """
    PORTAL_CHOICES = [
        ('fotocasa', 'Fotocasa'),
        ('habitaclia', 'Habitaclia'),
        ('milanuncios', 'Milanuncios'),
        ('idealista', 'Idealista'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='portal_sessions')
    portal = models.CharField(max_length=50, choices=PORTAL_CHOICES)
    email = models.EmailField(help_text="Email de la cuenta del portal")
    cookies = models.JSONField(help_text="Cookies de sesion (JSON)")
    is_valid = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Cuando expira la sesion")

    class Meta:
        db_table = 'leads_portal_session'
        verbose_name = 'Sesion de Portal'
        verbose_name_plural = 'Sesiones de Portales'
        unique_together = ['tenant', 'portal']

    def __str__(self):
        status = "válida" if self.is_valid else "inválida"
        return f"{self.portal} ({self.email}) - {status}"


class PortalCredential(models.Model):
    """
    Credenciales de portales por tenant.
    Las passwords se almacenan cifradas con Fernet.
    """
    PORTAL_CHOICES = [
        ('fotocasa', 'Fotocasa'),
        ('habitaclia', 'Habitaclia'),
        ('milanuncios', 'Milanuncios'),
        ('idealista', 'Idealista'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='portal_credentials')
    portal = models.CharField(max_length=50, choices=PORTAL_CHOICES)
    email = models.EmailField(help_text="Email de la cuenta del portal")
    password_encrypted = models.TextField(help_text="Password cifrada con Fernet")
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_portal_credential'
        verbose_name = 'Credencial de Portal'
        verbose_name_plural = 'Credenciales de Portales'
        unique_together = ['tenant', 'portal']

    def __str__(self):
        status = "activa" if self.is_active else "inactiva"
        return f"{self.portal} - {self.tenant.nombre} ({status})"

    def set_password(self, plain_password: str):
        """Cifra y guarda la password."""
        from core.encryption import encrypt_value
        self.password_encrypted = encrypt_value(plain_password)

    def get_password(self) -> str:
        """Descifra y retorna la password."""
        from core.encryption import decrypt_value
        return decrypt_value(self.password_encrypted)

    @classmethod
    def get_credential(cls, tenant_id: int, portal: str):
        """
        Obtiene las credenciales para un tenant y portal.
        Retorna None si no existe o no está activa.
        """
        try:
            return cls.objects.get(
                tenant_id=tenant_id,
                portal=portal,
                is_active=True
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_env(cls, tenant_id: int, portal: str):
        """
        Obtiene credenciales del tenant, con fallback a env vars.
        Retorna tuple (email, password) o (None, None).
        """
        import os

        # Intentar obtener del tenant
        cred = cls.get_credential(tenant_id, portal)
        if cred:
            return (cred.email, cred.get_password())

        # Fallback a env vars
        portal_upper = portal.upper()
        email = os.environ.get(f'{portal_upper}_EMAIL')
        password = os.environ.get(f'{portal_upper}_PASSWORD')

        if email and password:
            return (email, password)

        return (None, None)


class Task(models.Model):
    """
    Tareas/Recordatorios para seguimiento de leads.
    Agenda de acciones pendientes para el comercial.
    """
    TIPO_CHOICES = [
        ('llamar', 'Llamar'),
        ('visitar', 'Visitar'),
        ('enviar_info', 'Enviar información'),
        ('seguimiento', 'Seguimiento'),
        ('reunion', 'Reunión'),
        ('otro', 'Otro'),
    ]

    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tasks')
    lead_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tasks'
    )

    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='seguimiento')
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='media')

    fecha_vencimiento = models.DateTimeField()
    completada = models.BooleanField(default=False)
    fecha_completada = models.DateTimeField(null=True, blank=True)

    asignado_a = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks_asignadas'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks_creadas'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_task'
        verbose_name = 'Tarea'
        verbose_name_plural = 'Tareas'
        ordering = ['completada', 'fecha_vencimiento', '-prioridad']
        indexes = [
            models.Index(fields=['tenant', 'asignado_a', 'completada']),
            models.Index(fields=['fecha_vencimiento', 'completada']),
        ]

    def __str__(self):
        estado = "✓" if self.completada else "○"
        return f"{estado} {self.titulo} ({self.fecha_vencimiento.strftime('%d/%m')})"

    def marcar_completada(self):
        """Marca la tarea como completada."""
        self.completada = True
        self.fecha_completada = timezone.now()
        self.save(update_fields=['completada', 'fecha_completada', 'updated_at'])

    @property
    def esta_vencida(self):
        """Retorna True si la tarea está vencida y no completada."""
        if self.completada:
            return False
        return timezone.now() > self.fecha_vencimiento

    @property
    def dias_para_vencer(self):
        """Días restantes hasta vencimiento (negativo si vencida)."""
        if self.completada:
            return None
        delta = self.fecha_vencimiento - timezone.now()
        return delta.days

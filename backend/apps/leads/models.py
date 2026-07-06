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
    permite_inmobiliarias = models.BooleanField(null=True, blank=True)
    lead_score = models.IntegerField(null=True, blank=True)
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    fotos = models.JSONField(null=True, blank=True, db_column='fotos_json')
    precio_anterior = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    precio_cambio_pct = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    dias_en_mercado = models.IntegerField(null=True, blank=True)
    image_score = models.IntegerField(null=True, blank=True)
    lead_score_total = models.IntegerField(null=True, blank=True)

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

    @property
    def has_phone(self):
        """True solo si el telefono es real (no vacio ni clave sintetica 'lead:')."""
        return bool(self.telefono) and not self.telefono.startswith('lead:')

    @property
    def telefono_display(self):
        """Telefono para mostrar en UI; vacio si es sintetico o inexistente."""
        return self.telefono if self.has_phone else ''

    def get_leads(self):
        """Obtiene todos los leads asociados a este contacto por telefono."""
        if not self.has_phone:
            return Lead.objects.none()
        return Lead.objects.filter(
            tenant_id=self.tenant_id,
            telefono_norm=self.telefono
        ).order_by('-fecha_scraping')

    @property
    def leads_count(self):
        """Numero de propiedades/leads asociados (por telefono o asignadas)."""
        n = self.get_leads().count()
        return n if n else self.propiedades.count()


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

    # Template usado (para A/B testing)
    template = models.ForeignKey(
        'MessageTemplate', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contactos'
    )

    # Resultado del contacto
    telefono_extraido = models.CharField(max_length=20, blank=True, null=True)
    mensaje_enviado = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)

    # Tracking respuesta (A/B testing)
    respondio = models.BooleanField(default=False)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

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
    PRIORIDAD_ORDER = {'urgente': 0, 'alta': 1, 'media': 2, 'baja': 3}

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
        ordering = ['completada', 'fecha_vencimiento']
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


class MessageTemplate(models.Model):
    """Plantillas de mensaje para contacto automatico con A/B testing."""
    CANAL_CHOICES = [
        ('portal', 'Formulario Portal'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='message_templates')
    nombre = models.CharField(max_length=100)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default='portal')
    asunto = models.CharField(max_length=255, blank=True, help_text="Asunto (para email)")
    cuerpo = models.TextField(
        help_text="Variables: {nombre_zona}, {tipo_propiedad}, {precio}, {portal}, {url_anuncio}"
    )
    activa = models.BooleanField(default=True)
    peso = models.IntegerField(
        default=100,
        help_text="Peso relativo para A/B testing. Mayor peso = mas frecuente."
    )

    # Metricas A/B
    veces_usada = models.IntegerField(default=0)
    veces_respondida = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_message_template'
        ordering = ['-peso', 'nombre']

    def __str__(self):
        tasa = f" ({self.tasa_respuesta:.0%})" if self.veces_usada > 0 else ""
        return f"{self.nombre} [{self.get_canal_display()}]{tasa}"

    @property
    def tasa_respuesta(self):
        if self.veces_usada == 0:
            return 0.0
        return self.veces_respondida / self.veces_usada

    def render(self, context: dict) -> str:
        """Render template con variables. Ignora keys faltantes."""
        body = self.cuerpo
        for key, val in context.items():
            body = body.replace(f'{{{key}}}', str(val))
        return body


class AutoContactConfig(models.Model):
    """Configuracion de auto-contacto por tenant."""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='auto_contact_config')
    habilitado = models.BooleanField(default=False)

    # Filtros
    solo_particulares = models.BooleanField(default=True)
    score_minimo = models.IntegerField(default=0)
    precio_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=5000)
    precio_maximo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Portales habilitados
    contactar_fotocasa = models.BooleanField(default=True)
    contactar_habitaclia = models.BooleanField(default=True)
    contactar_milanuncios = models.BooleanField(default=True)
    contactar_idealista = models.BooleanField(default=True)

    # Limites
    max_contactos_dia = models.IntegerField(default=5)
    max_contactos_portal_dia = models.IntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_auto_contact_config'

    def __str__(self):
        estado = "ON" if self.habilitado else "OFF"
        return f"Auto-contacto {estado}"

    def portal_habilitado(self, portal: str) -> bool:
        mapping = {
            'fotocasa': self.contactar_fotocasa,
            'habitaclia': self.contactar_habitaclia,
            'milanuncios': self.contactar_milanuncios,
            'idealista': self.contactar_idealista,
        }
        return mapping.get(portal, False)

    def select_template(self, canal='portal'):
        """Selecciona template con weighted random para A/B testing."""
        import random
        templates = list(MessageTemplate.objects.filter(
            tenant=self.tenant, activa=True, canal=canal
        ))
        if not templates:
            return None
        weights = [t.peso for t in templates]
        return random.choices(templates, weights=weights, k=1)[0]


class LeadDireccion(models.Model):
    """
    Direccion exacta de un lead, escrita manualmente por el comercial.
    Lead es una vista dbt (solo lectura), asi que la direccion precisa y sus
    coordenadas geocodificadas se guardan aqui (tabla writable).
    """
    lead_id = models.CharField(max_length=100, primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='lead_direcciones')
    direccion_exacta = models.CharField(max_length=500)
    latitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geocoded = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lead_direcciones_creadas'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads_lead_direccion'
        verbose_name = 'Direccion de Lead'
        verbose_name_plural = 'Direcciones de Leads'

    def __str__(self):
        return f"{self.lead_id}: {self.direccion_exacta}"


class ContactPropiedad(models.Model):
    """
    Relacion explicita Contacto <-> propiedad (lead), con info de venta.
    Permite asignar a un contacto las propiedades que tiene en venta o que
    ya ha vendido, guardando precio y fecha de venta.
    """
    TIPO_CHOICES = [
        ('en_venta', 'En venta'),
        ('vendida', 'Vendida'),
    ]

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='propiedades')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='contact_propiedades')
    lead_id = models.CharField(max_length=100, db_index=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='en_venta')
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fecha_venta = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contact_propiedades_creadas'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'leads_contact_propiedad'
        verbose_name = 'Propiedad de Contacto'
        verbose_name_plural = 'Propiedades de Contactos'
        unique_together = ['contact', 'lead_id']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.contact} - {self.lead_id} ({self.tipo})"

    @property
    def lead(self):
        """Resuelve el Lead asociado (puede no existir si ya no esta en dim_leads)."""
        return Lead.objects.filter(lead_id=self.lead_id, tenant_id=self.tenant_id).first()


class AuditLog(models.Model):
    """
    Registro de auditoria interno (solo superuser via admin).
    Guarda cambios de estado y borrados de leads con snapshot de datos,
    de forma que el rastro sobrevive aunque el lead se elimine despues.
    """
    ACCION_CHOICES = [
        ('estado_creado', 'Estado creado'),
        ('estado_cambiado', 'Estado cambiado'),
        ('estado_borrado', 'Estado borrado'),
        ('lead_borrado', 'Lead borrado'),
        ('lead_agencia', 'Marcado como agencia (borrado)'),
    ]

    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs'
    )
    username = models.CharField(max_length=150, blank=True, default='')
    accion = models.CharField(max_length=30, choices=ACCION_CHOICES, db_index=True)
    lead_id = models.CharField(max_length=100, db_index=True)
    telefono = models.CharField(max_length=20, blank=True, default='')
    portal = models.CharField(max_length=50, blank=True, default='')
    titulo = models.TextField(blank=True, default='')
    estado_anterior = models.CharField(max_length=30, blank=True, default='')
    estado_nuevo = models.CharField(max_length=30, blank=True, default='')
    detalle = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'leads_audit_log'
        verbose_name = 'Registro de Auditoria'
        verbose_name_plural = 'Registros de Auditoria'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.username or 'sistema'}: {self.accion} {self.lead_id}"

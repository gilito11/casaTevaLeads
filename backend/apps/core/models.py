from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


# Zonas preestablecidas disponibles para todos los tenants
# Solo zonas de Lleida y Tarragona (Costa Daurada) - sincronizado con scrapers/milanuncios_scraper.py
ZONAS_PREESTABLECIDAS = {
    # === LLEIDA ===
    'lleida_ciudad': {'nombre': 'Lleida Ciudad', 'lat': 41.6175899, 'lon': 0.6200146, 'provincia_id': 25},
    'lleida_20km': {'nombre': 'Lleida (20 km)', 'lat': 41.6175899, 'lon': 0.6200146, 'provincia_id': 25},
    'lleida_30km': {'nombre': 'Lleida (30 km)', 'lat': 41.6175899, 'lon': 0.6200146, 'provincia_id': 25},
    'lleida_40km': {'nombre': 'Lleida (40 km)', 'lat': 41.6175899, 'lon': 0.6200146, 'provincia_id': 25},
    'lleida_50km': {'nombre': 'Lleida (50 km)', 'lat': 41.6175899, 'lon': 0.6200146, 'provincia_id': 25},
    'la_bordeta': {'nombre': 'La Bordeta, Lleida', 'lat': 41.6168393, 'lon': 0.6204561, 'provincia_id': 25},
    'balaguer': {'nombre': 'Balaguer', 'lat': 41.7907, 'lon': 0.8050, 'provincia_id': 25},
    'mollerussa': {'nombre': 'Mollerussa', 'lat': 41.6311, 'lon': 0.8947, 'provincia_id': 25},
    'tremp': {'nombre': 'Tremp', 'lat': 42.1667, 'lon': 0.8947, 'provincia_id': 25},
    'tarrega': {'nombre': 'Tàrrega', 'lat': 41.6472, 'lon': 1.1392, 'provincia_id': 25},

    # === TARRAGONA (con diferentes radios) ===
    'tarragona_ciudad': {'nombre': 'Tarragona Ciudad', 'lat': 41.1188827, 'lon': 1.2444909, 'provincia_id': 43},
    'tarragona_20km': {'nombre': 'Tarragona (20 km)', 'lat': 41.1188827, 'lon': 1.2444909, 'provincia_id': 43},
    'tarragona_30km': {'nombre': 'Tarragona (30 km)', 'lat': 41.1188827, 'lon': 1.2444909, 'provincia_id': 43},
    'tarragona_40km': {'nombre': 'Tarragona (40 km)', 'lat': 41.1188827, 'lon': 1.2444909, 'provincia_id': 43},
    'tarragona_50km': {'nombre': 'Tarragona (50 km)', 'lat': 41.1188827, 'lon': 1.2444909, 'provincia_id': 43},

    # === COSTA DAURADA - Pueblos costeros ===
    'salou': {'nombre': 'Salou', 'lat': 41.0764, 'lon': 1.1416, 'provincia_id': 43},
    'cambrils': {'nombre': 'Cambrils', 'lat': 41.0672, 'lon': 1.0597, 'provincia_id': 43},
    'reus': {'nombre': 'Reus', 'lat': 41.1548, 'lon': 1.1078, 'provincia_id': 43},
    'vendrell': {'nombre': 'El Vendrell', 'lat': 41.2186, 'lon': 1.5362, 'provincia_id': 43},
    'altafulla': {'nombre': 'Altafulla', 'lat': 41.1417, 'lon': 1.3778, 'provincia_id': 43},
    'torredembarra': {'nombre': 'Torredembarra', 'lat': 41.1456, 'lon': 1.3958, 'provincia_id': 43},
    'miami_platja': {'nombre': 'Miami Platja', 'lat': 41.0333, 'lon': 0.9833, 'provincia_id': 43},
    'hospitalet_infant': {'nombre': "L'Hospitalet de l'Infant", 'lat': 40.9917, 'lon': 0.9250, 'provincia_id': 43},
    'calafell': {'nombre': 'Calafell', 'lat': 41.2003, 'lon': 1.5681, 'provincia_id': 43},
    'coma_ruga': {'nombre': 'Coma-ruga', 'lat': 41.1833, 'lon': 1.5167, 'provincia_id': 43},

    # === COSTA DAURADA - Pueblos interiores ===
    'valls': {'nombre': 'Valls', 'lat': 41.2861, 'lon': 1.2497, 'provincia_id': 43},
    'montblanc': {'nombre': 'Montblanc', 'lat': 41.3772, 'lon': 1.1631, 'provincia_id': 43},
    'vila_seca': {'nombre': 'Vila-seca', 'lat': 41.1125, 'lon': 1.1458, 'provincia_id': 43},

    # === TERRES DE L'EBRE (sur de Tarragona) ===
    'tortosa': {'nombre': 'Tortosa', 'lat': 40.8125, 'lon': 0.5216, 'provincia_id': 43},
    'amposta': {'nombre': 'Amposta', 'lat': 40.7125, 'lon': 0.5811, 'provincia_id': 43},
    'deltebre': {'nombre': 'Deltebre', 'lat': 40.7208, 'lon': 0.7181, 'provincia_id': 43},
    'ametlla_mar': {'nombre': "L'Ametlla de Mar", 'lat': 40.8833, 'lon': 0.8000, 'provincia_id': 43},
    'sant_carles_rapita': {'nombre': 'Sant Carles de la Ràpita', 'lat': 40.6167, 'lon': 0.5917, 'provincia_id': 43},
}


class Tenant(models.Model):
    """Modelo para gestionar inquilinos/clientes del sistema"""
    tenant_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    email_contacto = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    config_scraping = models.JSONField(default=dict)
    activo = models.BooleanField(default=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)
    max_leads_mes = models.IntegerField(default=1000)

    class Meta:
        db_table = 'tenants'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)


class TenantUser(models.Model):
    """Modelo para relacionar usuarios con tenants y sus roles"""

    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('comercial', 'Comercial'),
        ('viewer', 'Visualizador'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_users')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_users')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)

    class Meta:
        db_table = 'tenant_users'
        unique_together = ['user', 'tenant']
        verbose_name = 'Usuario Tenant'
        verbose_name_plural = 'Usuarios Tenant'

    def __str__(self):
        return f"{self.user.username} - {self.tenant.nombre} ({self.rol})"


class ZonaGeografica(models.Model):
    """
    Zonas geográficas configuradas por cada tenant para scraping.
    Pueden ser zonas preestablecidas o personalizadas.
    """
    TIPO_CHOICES = [
        ('preestablecida', 'Zona Preestablecida'),
        ('personalizada', 'Zona Personalizada'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='zonas')
    nombre = models.CharField(max_length=255, help_text="Nombre descriptivo de la zona")
    slug = models.SlugField(max_length=100, help_text="Identificador único de la zona")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='preestablecida')

    # Coordenadas para búsqueda geolocalizada
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    radio_km = models.IntegerField(default=20, help_text="Radio de búsqueda en kilómetros")
    provincia_id = models.IntegerField(null=True, blank=True, help_text="ID de provincia para Milanuncios")

    # Configuración de scraping
    activa = models.BooleanField(default=True)
    precio_minimo = models.IntegerField(default=5000, help_text="Precio mínimo para filtrar alquileres")

    # Portales a scrapear en esta zona
    scrapear_milanuncios = models.BooleanField(default=True)
    scrapear_fotocasa = models.BooleanField(default=True)
    scrapear_habitaclia = models.BooleanField(default=True)
    scrapear_wallapop = models.BooleanField(default=False)  # Deshabilitado (bloqueado)
    scrapear_pisos = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zonas_geograficas'
        unique_together = ['tenant', 'slug']
        verbose_name = 'Zona Geográfica'
        verbose_name_plural = 'Zonas Geográficas'
        ordering = ['tenant', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.tenant.nombre})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    @classmethod
    def crear_desde_preestablecida(cls, tenant, zona_key):
        """Crea una zona a partir de una zona preestablecida."""
        if zona_key not in ZONAS_PREESTABLECIDAS:
            raise ValueError(f"Zona '{zona_key}' no encontrada en zonas preestablecidas")

        zona_data = ZONAS_PREESTABLECIDAS[zona_key]
        return cls.objects.create(
            tenant=tenant,
            nombre=zona_data['nombre'],
            slug=zona_key,
            tipo='preestablecida',
            latitud=zona_data['lat'],
            longitud=zona_data['lon'],
            provincia_id=zona_data.get('provincia_id'),
        )


class UsuarioBlacklist(models.Model):
    """
    Usuarios de portales detectados como inmobiliarias encubiertas.
    Si un usuario aparece en múltiples anuncios, se marca automáticamente.
    """
    PORTAL_CHOICES = [
        ('wallapop', 'Wallapop'),
        ('milanuncios', 'Milanuncios'),
        ('fotocasa', 'Fotocasa'),
    ]

    MOTIVO_CHOICES = [
        ('manual', 'Añadido manualmente'),
        ('automatico', 'Detectado automáticamente (múltiples anuncios)'),
        ('reportado', 'Reportado por usuario'),
    ]

    portal = models.CharField(max_length=50, choices=PORTAL_CHOICES)
    usuario_id = models.CharField(max_length=255, help_text="ID del usuario en el portal")
    nombre_usuario = models.CharField(max_length=255, help_text="Nombre mostrado en el portal")

    # Puede ser global (todos los tenants) o específico de un tenant
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='usuarios_blacklist',
        help_text="Si es null, aplica a todos los tenants"
    )

    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, default='manual')
    num_anuncios_detectados = models.IntegerField(default=1)
    notas = models.TextField(blank=True)

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios_blacklist'
        unique_together = ['portal', 'usuario_id', 'tenant']
        verbose_name = 'Usuario Blacklist'
        verbose_name_plural = 'Usuarios Blacklist'

    def __str__(self):
        scope = f"Tenant: {self.tenant.nombre}" if self.tenant else "Global"
        return f"{self.nombre_usuario} ({self.portal}) - {scope}"

    @classmethod
    def esta_en_blacklist(cls, portal, usuario_id, tenant=None):
        """Verifica si un usuario está en la blacklist."""
        # Buscar en blacklist global o del tenant específico
        return cls.objects.filter(
            portal=portal,
            usuario_id=usuario_id,
            activo=True
        ).filter(
            models.Q(tenant__isnull=True) | models.Q(tenant=tenant)
        ).exists()


class ScrapingJob(models.Model):
    """
    Modelo para trackear trabajos de scraping con feedback al usuario.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('running', 'Ejecutando'),
        ('completed', 'Completado'),
        ('error', 'Error'),
    ]

    PORTAL_CHOICES = [
        ('milanuncios', 'Milanuncios'),
        ('fotocasa', 'Fotocasa'),
        ('habitaclia', 'Habitaclia'),
        ('pisos', 'Pisos.com'),
        ('all', 'Todos los portales'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='scraping_jobs')
    portal = models.CharField(max_length=50, choices=PORTAL_CHOICES)
    zona = models.ForeignKey(
        'ZonaGeografica', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scraping_jobs'
    )
    zona_nombre = models.CharField(max_length=255, blank=True)  # Backup if zona deleted

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Resultados
    leads_encontrados = models.IntegerField(default=0)
    leads_guardados = models.IntegerField(default=0)
    leads_filtrados = models.IntegerField(default=0)
    leads_duplicados = models.IntegerField(default=0)

    # Errores
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scraping_jobs'
        verbose_name = 'Trabajo de Scraping'
        verbose_name_plural = 'Trabajos de Scraping'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.portal} - {self.zona_nombre or 'Todas'} ({self.get_status_display()})"

    @property
    def duration_seconds(self):
        """Duración del trabajo en segundos."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def mark_running(self):
        """Marca el trabajo como en ejecución."""
        from django.utils import timezone
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self, encontrados=0, guardados=0, filtrados=0, duplicados=0):
        """Marca el trabajo como completado con resultados."""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.leads_encontrados = encontrados
        self.leads_guardados = guardados
        self.leads_filtrados = filtrados
        self.leads_duplicados = duplicados
        self.save()

    def mark_error(self, message):
        """Marca el trabajo como error."""
        from django.utils import timezone
        self.status = 'error'
        self.completed_at = timezone.now()
        self.error_message = message
        self.save()


class ContadorUsuarioPortal(models.Model):
    """
    Contador de anuncios por usuario de portal.
    Cuando supera el umbral, se añade automáticamente a blacklist.
    """
    UMBRAL_BLACKLIST = 5  # Si un usuario tiene 5+ anuncios, es inmobiliaria

    portal = models.CharField(max_length=50)
    usuario_id = models.CharField(max_length=255)
    nombre_usuario = models.CharField(max_length=255)
    num_anuncios = models.IntegerField(default=0)
    ultimo_anuncio_url = models.TextField(blank=True)
    primera_deteccion = models.DateTimeField(auto_now_add=True)
    ultima_deteccion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contador_usuarios_portal'
        unique_together = ['portal', 'usuario_id']
        verbose_name = 'Contador Usuario Portal'
        verbose_name_plural = 'Contadores Usuarios Portal'

    def __str__(self):
        return f"{self.nombre_usuario} ({self.portal}): {self.num_anuncios} anuncios"

    def incrementar(self, url_anuncio=''):
        """Incrementa el contador y añade a blacklist si supera umbral."""
        self.num_anuncios += 1
        self.ultimo_anuncio_url = url_anuncio
        self.save()

        # Si supera el umbral, añadir a blacklist global
        if self.num_anuncios >= self.UMBRAL_BLACKLIST:
            UsuarioBlacklist.objects.get_or_create(
                portal=self.portal,
                usuario_id=self.usuario_id,
                tenant=None,  # Global
                defaults={
                    'nombre_usuario': self.nombre_usuario,
                    'motivo': 'automatico',
                    'num_anuncios_detectados': self.num_anuncios,
                    'notas': f'Detectado automáticamente con {self.num_anuncios} anuncios',
                }
            )
            return True  # Indica que fue añadido a blacklist

        return False

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


# Zonas organizadas por región para mejor UX
ZONAS_POR_REGION = {
    'lleida': {
        'nombre': 'Provincia de Lleida',
        'zonas': {
            'lleida': {'nombre': 'Lleida', 'lat': 41.6175899, 'lon': 0.6200146, 'provincia_id': 25, 'radio_default': 30},
            'balaguer': {'nombre': 'Balaguer', 'lat': 41.7907, 'lon': 0.8050, 'provincia_id': 25, 'radio_default': 15},
            'mollerussa': {'nombre': 'Mollerussa', 'lat': 41.6311, 'lon': 0.8947, 'provincia_id': 25, 'radio_default': 15},
            'tremp': {'nombre': 'Tremp', 'lat': 42.1667, 'lon': 0.8947, 'provincia_id': 25, 'radio_default': 20},
            'tarrega': {'nombre': 'Tàrrega', 'lat': 41.6472, 'lon': 1.1392, 'provincia_id': 25, 'radio_default': 15},
            # Pueblos alrededor de Lleida
            'alcoletge': {'nombre': 'Alcoletge', 'lat': 41.6417, 'lon': 0.6833, 'provincia_id': 25, 'radio_default': 5},
            'alamus': {'nombre': 'Alamús', 'lat': 41.5833, 'lon': 0.7833, 'provincia_id': 25, 'radio_default': 5},
            'artesa_lleida': {'nombre': 'Artesa de Lleida', 'lat': 41.5500, 'lon': 0.6833, 'provincia_id': 25, 'radio_default': 5},
            'puigverd_lleida': {'nombre': 'Puigverd de Lleida', 'lat': 41.5667, 'lon': 0.7500, 'provincia_id': 25, 'radio_default': 5},
            'albatarrec': {'nombre': 'Albatàrrec', 'lat': 41.5667, 'lon': 0.6167, 'provincia_id': 25, 'radio_default': 5},
            'alcarras': {'nombre': 'Alcarràs', 'lat': 41.5667, 'lon': 0.5167, 'provincia_id': 25, 'radio_default': 5},
            'sudanell': {'nombre': 'Sudanell', 'lat': 41.5500, 'lon': 0.5667, 'provincia_id': 25, 'radio_default': 5},
            'montoliu_lleida': {'nombre': 'Montoliu de Lleida', 'lat': 41.5500, 'lon': 0.6500, 'provincia_id': 25, 'radio_default': 5},
            'alpicat': {'nombre': 'Alpicat', 'lat': 41.6667, 'lon': 0.5500, 'provincia_id': 25, 'radio_default': 5},
            'torrefarrera': {'nombre': 'Torrefarrera', 'lat': 41.6667, 'lon': 0.5833, 'provincia_id': 25, 'radio_default': 5},
            'rossello': {'nombre': 'Rosselló', 'lat': 41.6667, 'lon': 0.7000, 'provincia_id': 25, 'radio_default': 5},
            'benavent_segria': {'nombre': 'Benavent de Segrià', 'lat': 41.6833, 'lon': 0.6667, 'provincia_id': 25, 'radio_default': 5},
            'vilanova_segria': {'nombre': 'Vilanova de Segrià', 'lat': 41.6833, 'lon': 0.6333, 'provincia_id': 25, 'radio_default': 5},
            'vilanova_bellpuig': {'nombre': 'Vilanova de Bellpuig', 'lat': 41.6167, 'lon': 0.9667, 'provincia_id': 25, 'radio_default': 5},
            'castelldans': {'nombre': 'Castelldans', 'lat': 41.5000, 'lon': 0.7500, 'provincia_id': 25, 'radio_default': 5},
            'torres_segre': {'nombre': 'Torres de Segre', 'lat': 41.5333, 'lon': 0.5000, 'provincia_id': 25, 'radio_default': 5},
        }
    },
    'tarragona': {
        'nombre': 'Tarragona Capital',
        'zonas': {
            'tarragona': {'nombre': 'Tarragona', 'lat': 41.1188827, 'lon': 1.2444909, 'provincia_id': 43, 'radio_default': 30},
            'reus': {'nombre': 'Reus', 'lat': 41.1548, 'lon': 1.1078, 'provincia_id': 43, 'radio_default': 15},
        }
    },
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'zonas': {
            'salou': {'nombre': 'Salou', 'lat': 41.0764, 'lon': 1.1416, 'provincia_id': 43, 'radio_default': 10},
            'cambrils': {'nombre': 'Cambrils', 'lat': 41.0672, 'lon': 1.0597, 'provincia_id': 43, 'radio_default': 10},
            'miami_platja': {'nombre': 'Miami Platja', 'lat': 41.0333, 'lon': 0.9833, 'provincia_id': 43, 'radio_default': 10},
            'hospitalet_infant': {'nombre': "L'Hospitalet de l'Infant", 'lat': 40.9917, 'lon': 0.9250, 'provincia_id': 43, 'radio_default': 10},
            'calafell': {'nombre': 'Calafell', 'lat': 41.2003, 'lon': 1.5681, 'provincia_id': 43, 'radio_default': 10},
            'vendrell': {'nombre': 'El Vendrell', 'lat': 41.2186, 'lon': 1.5362, 'provincia_id': 43, 'radio_default': 10},
            'altafulla': {'nombre': 'Altafulla', 'lat': 41.1417, 'lon': 1.3778, 'provincia_id': 43, 'radio_default': 10},
            'torredembarra': {'nombre': 'Torredembarra', 'lat': 41.1456, 'lon': 1.3958, 'provincia_id': 43, 'radio_default': 10},
            'coma_ruga': {'nombre': 'Coma-ruga', 'lat': 41.1833, 'lon': 1.5167, 'provincia_id': 43, 'radio_default': 10},
            'vila_seca': {'nombre': 'Vila-seca', 'lat': 41.1125, 'lon': 1.1458, 'provincia_id': 43, 'radio_default': 10},
            # Zonas adicionales Costa Daurada
            'la_pineda': {'nombre': 'La Pineda', 'lat': 41.0833, 'lon': 1.1667, 'provincia_id': 43, 'radio_default': 5},
            'vilafortuny': {'nombre': 'Vilafortuny', 'lat': 41.0500, 'lon': 1.0333, 'provincia_id': 43, 'radio_default': 5},
            'montroig_camp': {'nombre': 'Mont-roig del Camp', 'lat': 41.0833, 'lon': 0.9500, 'provincia_id': 43, 'radio_default': 10},
            'calafat': {'nombre': 'Calafat', 'lat': 40.9000, 'lon': 0.7833, 'provincia_id': 43, 'radio_default': 5},
        }
    },
    'interior_tarragona': {
        'nombre': 'Interior Tarragona',
        'zonas': {
            'valls': {'nombre': 'Valls', 'lat': 41.2861, 'lon': 1.2497, 'provincia_id': 43, 'radio_default': 15},
            'montblanc': {'nombre': 'Montblanc', 'lat': 41.3772, 'lon': 1.1631, 'provincia_id': 43, 'radio_default': 15},
        }
    },
    'terres_ebre': {
        'nombre': "Terres de l'Ebre",
        'zonas': {
            'tortosa': {'nombre': 'Tortosa', 'lat': 40.8125, 'lon': 0.5216, 'provincia_id': 43, 'radio_default': 20},
            'amposta': {'nombre': 'Amposta', 'lat': 40.7125, 'lon': 0.5811, 'provincia_id': 43, 'radio_default': 15},
            'deltebre': {'nombre': 'Deltebre', 'lat': 40.7208, 'lon': 0.7181, 'provincia_id': 43, 'radio_default': 10},
            'ametlla_mar': {'nombre': "L'Ametlla de Mar", 'lat': 40.8833, 'lon': 0.8000, 'provincia_id': 43, 'radio_default': 10},
            'sant_carles_rapita': {'nombre': 'Sant Carles de la Ràpita', 'lat': 40.6167, 'lon': 0.5917, 'provincia_id': 43, 'radio_default': 10},
        }
    },
    # Madrid (Tenant 2: Find&Look)
    'madrid_norte': {
        'nombre': 'Madrid Norte',
        'zonas': {
            'chamartin': {'nombre': 'Chamartín', 'lat': 40.4597, 'lon': -3.6772, 'provincia_id': 28, 'radio_default': 5},
            'hortaleza': {'nombre': 'Hortaleza', 'lat': 40.4697, 'lon': -3.6407, 'provincia_id': 28, 'radio_default': 5},
        }
    },
}

# Dict plano para compatibilidad con código existente
ZONAS_PREESTABLECIDAS = {}
for region_key, region_data in ZONAS_POR_REGION.items():
    for zona_key, zona_data in region_data['zonas'].items():
        ZONAS_PREESTABLECIDAS[zona_key] = {
            'nombre': zona_data['nombre'],
            'lat': zona_data['lat'],
            'lon': zona_data['lon'],
            'provincia_id': zona_data['provincia_id'],
            'radio_default': zona_data.get('radio_default', 20),
            'region': region_key,
            'region_nombre': region_data['nombre'],
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

    # Datos del comercial para contacto automático de leads
    comercial_nombre = models.CharField(
        max_length=100, blank=True,
        help_text="Nombre que aparece en formularios de contacto"
    )
    comercial_email = models.EmailField(
        blank=True,
        help_text="Email para recibir respuestas de leads"
    )
    comercial_telefono = models.CharField(
        max_length=20, blank=True,
        help_text="Teléfono de contacto en formularios"
    )

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

    # Datos de contacto del comercial (para formularios de contacto automático)
    comercial_nombre = models.CharField(
        max_length=100, blank=True,
        help_text="Nombre en formularios (si vacío, usa user.first_name)"
    )
    comercial_email = models.EmailField(
        blank=True,
        help_text="Email para recibir respuestas (si vacío, usa user.email)"
    )
    comercial_telefono = models.CharField(
        max_length=20, blank=True,
        help_text="Teléfono de contacto en formularios"
    )

    class Meta:
        db_table = 'tenant_users'
        unique_together = ['user', 'tenant']
        verbose_name = 'Usuario Tenant'
        verbose_name_plural = 'Usuarios Tenant'

    def __str__(self):
        return f"{self.user.username} - {self.tenant.nombre} ({self.rol})"

    def get_contact_name(self):
        """Nombre para formularios de contacto."""
        return self.comercial_nombre or self.user.get_full_name() or self.user.username

    def get_contact_email(self):
        """Email para formularios de contacto."""
        return self.comercial_email or self.user.email

    def get_contact_phone(self):
        """Teléfono para formularios de contacto."""
        return self.comercial_telefono


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
    scrapear_idealista = models.BooleanField(default=True)

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
            radio_km=zona_data.get('radio_default', 20),
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
        ('idealista', 'Idealista'),
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

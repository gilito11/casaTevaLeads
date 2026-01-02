from django.db import models
from django.contrib.auth.models import User
from core.models import Tenant


class Lead(models.Model):
    """
    Modelo para gestionar leads inmobiliarios - Vista desde marts.dim_leads
    Las columnas coinciden con la VIEW existente en PostgreSQL.
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

    # Columnas que existen en la VIEW marts.dim_leads
    lead_id = models.CharField(max_length=100, primary_key=True)
    tenant_id = models.IntegerField()
    telefono_norm = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    nombre = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.TextField(null=True, blank=True)
    zona_geografica = models.CharField(max_length=100, null=True, blank=True)
    codigo_postal = models.CharField(max_length=10, blank=True, null=True)
    tipo_inmueble = models.CharField(max_length=50, blank=True, null=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    habitaciones = models.IntegerField(null=True, blank=True)
    metros = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)
    fotos = models.JSONField(default=list, null=True, blank=True)
    portal = models.CharField(max_length=50, null=True, blank=True)
    url_anuncio = models.TextField(null=True, blank=True)
    data_lake_reference = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='NUEVO')
    numero_intentos = models.IntegerField(default=0)
    fecha_scraping = models.DateTimeField(null=True, blank=True)
    fecha_primer_contacto = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_contacto = models.DateTimeField(null=True, blank=True)
    fecha_cambio_estado = models.DateTimeField(null=True, blank=True)
    asignado_a_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    anuncio_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'public_marts"."dim_leads'
        managed = False
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-fecha_scraping']

    def __str__(self):
        return f"{self.telefono_norm} - {self.direccion} ({self.estado})"

    # Campos adicionales como properties (para datos que vendrán cuando se actualice dbt)
    @property
    def titulo(self):
        """El título será extraído de descripción o URL por ahora"""
        return self.descripcion[:100] if self.descripcion else ''

    @property
    def banos(self):
        """Baños no está en la VIEW actual"""
        return None

    @property
    def certificado_energetico(self):
        """Certificado energético no está en la VIEW actual"""
        return ''

    @property
    def fecha_publicacion(self):
        """Fecha publicación no está en la VIEW actual"""
        return None


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


class AnuncioBlacklist(models.Model):
    """
    Modelo para almacenar anuncios que no deben volver a scrapearse.
    Cuando un usuario elimina un lead con la opcion "no volver a scrapear",
    se guarda aqui para que los scrapers lo ignoren en futuras ejecuciones.
    """
    PORTAL_CHOICES = [
        ('milanuncios', 'Milanuncios'),
        ('wallapop', 'Wallapop'),
        ('fotocasa', 'Fotocasa'),
        ('pisos', 'Pisos.com'),
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

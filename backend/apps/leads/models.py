from django.db import models
from django.contrib.auth.models import User
from core.models import Tenant


class Lead(models.Model):
    """Modelo para gestionar leads inmobiliarios - Vista desde marts.dim_leads"""

    ESTADO_CHOICES = [
        ('NUEVO', 'Nuevo'),
        ('EN_PROCESO', 'En proceso'),
        ('CONTACTADO_SIN_RESPUESTA', 'Contactado sin respuesta'),
        ('INTERESADO', 'Interesado'),
        ('NO_INTERESADO', 'No interesado'),
        ('NO_CONTACTAR', 'No contactar'),
        ('CLIENTE', 'Cliente'),
        ('YA_VENDIDO', 'Ya vendido'),
    ]

    lead_id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='leads')
    telefono_norm = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    nombre = models.CharField(max_length=255, blank=True)
    direccion = models.TextField()
    zona_geografica = models.CharField(max_length=100)
    codigo_postal = models.CharField(max_length=10, blank=True)
    tipo_inmueble = models.CharField(max_length=50, blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    habitaciones = models.IntegerField(null=True, blank=True)
    metros = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(blank=True)
    fotos = models.JSONField(default=list)
    portal = models.CharField(max_length=50)
    url_anuncio = models.TextField()
    data_lake_reference = models.TextField(blank=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='NUEVO')
    asignado_a = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_asignados'
    )
    numero_intentos = models.IntegerField(default=0)
    fecha_scraping = models.DateTimeField()
    fecha_primer_contacto = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_contacto = models.DateTimeField(null=True, blank=True)
    fecha_cambio_estado = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marts"."dim_leads'
        managed = False
        unique_together = ['tenant', 'telefono_norm']
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-fecha_scraping']

    def __str__(self):
        return f"{self.telefono_norm} - {self.direccion} ({self.estado})"


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

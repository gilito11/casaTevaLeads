from django.db import models
from django.contrib.auth.models import User
from core.models import Tenant


class ACMReport(models.Model):
    """
    Informe de Analisis Comparativo de Mercado para un lead.
    Almacena la valoracion calculada y los comparables usados.
    """
    METODOLOGIA_CHOICES = [
        ('comparables', 'Comparables de mercado'),
        ('precio_m2', 'Precio medio por m2'),
        ('mixta', 'Metodologia mixta'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='acm_reports')
    lead_id = models.CharField(max_length=100, db_index=True)

    # Valoracion calculada
    valoracion_min = models.DecimalField(max_digits=12, decimal_places=2)
    valoracion_max = models.DecimalField(max_digits=12, decimal_places=2)
    valoracion_media = models.DecimalField(max_digits=12, decimal_places=2)

    # Precio por m2
    precio_m2_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_m2_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_m2_medio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Metadata del lead analizado
    zona = models.CharField(max_length=100)
    tipo_propiedad = models.CharField(max_length=50, blank=True, null=True)
    superficie_m2 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    habitaciones = models.IntegerField(null=True, blank=True)
    precio_anuncio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Comparables usados (JSON array)
    comparables = models.JSONField(default=list, help_text="Lista de leads comparables usados")
    num_comparables = models.IntegerField(default=0)

    # Ajustes aplicados
    ajustes = models.JSONField(default=dict, help_text="Ajustes aplicados al calculo")

    # Metodologia
    metodologia = models.CharField(max_length=20, choices=METODOLOGIA_CHOICES, default='comparables')

    # Confianza del calculo (0-100)
    confianza = models.IntegerField(default=0, help_text="Nivel de confianza del calculo (0-100)")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acm_reports_created'
    )

    class Meta:
        db_table = 'acm_report'
        verbose_name = 'Informe ACM'
        verbose_name_plural = 'Informes ACM'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'lead_id']),
            models.Index(fields=['zona', 'tipo_propiedad']),
        ]

    def __str__(self):
        return f"ACM {self.lead_id} - {self.valoracion_media:,.0f} EUR"

    @property
    def rango_valoracion(self):
        """Retorna el rango de valoracion formateado."""
        return f"{self.valoracion_min:,.0f} - {self.valoracion_max:,.0f} EUR"

    @property
    def diferencia_precio(self):
        """Diferencia entre precio anuncio y valoracion media."""
        if self.precio_anuncio and self.valoracion_media:
            return float(self.precio_anuncio - self.valoracion_media)
        return None

    @property
    def diferencia_pct(self):
        """Diferencia porcentual entre precio anuncio y valoracion media."""
        if self.precio_anuncio and self.valoracion_media and self.valoracion_media > 0:
            return float((self.precio_anuncio - self.valoracion_media) / self.valoracion_media * 100)
        return None

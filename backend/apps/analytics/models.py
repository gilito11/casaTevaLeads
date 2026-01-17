from django.db import models
from core.models import Tenant


class ScrapeLog(models.Model):
    """Log de cada ejecución de scraping por zona y portal."""

    ESTADO_CHOICES = [
        ('OK', 'Exitoso'),
        ('ERROR', 'Error'),
        ('SKIP', 'Omitido'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='scrape_logs')
    zona_slug = models.CharField(max_length=100)
    zona_nombre = models.CharField(max_length=255)
    portal = models.CharField(max_length=50)

    # Resultados
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='OK')
    listings_encontrados = models.IntegerField(default=0)
    listings_nuevos = models.IntegerField(default=0)
    error_mensaje = models.TextField(blank=True, null=True)

    # Timestamps
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(auto_now_add=True)
    duracion_segundos = models.IntegerField(default=0)

    # Metadata
    job_run_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'analytics_scrape_log'
        ordering = ['-finished_at']
        indexes = [
            models.Index(fields=['tenant', '-finished_at']),
            models.Index(fields=['zona_slug', 'portal']),
            models.Index(fields=['-finished_at']),
        ]

    def __str__(self):
        return f"{self.zona_nombre} ({self.portal}) - {self.finished_at.strftime('%Y-%m-%d %H:%M')}"

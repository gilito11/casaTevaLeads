from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


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

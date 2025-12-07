# Generated manually for casa_teva project.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('tenant_id', models.AutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('email_contacto', models.EmailField(max_length=254)),
                ('telefono', models.CharField(blank=True, max_length=20)),
                ('config_scraping', models.JSONField(default=dict)),
                ('activo', models.BooleanField(default=True)),
                ('fecha_alta', models.DateTimeField(auto_now_add=True)),
                ('max_leads_mes', models.IntegerField(default=1000)),
            ],
            options={
                'verbose_name': 'Tenant',
                'verbose_name_plural': 'Tenants',
                'db_table': 'tenants',
            },
        ),
        migrations.CreateModel(
            name='TenantUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rol', models.CharField(choices=[('admin', 'Administrador'), ('comercial', 'Comercial'), ('viewer', 'Visualizador')], max_length=20)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tenant_users', to='core.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tenant_users', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Usuario Tenant',
                'verbose_name_plural': 'Usuarios Tenant',
                'db_table': 'tenant_users',
                'unique_together': {('user', 'tenant')},
            },
        ),
    ]

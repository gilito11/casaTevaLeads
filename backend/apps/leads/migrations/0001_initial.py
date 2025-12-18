# Generated manually for casa_teva project.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Lead model first (unmanaged - maps to marts.dim_leads view)
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('lead_id', models.AutoField(primary_key=True, serialize=False)),
                ('telefono_norm', models.CharField(max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('nombre', models.CharField(blank=True, max_length=255)),
                ('direccion', models.TextField()),
                ('zona_geografica', models.CharField(max_length=100)),
                ('codigo_postal', models.CharField(blank=True, max_length=10)),
                ('tipo_inmueble', models.CharField(blank=True, max_length=50)),
                ('precio', models.DecimalField(decimal_places=2, max_digits=12)),
                ('habitaciones', models.IntegerField(blank=True, null=True)),
                ('metros', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('descripcion', models.TextField(blank=True)),
                ('fotos', models.JSONField(default=list)),
                ('portal', models.CharField(max_length=50)),
                ('url_anuncio', models.TextField()),
                ('data_lake_reference', models.TextField(blank=True)),
                ('estado', models.CharField(choices=[('NUEVO', 'Nuevo'), ('EN_PROCESO', 'En proceso'), ('CONTACTADO_SIN_RESPUESTA', 'Contactado sin respuesta'), ('INTERESADO', 'Interesado'), ('NO_INTERESADO', 'No interesado'), ('EN_ESPERA', 'En espera'), ('NO_CONTACTAR', 'No contactar'), ('CLIENTE', 'Cliente'), ('YA_VENDIDO', 'Ya vendido')], default='NUEVO', max_length=30)),
                ('numero_intentos', models.IntegerField(default=0)),
                ('fecha_scraping', models.DateTimeField()),
                ('fecha_primer_contacto', models.DateTimeField(blank=True, null=True)),
                ('fecha_ultimo_contacto', models.DateTimeField(blank=True, null=True)),
                ('fecha_cambio_estado', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leads', to='core.tenant')),
                ('asignado_a', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads_asignados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Lead',
                'verbose_name_plural': 'Leads',
                'db_table': 'marts"."dim_leads',
                'ordering': ['-fecha_scraping'],
                'managed': False,
            },
        ),
        # Nota model with ForeignKey to Lead
        migrations.CreateModel(
            name='Nota',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('autor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notas', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notas', to='leads.lead')),
            ],
            options={
                'verbose_name': 'Nota',
                'verbose_name_plural': 'Notas',
                'ordering': ['-created_at'],
            },
        ),
    ]

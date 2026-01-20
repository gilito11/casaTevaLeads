from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ACMReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lead_id', models.CharField(db_index=True, max_length=100)),
                ('valoracion_min', models.DecimalField(decimal_places=2, max_digits=12)),
                ('valoracion_max', models.DecimalField(decimal_places=2, max_digits=12)),
                ('valoracion_media', models.DecimalField(decimal_places=2, max_digits=12)),
                ('precio_m2_min', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('precio_m2_max', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('precio_m2_medio', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('zona', models.CharField(max_length=100)),
                ('tipo_propiedad', models.CharField(blank=True, max_length=50, null=True)),
                ('superficie_m2', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('habitaciones', models.IntegerField(blank=True, null=True)),
                ('precio_anuncio', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('comparables', models.JSONField(default=list, help_text='Lista de leads comparables usados')),
                ('num_comparables', models.IntegerField(default=0)),
                ('ajustes', models.JSONField(default=dict, help_text='Ajustes aplicados al calculo')),
                ('metodologia', models.CharField(choices=[('comparables', 'Comparables de mercado'), ('precio_m2', 'Precio medio por m2'), ('mixta', 'Metodologia mixta')], default='comparables', max_length=20)),
                ('confianza', models.IntegerField(default=0, help_text='Nivel de confianza del calculo (0-100)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acm_reports_created', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acm_reports', to='core.tenant')),
            ],
            options={
                'verbose_name': 'Informe ACM',
                'verbose_name_plural': 'Informes ACM',
                'db_table': 'acm_report',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='acmreport',
            index=models.Index(fields=['tenant', 'lead_id'], name='acm_report_tenant__bc0f3a_idx'),
        ),
        migrations.AddIndex(
            model_name='acmreport',
            index=models.Index(fields=['zona', 'tipo_propiedad'], name='acm_report_zona_2b1a87_idx'),
        ),
    ]

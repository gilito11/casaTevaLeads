import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_remove_pisos_wallapop_add_idealista'),
        ('leads', '0005_add_contact_interaction_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactQueue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lead_id', models.CharField(max_length=100)),
                ('portal', models.CharField(choices=[('fotocasa', 'Fotocasa'), ('habitaclia', 'Habitaclia')], max_length=50)),
                ('listing_url', models.TextField()),
                ('titulo', models.CharField(blank=True, max_length=500, null=True)),
                ('mensaje', models.TextField(help_text='Mensaje a enviar al vendedor')),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('EN_PROCESO', 'En proceso'), ('COMPLETADO', 'Completado'), ('FALLIDO', 'Fallido'), ('CANCELADO', 'Cancelado')], default='PENDIENTE', max_length=20)),
                ('prioridad', models.IntegerField(default=0, help_text='Mayor numero = mayor prioridad')),
                ('telefono_extraido', models.CharField(blank=True, max_length=20, null=True)),
                ('mensaje_enviado', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contact_queue', to='core.tenant')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contacts_encolados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Cola de Contacto',
                'verbose_name_plural': 'Cola de Contactos',
                'db_table': 'leads_contact_queue',
                'ordering': ['-prioridad', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='PortalSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('portal', models.CharField(choices=[('fotocasa', 'Fotocasa'), ('habitaclia', 'Habitaclia')], max_length=50)),
                ('email', models.EmailField(help_text='Email de la cuenta del portal', max_length=254)),
                ('cookies', models.JSONField(help_text='Cookies de sesion (JSON)')),
                ('is_valid', models.BooleanField(default=True)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='Cuando expira la sesion', null=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='portal_sessions', to='core.tenant')),
            ],
            options={
                'verbose_name': 'Sesion de Portal',
                'verbose_name_plural': 'Sesiones de Portales',
                'db_table': 'leads_portal_session',
                'unique_together': {('tenant', 'portal')},
            },
        ),
        migrations.AddIndex(
            model_name='contactqueue',
            index=models.Index(fields=['estado', 'portal'], name='leads_conta_estado_a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='contactqueue',
            index=models.Index(fields=['tenant', 'estado'], name='leads_conta_tenant__d4e5f6_idx'),
        ),
    ]

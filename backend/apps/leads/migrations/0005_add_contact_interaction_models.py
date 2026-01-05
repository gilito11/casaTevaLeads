import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_remove_pisos_wallapop_add_idealista'),
        ('leads', '0004_add_anuncio_blacklist'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(db_index=True, max_length=20)),
                ('telefono2', models.CharField(blank=True, max_length=20, null=True)),
                ('nombre', models.CharField(blank=True, max_length=255, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('notas', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contacts', to='core.tenant')),
            ],
            options={
                'verbose_name': 'Contacto',
                'verbose_name_plural': 'Contactos',
                'db_table': 'leads_contact',
                'ordering': ['-updated_at'],
                'unique_together': {('tenant', 'telefono')},
            },
        ),
        migrations.CreateModel(
            name='Interaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('llamada', 'Llamada'), ('email', 'Email'), ('nota', 'Nota'), ('visita', 'Visita'), ('whatsapp', 'WhatsApp'), ('otro', 'Otro')], default='nota', max_length=20)),
                ('descripcion', models.TextField()),
                ('fecha', models.DateTimeField(default=None)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interactions', to='leads.contact')),
                ('usuario', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='interactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Interaccion',
                'verbose_name_plural': 'Interacciones',
                'db_table': 'leads_interaction',
                'ordering': ['-fecha', '-created_at'],
            },
        ),
    ]

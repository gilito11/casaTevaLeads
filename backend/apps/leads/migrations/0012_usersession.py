from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('leads', '0011_auditlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(blank=True, default='', max_length=150)),
                ('started_at', models.DateTimeField(db_index=True)),
                ('last_seen', models.DateTimeField(db_index=True)),
                ('request_count', models.IntegerField(default=1)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Sesion de Usuario',
                'verbose_name_plural': 'Sesiones de Usuario',
                'db_table': 'leads_user_session',
                'ordering': ['-last_seen'],
            },
        ),
    ]

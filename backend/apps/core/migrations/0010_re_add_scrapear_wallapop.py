# Re-add scrapear_wallapop to ZonaGeografica (removed in 0006, Wallapop back as portal)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_add_comercial_fields_to_tenantuser'),
    ]

    operations = [
        migrations.AddField(
            model_name='zonageografica',
            name='scrapear_wallapop',
            field=models.BooleanField(default=True),
        ),
    ]

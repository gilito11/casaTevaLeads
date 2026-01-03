from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_scrapear_habitaclia'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='zonageografica',
            name='scrapear_pisos',
        ),
        migrations.RemoveField(
            model_name='zonageografica',
            name='scrapear_wallapop',
        ),
        migrations.AddField(
            model_name='zonageografica',
            name='scrapear_idealista',
            field=models.BooleanField(default=True),
        ),
    ]

# Generated manually for Habitaclia scraper support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_scraping_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='zonageografica',
            name='scrapear_habitaclia',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='zonageografica',
            name='scrapear_wallapop',
            field=models.BooleanField(default=False),
        ),
    ]

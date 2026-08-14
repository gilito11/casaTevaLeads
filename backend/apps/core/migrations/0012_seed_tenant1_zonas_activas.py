"""Siembra zonas_geograficas del tenant 1 con la keep-list de dim_leads.

Desde este cambio, la tabla es la fuente de verdad de zonas activas: dbt
(dim_leads) filtra contra ella y el cron de scrape-neon.yml lee de ella la
lista de zonas por portal. slug = clave de zona que entienden los scrapers.

Zonas de costa: activa=True (se ingieren en dim_leads) pero solo milanuncios
las scrapea a diario (cubre la provincia entera); resto de portales quedan
fuera del cron por coste, igual que antes de este cambio.
"""
from decimal import Decimal

from django.db import migrations

ZONAS_SEED = [
    # (slug, nombre, lat, lng, radio_km, cron_diario_todos_los_portales)
    ('lleida', 'Lleida', '41.6176', '0.62', 12, True),
    ('alpicat', 'Alpicat', '41.668', '0.523', 6, True),
    ('alcarras', 'Alcarràs', '41.568', '0.523', 6, True),
    ('torrefarrera', 'Torrefarrera', '41.67', '0.587', 6, True),
    ('bell_lloc', "Bell-lloc d'Urgell", '41.632', '0.774', 6, True),
    ('termens', 'Térmens', '41.715', '0.756', 6, True),
    ('juneda', 'Juneda', '41.547', '0.823', 6, True),
    ('almacelles', 'Almacelles', '41.731', '0.438', 6, True),
    ('almenar', 'Almenar', '41.795', '0.564', 6, True),
    ('mollerussa', 'Mollerussa', '41.63', '0.895', 8, True),
    ('mollerussa_rural', 'Mollerussa Rural', '41.651', '0.88', 6, True),
    ('albatarrec', 'Albatàrrec', '41.573', '0.607', 3, True),
    ('torre_serona', 'Torre-serona', '41.664', '0.598', 3, True),
    ('montoliu_de_lleida', 'Montoliu de Lleida', '41.57', '0.633', 3, True),
    ('alcoletge', 'Alcoletge', '41.646', '0.694', 3, True),
    ('sudanell', 'Sudanell', '41.559', '0.573', 3, True),
    ('benavent_de_segria', 'Benavent de Segrià', '41.712', '0.635', 3, True),
    ('rossello', 'Rosselló', '41.69', '0.607', 3, True),
    ('artesa_de_lleida', 'Artesa de Lleida', '41.552', '0.701', 3, True),
    ('corbins', 'Corbins', '41.68', '0.7', 3, True),
    ('vilanova_de_segria', 'Vilanova de Segrià', '41.723', '0.628', 3, True),
    ('alfes', 'Alfés', '41.549', '0.618', 3, True),
    ('sunyer', 'Sunyer', '41.542', '0.596', 3, True),
    ('vilanova_de_la_barca', 'Vilanova de la Barca', '41.687', '0.723', 3, True),
    ('puigverd_de_lleida', 'Puigverd de Lleida', '41.538', '0.693', 3, True),
    ('torres_de_segre', 'Torres de Segre', '41.532', '0.512', 3, True),
    ('alguaire', 'Alguaire', '41.735', '0.585', 3, True),
    ('aspa', 'Aspa', '41.532', '0.672', 3, True),
    ('soses', 'Soses', '41.536', '0.518', 3, True),
    ('menarguens', 'Menàrguens', '41.734', '0.737', 3, True),
    ('bellvis', 'Bellvís', '41.67', '0.818', 3, True),
    ('sidamon', 'Sidamon', '41.632', '0.843', 3, True),
    ('sarroca_de_lleida', 'Sarroca de Lleida', '41.443', '0.554', 4, True),
    ('aitona', 'Aitona', '41.492', '0.461', 4, True),
    ('fondarella', 'Fondarella', '41.634', '0.87', 3, True),
    ('torrebesses', 'Torrebesses', '41.428', '0.598', 4, True),
    ('miralcamp', 'Miralcamp', '41.607', '0.868', 3, True),
    ('vallfogona_balaguer', 'Vallfogona de Balaguer', '41.771', '0.821', 3, True),
    ('gimenells', 'Gimenells', '41.654', '0.39', 4, True),
    ('tarragona', 'Tarragona', '41.1189', '1.2445', 12, False),
    ('bonavista', 'Bonavista', '41.1064', '1.1954', 3, False),
    ('la_canonja', 'La Canonja', '41.122', '1.196', 3, False),
    ('reus', 'Reus', '41.1561', '1.1069', 8, False),
    ('salou', 'Salou', '41.0772', '1.1417', 6, False),
    ('cambrils', 'Cambrils', '41.0658', '1.0556', 6, False),
    ('la_pineda', 'La Pineda', '41.084', '1.186', 4, False),
    ('vila_seca', 'Vila-seca', '41.111', '1.1456', 5, False),
    ('miami_platja', 'Miami Platja', '40.993', '0.987', 6, False),
    ('mont_roig_del_camp', 'Mont-roig del Camp', '41.087', '0.958', 5, False),
    ('vinyols_i_els_arcs', 'Vinyols i els Arcs', '41.112', '1.041', 3, False),
    ('montbrio_del_camp', 'Montbrió del Camp', '41.121', '1.001', 3, False),
    ('riudoms', 'Riudoms', '41.137', '1.051', 4, False),
    ('constanti', 'Constantí', '41.153', '1.213', 4, False),
]

TENANT_ID = 1


def seed(apps, schema_editor):
    Tenant = apps.get_model('core', 'Tenant')
    ZonaGeografica = apps.get_model('core', 'ZonaGeografica')
    if not Tenant.objects.filter(tenant_id=TENANT_ID).exists():
        return
    for slug, nombre, lat, lng, radio, cron_full in ZONAS_SEED:
        ZonaGeografica.objects.update_or_create(
            tenant_id=TENANT_ID, slug=slug,
            defaults=dict(
                nombre=nombre,
                tipo='preestablecida',
                latitud=Decimal(lat),
                longitud=Decimal(lng),
                radio_km=radio,
                activa=True,
                scrapear_milanuncios=True,
                scrapear_fotocasa=cron_full,
                scrapear_habitaclia=cron_full,
                scrapear_idealista=cron_full,
                scrapear_wallapop=cron_full,
            ),
        )


def unseed(apps, schema_editor):
    ZonaGeografica = apps.get_model('core', 'ZonaGeografica')
    slugs = [z[0] for z in ZONAS_SEED]
    ZonaGeografica.objects.filter(tenant_id=TENANT_ID, slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_alter_scrapingjob_portal'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]

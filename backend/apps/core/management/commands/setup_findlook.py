"""
Management command to setup Find&Look tenant with Madrid zones,
AutoContactConfig, and MessageTemplate.
"""
import os

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Tenant, TenantUser, ZonaGeografica


# Madrid zones - confirmed for scraping
MADRID_ZONES = {
    'chamartin': {
        'nombre': 'Chamartín',
        'lat': 40.4597,
        'lon': -3.6772,
        'provincia_id': 28,
        'radio_default': 5,
    },
    'hortaleza': {
        'nombre': 'Hortaleza',
        'lat': 40.4697,
        'lon': -3.6407,
        'provincia_id': 28,
        'radio_default': 5,
    },
}


class Command(BaseCommand):
    help = 'Setup Find&Look tenant with Madrid zones, auto-contact config, and message template'

    def handle(self, *args, **options):
        # 1. Create tenant
        tenant, created = Tenant.objects.get_or_create(
            slug='findlook',
            defaults={
                'nombre': 'Find&Look',
                'email_contacto': 'contacto@findlook.es',
                'telefono': '',
                'config_scraping': {
                    'zones': ['chamartin', 'hortaleza'],
                    'portals': ['fotocasa', 'idealista', 'milanuncios', 'habitaclia'],
                },
                'activo': True,
                'max_leads_mes': 500,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created tenant: {tenant.nombre} (id={tenant.tenant_id})'))
        else:
            self.stdout.write(f'Tenant already exists: {tenant.nombre} (id={tenant.tenant_id})')

        # 2. Create user Mariano
        password = os.environ.get('FINDLOOK_PASSWORD', 'changeme')
        user, user_created = User.objects.get_or_create(
            username='mariano',
            defaults={
                'email': 'mariano@findlook.es',
                'first_name': 'Mariano',
                'last_name': 'García',
                'is_active': True,
            }
        )

        if user_created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created user: mariano'))
        else:
            self.stdout.write(f'User already exists: mariano')

        # 3. Link user to tenant as admin
        tenant_user, tu_created = TenantUser.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={'rol': 'admin'}
        )
        if tu_created:
            self.stdout.write(self.style.SUCCESS(f'Linked mariano to Find&Look as admin'))

        # 4. Create zones
        zones_created = 0
        for slug, zone_data in MADRID_ZONES.items():
            zona, z_created = ZonaGeografica.objects.get_or_create(
                tenant=tenant,
                slug=slug,
                defaults={
                    'nombre': zone_data['nombre'],
                    'tipo': 'personalizada',
                    'latitud': zone_data['lat'],
                    'longitud': zone_data['lon'],
                    'radio_km': zone_data['radio_default'],
                    'provincia_id': zone_data['provincia_id'],
                    'activa': True,
                    'precio_minimo': 50000,
                    'scrapear_milanuncios': True,
                    'scrapear_fotocasa': True,
                    'scrapear_habitaclia': True,
                    'scrapear_idealista': True,
                }
            )
            if z_created:
                zones_created += 1
                self.stdout.write(f'  Created zone: {zone_data["nombre"]}')

        # 5. Create AutoContactConfig
        from leads.models import AutoContactConfig, MessageTemplate
        acc, acc_created = AutoContactConfig.objects.get_or_create(
            tenant=tenant,
            defaults={
                'habilitado': True,
                'solo_particulares': True,
                'score_minimo': 30,
                'precio_minimo': 50000,
                'precio_maximo': 1000000,
                'contactar_fotocasa': True,
                'contactar_habitaclia': True,
                'contactar_milanuncios': True,
                'contactar_idealista': True,
                'max_contactos_dia': 5,
                'max_contactos_portal_dia': 3,
            }
        )
        if acc_created:
            self.stdout.write(self.style.SUCCESS('Created AutoContactConfig'))
        else:
            self.stdout.write('AutoContactConfig already exists')

        # 6. Create MessageTemplate
        mt, mt_created = MessageTemplate.objects.get_or_create(
            tenant=tenant,
            nombre='Contacto inicial Find&Look',
            defaults={
                'canal': 'portal',
                'cuerpo': (
                    'Hola, soy {comercial_nombre} de Find&Look. '
                    'He visto su inmueble en {portal} en la zona de {nombre_zona} '
                    'y me gustaría hablar con usted. '
                    '¿Podríamos concertar una visita? '
                    'Mi teléfono: {comercial_telefono}'
                ),
                'activa': True,
                'peso': 100,
            }
        )
        if mt_created:
            self.stdout.write(self.style.SUCCESS('Created MessageTemplate'))
        else:
            self.stdout.write('MessageTemplate already exists')

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\nSetup complete!\n'
            f'  Tenant: Find&Look (id={tenant.tenant_id})\n'
            f'  User: mariano\n'
            f'  Zones: {zones_created} new ({len(MADRID_ZONES)} total)\n'
            f'  AutoContactConfig: {"created" if acc_created else "exists"}\n'
            f'  MessageTemplate: {"created" if mt_created else "exists"}\n'
            f'  URL: /admin/ -> login as mariano\n'
            f'\n  IMPORTANT: Tenant ID must be {tenant.tenant_id} in workflows/schedulers'
        ))

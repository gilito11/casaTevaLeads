"""
Management command to setup Find&Look tenant with Madrid zones.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Tenant, TenantUser, ZonaGeografica


# Madrid zones - Hortaleza area and nearby
MADRID_ZONES = {
    'hortaleza': {
        'nombre': 'Hortaleza',
        'lat': 40.4697,
        'lon': -3.6407,
        'provincia_id': 28,
        'radio_default': 5,
    },
    'chamartin': {
        'nombre': 'Chamartín',
        'lat': 40.4597,
        'lon': -3.6772,
        'provincia_id': 28,
        'radio_default': 5,
    },
    'ciudad_lineal': {
        'nombre': 'Ciudad Lineal',
        'lat': 40.4395,
        'lon': -3.6512,
        'provincia_id': 28,
        'radio_default': 5,
    },
    'san_blas': {
        'nombre': 'San Blas-Canillejas',
        'lat': 40.4317,
        'lon': -3.6133,
        'provincia_id': 28,
        'radio_default': 5,
    },
    'barajas': {
        'nombre': 'Barajas',
        'lat': 40.4697,
        'lon': -3.5803,
        'provincia_id': 28,
        'radio_default': 5,
    },
    'fuencarral': {
        'nombre': 'Fuencarral-El Pardo',
        'lat': 40.4997,
        'lon': -3.7172,
        'provincia_id': 28,
        'radio_default': 8,
    },
}


class Command(BaseCommand):
    help = 'Setup Find&Look tenant with Madrid zones and Mariano user'

    def handle(self, *args, **options):
        # Create tenant
        tenant, created = Tenant.objects.get_or_create(
            slug='findlook',
            defaults={
                'nombre': 'Find&Look',
                'email_contacto': 'contacto@findlook.es',
                'telefono': '',
                'config_scraping': {
                    'contact_automation_enabled': True,
                    'max_contacts_per_day': 5,
                },
                'activo': True,
                'max_leads_mes': 500,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created tenant: {tenant.nombre}'))
        else:
            self.stdout.write(f'Tenant already exists: {tenant.nombre}')

        # Create user Mariano
        password = 'FindLook2026!'
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
            self.stdout.write(self.style.SUCCESS(f'Created user: mariano / {password}'))
        else:
            self.stdout.write(f'User already exists: mariano')

        # Link user to tenant as admin
        tenant_user, tu_created = TenantUser.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={'rol': 'admin'}
        )

        if tu_created:
            self.stdout.write(self.style.SUCCESS(f'Linked mariano to Find&Look as admin'))

        # Create zones
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
                    'precio_minimo': 50000,  # Para compra, no alquiler
                    'scrapear_milanuncios': True,
                    'scrapear_fotocasa': True,
                    'scrapear_habitaclia': True,
                    'scrapear_idealista': True,
                }
            )
            if z_created:
                zones_created += 1
                self.stdout.write(f'  Created zone: {zone_data["nombre"]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nSetup complete!\n'
            f'  Tenant: Find&Look\n'
            f'  User: mariano / {password}\n'
            f'  Zones: {zones_created} new zones created\n'
            f'  URL: /admin/ -> login as mariano'
        ))

from django.core.management.base import BaseCommand, CommandError
from core.models import Tenant
from django.db import IntegrityError


class Command(BaseCommand):
    help = 'Crea un nuevo tenant (inmobiliaria) en el sistema'

    def add_arguments(self, parser):
        # Argumentos posicionales requeridos
        parser.add_argument(
            'nombre',
            type=str,
            help='Nombre de la inmobiliaria'
        )
        parser.add_argument(
            'slug',
            type=str,
            help='Slug único para la inmobiliaria (ej: casa-teva)'
        )

        # Argumentos opcionales
        parser.add_argument(
            '--email',
            type=str,
            default='',
            help='Email de contacto de la inmobiliaria'
        )
        parser.add_argument(
            '--telefono',
            type=str,
            default='',
            help='Teléfono de contacto de la inmobiliaria'
        )
        parser.add_argument(
            '--max-leads',
            type=int,
            default=1000,
            help='Máximo de leads por mes (default: 1000)'
        )

    def handle(self, *args, **options):
        nombre = options['nombre']
        slug = options['slug']
        email = options['email']
        telefono = options['telefono']
        max_leads_mes = options['max_leads']

        # Configuración de scraping por defecto
        config_scraping_default = {
            "portales": ["fotocasa", "milanuncios", "wallapop"],
            "zonas": {
                "lleida_ciudad": {
                    "enabled": True,
                    "codigos_postales": ["25001", "25002", "25003"]
                }
            },
            "filtros_precio": {
                "min": 50000,
                "max": 1000000
            },
            "schedule_scraping": "0 */6 * * *",
            "max_leads_por_dia": 50
        }

        try:
            # Crear el tenant
            tenant = Tenant.objects.create(
                nombre=nombre,
                slug=slug,
                email_contacto=email,
                telefono=telefono,
                config_scraping=config_scraping_default,
                max_leads_mes=max_leads_mes,
                activo=True
            )

            # Mensaje de éxito
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Tenant creado exitosamente!\n'
                    f'  ID: {tenant.tenant_id}\n'
                    f'  Nombre: {tenant.nombre}\n'
                    f'  Slug: {tenant.slug}\n'
                    f'  Email: {tenant.email_contacto or "No especificado"}\n'
                    f'  Teléfono: {tenant.telefono or "No especificado"}\n'
                    f'  Max leads/mes: {tenant.max_leads_mes}\n'
                    f'  Activo: {"Sí" if tenant.activo else "No"}\n'
                )
            )

            # Mostrar configuración de scraping
            self.stdout.write(
                self.style.WARNING(
                    f'\nConfiguración de scraping:\n'
                    f'  Portales: {", ".join(config_scraping_default["portales"])}\n'
                    f'  Zonas configuradas: {", ".join(config_scraping_default["zonas"].keys())}\n'
                    f'  Rango de precios: €{config_scraping_default["filtros_precio"]["min"]:,} - €{config_scraping_default["filtros_precio"]["max"]:,}\n'
                    f'  Schedule: {config_scraping_default["schedule_scraping"]}\n'
                    f'  Max leads/día: {config_scraping_default["max_leads_por_dia"]}\n'
                )
            )

        except IntegrityError as e:
            raise CommandError(
                f'Error al crear el tenant: El slug "{slug}" ya existe. '
                f'Por favor usa un slug único.'
            )
        except Exception as e:
            raise CommandError(f'Error inesperado al crear el tenant: {str(e)}')

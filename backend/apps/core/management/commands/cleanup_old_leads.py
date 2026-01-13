from django.core.management.base import BaseCommand
from django.db import connection
from datetime import datetime


class Command(BaseCommand):
    help = 'Elimina leads antiguos de raw_listings y dim_leads para permitir re-scraping'

    def add_arguments(self, parser):
        parser.add_argument(
            '--before-date',
            type=str,
            default='2026-01-10',
            help='Eliminar leads con scraping_timestamp anterior a esta fecha (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar cuantos registros se eliminarían sin eliminarlos'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar la eliminación sin preguntar'
        )

    def handle(self, *args, **options):
        before_date = options['before_date']
        dry_run = options['dry_run']
        confirm = options['confirm']

        try:
            datetime.strptime(before_date, '%Y-%m-%d')
        except ValueError:
            self.stderr.write(self.style.ERROR(f'Fecha inválida: {before_date}. Usar formato YYYY-MM-DD'))
            return

        with connection.cursor() as cursor:
            # Contar registros en raw_listings
            cursor.execute("""
                SELECT COUNT(*) FROM raw.raw_listings
                WHERE scraping_timestamp < %s::timestamp
            """, [before_date])
            raw_count = cursor.fetchone()[0]

            # Contar registros en dim_leads
            cursor.execute("""
                SELECT COUNT(*) FROM public_marts.dim_leads
                WHERE fecha_primera_captura < %s::timestamp
            """, [before_date])
            dim_count = cursor.fetchone()[0]

            # Contar en leads_lead_estado
            cursor.execute("""
                SELECT COUNT(*) FROM leads_lead_estado le
                WHERE EXISTS (
                    SELECT 1 FROM public_marts.dim_leads d
                    WHERE d.lead_id = le.lead_id
                    AND d.fecha_primera_captura < %s::timestamp
                )
            """, [before_date])
            estado_count = cursor.fetchone()[0]

            self.stdout.write(f'\nRegistros anteriores a {before_date}:')
            self.stdout.write(f'  raw.raw_listings: {raw_count}')
            self.stdout.write(f'  public_marts.dim_leads: {dim_count}')
            self.stdout.write(f'  leads_lead_estado: {estado_count}')

            if dry_run:
                self.stdout.write(self.style.WARNING('\n[DRY RUN] No se eliminó nada'))
                return

            if raw_count == 0 and dim_count == 0:
                self.stdout.write(self.style.SUCCESS('\nNo hay registros para eliminar'))
                return

            if not confirm:
                self.stdout.write(self.style.WARNING(
                    f'\nSe eliminarán {raw_count + dim_count + estado_count} registros en total.'
                ))
                response = input('¿Continuar? [y/N]: ')
                if response.lower() != 'y':
                    self.stdout.write('Operación cancelada')
                    return

            # Eliminar en orden: primero estados, luego dim_leads, luego raw
            self.stdout.write('\nEliminando registros...')

            # 1. Eliminar estados asociados
            if estado_count > 0:
                cursor.execute("""
                    DELETE FROM leads_lead_estado
                    WHERE lead_id IN (
                        SELECT lead_id FROM public_marts.dim_leads
                        WHERE fecha_primera_captura < %s::timestamp
                    )
                """, [before_date])
                self.stdout.write(f'  leads_lead_estado: {cursor.rowcount} eliminados')

            # 2. Eliminar de dim_leads (nota: es una tabla materializada por dbt)
            # En realidad dim_leads es incremental, así que eliminamos directamente
            if dim_count > 0:
                cursor.execute("""
                    DELETE FROM public_marts.dim_leads
                    WHERE fecha_primera_captura < %s::timestamp
                """, [before_date])
                self.stdout.write(f'  public_marts.dim_leads: {cursor.rowcount} eliminados')

            # 3. Eliminar de raw_listings
            if raw_count > 0:
                cursor.execute("""
                    DELETE FROM raw.raw_listings
                    WHERE scraping_timestamp < %s::timestamp
                """, [before_date])
                self.stdout.write(f'  raw.raw_listings: {cursor.rowcount} eliminados')

            self.stdout.write(self.style.SUCCESS('\nLimpieza completada. Los leads podrán ser re-scrapeados.'))

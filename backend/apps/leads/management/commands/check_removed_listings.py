"""
Django management command to check if listings are still active on portals.
"""

from django.core.management.base import BaseCommand

import sys
import os

# Add scrapers to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))))


class Command(BaseCommand):
    help = 'Check if listings are still active on their source portals and mark removed ones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of leads to check (default: 50)',
        )
        parser.add_argument(
            '--portal',
            type=str,
            choices=['habitaclia', 'fotocasa', 'milanuncios', 'idealista'],
            help='Filter by portal',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Check listings but do not update database',
        )

    def handle(self, *args, **options):
        from scrapers.listing_checker import ListingChecker

        limit = options['limit']
        portal = options.get('portal')
        dry_run = options['dry_run']

        self.stdout.write(f"Checking up to {limit} listings...")
        if portal:
            self.stdout.write(f"Filtering by portal: {portal}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no database updates"))

        with ListingChecker() as checker:
            results = checker.check_leads(
                limit=limit,
                portal=portal,
                mark_removed=not dry_run,
            )

        stats = results['stats']
        self.stdout.write(f"\n=== Results ===")
        self.stdout.write(f"Checked: {stats['checked']}")
        self.stdout.write(self.style.SUCCESS(f"Active: {stats['active']}"))
        self.stdout.write(self.style.WARNING(f"Removed: {stats['removed']}"))

        if results['removed_leads']:
            self.stdout.write(f"\nRemoved listings:")
            for lead in results['removed_leads']:
                self.stdout.write(
                    self.style.ERROR(f"  - {lead['lead_id']} ({lead['portal']}): {lead['reason']}")
                )

        if not dry_run and results['removed_leads']:
            self.stdout.write(
                self.style.SUCCESS(f"\nMarked {len(results['removed_leads'])} leads as 'YA_VENDIDO'")
            )

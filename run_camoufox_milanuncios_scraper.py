#!/usr/bin/env python
"""
Runner script for Camoufox Milanuncios scraper.

Replaces ScrapingBee - completely FREE using Camoufox anti-detect browser.

Usage:
    python run_camoufox_milanuncios.py                    # Default: salou
    python run_camoufox_milanuncios.py salou cambrils    # Multiple zones
    python run_camoufox_milanuncios.py --all              # All zones
    python run_camoufox_milanuncios.py --zones salou cambrils --postgres
"""

import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.camoufox_milanuncios import run_camoufox_milanuncios, ZONAS_GEOGRAFICAS


def main():
    parser = argparse.ArgumentParser(description='Run Camoufox Milanuncios scraper')
    parser.add_argument('zones', nargs='*', default=['salou'], help='Zones to scrape')
    parser.add_argument('--zones', dest='zones_flag', nargs='*', help='Zones to scrape (flag style)')
    parser.add_argument('--all', action='store_true', help='Scrape all zones')
    parser.add_argument('--max-pages', type=int, default=2, help='Max pages per zone')
    parser.add_argument('--visible', action='store_true', help='Run with visible browser')
    parser.add_argument('--list-zones', action='store_true', help='List available zones')
    parser.add_argument('--postgres', action='store_true', help='Save to PostgreSQL (default behavior)')
    parser.add_argument('--tenant-id', type=int, default=1, help='Tenant ID')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if args.list_zones:
        print("\nAvailable zones:")
        for key, info in ZONAS_GEOGRAFICAS.items():
            print(f"  {key:20} - {info['nombre']}")
        return

    # Determine zones (support both positional and --zones flag)
    zones = args.zones_flag if args.zones_flag else args.zones
    if args.all:
        zones = list(ZONAS_GEOGRAFICAS.keys())

    print(f"\n{'='*50}")
    print("  CAMOUFOX MILANUNCIOS SCRAPER")
    print("  (Replaces ScrapingBee - FREE)")
    print(f"{'='*50}")
    print(f"  Zones: {', '.join(zones)}")
    print(f"  Max pages: {args.max_pages}")
    print(f"  Headless: {not args.visible}")
    print(f"  Tenant ID: {args.tenant_id}")
    print(f"{'='*50}\n")

    try:
        stats = run_camoufox_milanuncios(
            zones=zones,
            max_pages_per_zone=args.max_pages,
            headless=not args.visible,
            tenant_id=args.tenant_id,
        )

        print(f"\n{'='*50}")
        print("  RESULTS")
        print(f"{'='*50}")
        print(f"  Pages scraped: {stats.get('pages_scraped', 0)}")
        print(f"  Listings found: {stats.get('listings_found', 0)}")
        print(f"  Listings saved: {stats.get('listings_saved', 0)}")
        print(f"  Errors: {stats.get('errors', 0)}")
        print(f"{'='*50}\n")

        # Output for Dagster parsing
        print(f"{stats.get('listings_saved', 0)} leads guardados")

    except Exception as e:
        print(f"\nError: {e}")
        logging.exception("Scraper failed")
        sys.exit(1)


if __name__ == '__main__':
    main()

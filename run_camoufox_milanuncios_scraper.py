#!/usr/bin/env python
"""
Runner script for Camoufox Milanuncios scraper.

Uses Camoufox anti-detect browser to bypass GeeTest captcha. FREE.

Usage:
    python run_camoufox_milanuncios_scraper.py --zones salou cambrils
    python run_camoufox_milanuncios_scraper.py --zones lleida_ciudad --max-pages 3
    python run_camoufox_milanuncios_scraper.py --list-zones

Environment:
    DATABASE_URL: PostgreSQL connection string (Neon)
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.camoufox_milanuncios import CamoufoxMilanuncios, ZONAS_GEOGRAFICAS


def main():
    parser = argparse.ArgumentParser(
        description='Camoufox Milanuncios Scraper (GeeTest bypass)'
    )
    parser.add_argument(
        '--zones',
        nargs='+',
        default=['salou'],
        help='Zones to scrape (e.g., salou cambrils lleida_ciudad)'
    )
    parser.add_argument(
        '--tenant-id',
        type=int,
        default=1,
        help='Tenant ID for multi-tenancy'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=3,
        help='Maximum pages per zone'
    )
    parser.add_argument(
        '--include-agencies',
        action='store_true',
        help='Include agency listings (default: only particulares)'
    )
    parser.add_argument(
        '--no-watermark-filter',
        action='store_true',
        help='Disable watermark filtering'
    )
    parser.add_argument(
        '--list-zones',
        action='store_true',
        help='List available zones and exit'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--visible',
        action='store_true',
        help='Run with visible browser (for debugging)'
    )
    parser.add_argument(
        '--postgres',
        action='store_true',
        help='Save to PostgreSQL (always enabled)'
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)

    if args.list_zones:
        print("\nAvailable zones for Milanuncios:")
        print("-" * 40)
        for key, info in sorted(ZONAS_GEOGRAFICAS.items()):
            print(f"  {key:20} - {info['nombre']}")
        return 0

    # Handle comma-separated zones (from GitHub Actions)
    all_zones = []
    for z in args.zones:
        all_zones.extend(z.split(','))
    zones = [z.strip() for z in all_zones if z.strip()]

    invalid_zones = [z for z in zones if z not in ZONAS_GEOGRAFICAS]
    if invalid_zones:
        logger.error(f"Invalid zones: {invalid_zones}")
        logger.info(f"Valid zones: {list(ZONAS_GEOGRAFICAS.keys())}")
        return 1

    only_particulares = not args.include_agencies
    headless = not args.visible
    filter_watermarks = not args.no_watermark_filter

    print(f"\n{'='*50}")
    print("  CAMOUFOX MILANUNCIOS SCRAPER")
    print(f"{'='*50}")
    print(f"  Zones: {zones}")
    print(f"  Tenant ID: {args.tenant_id}")
    print(f"  Max pages per zone: {args.max_pages}")
    print(f"  Only particulares: {only_particulares}")
    print(f"  Watermark filter: {filter_watermarks}")
    print(f"  Headless: {headless}")
    print(f"  Cost: FREE")
    print(f"{'='*50}\n")

    try:
        scraper = CamoufoxMilanuncios(
            zones=zones,
            tenant_id=args.tenant_id,
            max_pages_per_zone=args.max_pages,
            only_particulares=only_particulares,
            headless=headless,
            filter_watermarks=filter_watermarks,
        )
        stats = scraper.scrape()

        print(f"\n{'='*50}")
        print("  SCRAPING COMPLETE")
        print(f"{'='*50}")
        print(f"  Pages scraped: {stats['pages_scraped']}")
        print(f"  Listings found: {stats['listings_found']}")
        print(f"  Listings saved: {stats['listings_saved']}")
        print(f"  Watermark skipped: {stats['listings_skipped_watermark']}")
        print(f"  Errors: {stats['errors']}")
        print(f"{'='*50}\n")

        return 0 if stats['errors'] == 0 else 1

    except Exception as e:
        logger.exception(f"Scraper failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

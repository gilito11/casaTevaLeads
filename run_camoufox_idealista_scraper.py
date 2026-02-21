#!/usr/bin/env python
"""
Runner script for Camoufox Idealista scraper.

Uses Camoufox anti-detect browser + IPRoyal proxy to bypass DataDome.
Cost: ~$0.01/scrape (vs ~$2.50/scrape with ScrapingBee)

Usage:
    python run_camoufox_idealista_scraper.py --zones salou cambrils
    python run_camoufox_idealista_scraper.py --zones igualada --max-pages 2
    python run_camoufox_idealista_scraper.py --list-zones

Environment:
    DATADOME_PROXY: IPRoyal proxy (format: user:pass_country-es@geo.iproyal.com:12321)
    DATABASE_URL: PostgreSQL connection string (Neon)
"""

import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from scrapers.camoufox_idealista import CamoufoxIdealista, ZONAS_GEOGRAFICAS


def main():
    parser = argparse.ArgumentParser(
        description='Camoufox Idealista Scraper (DataDome bypass)'
    )
    parser.add_argument(
        '--zones',
        nargs='+',
        default=['salou'],
        help='Zones to scrape (e.g., salou cambrils tarragona)'
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
        default=2,
        help='Maximum pages per zone'
    )
    parser.add_argument(
        '--include-agencies',
        action='store_true',
        help='Include agency listings (default: only particulares)'
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
        '--virtual',
        action='store_true',
        help='Use Xvfb virtual display (for CI - evades headless detection)'
    )
    parser.add_argument(
        '--postgres',
        action='store_true',
        help='Save to PostgreSQL (always enabled)'
    )
    parser.add_argument('--min-delay', type=float, default=None, help='Min delay between requests (seconds)')
    parser.add_argument('--max-delay', type=float, default=None, help='Max delay between requests (seconds)')

    args = parser.parse_args()

    if args.min_delay is not None:
        os.environ['SCRAPER_MIN_DELAY'] = str(args.min_delay)
    if args.max_delay is not None:
        os.environ['SCRAPER_MAX_DELAY'] = str(args.max_delay)

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    logger = logging.getLogger(__name__)

    # List zones if requested
    if args.list_zones:
        print("\nAvailable zones for Idealista:")
        print("-" * 40)
        for key, info in sorted(ZONAS_GEOGRAFICAS.items()):
            print(f"  {key:20} - {info['nombre']}")
        return 0

    # Validate zones
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

    # Check for proxy
    proxy = os.environ.get('DATADOME_PROXY')
    if not proxy:
        logger.warning(
            "DATADOME_PROXY not set - scraper may get blocked by DataDome. "
            "Set DATADOME_PROXY=user:pass_country-es@geo.iproyal.com:12321"
        )

    only_particulares = not args.include_agencies
    if args.visible:
        headless = False
    elif args.virtual:
        headless = "virtual"
    else:
        headless = True

    print(f"\n{'='*50}")
    print("  CAMOUFOX IDEALISTA SCRAPER")
    print(f"{'='*50}")
    print(f"  Zones: {zones}")
    print(f"  Tenant ID: {args.tenant_id}")
    print(f"  Max pages per zone: {args.max_pages}")
    print(f"  Only particulares: {only_particulares}")
    print(f"  Proxy: {'configured' if proxy else 'NOT CONFIGURED'}")
    print(f"  Headless: {headless}")
    print(f"{'='*50}\n")

    try:
        scraper = CamoufoxIdealista(
            zones=zones,
            tenant_id=args.tenant_id,
            max_pages_per_zone=args.max_pages,
            only_particulares=only_particulares,
            headless=headless,
        )
        stats = scraper.scrape()

        print(f"\n{'='*50}")
        print("  SCRAPING COMPLETE")
        print(f"{'='*50}")
        print(f"  Pages scraped: {stats['pages_scraped']}")
        print(f"  Listings found: {stats['listings_found']}")
        print(f"  Listings saved: {stats['listings_saved']}")
        print(f"  Errors: {stats['errors']}")
        print(f"{'='*50}\n")

        return 0 if stats['errors'] == 0 else 1

    except Exception as e:
        logger.exception(f"Scraper failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

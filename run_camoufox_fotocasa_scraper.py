#!/usr/bin/env python3
"""
Run Fotocasa scraper using Camoufox anti-detect browser.

Usage:
    python run_camoufox_fotocasa_scraper.py --zones salou cambrils --postgres
    python run_camoufox_fotocasa_scraper.py --zones salou --virtual --postgres
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from scrapers.camoufox_fotocasa import CamoufoxFotocasa, ZONAS_GEOGRAFICAS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Fotocasa scraper (Camoufox)')
    parser.add_argument('--zones', nargs='+', default=['salou'])
    parser.add_argument('--postgres', action='store_true')
    parser.add_argument('--tenant-id', type=int, default=1)
    parser.add_argument('--virtual', action='store_true', help='Use virtual display (for CI)')
    parser.add_argument('--visible', action='store_true', help='Show browser window')
    parser.add_argument('--min-delay', type=float, default=None, help='Min delay between requests (seconds)')
    parser.add_argument('--max-delay', type=float, default=None, help='Max delay between requests (seconds)')
    args = parser.parse_args()

    if args.min_delay is not None:
        os.environ['SCRAPER_MIN_DELAY'] = str(args.min_delay)
    if args.max_delay is not None:
        os.environ['SCRAPER_MAX_DELAY'] = str(args.max_delay)

    # Determine headless mode
    headless = True
    if args.virtual:
        headless = "virtual"
    elif args.visible:
        headless = False

    # Validate zones
    for zone in args.zones:
        if zone not in ZONAS_GEOGRAFICAS:
            print(f"ERROR: Unknown zone: {zone}")
            sys.exit(1)

    scraper = CamoufoxFotocasa(
        zones=args.zones,
        headless=headless,
        postgres=args.postgres,
        tenant_id=args.tenant_id,
    )

    stats = scraper.scrape()
    print(f"\nResults: {stats}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python
"""
Runner script for Camoufox Idealista scraper.

Usage:
    python run_camoufox_idealista.py                    # Default: salou
    python run_camoufox_idealista.py salou cambrils    # Multiple zones
    python run_camoufox_idealista.py --all              # All zones
"""

import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.camoufox_idealista import run_camoufox_idealista, ZONAS_GEOGRAFICAS


def main():
    parser = argparse.ArgumentParser(description='Run Camoufox Idealista scraper')
    parser.add_argument('zones', nargs='*', default=['salou'], help='Zones to scrape')
    parser.add_argument('--all', action='store_true', help='Scrape all zones')
    parser.add_argument('--max-pages', type=int, default=2, help='Max pages per zone')
    parser.add_argument('--visible', action='store_true', help='Run with visible browser')
    parser.add_argument('--list-zones', action='store_true', help='List available zones')

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

    zones = list(ZONAS_GEOGRAFICAS.keys()) if args.all else args.zones

    print(f"\n{'='*50}")
    print("  CAMOUFOX IDEALISTA SCRAPER")
    print(f"{'='*50}")
    print(f"  Zones: {', '.join(zones)}")
    print(f"  Max pages: {args.max_pages}")
    print(f"  Headless: {not args.visible}")
    print(f"{'='*50}\n")

    try:
        stats = run_camoufox_idealista(
            zones=zones,
            max_pages_per_zone=args.max_pages,
            headless=not args.visible,
        )

        print(f"\n{'='*50}")
        print("  RESULTS")
        print(f"{'='*50}")
        print(f"  Pages scraped: {stats.get('pages_scraped', 0)}")
        print(f"  Listings found: {stats.get('listings_found', 0)}")
        print(f"  Listings saved: {stats.get('listings_saved', 0)}")
        print(f"  Errors: {stats.get('errors', 0)}")
        print(f"{'='*50}\n")

    except Exception as e:
        print(f"\nError: {e}")
        logging.exception("Scraper failed")
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Runner script for Milanuncios HTTP scraper.

Uses curl_cffi for TLS fingerprint impersonation to bypass GeeTest.
Cost: €0 (completely FREE)
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.http_milanuncios import MilanunciosHTTPScraper


def main():
    parser = argparse.ArgumentParser(description='Milanuncios HTTP Scraper (curl_cffi)')
    parser.add_argument('--zones', nargs='+', required=True,
                        help='Zone keys to scrape (e.g., salou reus lleida_ciudad)')
    parser.add_argument('--max-pages', type=int, default=2,
                        help='Max pages per zone (default: 2)')
    parser.add_argument('--tenant-id', type=int, default=1,
                        help='Tenant ID (default: 1)')
    parser.add_argument('--postgres', action='store_true',
                        help='Save to PostgreSQL')

    args = parser.parse_args()

    print()
    print("=" * 60)
    print("MILANUNCIOS HTTP SCRAPER (curl_cffi)")
    print("(Replaces Camoufox - FREE, bypasses GeeTest via TLS fingerprint)")
    print("=" * 60)
    print(f"Zones: {', '.join(args.zones)}")
    print(f"Max pages: {args.max_pages}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"PostgreSQL: {'Enabled' if args.postgres else 'Disabled'}")
    print("=" * 60)
    print()

    try:
        scraper = MilanunciosHTTPScraper(
            zones=args.zones,
            max_pages=args.max_pages,
            tenant_id=args.tenant_id,
            use_postgres=args.postgres,
        )

        stats = scraper.scrape()

        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Pages scraped: {stats['pages_scraped']}")
        print(f"Listings found: {stats['listings_found']}")
        print(f"Listings saved: {stats['listings_saved']}")
        print(f"Errors: {stats['errors']}")
        print("=" * 60)
        print()
        print(f"{stats['listings_saved']} leads guardados")
        print()

        return 0 if stats['errors'] == 0 else 1

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

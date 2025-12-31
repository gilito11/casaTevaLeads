#!/usr/bin/env python
"""
Runner script for ScrapingBee Idealista scraper.

Usage:
    python run_scrapingbee_idealista.py --zones salou cambrils
    python run_scrapingbee_idealista.py --zones lleida --max-pages 2
    python run_scrapingbee_idealista.py --zones costa_daurada --tenant-id 1
"""

import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.scrapingbee_idealista import ScrapingBeeIdealista, ZONAS_GEOGRAFICAS


def main():
    parser = argparse.ArgumentParser(
        description='ScrapingBee Idealista Scraper'
    )
    parser.add_argument(
        '--zones',
        nargs='+',
        default=['salou'],
        help='Zones to scrape (e.g., salou cambrils lleida)'
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
        help='Maximum pages per zone (budget control)'
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
        '--postgres',
        action='store_true',
        help='Save to PostgreSQL (always enabled for ScrapingBee)'
    )

    args = parser.parse_args()

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
            zone_type = "composite" if "composite" in info else "single"
            print(f"  {key}: {info['nombre']} ({zone_type})")
        return 0

    # Validate zones
    invalid_zones = [z for z in args.zones if z not in ZONAS_GEOGRAFICAS]
    if invalid_zones:
        logger.error(f"Invalid zones: {invalid_zones}")
        logger.info(f"Valid zones: {list(ZONAS_GEOGRAFICAS.keys())}")
        return 1

    # Check for API key
    if not os.environ.get('SCRAPINGBEE_API_KEY'):
        logger.error(
            "SCRAPINGBEE_API_KEY environment variable not set. "
            "Please set it before running the scraper."
        )
        return 1

    only_particulares = not args.include_agencies

    logger.info(f"Starting ScrapingBee Idealista scraper")
    logger.info(f"  Zones: {args.zones}")
    logger.info(f"  Tenant ID: {args.tenant_id}")
    logger.info(f"  Max pages per zone: {args.max_pages}")
    logger.info(f"  Only particulares: {only_particulares}")

    try:
        with ScrapingBeeIdealista(
            zones=args.zones,
            tenant_id=args.tenant_id,
            max_pages_per_zone=args.max_pages,
            only_particulares=only_particulares,
        ) as scraper:
            stats = scraper.scrape_and_save()

            logger.info("=" * 50)
            logger.info("SCRAPING COMPLETE")
            logger.info("=" * 50)
            logger.info(f"  Requests made: {stats['requests']}")
            logger.info(f"  Credits used: {stats['credits_used']}")
            logger.info(f"  Pages scraped: {stats['pages_scraped']}")
            logger.info(f"  Listings found: {stats['listings_found']}")
            logger.info(f"  Listings saved: {stats['listings_saved']}")
            logger.info(f"  Errors: {stats['errors']}")
            logger.info(f"  Estimated cost: €{stats['cost_estimate_eur']:.2f}")
            logger.info("=" * 50)

            return 0 if stats['errors'] == 0 else 1

    except Exception as e:
        logger.exception(f"Scraper failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

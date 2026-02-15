#!/usr/bin/env python
"""
Quick Scan: scrape only listing pages (skip detail enrichment) for fast new-lead detection.

Designed to run frequently (every 2-4 hours) within GitHub Actions free tier budget.
~3-5 min per run vs 10-15 min for full scrape.

Usage:
    python run_quick_scan.py --zones salou cambrils --postgres
    python run_quick_scan.py --zones tarragona --postgres --portals habitaclia fotocasa
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia, ZONAS_GEOGRAFICAS as HAB_ZONAS
from scrapers.botasaurus_fotocasa import BotasaurusFotocasa, ZONAS_GEOGRAFICAS as FOT_ZONAS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_postgres_config():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        return None

    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/'),
        'user': parsed.username,
        'password': parsed.password,
        'sslmode': 'require' if 'neon' in (parsed.hostname or '') else 'prefer',
    }


def main():
    parser = argparse.ArgumentParser(description='Quick scan for new listings')
    parser.add_argument('--zones', nargs='+', default=['salou', 'cambrils', 'tarragona'])
    parser.add_argument('--portals', nargs='+', default=['habitaclia', 'fotocasa'])
    parser.add_argument('--postgres', action='store_true')
    parser.add_argument('--tenant-id', type=int, default=1)
    args = parser.parse_args()

    postgres_config = get_postgres_config() if args.postgres else None

    total_saved = 0
    total_found = 0

    for portal in args.portals:
        if portal == 'habitaclia':
            # Filter zones that exist in habitaclia config
            valid_zones = [z for z in args.zones if z in HAB_ZONAS]
            if not valid_zones:
                logger.info(f"No valid zones for habitaclia, skipping")
                continue

            logger.info(f"Quick scan habitaclia: {valid_zones}")
            with BotasaurusHabitaclia(
                tenant_id=args.tenant_id,
                zones=valid_zones,
                postgres_config=postgres_config,
                headless=True,
                quick_scan=True,
            ) as scraper:
                if args.postgres:
                    stats = scraper.scrape_and_save()
                    total_saved += stats.get('saved', 0)
                    total_found += stats.get('total_listings', 0)
                else:
                    listings = scraper.scrape()
                    total_found += len(listings)

        elif portal == 'fotocasa':
            valid_zones = [z for z in args.zones if z in FOT_ZONAS]
            if not valid_zones:
                logger.info(f"No valid zones for fotocasa, skipping")
                continue

            logger.info(f"Quick scan fotocasa: {valid_zones}")
            with BotasaurusFotocasa(
                tenant_id=args.tenant_id,
                zones=valid_zones,
                postgres_config=postgres_config,
                headless=True,
                quick_scan=True,
            ) as scraper:
                if args.postgres:
                    stats = scraper.scrape_and_save()
                    total_saved += stats.get('saved', 0)
                    total_found += stats.get('total_listings', 0)
                else:
                    listings = scraper.scrape()
                    total_found += len(listings)

    logger.info(f"Quick scan complete: {total_found} found, {total_saved} new saved")


if __name__ == '__main__':
    main()

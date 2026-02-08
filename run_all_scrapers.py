#!/usr/bin/env python3
"""Run scrapers for configured zones.

Usage:
    python run_all_scrapers.py --zones amposta deltebre --portals habitaclia fotocasa
    python run_all_scrapers.py --portals habitaclia --zones salou --dry-run
    python run_all_scrapers.py --all-portals --zones salou cambrils

Environment variables required:
    DATABASE_URL: PostgreSQL connection string (or set individual vars)
    SCRAPINGBEE_API_KEY: Required for milanuncios and idealista

Note: Credentials should be in .env file, NOT hardcoded.
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment from .env file if present
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        logger.info("Loaded .env file")
    except ImportError:
        logger.warning("python-dotenv not installed, skipping .env loading")


def get_postgres_config():
    """Get PostgreSQL config from environment."""
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'database': parsed.path[1:],  # Remove leading /
            'user': parsed.username,
            'password': parsed.password,
            'port': parsed.port or 5432,
            'sslmode': 'require' if parsed.hostname and parsed.hostname != 'localhost' else 'prefer',
        }

    # Fallback to individual env vars
    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', ''),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer'),
    }


def run_habitaclia(zones, postgres_config, dry_run=False, save_to_db=True):
    """Run Habitaclia scraper."""
    print("\n" + "=" * 60)
    print("HABITACLIA (Botasaurus)")
    print("=" * 60)

    if dry_run:
        print(f"DRY RUN: Would scrape zones {zones}")
        return {'listings_found': 0, 'dry_run': True}

    try:
        from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia
        # Try with postgres_config, fallback to None if connection fails
        try:
            with BotasaurusHabitaclia(
                zones=zones,
                tenant_id=1,
                postgres_config=postgres_config if save_to_db else None
            ) as scraper:
                if save_to_db:
                    scraper.scrape_and_save()
                else:
                    listings = scraper.scrape()
                    scraper.stats['listings_found'] = len(listings)
                print(f"Stats: {scraper.stats}")
                return scraper.stats
        except Exception as conn_err:
            if 'Connection refused' in str(conn_err):
                logger.warning("PostgreSQL not available, running without DB save")
                with BotasaurusHabitaclia(
                    zones=zones,
                    tenant_id=1,
                    postgres_config=None
                ) as scraper:
                    listings = scraper.scrape()
                    scraper.stats['listings_found'] = len(listings)
                    print(f"Stats: {scraper.stats}")
                    return scraper.stats
            raise
    except Exception as e:
        logger.error(f"Habitaclia error: {e}")
        return {'error': str(e)}


def run_fotocasa(zones, postgres_config, dry_run=False, save_to_db=True):
    """Run Fotocasa scraper."""
    print("\n" + "=" * 60)
    print("FOTOCASA (Botasaurus)")
    print("=" * 60)

    if dry_run:
        print(f"DRY RUN: Would scrape zones {zones}")
        return {'listings_found': 0, 'dry_run': True}

    try:
        from scrapers.botasaurus_fotocasa import BotasaurusFotocasa
        try:
            with BotasaurusFotocasa(
                zones=zones,
                tenant_id=1,
                postgres_config=postgres_config if save_to_db else None
            ) as scraper:
                if save_to_db:
                    scraper.scrape_and_save()
                else:
                    listings = scraper.scrape()
                    scraper.stats['listings_found'] = len(listings)
                print(f"Stats: {scraper.stats}")
                return scraper.stats
        except Exception as conn_err:
            if 'Connection refused' in str(conn_err):
                logger.warning("PostgreSQL not available, running without DB save")
                with BotasaurusFotocasa(
                    zones=zones,
                    tenant_id=1,
                    postgres_config=None
                ) as scraper:
                    listings = scraper.scrape()
                    scraper.stats['listings_found'] = len(listings)
                    print(f"Stats: {scraper.stats}")
                    return scraper.stats
            raise
    except Exception as e:
        logger.error(f"Fotocasa error: {e}")
        return {'error': str(e)}


def run_milanuncios(zones, postgres_config, dry_run=False):
    """Run Milanuncios scraper (requires ScrapingBee API key)."""
    print("\n" + "=" * 60)
    print("MILANUNCIOS (Camoufox)")
    print("=" * 60)

    if dry_run:
        print(f"DRY RUN: Would scrape zones {zones}")
        return {'listings_found': 0, 'dry_run': True}

    try:
        from scrapers.camoufox_milanuncios import CamoufoxMilanuncios
        scraper = CamoufoxMilanuncios(
            zones=zones,
            tenant_id=1,
            max_pages_per_zone=2,
        )
        stats = scraper.scrape()
        print(f"Stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Milanuncios error: {e}")
        return {'error': str(e)}


def run_idealista(zones, postgres_config, dry_run=False):
    """Run Idealista scraper (Camoufox + IPRoyal proxy)."""
    print("\n" + "=" * 60)
    print("IDEALISTA (Camoufox)")
    print("=" * 60)

    if dry_run:
        print(f"DRY RUN: Would scrape zones {zones}")
        return {'listings_found': 0, 'dry_run': True}

    try:
        from scrapers.camoufox_idealista import CamoufoxIdealista
        scraper = CamoufoxIdealista(
            zones=zones,
            tenant_id=1,
            max_pages_per_zone=2,
        )
        stats = scraper.scrape()
        print(f"Stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Idealista error: {e}")
        return {'error': str(e)}


def show_results(postgres_config):
    """Show scraping results from database."""
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    try:
        import psycopg2
        conn = psycopg2.connect(**postgres_config)
        cur = conn.cursor()

        cur.execute('''
            SELECT portal, COUNT(*)
            FROM raw.raw_listings
            WHERE fecha_scraping > NOW() - INTERVAL '1 hour'
            GROUP BY portal
            ORDER BY portal
        ''')
        rows = cur.fetchall()

        if rows:
            print("Raw listings by portal (last hour):")
            for r in rows:
                print(f"  {r[0]}: {r[1]}")
        else:
            print("No new listings in the last hour")

        conn.close()
    except Exception as e:
        logger.warning(f"Could not show results: {e}")


def main():
    parser = argparse.ArgumentParser(description='Run Casa Teva scrapers')
    parser.add_argument(
        '--portals', '-p',
        nargs='+',
        choices=['habitaclia', 'fotocasa', 'milanuncios', 'idealista'],
        help='Portals to scrape'
    )
    parser.add_argument(
        '--all-portals',
        action='store_true',
        help='Scrape all portals'
    )
    parser.add_argument(
        '--zones', '-z',
        nargs='+',
        default=['salou'],
        help='Zones to scrape (default: salou)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scraped without actually scraping'
    )
    parser.add_argument(
        '--postgres',
        action='store_true',
        help='Save results to PostgreSQL (default: just scrape)'
    )

    args = parser.parse_args()

    # Determine which portals to run
    if args.all_portals:
        portals = ['habitaclia', 'fotocasa', 'milanuncios', 'idealista']
    elif args.portals:
        portals = args.portals
    else:
        # Default to free portals only
        portals = ['habitaclia', 'fotocasa']

    # Get PostgreSQL config
    postgres_config = get_postgres_config()

    # Print config
    print("=" * 60)
    print("SCRAPER CONFIGURATION")
    print("=" * 60)
    print(f"Portals: {portals}")
    print(f"Zones: {args.zones}")
    print(f"Dry run: {args.dry_run}")
    print(f"PostgreSQL host: {postgres_config.get('host', 'N/A')}")
    print(f"ScrapingBee API: {'configured' if os.environ.get('SCRAPINGBEE_API_KEY') else 'not set'}")

    # Run scrapers
    results = {}

    if 'habitaclia' in portals:
        results['habitaclia'] = run_habitaclia(args.zones, postgres_config, args.dry_run)

    if 'fotocasa' in portals:
        results['fotocasa'] = run_fotocasa(args.zones, postgres_config, args.dry_run)

    if 'milanuncios' in portals:
        results['milanuncios'] = run_milanuncios(args.zones, postgres_config, args.dry_run)

    if 'idealista' in portals:
        results['idealista'] = run_idealista(args.zones, postgres_config, args.dry_run)

    # Show results
    if not args.dry_run:
        show_results(postgres_config)

    print("\nDone!")
    return results


if __name__ == '__main__':
    main()

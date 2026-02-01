#!/usr/bin/env python
"""
Unified script to run all Botasaurus scrapers.

This script runs scrapers for:
- Milanuncios (works)
- Fotocasa (works)
- Habitaclia (works)
- Pisos.com (works)

Note: Idealista requires paid service (Cloudflare protection)

Usage:
    # Run all portals
    python run_botasaurus_scrapers.py --all

    # Run specific portals
    python run_botasaurus_scrapers.py --portals milanuncios fotocasa

    # Run with PostgreSQL saving
    python run_botasaurus_scrapers.py --all --postgres

    # Run specific zones
    python run_botasaurus_scrapers.py --portals milanuncios --zones salou cambrils
"""

import argparse
import logging
import sys
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_postgres_config(use_azure: bool = False, inside_docker: bool = False) -> Dict[str, str]:
    """Get PostgreSQL configuration.

    Args:
        use_azure: Use Azure PostgreSQL (production)
        inside_docker: Running inside Docker container (use 'postgres' as host)
    """
    if use_azure:
        import os
        return {
            'host': os.environ.get('DB_HOST', 'inmoleads-db.postgres.database.azure.com'),
            'port': 5432,
            'database': os.environ.get('DB_NAME', 'inmoleadsdb'),
            'user': os.environ.get('DB_USER', 'inmoleadsadmin'),
            'password': os.environ['DB_PASS'],
            'sslmode': 'require',
        }
    else:
        # Local Docker config
        return {
            'host': 'postgres' if inside_docker else 'localhost',
            'port': 5432,
            'database': 'casa_teva_db',
            'user': 'casa_teva',
            'password': 'casateva2024',
        }


def run_milanuncios(zones: List[str], postgres_config: Dict = None, headless: bool = True):
    """Run Milanuncios scraper."""
    from scrapers.botasaurus_milanuncios import BotasaurusMilanuncios

    logger.info("=" * 60)
    logger.info("MILANUNCIOS SCRAPER")
    logger.info("=" * 60)

    with BotasaurusMilanuncios(
        zones=zones or ['salou', 'cambrils', 'tarragona_ciudad'],
        postgres_config=postgres_config,
        headless=headless,
    ) as scraper:
        if postgres_config:
            stats = scraper.scrape_and_save()
        else:
            listings = scraper.scrape()
            stats = {'total': len(listings)}

        logger.info(f"Milanuncios stats: {stats}")
        return stats


def run_fotocasa(zones: List[str], postgres_config: Dict = None, headless: bool = True):
    """Run Fotocasa scraper."""
    from scrapers.botasaurus_fotocasa import BotasaurusFotocasa

    logger.info("=" * 60)
    logger.info("FOTOCASA SCRAPER")
    logger.info("=" * 60)

    with BotasaurusFotocasa(
        zones=zones or ['tarragona_provincia'],
        postgres_config=postgres_config,
        headless=headless,
        only_private=True,
    ) as scraper:
        if postgres_config:
            stats = scraper.scrape_and_save()
        else:
            listings = scraper.scrape()
            stats = {'total': len(listings)}

        logger.info(f"Fotocasa stats: {stats}")
        return stats


def run_habitaclia(zones: List[str], postgres_config: Dict = None, headless: bool = True):
    """Run Habitaclia scraper."""
    from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia

    logger.info("=" * 60)
    logger.info("HABITACLIA SCRAPER")
    logger.info("=" * 60)

    with BotasaurusHabitaclia(
        zones=zones or ['tarragona_provincia'],
        postgres_config=postgres_config,
        headless=headless,
        only_private=True,  # Use /viviendas-particulares-{zona}.htm URL
    ) as scraper:
        if postgres_config:
            stats = scraper.scrape_and_save()
        else:
            listings = scraper.scrape()
            stats = {'total': len(listings)}

        logger.info(f"Habitaclia stats: {stats}")
        return stats


def run_pisos(zones: List[str], postgres_config: Dict = None, headless: bool = True):
    """Run Pisos.com scraper."""
    from scrapers.botasaurus_pisos import BotasaurusPisos

    logger.info("=" * 60)
    logger.info("PISOS.COM SCRAPER")
    logger.info("=" * 60)

    with BotasaurusPisos(
        zones=zones or ['tarragona_provincia'],
        postgres_config=postgres_config,
        headless=headless,
    ) as scraper:
        if postgres_config:
            stats = scraper.scrape_and_save()
        else:
            listings = scraper.scrape()
            stats = {'total': len(listings)}

        logger.info(f"Pisos.com stats: {stats}")
        return stats


PORTAL_RUNNERS = {
    'milanuncios': run_milanuncios,
    'fotocasa': run_fotocasa,
    'habitaclia': run_habitaclia,
    'pisos': run_pisos,
}


def main():
    parser = argparse.ArgumentParser(
        description='Run Botasaurus scrapers for real estate portals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available portals:
  milanuncios  - Milanuncios.com (free with Botasaurus)
  fotocasa     - Fotocasa.es (free with Botasaurus)
  habitaclia   - Habitaclia.com (free with Botasaurus)
  pisos        - Pisos.com (free with Botasaurus)

Note: Idealista requires paid service (ScrapingBee with stealth_proxy)

Examples:
  python run_botasaurus_scrapers.py --all
  python run_botasaurus_scrapers.py --portals milanuncios fotocasa
  python run_botasaurus_scrapers.py --all --postgres
  python run_botasaurus_scrapers.py --portals habitaclia --zones salou cambrils
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all available scrapers'
    )
    parser.add_argument(
        '--portals',
        nargs='+',
        choices=list(PORTAL_RUNNERS.keys()),
        help='Specific portals to scrape'
    )
    parser.add_argument(
        '--zones',
        nargs='+',
        help='Zones to scrape (portal-specific)'
    )
    parser.add_argument(
        '--postgres',
        action='store_true',
        help='Save results to PostgreSQL'
    )
    parser.add_argument(
        '--azure',
        action='store_true',
        help='Use Azure PostgreSQL instead of local Docker'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Run browser in headless mode (default: True)'
    )
    parser.add_argument(
        '--visible',
        action='store_true',
        help='Run browser in visible mode (for debugging)'
    )

    args = parser.parse_args()

    # Determine which portals to run
    if args.all:
        portals = list(PORTAL_RUNNERS.keys())
    elif args.portals:
        portals = args.portals
    else:
        parser.print_help()
        print("\nError: Must specify --all or --portals")
        sys.exit(1)

    # Get PostgreSQL config if needed
    postgres_config = None
    if args.postgres:
        import os
        # Detect if running inside Docker container
        inside_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER', False)
        postgres_config = get_postgres_config(use_azure=args.azure, inside_docker=inside_docker)
        logger.info(f"PostgreSQL: {postgres_config['host']}")

    # Headless mode
    headless = not args.visible

    # Run scrapers
    all_stats = {}
    for portal in portals:
        try:
            runner = PORTAL_RUNNERS[portal]
            stats = runner(
                zones=args.zones,
                postgres_config=postgres_config,
                headless=headless,
            )
            all_stats[portal] = stats
        except Exception as e:
            logger.error(f"Error running {portal}: {e}")
            all_stats[portal] = {'error': str(e)}

    # Summary
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    for portal, stats in all_stats.items():
        if 'error' in stats:
            print(f"[X] {portal}: ERROR - {stats['error']}")
        else:
            saved = stats.get('saved', stats.get('total', 0))
            filtered = stats.get('filtered_out', 0)
            print(f"[OK] {portal}: {saved} guardados, {filtered} filtrados")

    print("=" * 60)


if __name__ == '__main__':
    main()

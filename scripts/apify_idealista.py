#!/usr/bin/env python3
"""
Apify Idealista Scraper Integration.

Uses Apify's idealista-scraper actor to fetch listings and save to PostgreSQL.
Free tier: $5/month (~5,000-10,000 listings)

Usage:
    python scripts/apify_idealista.py --zone salou --max-items 50

Requires:
    APIFY_API_TOKEN: Your Apify API token
    DATABASE_URL: PostgreSQL connection string
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import requests
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Apify actor - Smart Idealista (free tier ~200/month)
ACTOR_ID = "sian.agency/smart-idealista-scraper"

# Zone to Idealista search URL mapping
ZONE_URLS = {
    "salou": "https://www.idealista.com/venta-viviendas/salou-tarragona/",
    "cambrils": "https://www.idealista.com/venta-viviendas/cambrils-tarragona/",
    "tarragona": "https://www.idealista.com/venta-viviendas/tarragona-tarragona/",
    "reus": "https://www.idealista.com/venta-viviendas/reus-tarragona/",
    "amposta": "https://www.idealista.com/venta-viviendas/amposta-tarragona/",
    "tortosa": "https://www.idealista.com/venta-viviendas/tortosa-tarragona/",
}


def run_apify_actor(api_token: str, zone: str, max_items: int = 50) -> list:
    """Run Apify actor and return results."""
    if zone not in ZONE_URLS:
        logger.error(f"Unknown zone: {zone}. Available: {list(ZONE_URLS.keys())}")
        return []

    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={api_token}"

    # Smart Idealista Scraper input format
    input_data = {
        "urls": [ZONE_URLS[zone]],
        "maxResults": max_items,
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        },
    }

    logger.info(f"Starting Apify actor for zone: {zone}")

    response = requests.post(url, json=input_data)
    if response.status_code != 201:
        logger.error(f"Failed to start actor: {response.text}")
        return []

    run_data = response.json()["data"]
    run_id = run_data["id"]
    logger.info(f"Actor started, run ID: {run_id}")

    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_token}"

    for _ in range(30):
        time.sleep(10)
        status = requests.get(status_url).json()["data"]["status"]
        logger.info(f"Actor status: {status}")

        if status == "SUCCEEDED":
            break
        elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            logger.error(f"Actor failed with status: {status}")
            return []

    dataset_id = run_data["defaultDatasetId"]
    results_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={api_token}"

    results = requests.get(results_url).json()
    logger.info(f"Retrieved {len(results)} listings")

    return results


def save_to_postgres(listings: list, zone: str, tenant_id: int = 1):
    """Save listings to raw.raw_listings."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        return 0

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    saved = 0
    for listing in listings:
        try:
            anuncio_id = listing.get("propertyCode") or listing.get("id", "")

            raw_data = {
                "anuncio_id": str(anuncio_id),
                "url": listing.get("url", ""),
                "titulo": listing.get("title", ""),
                "precio": listing.get("price", 0),
                "descripcion": listing.get("description", ""),
                "telefono": listing.get("phone", ""),
                "metros": listing.get("size", 0),
                "habitaciones": listing.get("rooms", 0),
                "banos": listing.get("bathrooms", 0),
                "zona": zone,
                "fotos": listing.get("images", []),
                "source": "apify",
            }

            cursor.execute("""
                INSERT INTO raw.raw_listings (tenant_id, portal, raw_data, scraping_timestamp)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
                WHERE raw_data->>'anuncio_id' IS NOT NULL
                DO NOTHING
            """, (tenant_id, "idealista", json.dumps(raw_data), datetime.now()))

            saved += 1
        except Exception as e:
            logger.warning(f"Error saving listing: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"Saved {saved} listings to PostgreSQL")
    return saved


def main():
    parser = argparse.ArgumentParser(description="Apify Idealista Scraper")
    parser.add_argument("--zone", required=True, help="Zone to scrape")
    parser.add_argument("--max-items", type=int, default=50, help="Max items to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to DB")
    args = parser.parse_args()

    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN not set")
        sys.exit(1)

    listings = run_apify_actor(api_token, args.zone, args.max_items)

    if not listings:
        logger.warning("No listings retrieved")
        sys.exit(0)

    if args.dry_run:
        print(json.dumps(listings[:3], indent=2))
    else:
        save_to_postgres(listings, args.zone)


if __name__ == "__main__":
    main()

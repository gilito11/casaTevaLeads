#!/usr/bin/env python3
"""Clear old data and run all scrapers for salou and cambrils."""
import os
import sys

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://inmoleadsadmin:ataulfo1!@inmoleads-db.postgres.database.azure.com:5432/inmoleadsdb?sslmode=require'
os.environ['SCRAPINGBEE_API_KEY'] = 'BBBEGEVLII2EIG4U6Q2Y9CNQ7M9CNBQ8SCLKX61REZDDHZI07MH1VO0RLDPKQ38XFS4GOHA1WMWLTE58'

import psycopg2

# Clear old data
print("=" * 60)
print("CLEARING OLD DATA")
print("=" * 60)
conn = psycopg2.connect(
    host='inmoleads-db.postgres.database.azure.com',
    database='inmoleadsdb',
    user='inmoleadsadmin',
    password='ataulfo1!',
    sslmode='require'
)
cur = conn.cursor()
cur.execute('DELETE FROM raw.raw_listings WHERE tenant_id = 1')
deleted_raw = cur.rowcount
cur.execute('DELETE FROM marts.dim_leads WHERE tenant_id = 1')
deleted_leads = cur.rowcount
conn.commit()
print(f"Deleted {deleted_raw} raw listings and {deleted_leads} leads")
conn.close()

zones = ['salou', 'cambrils']

# Run Habitaclia
print("\n" + "=" * 60)
print("HABITACLIA (Botasaurus)")
print("=" * 60)
try:
    from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia
    with BotasaurusHabitaclia(zones=zones, tenant_id=1, postgres_config={
        'host': 'inmoleads-db.postgres.database.azure.com',
        'database': 'inmoleadsdb',
        'user': 'inmoleadsadmin',
        'password': 'ataulfo1!',
        'sslmode': 'require'
    }) as scraper:
        scraper.scrape_and_save()
        print(f"Stats: {scraper.stats}")
except Exception as e:
    print(f"Error: {e}")

# Run Fotocasa
print("\n" + "=" * 60)
print("FOTOCASA (Botasaurus)")
print("=" * 60)
try:
    from scrapers.botasaurus_fotocasa import BotasaurusFotocasa
    with BotasaurusFotocasa(zones=zones, tenant_id=1, postgres_config={
        'host': 'inmoleads-db.postgres.database.azure.com',
        'database': 'inmoleadsdb',
        'user': 'inmoleadsadmin',
        'password': 'ataulfo1!',
        'sslmode': 'require'
    }) as scraper:
        scraper.scrape_and_save()
        print(f"Stats: {scraper.stats}")
except Exception as e:
    print(f"Error: {e}")

# Run Milanuncios (ScrapingBee)
print("\n" + "=" * 60)
print("MILANUNCIOS (ScrapingBee)")
print("=" * 60)
try:
    from scrapers.scrapingbee_milanuncios import ScrapingBeeMilanuncios
    with ScrapingBeeMilanuncios(zones=zones, tenant_id=1, max_pages_per_zone=2) as scraper:
        scraper.scrape_and_save()
        print(f"Stats: {scraper.get_stats()}")
except Exception as e:
    print(f"Error: {e}")

# Run Idealista (ScrapingBee)
print("\n" + "=" * 60)
print("IDEALISTA (ScrapingBee)")
print("=" * 60)
try:
    from scrapers.scrapingbee_idealista import ScrapingBeeIdealista
    with ScrapingBeeIdealista(zones=zones, tenant_id=1, max_pages_per_zone=2) as scraper:
        scraper.scrape_and_save()
        print(f"Stats: {scraper.get_stats()}")
except Exception as e:
    print(f"Error: {e}")

# Show results
print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
conn = psycopg2.connect(
    host='inmoleads-db.postgres.database.azure.com',
    database='inmoleadsdb',
    user='inmoleadsadmin',
    password='ataulfo1!',
    sslmode='require'
)
cur = conn.cursor()
cur.execute('SELECT portal, COUNT(*) FROM raw.raw_listings GROUP BY portal ORDER BY portal')
rows = cur.fetchall()
print("Raw listings by portal:")
for r in rows:
    print(f"  {r[0]}: {r[1]}")
conn.close()

print("\nDone!")

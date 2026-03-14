"""
Cleanup: Mark unverified idealista listings as es_particular=false.
Next dbt run will exclude them from dim_leads.
"""
import os
import sys
import psycopg2

def main():
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
    if not db_url:
        # Try Django settings
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'casa_teva.settings')
        import django
        django.setup()
        from django.conf import settings
        db = settings.DATABASES['default']
        db_url = f"postgresql://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"

    conn = psycopg2.connect(db_url, sslmode='require')
    cursor = conn.cursor()

    # 1. Count current state
    cursor.execute("""
        SELECT
            COALESCE((raw_data->>'es_particular')::boolean, true) as es_particular,
            COALESCE((raw_data->>'verified')::boolean, false) as verified,
            COUNT(*)
        FROM raw.raw_listings
        WHERE portal = 'idealista'
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)
    print("\n=== BEFORE: Idealista raw_listings status ===")
    for row in cursor.fetchall():
        print(f"  es_particular={row[0]}, verified={row[1]}: {row[2]} listings")

    # 2. Mark unverified idealista listings as NOT particular
    # These are from old scraper runs that defaulted to es_particular=true
    cursor.execute("""
        UPDATE raw.raw_listings
        SET raw_data = jsonb_set(raw_data, '{es_particular}', 'false')
        WHERE portal = 'idealista'
          AND COALESCE((raw_data->>'es_particular')::boolean, true) = true
          AND COALESCE((raw_data->>'verified')::boolean, false) = false
    """)
    updated = cursor.rowcount
    print(f"\n=== Updated {updated} unverified idealista listings to es_particular=false ===")

    conn.commit()

    # 3. Count after
    cursor.execute("""
        SELECT
            COALESCE((raw_data->>'es_particular')::boolean, true) as es_particular,
            COUNT(*)
        FROM raw.raw_listings
        WHERE portal = 'idealista'
        GROUP BY 1
        ORDER BY 1
    """)
    print("\n=== AFTER: Idealista raw_listings status ===")
    for row in cursor.fetchall():
        print(f"  es_particular={row[0]}: {row[1]} listings")

    cursor.close()
    conn.close()
    print("\nDone. Run dbt full-refresh to update dim_leads.")

if __name__ == '__main__':
    main()

import psycopg2

conn = psycopg2.connect(
    host="inmoleads-db.postgres.database.azure.com",
    user="inmoleadsadmin",
    password="ataulfo1!",
    dbname="inmoleadsdb",
    sslmode="require"
)
cur = conn.cursor()
cur.execute("""
SELECT nombre, slug, activa, portales
FROM zonas_geograficas
WHERE activa = true
ORDER BY nombre
""")
print("=== ZONAS ACTIVAS ===")
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]}) - Portales: {row[3]}")
conn.close()

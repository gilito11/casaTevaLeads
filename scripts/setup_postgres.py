#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para configurar PostgreSQL para Casa Teva Lead System.

Este script:
1. Verifica conexión a PostgreSQL
2. Crea schemas necesarios (raw, staging, marts, analytics)
3. Crea tabla raw.raw_listings
4. Crea índices
5. Verifica todo está OK

Uso:
    python scripts/setup_postgres.py
    python scripts/setup_postgres.py --drop-all  # Recrear todo desde cero
"""

import sys
import os
import argparse
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ ERROR: psycopg2 no está instalado")
    print("Instala con: pip install psycopg2-binary")
    sys.exit(1)

# Configuración de conexión (desde .env o defaults)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'casa_teva_db'),
    'user': os.getenv('DB_USER', 'casa_teva'),
    'password': os.getenv('DB_PASSWORD', 'casateva2024'),
}


def test_connection():
    """Prueba conexión a PostgreSQL"""
    print("\n🔍 Verificando conexión a PostgreSQL...")
    print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"   Database: {DB_CONFIG['database']}")
    print(f"   User: {DB_CONFIG['user']}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Verificar versión
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Conexión exitosa!")
        print(f"   PostgreSQL: {version.split(',')[0]}")

        cursor.close()
        conn.close()
        return True

    except psycopg2.OperationalError as e:
        print(f"❌ ERROR de conexión: {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verifica que PostgreSQL está corriendo")
        print("   2. Verifica las credenciales en .env")
        print("   3. Crea la base de datos si no existe:")
        print(f"      createdb -U postgres {DB_CONFIG['database']}")
        return False


def create_schemas(conn, drop_existing=False):
    """Crea schemas necesarios"""
    print("\n📁 Creando schemas...")

    cursor = conn.cursor()

    schemas = ['raw', 'staging', 'marts', 'analytics']

    for schema in schemas:
        try:
            if drop_existing:
                print(f"   ⚠️  Eliminando schema {schema} (si existe)...")
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE;")

            print(f"   📂 Creando schema: {schema}")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")

        except Exception as e:
            print(f"   ❌ Error creando schema {schema}: {e}")
            return False

    conn.commit()
    print("✅ Schemas creados exitosamente")
    return True


def create_raw_listings_table(conn):
    """Crea tabla raw.raw_listings"""
    print("\n📋 Creando tabla raw.raw_listings...")

    cursor = conn.cursor()

    # Crear tabla
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS raw.raw_listings (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL,
        portal VARCHAR(50) NOT NULL,

        -- Data Lake reference
        data_lake_path TEXT NOT NULL,

        -- Datos raw en JSONB
        raw_data JSONB NOT NULL,

        -- Timestamps
        scraping_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),

        -- Constraints
        CONSTRAINT valid_portal CHECK (portal IN ('fotocasa', 'milanuncios', 'wallapop', 'pisos', 'habitaclia', 'idealista'))
    );
    """

    try:
        cursor.execute(create_table_sql)
        print("✅ Tabla raw.raw_listings creada")
    except Exception as e:
        print(f"❌ Error creando tabla: {e}")
        return False

    # Crear índices
    print("   📑 Creando índices...")

    indices = [
        "CREATE INDEX IF NOT EXISTS idx_raw_listings_tenant ON raw.raw_listings(tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_raw_listings_portal ON raw.raw_listings(portal);",
        "CREATE INDEX IF NOT EXISTS idx_raw_listings_scraping_ts ON raw.raw_listings(scraping_timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_raw_listings_tenant_portal ON raw.raw_listings(tenant_id, portal);",
        # GIN index para búsquedas en JSONB
        "CREATE INDEX IF NOT EXISTS idx_raw_listings_raw_data ON raw.raw_listings USING GIN (raw_data);",
    ]

    for idx_sql in indices:
        try:
            cursor.execute(idx_sql)
        except Exception as e:
            print(f"   ⚠️  Error creando índice: {e}")

    conn.commit()
    print("✅ Índices creados")
    return True


def grant_permissions(conn):
    """Otorga permisos a schemas y tablas"""
    print("\n🔐 Configurando permisos...")

    cursor = conn.cursor()
    user = DB_CONFIG['user']

    try:
        # Permisos en schemas
        for schema in ['raw', 'staging', 'marts', 'analytics']:
            cursor.execute(f"GRANT USAGE ON SCHEMA {schema} TO {user};")
            cursor.execute(f"GRANT CREATE ON SCHEMA {schema} TO {user};")
            cursor.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema} TO {user};")
            cursor.execute(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema} TO {user};")

            # Permisos por defecto para tablas futuras
            cursor.execute(f"""
                ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
                GRANT ALL PRIVILEGES ON TABLES TO {user};
            """)

        conn.commit()
        print(f"✅ Permisos otorgados a usuario '{user}'")
        return True

    except Exception as e:
        print(f"⚠️  Error configurando permisos: {e}")
        return False


def verify_setup(conn):
    """Verifica que todo esté correctamente configurado"""
    print("\n✅ Verificando configuración...")

    cursor = conn.cursor()

    # Verificar schemas
    cursor.execute("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name IN ('raw', 'staging', 'marts', 'analytics')
        ORDER BY schema_name;
    """)
    schemas = [row[0] for row in cursor.fetchall()]
    print(f"   📁 Schemas encontrados: {', '.join(schemas)}")

    # Verificar tabla raw.raw_listings
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'raw'
            AND table_name = 'raw_listings'
        );
    """)
    table_exists = cursor.fetchone()[0]
    print(f"   📋 Tabla raw.raw_listings: {'✅ Existe' if table_exists else '❌ No existe'}")

    # Contar índices
    cursor.execute("""
        SELECT COUNT(*)
        FROM pg_indexes
        WHERE schemaname = 'raw'
        AND tablename = 'raw_listings';
    """)
    num_indices = cursor.fetchone()[0]
    print(f"   📑 Índices en raw.raw_listings: {num_indices}")

    cursor.close()

    if len(schemas) == 4 and table_exists:
        print("\n🎉 Setup completado exitosamente!")
        return True
    else:
        print("\n⚠️  Setup incompleto. Revisa los errores arriba.")
        return False


def main():
    parser = argparse.ArgumentParser(description='Setup PostgreSQL para Casa Teva')
    parser.add_argument(
        '--drop-all',
        action='store_true',
        help='Eliminar schemas existentes antes de crear (⚠️ PELIGROSO)'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  SETUP POSTGRESQL - Casa Teva Lead System")
    print("=" * 60)

    # Test conexión
    if not test_connection():
        print("\n❌ Setup abortado. Arregla la conexión primero.")
        sys.exit(1)

    # Confirmar si drop-all
    if args.drop_all:
        print("\n⚠️  ADVERTENCIA: Vas a ELIMINAR todos los schemas existentes!")
        respuesta = input("¿Estás seguro? Escribe 'SI' para continuar: ")
        if respuesta != 'SI':
            print("Operación cancelada.")
            sys.exit(0)

    # Conectar
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    try:
        # Crear schemas
        if not create_schemas(conn, drop_existing=args.drop_all):
            sys.exit(1)

        # Crear tabla raw.raw_listings
        if not create_raw_listings_table(conn):
            sys.exit(1)

        # Configurar permisos
        grant_permissions(conn)

        # Verificar
        if verify_setup(conn):
            print("\n" + "=" * 60)
            print("  ✅ PostgreSQL está listo para Casa Teva!")
            print("=" * 60)
            print("\n📝 Próximos pasos:")
            print("   1. Ejecutar migraciones Django: cd backend && python manage.py migrate")
            print("   2. Ejecutar dbt: cd dbt_project && dbt run")
            print("   3. Verificar datos: psql -U casa_teva -d casa_teva_db")
        else:
            sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    main()

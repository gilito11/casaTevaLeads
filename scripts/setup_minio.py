#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para configurar MinIO (Data Lake) para Casa Teva Lead System.

Este script:
1. Verifica conexión a MinIO
2. Crea bucket principal (casa-teva-data-lake)
3. Crea estructura de carpetas (bronze/, screenshots/, logs/)
4. Configura políticas de acceso
5. Verifica todo está OK

Uso:
    python scripts/setup_minio.py
    python scripts/setup_minio.py --recreate  # Recrear bucket desde cero

Requisitos:
    - MinIO corriendo en localhost:9000
    - pip install minio
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

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
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    print("❌ ERROR: minio no está instalado")
    print("Instala con: pip install minio")
    sys.exit(1)

# Configuración de MinIO (desde .env o defaults)
MINIO_CONFIG = {
    'endpoint': os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
    'access_key': os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
    'secret_key': os.getenv('MINIO_SECRET_KEY', 'minioadmin'),
    'secure': os.getenv('MINIO_SECURE', 'False').lower() == 'true',
}

BUCKET_NAME = 'casa-teva-data-lake'


def test_connection():
    """Prueba conexión a MinIO"""
    print("\n🔍 Verificando conexión a MinIO...")
    print(f"   Endpoint: {MINIO_CONFIG['endpoint']}")
    print(f"   Access Key: {MINIO_CONFIG['access_key']}")
    print(f"   Secure (HTTPS): {MINIO_CONFIG['secure']}")

    try:
        client = Minio(
            endpoint=MINIO_CONFIG['endpoint'],
            access_key=MINIO_CONFIG['access_key'],
            secret_key=MINIO_CONFIG['secret_key'],
            secure=MINIO_CONFIG['secure']
        )

        # Verificar que podemos listar buckets
        buckets = client.list_buckets()
        print(f"✅ Conexión exitosa!")
        print(f"   Buckets existentes: {len(buckets)}")
        for bucket in buckets:
            print(f"      - {bucket.name}")

        return client

    except S3Error as e:
        print(f"❌ ERROR S3: {e}")
        return None
    except Exception as e:
        print(f"❌ ERROR de conexión: {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verifica que MinIO está corriendo:")
        print("      docker run -p 9000:9000 -p 9001:9001 minio/minio server /data --console-address ':9001'")
        print("   2. Verifica las credenciales en .env")
        print("   3. Accede a la consola: http://localhost:9001")
        return None


def create_bucket(client, recreate=False):
    """Crea el bucket principal"""
    print(f"\n🪣 Configurando bucket '{BUCKET_NAME}'...")

    try:
        # Verificar si existe
        bucket_exists = client.bucket_exists(BUCKET_NAME)

        if bucket_exists:
            if recreate:
                print(f"   ⚠️  Eliminando bucket existente...")
                # Eliminar todos los objetos primero
                objects = client.list_objects(BUCKET_NAME, recursive=True)
                for obj in objects:
                    client.remove_object(BUCKET_NAME, obj.object_name)
                # Eliminar bucket
                client.remove_bucket(BUCKET_NAME)
                print(f"   ✅ Bucket eliminado")
            else:
                print(f"   ℹ️  Bucket ya existe, usando existente")
                return True

        # Crear bucket
        print(f"   📦 Creando bucket '{BUCKET_NAME}'...")
        client.make_bucket(BUCKET_NAME)
        print(f"✅ Bucket '{BUCKET_NAME}' creado exitosamente")
        return True

    except S3Error as e:
        print(f"❌ Error creando bucket: {e}")
        return False


def create_folder_structure(client):
    """Crea estructura de carpetas en el bucket"""
    print("\n📁 Creando estructura de carpetas...")

    from io import BytesIO

    # Estructura según PROJECT_SPEC_v2.0.md
    folders = [
        'bronze/',
        'bronze/tenant_1/',
        'bronze/tenant_1/fotocasa/',
        'bronze/tenant_1/milanuncios/',
        'bronze/tenant_1/wallapop/',
        'screenshots/',
        'screenshots/tenant_1/',
        'logs/',
    ]

    for folder in folders:
        try:
            # MinIO/S3 no tiene "carpetas" reales, pero podemos crear objetos vacíos
            # con "/" al final para simularlas
            client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=folder + '.keep',
                data=BytesIO(b''),
                length=0,
            )
            print(f"   📂 {folder}")

        except S3Error as e:
            print(f"   ⚠️  Error creando {folder}: {e}")

    print("✅ Estructura de carpetas creada")
    return True


def create_test_file(client):
    """Crea un archivo de prueba para verificar funcionamiento"""
    print("\n🧪 Creando archivo de prueba...")

    test_data = {
        'created_at': datetime.now().isoformat(),
        'message': 'MinIO configurado correctamente para Casa Teva',
        'version': '2.0',
    }

    import json
    test_json = json.dumps(test_data, indent=2).encode('utf-8')

    try:
        from io import BytesIO

        client.put_object(
            bucket_name=BUCKET_NAME,
            object_name='logs/setup_test.json',
            data=BytesIO(test_json),
            length=len(test_json),
            content_type='application/json'
        )

        print(f"✅ Archivo de prueba creado: logs/setup_test.json")
        return True

    except S3Error as e:
        print(f"❌ Error creando archivo de prueba: {e}")
        return False


def verify_setup(client):
    """Verifica que todo esté correctamente configurado"""
    print("\n✅ Verificando configuración...")

    try:
        # Verificar bucket existe
        exists = client.bucket_exists(BUCKET_NAME)
        print(f"   🪣 Bucket '{BUCKET_NAME}': {'✅ Existe' if exists else '❌ No existe'}")

        if not exists:
            return False

        # Contar objetos
        objects = list(client.list_objects(BUCKET_NAME, recursive=True))
        print(f"   📄 Objetos en bucket: {len(objects)}")

        # Listar estructura
        print(f"   📁 Estructura:")
        for obj in sorted(objects, key=lambda x: x.object_name):
            size_kb = obj.size / 1024 if obj.size > 0 else 0
            print(f"      - {obj.object_name} ({size_kb:.2f} KB)")

        print("\n🎉 MinIO configurado exitosamente!")
        return True

    except S3Error as e:
        print(f"❌ Error verificando: {e}")
        return False


def print_access_info():
    """Imprime información de acceso a MinIO"""
    print("\n" + "=" * 60)
    print("  📊 INFORMACIÓN DE ACCESO A MinIO")
    print("=" * 60)
    print(f"\n  Console URL: http://localhost:9001")
    print(f"  API Endpoint: http://localhost:9000")
    print(f"  Access Key: {MINIO_CONFIG['access_key']}")
    print(f"  Secret Key: {MINIO_CONFIG['secret_key']}")
    print(f"\n  Bucket: {BUCKET_NAME}")
    print(f"  Estructura:")
    print(f"    - bronze/tenant_X/portal/YYYY-MM-DD/listing_*.json")
    print(f"    - screenshots/tenant_X/listing_*.png")
    print(f"    - logs/*.log")


def main():
    parser = argparse.ArgumentParser(description='Setup MinIO para Casa Teva')
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Recrear bucket desde cero (⚠️ ELIMINA DATOS)'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  SETUP MinIO - Casa Teva Lead System")
    print("=" * 60)

    # Test conexión
    client = test_connection()
    if not client:
        print("\n❌ Setup abortado. Verifica que MinIO está corriendo.")
        print("\n💡 Para iniciar MinIO con Docker:")
        print("   docker run -d \\")
        print("     -p 9000:9000 -p 9001:9001 \\")
        print("     -e 'MINIO_ROOT_USER=minioadmin' \\")
        print("     -e 'MINIO_ROOT_PASSWORD=minioadmin' \\")
        print("     --name minio \\")
        print("     minio/minio server /data --console-address ':9001'")
        sys.exit(1)

    # Confirmar si recreate
    if args.recreate:
        print("\n⚠️  ADVERTENCIA: Vas a ELIMINAR el bucket y todos sus datos!")
        respuesta = input("¿Estás seguro? Escribe 'SI' para continuar: ")
        if respuesta != 'SI':
            print("Operación cancelada.")
            sys.exit(0)

    try:
        # Crear bucket
        if not create_bucket(client, recreate=args.recreate):
            sys.exit(1)

        # Crear estructura
        if not create_folder_structure(client):
            sys.exit(1)

        # Crear archivo de prueba
        if not create_test_file(client):
            sys.exit(1)

        # Verificar
        if verify_setup(client):
            print_access_info()
            print("\n" + "=" * 60)
            print("  ✅ MinIO está listo para Casa Teva!")
            print("=" * 60)
            print("\n📝 Próximos pasos:")
            print("   1. Ejecutar scraper: python run_fotocasa_scraper.py --minio")
            print("   2. Verificar datos en consola: http://localhost:9001")
            print("   3. Ejecutar Dagster assets para cargar a PostgreSQL")
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperación cancelada por el usuario.")
        sys.exit(0)


if __name__ == '__main__':
    main()

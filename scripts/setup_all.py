#!/usr/bin/env python
"""
Script maestro para configurar TODA la infraestructura de Casa Teva.

Este script ejecuta:
1. Setup PostgreSQL (schemas + tablas)
2. Setup MinIO (bucket + estructura)
3. Verifica todo está listo

Uso:
    python scripts/setup_all.py
    python scripts/setup_all.py --reset  # Recrear todo desde cero
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

project_root = Path(__file__).parent.parent


def print_header(title):
    """Imprime un header bonito"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def run_script(script_name, args=None):
    """Ejecuta un script Python y retorna el código de salida"""
    script_path = project_root / 'scripts' / script_name
    cmd = [sys.executable, str(script_path)]

    if args:
        cmd.extend(args)

    print(f"🚀 Ejecutando: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"❌ Error ejecutando {script_name}: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Setup completo de infraestructura para Casa Teva'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Recrear toda la infraestructura desde cero (⚠️ PELIGROSO)'
    )
    parser.add_argument(
        '--skip-postgres',
        action='store_true',
        help='Saltar setup de PostgreSQL'
    )
    parser.add_argument(
        '--skip-minio',
        action='store_true',
        help='Saltar setup de MinIO'
    )
    args = parser.parse_args()

    print_header("SETUP COMPLETO - Casa Teva Lead System v2.0")

    if args.reset:
        print("⚠️  MODO RESET: Se recreará toda la infraestructura")
        print("⚠️  Esto ELIMINARÁ todos los datos existentes")
        respuesta = input("\n¿Continuar? Escribe 'SI ESTOY SEGURO': ")
        if respuesta != 'SI ESTOY SEGURO':
            print("Operación cancelada.")
            sys.exit(0)

    success = True

    # 1. Setup PostgreSQL
    if not args.skip_postgres:
        print_header("PASO 1/2: PostgreSQL Setup")
        postgres_args = ['--drop-all'] if args.reset else []
        returncode = run_script('setup_postgres.py', postgres_args)

        if returncode != 0:
            print("\n❌ PostgreSQL setup falló")
            success = False
        else:
            print("\n✅ PostgreSQL configurado correctamente")
    else:
        print_header("PASO 1/2: PostgreSQL Setup (SALTADO)")

    # 2. Setup MinIO
    if not args.skip_minio:
        print_header("PASO 2/2: MinIO Setup")
        minio_args = ['--recreate'] if args.reset else []
        returncode = run_script('setup_minio.py', minio_args)

        if returncode != 0:
            print("\n❌ MinIO setup falló")
            success = False
        else:
            print("\n✅ MinIO configurado correctamente")
    else:
        print_header("PASO 2/2: MinIO Setup (SALTADO)")

    # Resumen final
    print_header("RESUMEN FINAL")

    if success:
        print("🎉 ¡SETUP COMPLETADO EXITOSAMENTE!")
        print("\n📊 Infraestructura lista:")
        print("   ✅ PostgreSQL: Schemas + raw.raw_listings")
        print("   ✅ MinIO: Bucket + estructura bronze/")
        print("\n📝 Próximos pasos:")
        print("   1. Ejecutar migraciones Django:")
        print("      cd backend && python manage.py migrate")
        print("\n   2. Ejecutar dbt:")
        print("      cd dbt_project && dbt run")
        print("\n   3. Test scraper → MinIO:")
        print("      python run_fotocasa_scraper.py --tenant-id=1 --minio")
        print("\n   4. Ejecutar Dagster:")
        print("      dagster dev -f dagster/workspace.yaml")
        print("\n   5. Verificar datos:")
        print("      psql -U casa_teva -d casa_teva_db -c 'SELECT COUNT(*) FROM marts.dim_leads;'")

        print("\n🌐 URLs útiles:")
        print("   - MinIO Console: http://localhost:9001")
        print("   - Dagster UI: http://localhost:3000")
        print("   - Django Admin: http://localhost:8000/admin")

    else:
        print("❌ SETUP INCOMPLETO")
        print("\nRevisa los errores arriba y vuelve a ejecutar.")
        sys.exit(1)


if __name__ == '__main__':
    main()

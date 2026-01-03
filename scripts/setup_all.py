#!/usr/bin/env python
"""
Script maestro para configurar la infraestructura de Casa Teva.

Este script ejecuta:
1. Setup PostgreSQL (schemas + tablas)
2. Verifica todo está listo

Nota: MinIO fue eliminado del proyecto. Los datos se guardan directamente
en PostgreSQL como JSONB. Ver INSTRUCCIONES_SETUP.md para más detalles.

Uso:
    python scripts/setup_all.py
    python scripts/setup_all.py --reset  # Recrear todo desde cero
"""

import sys
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

    print(f"Ejecutando: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error ejecutando {script_name}: {e}")
        return 1


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Setup completo de infraestructura para Casa Teva'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Recrear toda la infraestructura desde cero (PELIGROSO)'
    )
    args = parser.parse_args()

    print_header("SETUP - Casa Teva Lead System")

    if args.reset:
        print("MODO RESET: Se recreará toda la infraestructura")
        print("Esto ELIMINARÁ todos los datos existentes")
        respuesta = input("\n¿Continuar? Escribe 'SI ESTOY SEGURO': ")
        if respuesta != 'SI ESTOY SEGURO':
            print("Operación cancelada.")
            sys.exit(0)

    # Setup PostgreSQL
    print_header("PostgreSQL Setup")
    postgres_args = ['--drop-all'] if args.reset else []
    returncode = run_script('setup_postgres.py', postgres_args)

    if returncode != 0:
        print("\nPostgreSQL setup falló")
        sys.exit(1)

    print("\nPostgreSQL configurado correctamente")

    # Resumen final
    print_header("RESUMEN FINAL")

    print("SETUP COMPLETADO EXITOSAMENTE!")
    print("\nInfraestructura lista:")
    print("   - PostgreSQL: Schemas + raw.raw_listings (JSONB)")
    print("\nPróximos pasos:")
    print("   1. Ejecutar migraciones Django:")
    print("      cd backend && python manage.py migrate")
    print("\n   2. Ejecutar dbt:")
    print("      cd dbt_project && dbt run")
    print("\n   3. Test scraper:")
    print("      python run_all_scrapers.py --zones salou --postgres")
    print("\n   4. Iniciar servicios:")
    print("      docker-compose up -d")

    print("\nURLs útiles:")
    print("   - Django Web: http://localhost:8000")
    print("   - Dagster UI: http://localhost:3000")


if __name__ == '__main__':
    main()

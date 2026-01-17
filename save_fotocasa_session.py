#!/usr/bin/env python
"""
Script para guardar sesion de Fotocasa manualmente.

1. Abre el navegador
2. Tu haces login manualmente en Fotocasa
3. Cuando termines, presiona Enter en la consola
4. El script guarda las cookies en PostgreSQL Azure

Uso:
    python save_fotocasa_session.py [--local]

    --local: Guardar solo en archivo local (no PostgreSQL)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# Para conexion a PostgreSQL
import psycopg2
from urllib.parse import urlparse

COOKIES_DIR = Path(__file__).parent / "scrapers/contact_automation/cookies"
COOKIES_FILE = COOKIES_DIR / "fotocasa_cookies.json"

# Azure PostgreSQL
AZURE_DB_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://inmoleadsadmin@inmoleads-db.postgres.database.azure.com/inmoleadsdb?sslmode=require'
)


def save_to_postgres(cookies: list, email: str) -> bool:
    """Guarda las cookies en PostgreSQL Azure."""
    try:
        parsed = urlparse(AZURE_DB_URL)

        # Pedir password si no está en la URL
        password = parsed.password
        if not password:
            password = input("Password PostgreSQL Azure: ").strip()

        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip('/').split('?')[0],
            user=parsed.username,
            password=password,
            sslmode='require'
        )

        cursor = conn.cursor()

        # Upsert en leads_portal_session
        cursor.execute("""
            INSERT INTO leads_portal_session
                (tenant_id, portal, email, cookies, is_valid, created_at, updated_at, expires_at)
            VALUES
                (1, 'fotocasa', %s, %s, true, NOW(), NOW(), %s)
            ON CONFLICT (tenant_id, portal)
            DO UPDATE SET
                email = EXCLUDED.email,
                cookies = EXCLUDED.cookies,
                is_valid = true,
                updated_at = NOW(),
                expires_at = EXCLUDED.expires_at
        """, (
            email,
            json.dumps(cookies),
            datetime.now() + timedelta(days=30)  # Expira en 30 días
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"\n[ERROR] No se pudo guardar en PostgreSQL: {e}")
        return False


async def main():
    local_only = '--local' in sys.argv

    print("\n" + "="*60)
    print("GUARDAR SESION DE FOTOCASA")
    print("="*60)

    if local_only:
        print("[MODE] Solo archivo local")
    else:
        print("[MODE] PostgreSQL Azure + archivo local")

    COOKIES_DIR.mkdir(parents=True, exist_ok=True)

    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )

    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        locale='es-ES',
        timezone_id='Europe/Madrid',
    )

    page = await context.new_page()

    print("\n[1] Abriendo Fotocasa...")
    await page.goto("https://www.fotocasa.es/es/")
    await asyncio.sleep(2)

    print("\n" + "-"*60)
    print("INSTRUCCIONES:")
    print("-"*60)
    print("1. Acepta las cookies si aparece el dialogo")
    print("2. Haz clic en 'Acceder' o 'Iniciar sesion'")
    print("3. Introduce tu email y contrasena")
    print("4. Completa el login")
    print("5. Verifica que estas logueado (ves tu nombre/avatar)")
    print("-"*60)

    input("\n>>> Presiona ENTER cuando hayas completado el login... ")

    # Preguntar email usado
    email = input("Email de Fotocasa usado: ").strip()
    if not email:
        email = "unknown@example.com"

    # Save cookies
    cookies = await context.cookies()

    # Guardar en archivo local
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    print(f"\n[OK] Guardadas {len(cookies)} cookies en archivo local:")
    print(f"     {COOKIES_FILE}")

    # Guardar en PostgreSQL Azure
    if not local_only:
        print("\n[2] Guardando en PostgreSQL Azure...")
        if save_to_postgres(cookies, email):
            print("[OK] Cookies guardadas en PostgreSQL Azure")
        else:
            print("[WARN] No se pudieron guardar en PostgreSQL")
            print("       Pero el archivo local está disponible.")

    await browser.close()
    await playwright.stop()

    print("\n" + "="*60)
    print("[OK] Sesion de Fotocasa guardada")
    print("="*60 + "\n")


if __name__ == '__main__':
    asyncio.run(main())

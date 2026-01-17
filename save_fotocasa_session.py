#!/usr/bin/env python
"""
Script para guardar sesion de Fotocasa manualmente.

1. Abre el navegador
2. Tu haces login manualmente en Fotocasa
3. Cuando termines, presiona Enter en la consola
4. El script guarda las cookies para uso futuro

Uso:
    python save_fotocasa_session.py
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

COOKIES_DIR = Path(__file__).parent / "scrapers/contact_automation/cookies"
COOKIES_FILE = COOKIES_DIR / "fotocasa_cookies.json"


async def main():
    print("\n" + "="*60)
    print("GUARDAR SESION DE FOTOCASA")
    print("="*60)

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

    # Save cookies
    cookies = await context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))

    print(f"\n[OK] Guardadas {len(cookies)} cookies en:")
    print(f"     {COOKIES_FILE}")

    await browser.close()
    await playwright.stop()

    print("\n[OK] Ahora puedes usar test_fotocasa_contact.py")
    print("     Las cookies se cargaran automaticamente.")
    print("="*60 + "\n")


if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python
"""
Script para capturar cookies de Milanuncios manualmente.

Uso:
    python scrapers/capture_cookies.py

Este script abre un navegador visible donde puedes:
1. Navegar a Milanuncios
2. Resolver el captcha si aparece
3. Navegar por la web normalmente
4. Cuando termines, cierra el navegador o presiona Ctrl+C

Las cookies se guardan en 'milanuncios_cookies.json' para usar en el scraper.
"""

import asyncio
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'milanuncios_cookies.json')


async def capture_cookies():
    """Abre navegador para capturar cookies manualmente."""

    print("=" * 60)
    print("CAPTURA DE COOKIES DE MILANUNCIOS")
    print("=" * 60)
    print()
    print("Se abrirá un navegador. Por favor:")
    print("  1. Navega a Milanuncios")
    print("  2. Resuelve el captcha si aparece")
    print("  3. Navega un poco por la web (busca algo)")
    print("  4. Cuando termines, CIERRA EL NAVEGADOR")
    print()
    print(f"Las cookies se guardarán en: {COOKIES_FILE}")
    print("=" * 60)
    print()

    async with async_playwright() as p:
        # Lanzar navegador en modo VISIBLE (headful)
        browser = await p.chromium.launch(
            headless=False,  # VISIBLE
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
            ]
        )

        # Crear contexto con configuración realista
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='es-ES',
            timezone_id='Europe/Madrid',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ),
            # No cargar cookies previas - empezar limpio
        )

        # Anti-detección
        page = await context.new_page()
        await page.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['es-ES', 'es', 'en']});
            window.chrome = {runtime: {}};
        ''')

        # Navegar a Milanuncios
        print("Navegando a Milanuncios...")
        await page.goto('https://www.milanuncios.com/inmobiliaria/')

        print()
        print(">>> El navegador está abierto. Resuelve el captcha y navega.")
        print(">>> Cuando termines, CIERRA EL NAVEGADOR para guardar las cookies.")
        print()

        # Esperar a que el usuario cierre el navegador
        try:
            # Esperar indefinidamente hasta que se cierre
            await page.wait_for_event('close', timeout=0)
        except Exception:
            pass

        # Intentar guardar cookies antes de cerrar
        try:
            # Guardar el estado del contexto (cookies + localStorage)
            await context.storage_state(path=COOKIES_FILE)
            print()
            print(f"Cookies guardadas en: {COOKIES_FILE}")
            print("Ahora puedes ejecutar el scraper con: python run_all_scrapers.py")
        except Exception as e:
            print(f"Error guardando cookies: {e}")

        await browser.close()


async def main():
    """Función principal."""
    try:
        await capture_cookies()
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    asyncio.run(main())

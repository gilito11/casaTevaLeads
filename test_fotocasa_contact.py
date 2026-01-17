#!/usr/bin/env python
"""
Script para probar el contacto automático de Fotocasa.

SETUP:
1. Instalar dependencias:
   pip install playwright playwright-stealth
   playwright install firefox

2. Configurar credenciales (en .env o como variables de entorno):
   FOTOCASA_EMAIL=tu_email@ejemplo.com
   FOTOCASA_PASSWORD=tu_contraseña
   CONTACT_PHONE=600123456  (tu teléfono para que te contacten)

3. Ejecutar en modo visual (sin headless) la primera vez para hacer login manual si es necesario:
   python test_fotocasa_contact.py --url <URL_ANUNCIO>

USO:
   # Primera ejecución - login y guardar sesión (sin headless)
   python test_fotocasa_contact.py --url https://fotocasa.es/es/comprar/vivienda/... --login

   # Siguientes ejecuciones - usa sesión guardada
   python test_fotocasa_contact.py --url https://fotocasa.es/es/comprar/vivienda/...

   # Solo extraer teléfono (sin enviar mensaje)
   python test_fotocasa_contact.py --url https://fotocasa.es/es/comprar/vivienda/... --phone-only
"""

import asyncio
import os
import sys
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from scrapers.contact_automation.fotocasa_contact import FotocasaContact

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description='Test Fotocasa Contact Automation')
    parser.add_argument('--url', required=True, help='URL del anuncio en Fotocasa')
    parser.add_argument('--message',
                        default='Hola, me interesa este inmueble. ¿Estaría disponible para una visita? Gracias.',
                        help='Mensaje a enviar')
    parser.add_argument('--headless', action='store_true',
                        help='Ejecutar sin ventana (modo invisible)')
    parser.add_argument('--login', action='store_true',
                        help='Forzar login (ignora sesión guardada)')
    parser.add_argument('--phone-only', action='store_true',
                        help='Solo extraer teléfono, no enviar mensaje')

    args = parser.parse_args()

    # Verificar credenciales
    if not os.getenv('FOTOCASA_EMAIL') or not os.getenv('FOTOCASA_PASSWORD'):
        print("\n⚠️  CONFIGURACIÓN REQUERIDA:")
        print("   Crea un archivo .env con:")
        print("   FOTOCASA_EMAIL=tu_email@ejemplo.com")
        print("   FOTOCASA_PASSWORD=tu_contraseña")
        print("   CONTACT_PHONE=600123456")
        print("\n   O ejecuta con las variables de entorno configuradas.\n")
        return

    print("\n" + "="*60)
    print("🏠 FOTOCASA CONTACT AUTOMATION - TEST")
    print("="*60)
    print(f"URL: {args.url}")
    print(f"Headless: {args.headless}")
    print(f"Solo teléfono: {args.phone_only}")
    print("="*60 + "\n")

    contact = FotocasaContact(headless=args.headless)

    try:
        print("🔧 Iniciando navegador...")
        await contact.setup_browser()

        # Check/perform login
        if args.login:
            print("🔑 Forzando login...")
            success = await contact.login()
            if not success:
                print("❌ Login fallido. Verifica credenciales.")
                return
        else:
            print("🔍 Verificando sesión guardada...")
            if not await contact.is_logged_in():
                print("🔑 Sesión expirada, haciendo login...")
                success = await contact.login()
                if not success:
                    print("❌ Login fallido. Verifica credenciales.")
                    return
            else:
                print("✅ Sesión activa")

        # Navigate to listing
        print(f"\n📄 Abriendo anuncio...")
        await contact.page.goto(args.url, wait_until='networkidle')
        await asyncio.sleep(2)

        # Get seller name
        seller = await contact.get_seller_name()
        if seller:
            print(f"👤 Vendedor: {seller}")

        # Extract phone
        print("\n📞 Intentando extraer teléfono...")
        phone = await contact.extract_phone(args.url)
        if phone:
            print(f"✅ Teléfono extraído: {phone}")
        else:
            print("⚠️  No se pudo extraer el teléfono")

        # Send message if not phone-only
        if not args.phone_only:
            print(f"\n✉️  Enviando mensaje...")
            print(f"   Mensaje: {args.message[:50]}...")

            success = await contact.send_message(args.url, args.message)
            if success:
                print("✅ ¡Mensaje enviado correctamente!")
            else:
                print("❌ Error al enviar mensaje")

        # Summary
        print("\n" + "="*60)
        print("📊 RESUMEN")
        print("="*60)
        print(f"Vendedor: {seller or 'No encontrado'}")
        print(f"Teléfono: {phone or 'No extraído'}")
        if not args.phone_only:
            print(f"Mensaje: {'Enviado ✓' if success else 'Fallido ✗'}")
        print("="*60 + "\n")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        print("🔧 Cerrando navegador...")
        await contact.close()


if __name__ == '__main__':
    asyncio.run(main())

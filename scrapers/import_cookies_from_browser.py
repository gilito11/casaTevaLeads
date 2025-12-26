#!/usr/bin/env python
"""
Importar cookies desde el navegador Chrome.

Instrucciones:
1. Abre Chrome y ve a https://www.milanuncios.com/inmobiliaria/
2. Resuelve el captcha si aparece
3. Presiona F12 -> Application -> Cookies -> www.milanuncios.com
4. En la consola de DevTools (pestaña Console), ejecuta:

   JSON.stringify(
     document.cookie.split(';').map(c => {
       const [name, ...rest] = c.trim().split('=');
       return {name, value: rest.join('='), domain: '.milanuncios.com', path: '/'};
     })
   )

5. Copia el resultado y pégalo cuando ejecutes este script
"""

import json
import os

COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'milanuncios_cookies.json')


def main():
    print("=" * 60)
    print("IMPORTAR COOKIES DE MILANUNCIOS")
    print("=" * 60)
    print()
    print("1. Abre Chrome y ve a: https://www.milanuncios.com/inmobiliaria/")
    print("2. Resuelve el captcha si aparece")
    print("3. Presiona F12 -> Console")
    print("4. Pega este comando y presiona Enter:")
    print()
    print('   copy(JSON.stringify(document.cookie.split(";").map(c=>{const [n,...r]=c.trim().split("=");return{name:n,value:r.join("="),domain:".milanuncios.com",path:"/"}})))')
    print()
    print("5. Las cookies se copiarán al portapapeles")
    print("6. Pégalas aquí abajo y presiona Enter dos veces:")
    print("=" * 60)
    print()

    lines = []
    while True:
        try:
            line = input()
            if line:
                lines.append(line)
            else:
                if lines:
                    break
        except EOFError:
            break

    cookies_json = ''.join(lines)

    try:
        cookies = json.loads(cookies_json)

        # Formato de Playwright storage_state
        storage_state = {
            "cookies": [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".milanuncios.com"),
                    "path": c.get("path", "/"),
                    "expires": -1,
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax"
                }
                for c in cookies if c.get("name") and c.get("value")
            ],
            "origins": []
        }

        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(storage_state, f, indent=2)

        print()
        print(f"Cookies guardadas: {len(storage_state['cookies'])} cookies")
        print(f"Archivo: {COOKIES_FILE}")
        print()
        print("Ahora ejecuta: python run_all_scrapers.py --zones salou --postgres")

    except json.JSONDecodeError as e:
        print(f"Error: JSON inválido - {e}")
        print("Asegúrate de copiar el resultado completo del comando")


if __name__ == '__main__':
    main()

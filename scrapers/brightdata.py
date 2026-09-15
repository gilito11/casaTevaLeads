"""
Bright Data Web Unlocker: sesion compartida + verificacion del token.

Las API keys de Bright Data CADUCAN (la creada el 26-May-2026 murio el
27-Ago-2026: 3 meses). Con token caducado el API responde 401 "Token expired"
y los scrapers BD (fotocasa, milanuncios, wallapop, idealista, obra nueva)
quedan a cero en silencio mientras el workflow sigue en "success".
`verify_token()` corta el run al arrancar con un error explicito.
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BD_API_URL = "https://api.brightdata.com/request"
BD_STATUS_URL = "https://api.brightdata.com/status"  # gratis: solo valida auth

RENEW_HINT = (
    "Renovar: brightdata.com/cp/setting/users (API keys) -> Add key con "
    "expiration 'Unlimited' -> gh secret set BRIGHTDATA_API_KEY"
)


class BrightDataAuthError(RuntimeError):
    pass


def get_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.environ.get("BRIGHTDATA_API_KEY")
    if not key:
        raise RuntimeError(
            f"BRIGHTDATA_API_KEY env var or --brightdata-api-key arg required. {RENEW_HINT}"
        )
    return key


def build_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    return session


def verify_token(session: requests.Session, timeout: int = 20) -> None:
    """Lanza BrightDataAuthError si el token esta caducado/invalido (HTTP 401).

    Cualquier otra respuesta (403/5xx/red) no bloquea: solo avisa, para no
    parar el scraping por un fallo transitorio del endpoint de estado.
    """
    try:
        r = session.get(BD_STATUS_URL, timeout=timeout)
    except requests.RequestException as e:
        logger.warning(f"Bright Data status check failed ({e}); continuing")
        return
    if r.status_code == 401:
        raise BrightDataAuthError(
            f"Bright Data HTTP 401 ({r.text[:100].strip() or 'unauthorized'}). {RENEW_HINT}"
        )
    if r.status_code != 200:
        logger.warning(f"Bright Data status check HTTP {r.status_code}: {r.text[:120]}; continuing")
        return
    logger.info("Bright Data token OK")

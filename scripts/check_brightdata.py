#!/usr/bin/env python3
"""
Preflight: verifica el token de Bright Data antes de lanzar los scrapers BD.

Exit 1 + alerta Telegram si el token esta caducado/ausente. El workflow usa
el outcome de este paso para saltar fotocasa/milanuncios/wallapop/idealista
en vez de acumular 40 warnings 401 y reportar "success" con 0 leads.
"""
import logging
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scrapers.brightdata import BrightDataAuthError, build_session, get_api_key, verify_token  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        verify_token(build_session(get_api_key()))
    except (BrightDataAuthError, RuntimeError) as e:
        logger.error(str(e))
        try:
            from scrapers.utils.telegram_alerts import send_telegram_alert
            send_telegram_alert(
                "🔴 <b>Bright Data: token caducado o ausente</b>\n"
                "fotocasa, milanuncios, wallapop e idealista NO scrapean hasta renovarlo.\n\n"
                f"{e}"
            )
        except Exception as te:  # pragma: no cover
            logger.warning(f"Telegram alert failed: {te}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

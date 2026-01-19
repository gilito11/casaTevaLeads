"""
Telegram alerts for Casa Teva scrapers.
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def send_telegram_alert(message: str, parse_mode: str = "HTML") -> bool:
    """
    Send alert via Telegram Bot API.

    Args:
        message: Message text (supports HTML formatting)
        parse_mode: HTML or Markdown

    Returns:
        True if sent successfully

    Env vars:
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather
        TELEGRAM_CHAT_ID: Chat/group ID (can be negative for groups)
    """
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        logger.debug("Telegram not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
            },
            timeout=10,
        )

        if response.status_code == 200:
            logger.info("Telegram alert sent")
            return True
        else:
            logger.warning(f"Telegram API returned {response.status_code}: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


def send_new_leads_summary(
    total_leads: int,
    leads_by_portal: dict,
    new_today: int = 0,
) -> bool:
    """Send summary of new leads found."""
    if total_leads == 0:
        return False

    lines = [
        f"<b>Scraping completado</b>",
        f"Total leads: <b>{total_leads}</b>",
    ]

    if new_today > 0:
        lines.append(f"Nuevos hoy: <b>{new_today}</b>")

    if leads_by_portal:
        lines.append("")
        for portal, count in leads_by_portal.items():
            lines.append(f"  {portal}: {count}")

    return send_telegram_alert("\n".join(lines))


def send_price_drop_alert(
    titulo: str,
    portal: str,
    zona: str,
    precio_anterior: float,
    precio_nuevo: float,
    url: str,
) -> bool:
    """Send alert for price drop on a listing."""
    reduccion = precio_anterior - precio_nuevo
    porcentaje = (reduccion / precio_anterior) * 100

    message = (
        f"<b>Bajada de precio</b>\n\n"
        f"{titulo}\n"
        f"Portal: {portal}\n"
        f"Zona: {zona}\n\n"
        f"Antes: {precio_anterior:,.0f} EUR\n"
        f"Ahora: <b>{precio_nuevo:,.0f} EUR</b>\n"
        f"Reduccion: -{reduccion:,.0f} EUR (-{porcentaje:.1f}%)\n\n"
        f"<a href=\"{url}\">Ver anuncio</a>"
    )

    return send_telegram_alert(message)


def send_scraping_error(
    portal: str,
    error: str,
    zones: Optional[list] = None,
) -> bool:
    """Send alert for scraping error."""
    message = f"<b>Error scraping {portal}</b>\n\n"

    if zones:
        message += f"Zonas: {', '.join(zones)}\n\n"

    # Truncate error if too long
    error_truncated = error[:500] if len(error) > 500 else error
    message += f"<code>{error_truncated}</code>"

    return send_telegram_alert(message)

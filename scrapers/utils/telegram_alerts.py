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


def send_task_reminder(
    task_titulo: str,
    task_tipo: str,
    fecha_vencimiento: str,
    lead_titulo: Optional[str] = None,
    lead_url: Optional[str] = None,
    asignado_a: Optional[str] = None,
) -> bool:
    """
    Send reminder for task due today or overdue.

    Args:
        task_titulo: Task title
        task_tipo: Task type (llamar, visitar, etc)
        fecha_vencimiento: Due date/time
        lead_titulo: Associated lead title (optional)
        lead_url: URL to lead in portal (optional)
        asignado_a: Name of assigned user (optional)
    """
    lines = [
        f"<b>Recordatorio de tarea</b>",
        f"",
        f"{task_titulo}",
        f"Tipo: {task_tipo}",
        f"Vence: {fecha_vencimiento}",
    ]

    if asignado_a:
        lines.append(f"Asignado a: {asignado_a}")

    if lead_titulo:
        lines.append(f"")
        lines.append(f"Lead: {lead_titulo}")

    if lead_url:
        lines.append(f"<a href=\"{lead_url}\">Ver anuncio</a>")

    return send_telegram_alert("\n".join(lines))


def send_tasks_daily_summary(
    total_hoy: int,
    total_vencidas: int,
    tareas_hoy: list,
) -> bool:
    """
    Send daily summary of tasks due today.

    Args:
        total_hoy: Number of tasks due today
        total_vencidas: Number of overdue tasks
        tareas_hoy: List of dicts with task info (titulo, tipo, fecha_vencimiento)
    """
    if total_hoy == 0 and total_vencidas == 0:
        return False

    lines = [
        f"<b>Resumen de tareas</b>",
        f"",
    ]

    if total_vencidas > 0:
        lines.append(f"Vencidas: <b>{total_vencidas}</b>")

    lines.append(f"Para hoy: <b>{total_hoy}</b>")

    if tareas_hoy:
        lines.append("")
        for tarea in tareas_hoy[:5]:  # Max 5 tasks in summary
            tipo_emoji = {
                'llamar': 'Tel',
                'visitar': 'Visita',
                'enviar_info': 'Info',
                'seguimiento': 'Seguim',
                'reunion': 'Reunion',
                'otro': 'Otro',
            }.get(tarea.get('tipo', ''), '')

            hora = tarea.get('fecha_vencimiento', '')
            if hora:
                try:
                    from datetime import datetime
                    if isinstance(hora, str):
                        dt = datetime.fromisoformat(hora.replace('Z', '+00:00'))
                    else:
                        dt = hora
                    hora = dt.strftime('%H:%M')
                except Exception:
                    hora = ''

            lines.append(f"  {hora} [{tipo_emoji}] {tarea.get('titulo', '')[:40]}")

        if len(tareas_hoy) > 5:
            lines.append(f"  ...y {len(tareas_hoy) - 5} mas")

    return send_telegram_alert("\n".join(lines))

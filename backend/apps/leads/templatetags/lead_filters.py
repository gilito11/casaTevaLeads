from django import template
from datetime import datetime
import locale

register = template.Library()


@register.filter
def format_datetime_es(value):
    """
    Formatea una fecha ISO (2025-12-20T21:53:56) a formato español legible.
    Ejemplo: 2025-12-20T21:53:56 -> 20/12/2025 22:53 (ajustado a Madrid)
    """
    if not value:
        return "hace un momento"
    try:
        from datetime import timedelta
        # Si es string ISO, parsearlo
        if isinstance(value, str):
            # Quitar la parte de microsegundos si existe
            value = value.split('.')[0]
            dt = datetime.fromisoformat(value)
        else:
            dt = value
        # Ajustar a horario Madrid (+1 hora en invierno, +2 en verano)
        # En diciembre estamos en horario de invierno (+1)
        dt = dt + timedelta(hours=1)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError, AttributeError):
        return value


@register.filter
def format_price(value):
    """
    Formatea un precio con puntos como separador de miles.
    Ejemplo: 100000 -> 100.000
    """
    if value is None:
        return "-"
    try:
        # Convertir a entero para quitar decimales
        price = int(float(value))
        # Formatear con puntos de miles (formato español)
        return f"{price:,}".replace(",", ".")
    except (ValueError, TypeError):
        return value


@register.filter
def format_meters(value):
    """
    Formatea metros cuadrados.
    Ejemplo: 150.00 -> 150
    """
    if value is None:
        return None
    try:
        meters = int(float(value))
        return meters
    except (ValueError, TypeError):
        return value

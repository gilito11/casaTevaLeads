from django import template
import locale

register = template.Library()


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

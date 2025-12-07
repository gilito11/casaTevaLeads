"""
Sistema de filtrado de particulares para scrapers inmobiliarios.

Este módulo implementa la lógica crítica para filtrar y NUNCA scrapear:
- Anuncios de inmobiliarias/agencias
- Particulares que rechacen contacto de inmobiliarias
- Profesionales del sector inmobiliario

IMPORTANTE: Este es el componente MÁS IMPORTANTE del sistema de scraping.
"""

import re
from typing import Optional


# Palabras clave que indican que el anunciante es un profesional/inmobiliaria
PALABRAS_PROFESIONAL = [
    'inmobiliaria',
    'agencia',
    'real estate',
    'promotora',
    'gestoría',
    'gestoria',
    'asesor inmobiliario',
    'asesores inmobiliarios',
    'servicios inmobiliarios',
    'grupo inmobiliario',
]

# Badges que identifican a profesionales
BADGES_PROFESIONAL = [
    'profesional verificado',
    'agencia verificada',
    'pro',
    'professional',
    'verified pro',
    'agencia',
]

# Frases que indican que el particular NO quiere contacto de inmobiliarias
FRASES_RECHAZO = [
    'no inmobiliarias',
    'no agencias',
    'solo particulares',
    'particular a particular',
    'abstenerse inmobiliarias',
    'no intermediarios',
    'solo comprador directo',
    'sin agencias',
    'abstenerse agencias',
    'no profesionales',
    'sin intermediarios',
    'trato directo',
    'particular vende',
    'vendo como particular',
]

# Umbral de anuncios activos para considerar profesional
UMBRAL_ANUNCIOS_PROFESIONAL = 3


def es_profesional(data: dict) -> bool:
    """
    Detecta si el anuncio es de una inmobiliaria o profesional del sector.

    Args:
        data: Diccionario con información del anuncio. Campos esperados:
            - nombre (str, optional): Nombre del anunciante
            - descripcion (str, optional): Descripción del anuncio
            - badges (list, optional): Lista de badges del usuario
            - num_anuncios_activos (int, optional): Número de anuncios activos

    Returns:
        bool: True si es profesional/inmobiliaria, False si es particular

    Examples:
        >>> es_profesional({'nombre': 'Inmobiliaria Casa Bonita'})
        True
        >>> es_profesional({'nombre': 'Juan Pérez'})
        False
        >>> es_profesional({'descripcion': 'Somos una agencia inmobiliaria'})
        True
        >>> es_profesional({'badges': ['profesional verificado']})
        True
        >>> es_profesional({'num_anuncios_activos': 10})
        True
    """
    # Verificar nombre del anunciante
    nombre = data.get('nombre', '') or ''
    if isinstance(nombre, str):
        nombre = nombre.lower()
        if _contiene_palabras_clave(nombre, PALABRAS_PROFESIONAL):
            return True

    # Verificar descripción del anuncio
    # Pero excluir si contiene frases de rechazo (ej: "NO INMOBILIARIAS")
    descripcion = data.get('descripcion', '') or ''
    if isinstance(descripcion, str):
        descripcion = descripcion.lower()
        # Si la descripción contiene frases de rechazo, no es profesional
        tiene_rechazo = _contiene_palabras_clave(descripcion, FRASES_RECHAZO)
        if not tiene_rechazo and _contiene_palabras_clave(descripcion, PALABRAS_PROFESIONAL):
            return True

    # Verificar badges del usuario
    badges = data.get('badges', [])
    if isinstance(badges, list):
        badges_lower = [badge.lower() if isinstance(badge, str) else '' for badge in badges]
        if _contiene_palabras_clave(' '.join(badges_lower), BADGES_PROFESIONAL):
            return True

    # Verificar número de anuncios activos
    num_anuncios = data.get('num_anuncios_activos', 0)
    if isinstance(num_anuncios, int) and num_anuncios > UMBRAL_ANUNCIOS_PROFESIONAL:
        return True

    return False


def permite_inmobiliarias(data: dict) -> bool:
    """
    Detecta si el particular rechaza contacto de inmobiliarias.

    Args:
        data: Diccionario con información del anuncio. Campos esperados:
            - titulo (str, optional): Título del anuncio
            - descripcion (str, optional): Descripción del anuncio

    Returns:
        bool: False si rechaza inmobiliarias, True si las permite

    Examples:
        >>> permite_inmobiliarias({'titulo': 'Piso en venta - NO INMOBILIARIAS'})
        False
        >>> permite_inmobiliarias({'descripcion': 'Solo particulares por favor'})
        False
        >>> permite_inmobiliarias({'titulo': 'Piso en venta', 'descripcion': 'Buen estado'})
        True
        >>> permite_inmobiliarias({'descripcion': 'Abstenerse agencias'})
        False
    """
    # Verificar título del anuncio
    titulo = data.get('titulo', '') or ''
    if isinstance(titulo, str):
        titulo = titulo.lower()
        if _contiene_palabras_clave(titulo, FRASES_RECHAZO):
            return False

    # Verificar descripción del anuncio
    descripcion = data.get('descripcion', '') or ''
    if isinstance(descripcion, str):
        descripcion = descripcion.lower()
        if _contiene_palabras_clave(descripcion, FRASES_RECHAZO):
            return False

    return True


def debe_scrapear(data: dict) -> bool:
    """
    Decide si debemos scrapear este anuncio.

    Un anuncio debe ser scrapeado SOLO si:
    1. NO es de un profesional/inmobiliaria
    2. El particular SÍ permite contacto de inmobiliarias

    Args:
        data: Diccionario con información del anuncio

    Returns:
        bool: True si debemos scrapear, False si debemos ignorar

    Examples:
        >>> debe_scrapear({'nombre': 'Inmobiliaria XYZ'})
        False
        >>> debe_scrapear({'descripcion': 'NO INMOBILIARIAS'})
        False
        >>> debe_scrapear({'nombre': 'Juan', 'titulo': 'Piso en venta'})
        True
    """
    return (not es_profesional(data)) and permite_inmobiliarias(data)


def _contiene_palabras_clave(texto: str, palabras_clave: list) -> bool:
    """
    Verifica si el texto contiene alguna de las palabras clave.

    Búsqueda case-insensitive y con límites de palabra para evitar
    falsos positivos.

    Args:
        texto: Texto donde buscar
        palabras_clave: Lista de palabras/frases a buscar

    Returns:
        bool: True si encuentra alguna palabra clave, False en caso contrario
    """
    if not texto or not isinstance(texto, str):
        return False

    texto_normalizado = texto.lower().strip()

    for palabra in palabras_clave:
        if not palabra:
            continue

        palabra_normalizada = palabra.lower().strip()

        # Búsqueda exacta de la frase
        if palabra_normalizada in texto_normalizado:
            return True

        # Búsqueda con límites de palabra usando regex
        # Esto evita falsos positivos como "apilar" conteniendo "api"
        patron = r'\b' + re.escape(palabra_normalizada) + r'\b'
        if re.search(patron, texto_normalizado):
            return True

    return False


def get_razon_rechazo(data: dict) -> Optional[str]:
    """
    Obtiene la razón por la cual un anuncio fue rechazado.

    Útil para logging y debugging.

    Args:
        data: Diccionario con información del anuncio

    Returns:
        str: Razón del rechazo, o None si debe ser scrapeado

    Examples:
        >>> get_razon_rechazo({'nombre': 'Inmobiliaria ABC'})
        'Es profesional/inmobiliaria'
        >>> get_razon_rechazo({'descripcion': 'NO INMOBILIARIAS'})
        'Rechaza contacto de inmobiliarias'
        >>> get_razon_rechazo({'nombre': 'Juan', 'titulo': 'Piso'})
        None
    """
    if es_profesional(data):
        return 'Es profesional/inmobiliaria'

    if not permite_inmobiliarias(data):
        return 'Rechaza contacto de inmobiliarias'

    return None

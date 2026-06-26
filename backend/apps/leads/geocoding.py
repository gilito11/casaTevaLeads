"""Geocoding de direcciones exactas via Nominatim (OpenStreetMap, gratis).

Uso de bajo volumen (entrada manual del comercial), respetando el rate-limit
de Nominatim (1 req/s). No es critico: si falla, el lead simplemente se queda
sin coordenadas exactas y sigue mostrandose en el centroide del pueblo.
"""
import logging
import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "FincaRadar-CRM/1.0 (geocoding direcciones inmuebles)"


def geocode_address(direccion, municipio=None):
    """Geocodifica una direccion a (lat, lon).

    Devuelve (float, float) o None si no se encuentra / falla la peticion.
    Se anade el municipio y "España" como pista para acotar el resultado.
    """
    if not direccion or not direccion.strip():
        return None

    query = direccion.strip()
    if municipio and municipio.lower() not in query.lower():
        query = f"{query}, {municipio}"
    query = f"{query}, España"

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "es"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            logger.info("Geocoding sin resultados para: %s", query)
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:  # noqa: BLE001 - geocoding nunca debe romper el flujo
        logger.warning("Geocoding fallo para '%s': %s", query, e)
        return None

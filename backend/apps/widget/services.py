from django.db import connection
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Ajustes por tipo de propiedad respecto al precio medio
AJUSTE_TIPO_PROPIEDAD = {
    'piso': Decimal('1.0'),
    'casa': Decimal('1.15'),
    'chalet': Decimal('1.25'),
    'adosado': Decimal('1.10'),
    'duplex': Decimal('1.08'),
    'atico': Decimal('1.12'),
    'estudio': Decimal('0.95'),
    'local': Decimal('0.85'),
    'terreno': Decimal('0.50'),
}


def get_precio_medio_zona(zona: str, tenant_id: int = None) -> dict:
    """
    Obtiene estadisticas de precio por m2 de una zona.

    Args:
        zona: Nombre de la zona (ej: 'salou', 'lleida')
        tenant_id: Opcional, filtrar por tenant

    Returns:
        dict con precio_medio_m2, num_muestras, precio_min, precio_max
    """
    with connection.cursor() as cursor:
        sql = """
            SELECT
                AVG(precio / NULLIF(superficie_m2, 0)) as precio_medio_m2,
                COUNT(*) as num_muestras,
                MIN(precio / NULLIF(superficie_m2, 0)) as precio_min_m2,
                MAX(precio / NULLIF(superficie_m2, 0)) as precio_max_m2
            FROM public_marts.dim_leads
            WHERE
                LOWER(zona_clasificada) LIKE %s
                AND precio IS NOT NULL
                AND precio > 10000
                AND superficie_m2 IS NOT NULL
                AND superficie_m2 > 20
                AND fecha_primera_captura > NOW() - INTERVAL '90 days'
        """
        params = [f'%{zona.lower()}%']

        if tenant_id:
            sql = sql.replace(
                "AND fecha_primera_captura",
                "AND tenant_id = %s AND fecha_primera_captura"
            )
            params.insert(0, tenant_id)

        cursor.execute(sql, params)
        row = cursor.fetchone()

        if row and row[0]:
            return {
                'precio_medio_m2': Decimal(str(row[0])).quantize(Decimal('0.01')),
                'num_muestras': row[1],
                'precio_min_m2': Decimal(str(row[2])).quantize(Decimal('0.01')) if row[2] else None,
                'precio_max_m2': Decimal(str(row[3])).quantize(Decimal('0.01')) if row[3] else None,
            }

    return {
        'precio_medio_m2': None,
        'num_muestras': 0,
        'precio_min_m2': None,
        'precio_max_m2': None,
    }


def valorar_inmueble(
    zona: str,
    metros: float,
    tipo_propiedad: str = 'piso',
    habitaciones: int = None,
    tenant_id: int = None,
) -> dict:
    """
    Genera una valoracion estimada para un inmueble.

    Args:
        zona: Nombre de la zona geografica
        metros: Superficie en m2
        tipo_propiedad: Tipo de inmueble (piso, casa, chalet, etc)
        habitaciones: Numero de habitaciones (opcional, para ajuste fino)
        tenant_id: ID del tenant (opcional)

    Returns:
        dict con valoracion estimada, rango y metadata
    """
    if not zona or not metros or metros <= 0:
        return {
            'success': False,
            'error': 'Zona y metros son requeridos',
            'valoracion': None,
        }

    stats = get_precio_medio_zona(zona, tenant_id)

    if not stats['precio_medio_m2'] or stats['num_muestras'] < 5:
        return {
            'success': False,
            'error': f'No hay suficientes datos para la zona "{zona}". Necesitamos al menos 5 inmuebles de referencia.',
            'valoracion': None,
            'num_muestras': stats['num_muestras'],
        }

    precio_medio_m2 = stats['precio_medio_m2']

    # Ajuste por tipo de propiedad
    tipo_lower = tipo_propiedad.lower() if tipo_propiedad else 'piso'
    ajuste_tipo = AJUSTE_TIPO_PROPIEDAD.get(tipo_lower, Decimal('1.0'))

    # Ajuste por habitaciones (inmuebles con mas habitaciones valen mas por m2)
    ajuste_habitaciones = Decimal('1.0')
    if habitaciones:
        if habitaciones >= 4:
            ajuste_habitaciones = Decimal('1.05')
        elif habitaciones >= 3:
            ajuste_habitaciones = Decimal('1.02')
        elif habitaciones == 1:
            ajuste_habitaciones = Decimal('0.98')

    # Calculo de valoracion
    precio_m2_ajustado = precio_medio_m2 * ajuste_tipo * ajuste_habitaciones
    valoracion = precio_m2_ajustado * Decimal(str(metros))

    # Rango de valoracion (+-10%)
    valoracion_min = valoracion * Decimal('0.90')
    valoracion_max = valoracion * Decimal('1.10')

    return {
        'success': True,
        'valoracion': int(valoracion),
        'valoracion_min': int(valoracion_min),
        'valoracion_max': int(valoracion_max),
        'precio_m2': float(precio_m2_ajustado.quantize(Decimal('0.01'))),
        'precio_m2_zona': float(precio_medio_m2),
        'num_muestras': stats['num_muestras'],
        'zona': zona,
        'metros': metros,
        'tipo_propiedad': tipo_propiedad,
        'ajustes': {
            'tipo': float(ajuste_tipo),
            'habitaciones': float(ajuste_habitaciones),
        }
    }


def guardar_lead_widget(
    tenant_id: int,
    email: str,
    zona: str,
    metros: float,
    tipo_propiedad: str,
    habitaciones: int = None,
    direccion: str = None,
    telefono: str = None,
    valoracion: int = None,
) -> dict:
    """
    Guarda un lead captado desde el widget.
    Se guarda en raw.raw_listings para ser procesado por dbt.

    Args:
        tenant_id: ID del tenant
        email: Email del usuario
        zona: Zona geografica
        metros: Superficie en m2
        tipo_propiedad: Tipo de inmueble
        habitaciones: Numero de habitaciones
        direccion: Direccion (opcional)
        telefono: Telefono (opcional)
        valoracion: Valoracion calculada

    Returns:
        dict con resultado
    """
    import json
    import hashlib
    from datetime import datetime

    # Generar ID unico para el lead
    unique_str = f"widget_{tenant_id}_{email}_{zona}_{datetime.utcnow().isoformat()}"
    lead_id = hashlib.md5(unique_str.encode()).hexdigest()

    listing_data = {
        'source': 'widget_valorador',
        'email': email,
        'zona': zona,
        'metros': metros,
        'tipo_propiedad': tipo_propiedad,
        'habitaciones': habitaciones,
        'direccion': direccion,
        'telefono': telefono,
        'valoracion_estimada': valoracion,
        'captado_en': datetime.utcnow().isoformat(),
    }

    listing_data['anuncio_id'] = lead_id

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO raw.raw_listings (
                tenant_id, portal, data_lake_path, raw_data, scraping_timestamp
            ) VALUES (
                %s, 'widget', %s, %s, NOW()
            )
            ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
            DO UPDATE SET raw_data = EXCLUDED.raw_data, scraping_timestamp = NOW()
        """, [
            tenant_id,
            f"widget://{lead_id}",
            json.dumps(listing_data),
        ])

    logger.info(f"Lead widget guardado: {lead_id} para tenant {tenant_id}")

    return {
        'success': True,
        'lead_id': lead_id,
    }

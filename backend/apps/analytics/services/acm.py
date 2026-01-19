"""
Servicio de Análisis Comparativo de Mercado (ACM).

Calcula valoraciones de inmuebles basándose en comparables de la BD.
Esto es una feature diferenciadora vs Idealista Tools y Fotocasa Pro.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import connection

logger = logging.getLogger(__name__)


@dataclass
class Comparable:
    """Un inmueble comparable."""
    lead_id: str
    titulo: str
    precio: float
    metros: float
    precio_m2: float
    zona: str
    portal: str
    url: str
    habitaciones: Optional[int]
    fecha_captura: str
    similitud: float  # 0-100, qué tan similar es


@dataclass
class ACMResult:
    """Resultado del análisis comparativo de mercado."""
    # Inmueble a valorar
    zona: str
    tipo_inmueble: str
    metros: float
    habitaciones: Optional[int]

    # Estimación de precio
    precio_estimado: float
    precio_min: float
    precio_max: float
    precio_mediana: float
    precio_m2_medio: float

    # Confianza y datos
    num_comparables: int
    confianza: str  # 'alta', 'media', 'baja'
    comparables: List[Comparable]

    # Estadísticas adicionales
    dias_promedio_mercado: float
    tendencia_precios: str  # 'subiendo', 'bajando', 'estable'


def calcular_acm(
    tenant_id: int,
    zona: str,
    metros: float,
    tipo_inmueble: Optional[str] = None,
    habitaciones: Optional[int] = None,
    precio_referencia: Optional[float] = None,
    max_comparables: int = 10
) -> ACMResult:
    """
    Calcula el Análisis Comparativo de Mercado para un inmueble.

    Args:
        tenant_id: ID del tenant
        zona: Zona geográfica (ej: "Salou", "Lleida")
        metros: Superficie en m²
        tipo_inmueble: Tipo de propiedad (piso, casa, etc.)
        habitaciones: Número de habitaciones
        precio_referencia: Precio actual (si se tiene) para comparar
        max_comparables: Máximo de comparables a incluir

    Returns:
        ACMResult con la valoración y comparables
    """
    comparables = []

    with connection.cursor() as cursor:
        # Buscar comparables con criterios flexibles
        # Primero intentamos match exacto, luego ampliamos

        # Rangos de tolerancia
        metros_min = metros * 0.8  # -20%
        metros_max = metros * 1.2  # +20%

        # Query base para comparables
        query = """
            WITH comparables AS (
                SELECT
                    lead_id,
                    titulo,
                    precio,
                    superficie_m2 as metros,
                    CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 ELSE 0 END as precio_m2,
                    zona_clasificada as zona,
                    source_portal as portal,
                    listing_url as url,
                    habitaciones,
                    fecha_primera_captura,
                    -- Calcular similitud (0-100)
                    (
                        -- Similitud por metros (40 pts max)
                        CASE
                            WHEN superficie_m2 BETWEEN %s AND %s THEN 40
                            WHEN superficie_m2 BETWEEN %s * 0.7 AND %s * 1.3 THEN 25
                            ELSE 10
                        END
                        -- Similitud por zona (30 pts)
                        + CASE WHEN LOWER(zona_clasificada) ILIKE %s THEN 30 ELSE 15 END
                        -- Similitud por tipo (20 pts)
                        + CASE
                            WHEN %s IS NULL THEN 10
                            WHEN LOWER(tipo_propiedad) ILIKE %s THEN 20
                            ELSE 5
                        END
                        -- Similitud por habitaciones (10 pts)
                        + CASE
                            WHEN %s IS NULL THEN 5
                            WHEN habitaciones = %s THEN 10
                            WHEN ABS(COALESCE(habitaciones, 0) - %s) <= 1 THEN 7
                            ELSE 3
                        END
                    ) as similitud
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                  AND precio > 10000  -- Filtrar precios irreales
                  AND precio < 10000000
                  AND superficie_m2 > 10
                  -- Zona similar (match parcial)
                  AND (
                      LOWER(zona_clasificada) ILIKE %s
                      OR LOWER(zona_clasificada) ILIKE %s
                  )
                  -- Metros en rango amplio
                  AND superficie_m2 BETWEEN %s * 0.5 AND %s * 2
            )
            SELECT *
            FROM comparables
            WHERE similitud >= 40  -- Mínimo 40% similitud
            ORDER BY similitud DESC, fecha_primera_captura DESC
            LIMIT %s
        """

        zona_pattern = f'%{zona.lower()}%'
        tipo_pattern = f'%{tipo_inmueble.lower()}%' if tipo_inmueble else None
        hab = habitaciones or 0

        params = [
            metros_min, metros_max,  # Rango exacto
            metros, metros,  # Rango amplio
            zona_pattern,  # Zona
            tipo_inmueble, tipo_pattern,  # Tipo
            habitaciones, hab, hab,  # Habitaciones
            tenant_id,
            zona_pattern, zona_pattern,
            metros, metros,
            max_comparables
        ]

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]

            for row in rows:
                data = dict(zip(columns, row))
                comparables.append(Comparable(
                    lead_id=data['lead_id'],
                    titulo=data['titulo'] or 'Sin título',
                    precio=float(data['precio'] or 0),
                    metros=float(data['metros'] or 0),
                    precio_m2=float(data['precio_m2'] or 0),
                    zona=data['zona'] or '',
                    portal=data['portal'] or '',
                    url=data['url'] or '',
                    habitaciones=data['habitaciones'],
                    fecha_captura=data['fecha_primera_captura'].strftime('%d/%m/%Y') if data['fecha_primera_captura'] else '',
                    similitud=float(data['similitud'] or 0)
                ))
        except Exception as e:
            logger.error(f"Error buscando comparables: {e}")

    # Calcular estadísticas
    if not comparables:
        # Sin comparables, intentar estimación por zona
        return _estimar_sin_comparables(tenant_id, zona, metros, tipo_inmueble, habitaciones)

    precios = [c.precio for c in comparables]
    precios_m2 = [c.precio_m2 for c in comparables if c.precio_m2 > 0]

    precio_medio = sum(precios) / len(precios)
    precio_mediana = sorted(precios)[len(precios) // 2]
    precio_m2_medio = sum(precios_m2) / len(precios_m2) if precios_m2 else 0

    # Estimación basada en precio/m2 medio
    precio_estimado = precio_m2_medio * metros if precio_m2_medio > 0 else precio_medio

    # Rango de precios (percentiles 25-75)
    precios_sorted = sorted(precios)
    idx_25 = max(0, len(precios_sorted) // 4)
    idx_75 = min(len(precios_sorted) - 1, len(precios_sorted) * 3 // 4)
    precio_min = precios_sorted[idx_25]
    precio_max = precios_sorted[idx_75]

    # Confianza basada en número de comparables y similitud
    similitud_media = sum(c.similitud for c in comparables) / len(comparables)
    if len(comparables) >= 5 and similitud_media >= 70:
        confianza = 'alta'
    elif len(comparables) >= 3 and similitud_media >= 50:
        confianza = 'media'
    else:
        confianza = 'baja'

    # Tendencia de precios (últimos 30 días vs anteriores)
    tendencia = _calcular_tendencia(tenant_id, zona)

    return ACMResult(
        zona=zona,
        tipo_inmueble=tipo_inmueble or 'No especificado',
        metros=metros,
        habitaciones=habitaciones,
        precio_estimado=round(precio_estimado, 0),
        precio_min=round(precio_min, 0),
        precio_max=round(precio_max, 0),
        precio_mediana=round(precio_mediana, 0),
        precio_m2_medio=round(precio_m2_medio, 0),
        num_comparables=len(comparables),
        confianza=confianza,
        comparables=comparables,
        dias_promedio_mercado=0,  # TODO: calcular
        tendencia_precios=tendencia
    )


def _estimar_sin_comparables(
    tenant_id: int,
    zona: str,
    metros: float,
    tipo_inmueble: Optional[str],
    habitaciones: Optional[int]
) -> ACMResult:
    """Estimación cuando no hay comparables directos."""

    # Buscar precio/m2 promedio de la zona
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                AVG(CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 END) as precio_m2_medio,
                COUNT(*) as total
            FROM public_marts.dim_leads
            WHERE tenant_id = %s
              AND precio > 10000
              AND superficie_m2 > 10
              AND LOWER(zona_clasificada) ILIKE %s
        """, [tenant_id, f'%{zona.lower()}%'])

        row = cursor.fetchone()
        precio_m2 = float(row[0] or 0) if row else 0
        total = row[1] if row else 0

    if precio_m2 > 0:
        precio_estimado = precio_m2 * metros
    else:
        # Fallback: precio medio general de Catalunya ~2500€/m2
        precio_estimado = 2500 * metros

    return ACMResult(
        zona=zona,
        tipo_inmueble=tipo_inmueble or 'No especificado',
        metros=metros,
        habitaciones=habitaciones,
        precio_estimado=round(precio_estimado, 0),
        precio_min=round(precio_estimado * 0.85, 0),
        precio_max=round(precio_estimado * 1.15, 0),
        precio_mediana=round(precio_estimado, 0),
        precio_m2_medio=round(precio_m2 or 2500, 0),
        num_comparables=0,
        confianza='baja',
        comparables=[],
        dias_promedio_mercado=0,
        tendencia_precios='desconocida'
    )


def _calcular_tendencia(tenant_id: int, zona: str) -> str:
    """Calcula la tendencia de precios en la zona."""
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                WITH precios_periodo AS (
                    SELECT
                        CASE
                            WHEN fecha_primera_captura >= CURRENT_DATE - INTERVAL '30 days' THEN 'reciente'
                            ELSE 'anterior'
                        END as periodo,
                        AVG(CASE WHEN superficie_m2 > 0 THEN precio / superficie_m2 END) as precio_m2
                    FROM public_marts.dim_leads
                    WHERE tenant_id = %s
                      AND precio > 10000
                      AND superficie_m2 > 10
                      AND LOWER(zona_clasificada) ILIKE %s
                      AND fecha_primera_captura >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY 1
                )
                SELECT
                    MAX(CASE WHEN periodo = 'reciente' THEN precio_m2 END) as reciente,
                    MAX(CASE WHEN periodo = 'anterior' THEN precio_m2 END) as anterior
                FROM precios_periodo
            """, [tenant_id, f'%{zona.lower()}%'])

            row = cursor.fetchone()
            if row and row[0] and row[1]:
                reciente = float(row[0])
                anterior = float(row[1])
                cambio = (reciente - anterior) / anterior * 100

                if cambio > 3:
                    return 'subiendo'
                elif cambio < -3:
                    return 'bajando'
                else:
                    return 'estable'
        except Exception as e:
            logger.error(f"Error calculando tendencia: {e}")

    return 'estable'


def acm_para_lead(tenant_id: int, lead_id: str) -> Optional[ACMResult]:
    """
    Genera ACM para un lead existente.
    Útil para mostrar valoración en la ficha del lead.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                zona_clasificada,
                superficie_m2,
                tipo_propiedad,
                habitaciones,
                precio
            FROM public_marts.dim_leads
            WHERE lead_id = %s AND tenant_id = %s
        """, [lead_id, tenant_id])

        row = cursor.fetchone()
        if not row:
            return None

        zona, metros, tipo, habitaciones, precio = row

        if not zona or not metros:
            return None

        return calcular_acm(
            tenant_id=tenant_id,
            zona=zona,
            metros=float(metros),
            tipo_inmueble=tipo,
            habitaciones=habitaciones,
            precio_referencia=float(precio) if precio else None
        )

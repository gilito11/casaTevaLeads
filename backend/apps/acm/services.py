from django.db import connection
from decimal import Decimal
import logging
from typing import Optional
from .models import ACMReport

logger = logging.getLogger(__name__)

# Ajustes por caracteristicas del anuncio
AJUSTE_ANTIGUEDAD = {
    'reciente': Decimal('1.0'),      # < 30 dias
    'medio': Decimal('0.98'),        # 30-60 dias
    'antiguo': Decimal('0.95'),      # 60-90 dias
    'muy_antiguo': Decimal('0.92'),  # > 90 dias
}

AJUSTE_FOTOS = {
    'muchas': Decimal('1.02'),   # > 10 fotos
    'normal': Decimal('1.0'),    # 5-10 fotos
    'pocas': Decimal('0.98'),    # < 5 fotos
    'ninguna': Decimal('0.95'),  # 0 fotos
}

AJUSTE_TELEFONO = {
    'visible': Decimal('1.0'),
    'oculto': Decimal('0.97'),
}


def get_lead_data(lead_id: str, tenant_id: int) -> Optional[dict]:
    """Obtiene datos del lead desde dim_leads."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                lead_id,
                zona_clasificada,
                tipo_propiedad,
                superficie_m2,
                habitaciones,
                precio,
                titulo,
                telefono_norm,
                fotos_json,
                fecha_primera_captura,
                listing_url
            FROM public_marts.dim_leads
            WHERE lead_id = %s AND tenant_id = %s
        """, [lead_id, tenant_id])
        row = cursor.fetchone()

        if not row:
            return None

        return {
            'lead_id': row[0],
            'zona': row[1],
            'tipo_propiedad': row[2],
            'superficie_m2': row[3],
            'habitaciones': row[4],
            'precio': row[5],
            'titulo': row[6],
            'telefono': row[7],
            'fotos': row[8] or [],
            'fecha_captura': row[9],
            'url': row[10],
        }


def buscar_comparables(
    tenant_id: int,
    zona: str,
    tipo_propiedad: str,
    metros: float,
    habitaciones: int = None,
    exclude_lead_id: str = None,
    limit: int = 20,
) -> list:
    """
    Busca leads comparables en la misma zona.

    Criterios:
    - Misma zona geografica
    - Mismo tipo de propiedad (si se especifica)
    - Superficie +-20%
    - Habitaciones +-1 (si se especifica)
    - Ultimos 90 dias
    - Precio > 0
    """
    metros_min = metros * 0.8
    metros_max = metros * 1.2

    sql = """
        SELECT
            lead_id,
            titulo,
            precio,
            superficie_m2,
            habitaciones,
            tipo_propiedad,
            zona_clasificada,
            telefono_norm,
            fotos_json,
            fecha_primera_captura,
            listing_url,
            source_portal
        FROM public_marts.dim_leads
        WHERE tenant_id = %s
          AND LOWER(zona_clasificada) = LOWER(%s)
          AND precio > 10000
          AND superficie_m2 IS NOT NULL
          AND superficie_m2 BETWEEN %s AND %s
          AND fecha_primera_captura > NOW() - INTERVAL '90 days'
    """
    params = [tenant_id, zona, metros_min, metros_max]

    if tipo_propiedad:
        sql += " AND LOWER(tipo_propiedad) = LOWER(%s)"
        params.append(tipo_propiedad)

    if habitaciones:
        sql += " AND habitaciones BETWEEN %s AND %s"
        params.extend([habitaciones - 1, habitaciones + 1])

    if exclude_lead_id:
        sql += " AND lead_id != %s"
        params.append(exclude_lead_id)

    sql += " ORDER BY fecha_primera_captura DESC LIMIT %s"
    params.append(limit)

    comparables = []
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        for row in cursor.fetchall():
            fotos = row[8] or []
            fecha = row[9]

            # Calcular dias en mercado
            dias_mercado = 0
            if fecha:
                from django.utils import timezone
                dias_mercado = (timezone.now() - fecha).days

            comparables.append({
                'lead_id': row[0],
                'titulo': row[1],
                'precio': float(row[2]) if row[2] else 0,
                'superficie_m2': float(row[3]) if row[3] else 0,
                'habitaciones': row[4],
                'tipo_propiedad': row[5],
                'zona': row[6],
                'tiene_telefono': bool(row[7]),
                'num_fotos': len(fotos) if isinstance(fotos, list) else 0,
                'dias_mercado': dias_mercado,
                'url': row[10],
                'portal': row[11],
                'precio_m2': float(row[2] / row[3]) if row[2] and row[3] and row[3] > 0 else 0,
            })

    return comparables


def calcular_ajuste_comparable(comparable: dict) -> Decimal:
    """
    Calcula el factor de ajuste para un comparable basado en sus caracteristicas.
    """
    ajuste = Decimal('1.0')

    # Ajuste por antiguedad
    dias = comparable.get('dias_mercado', 0)
    if dias < 30:
        ajuste *= AJUSTE_ANTIGUEDAD['reciente']
    elif dias < 60:
        ajuste *= AJUSTE_ANTIGUEDAD['medio']
    elif dias < 90:
        ajuste *= AJUSTE_ANTIGUEDAD['antiguo']
    else:
        ajuste *= AJUSTE_ANTIGUEDAD['muy_antiguo']

    # Ajuste por fotos
    num_fotos = comparable.get('num_fotos', 0)
    if num_fotos > 10:
        ajuste *= AJUSTE_FOTOS['muchas']
    elif num_fotos >= 5:
        ajuste *= AJUSTE_FOTOS['normal']
    elif num_fotos > 0:
        ajuste *= AJUSTE_FOTOS['pocas']
    else:
        ajuste *= AJUSTE_FOTOS['ninguna']

    # Ajuste por telefono visible
    if comparable.get('tiene_telefono'):
        ajuste *= AJUSTE_TELEFONO['visible']
    else:
        ajuste *= AJUSTE_TELEFONO['oculto']

    return ajuste


def generar_acm(lead_id: str, tenant_id: int, user=None) -> dict:
    """
    Genera un informe ACM para un lead.

    Args:
        lead_id: ID del lead a analizar
        tenant_id: ID del tenant
        user: Usuario que genera el informe (opcional)

    Returns:
        dict con resultado del ACM o error
    """
    # Obtener datos del lead
    lead = get_lead_data(lead_id, tenant_id)
    if not lead:
        return {'success': False, 'error': 'Lead no encontrado'}

    zona = lead.get('zona')
    metros = lead.get('superficie_m2')
    tipo = lead.get('tipo_propiedad')
    habitaciones = lead.get('habitaciones')
    precio_anuncio = lead.get('precio')

    if not zona:
        return {'success': False, 'error': 'Lead sin zona geografica'}

    if not metros or metros <= 0:
        return {'success': False, 'error': 'Lead sin superficie definida'}

    # Buscar comparables
    comparables = buscar_comparables(
        tenant_id=tenant_id,
        zona=zona,
        tipo_propiedad=tipo,
        metros=float(metros),
        habitaciones=habitaciones,
        exclude_lead_id=lead_id,
        limit=20,
    )

    if len(comparables) < 3:
        return {
            'success': False,
            'error': f'Insuficientes comparables ({len(comparables)}). Se necesitan al menos 3.',
            'num_comparables': len(comparables),
        }

    # Calcular precios/m2 ajustados
    precios_m2_ajustados = []
    comparables_con_ajuste = []

    for comp in comparables:
        if comp['precio_m2'] > 0:
            ajuste = calcular_ajuste_comparable(comp)
            precio_m2_ajustado = Decimal(str(comp['precio_m2'])) * ajuste

            precios_m2_ajustados.append(precio_m2_ajustado)
            comparables_con_ajuste.append({
                **comp,
                'ajuste': float(ajuste),
                'precio_m2_ajustado': float(precio_m2_ajustado),
            })

    if not precios_m2_ajustados:
        return {'success': False, 'error': 'No se pudieron calcular precios por m2'}

    # Ordenar para calcular percentiles
    precios_m2_ajustados.sort()
    n = len(precios_m2_ajustados)

    # Percentil 25 (valoracion minima)
    idx_p25 = int(n * 0.25)
    precio_m2_min = precios_m2_ajustados[idx_p25]

    # Percentil 75 (valoracion maxima)
    idx_p75 = min(int(n * 0.75), n - 1)
    precio_m2_max = precios_m2_ajustados[idx_p75]

    # Media (valoracion media)
    precio_m2_medio = sum(precios_m2_ajustados) / len(precios_m2_ajustados)

    # Calcular valoraciones
    metros_decimal = Decimal(str(metros))
    valoracion_min = precio_m2_min * metros_decimal
    valoracion_max = precio_m2_max * metros_decimal
    valoracion_media = precio_m2_medio * metros_decimal

    # Calcular confianza (basada en numero de comparables y dispersion)
    confianza = min(100, len(comparables) * 5)  # Base: 5 puntos por comparable, max 100

    # Penalizar si hay mucha dispersion
    if precio_m2_max > 0 and precio_m2_min > 0:
        dispersion = float((precio_m2_max - precio_m2_min) / precio_m2_medio)
        if dispersion > 0.5:  # >50% dispersion
            confianza = max(30, confianza - 20)
        elif dispersion > 0.3:  # >30% dispersion
            confianza = max(40, confianza - 10)

    # Guardar informe
    report = ACMReport.objects.create(
        tenant_id=tenant_id,
        lead_id=lead_id,
        valoracion_min=valoracion_min,
        valoracion_max=valoracion_max,
        valoracion_media=valoracion_media,
        precio_m2_min=precio_m2_min,
        precio_m2_max=precio_m2_max,
        precio_m2_medio=precio_m2_medio,
        zona=zona,
        tipo_propiedad=tipo or '',
        superficie_m2=metros,
        habitaciones=habitaciones,
        precio_anuncio=precio_anuncio,
        comparables=comparables_con_ajuste[:10],  # Guardar solo los 10 mejores
        num_comparables=len(comparables),
        ajustes={
            'antiguedad': {k: float(v) for k, v in AJUSTE_ANTIGUEDAD.items()},
            'fotos': {k: float(v) for k, v in AJUSTE_FOTOS.items()},
            'telefono': {k: float(v) for k, v in AJUSTE_TELEFONO.items()},
        },
        metodologia='comparables',
        confianza=confianza,
        created_by=user,
    )

    logger.info(f"ACM generado para lead {lead_id}: {valoracion_media:,.0f} EUR ({len(comparables)} comparables)")

    return {
        'success': True,
        'report_id': report.id,
        'valoracion_min': int(valoracion_min),
        'valoracion_max': int(valoracion_max),
        'valoracion_media': int(valoracion_media),
        'precio_m2_medio': float(precio_m2_medio.quantize(Decimal('0.01'))),
        'num_comparables': len(comparables),
        'confianza': confianza,
        'diferencia_precio': report.diferencia_precio,
        'diferencia_pct': report.diferencia_pct,
    }


def get_ultimo_acm(lead_id: str, tenant_id: int) -> Optional[ACMReport]:
    """Obtiene el ultimo informe ACM para un lead."""
    return ACMReport.objects.filter(
        lead_id=lead_id,
        tenant_id=tenant_id,
    ).order_by('-created_at').first()

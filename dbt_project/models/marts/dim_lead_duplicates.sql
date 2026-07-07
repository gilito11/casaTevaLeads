{{
    config(
        materialized='table',
        schema='marts',
        tags=['marts', 'duplicates']
    )
}}

/*
    Deteccion de duplicados cross-portal (mismo inmueble en 2+ portales,
    tipico en fotocasa/habitaclia/milanuncios que comparten grupo Adevinta).

    Estrategia de matching (pares, comparacion por rangos REALES):
    1. Mismo telefono normalizado (match exacto) - raro: dim_leads ya fusiona
       por telefono, pero se mantiene por si conviven variantes.
    2. Misma zona_clasificada (nombre canonico) + precio EXACTO + metros +-5%,
       en portales distintos. Precio exacto porque los cross-posts (mismo
       vendedor publicando en varios portales) llevan el mismo precio; con
       +-2% aparecen falsos positivos (pisos distintos de la misma zona con
       precios parecidos).

    NOTA: la version anterior usaba buckets FLOOR(precio/(precio*0.1)) que son
    CONSTANTES para precio>=10k (el precio no influia) y exigia ubicacion
    identica como string (cross-portal casi nunca coincide). Esta version
    compara rangos de verdad.

    Genera duplicate_group_id (lead_id minimo del grupo, propagado 2 niveles
    para cubrir cadenas A-B-C). Solo grupos con mas de un portal.

    Consumidores: badge "En N portales" en detail.html, API v1,
    y scripts/post_scrape_auto_queue.py (no contactar 2 veces al mismo
    vendedor via portales distintos).
*/

WITH leads AS (
    SELECT
        lead_id,
        tenant_id,
        source_portal,
        NULLIF(telefono_norm, '') AS telefono_norm,
        zona_clasificada,
        precio,
        superficie_m2 AS metros,
        ultima_actualizacion
    FROM {{ ref('dim_leads') }}
),

-- Pares de leads que parecen el mismo inmueble en portales distintos
pares AS (
    SELECT
        a.tenant_id,
        a.lead_id AS lead_a,
        b.lead_id AS lead_b,
        CASE
            WHEN a.telefono_norm IS NOT NULL AND a.telefono_norm = b.telefono_norm
            THEN 'phone' ELSE 'location'
        END AS match_type
    FROM leads a
    JOIN leads b
        ON a.tenant_id = b.tenant_id
        AND a.lead_id < b.lead_id
        AND a.source_portal <> b.source_portal
        AND (
            (a.telefono_norm IS NOT NULL AND a.telefono_norm = b.telefono_norm)
            OR (
                a.zona_clasificada IS NOT NULL AND a.zona_clasificada <> ''
                AND a.zona_clasificada = b.zona_clasificada
                AND COALESCE(a.precio, 0) > 0 AND COALESCE(b.precio, 0) > 0
                AND COALESCE(a.metros, 0) > 0 AND COALESCE(b.metros, 0) > 0
                AND a.precio = b.precio
                AND ABS(a.metros - b.metros) <= GREATEST(a.metros, b.metros) * 0.05
            )
        )
),

-- Aristas en ambos sentidos + identidad, para agrupar
aristas AS (
    SELECT tenant_id, lead_a AS lead_id, lead_b AS vecino, match_type FROM pares
    UNION ALL
    SELECT tenant_id, lead_b AS lead_id, lead_a AS vecino, match_type FROM pares
),

-- Nivel 1: cada lead toma el minimo entre el mismo y sus vecinos
grupo_n1 AS (
    SELECT
        tenant_id,
        lead_id,
        LEAST(lead_id, MIN(vecino)) AS grupo,
        MIN(match_type) AS match_type
    FROM aristas
    GROUP BY tenant_id, lead_id
),

-- Nivel 2: propaga el grupo del vecino (cubre cadenas A-B-C)
grupo_n2 AS (
    SELECT
        g.tenant_id,
        g.lead_id,
        LEAST(g.grupo, MIN(COALESCE(gv.grupo, g.grupo))) AS duplicate_group_id,
        g.match_type
    FROM grupo_n1 g
    LEFT JOIN aristas a ON a.tenant_id = g.tenant_id AND a.lead_id = g.lead_id
    LEFT JOIN grupo_n1 gv ON gv.tenant_id = a.tenant_id AND gv.lead_id = a.vecino
    GROUP BY g.tenant_id, g.lead_id, g.grupo, g.match_type
),

group_stats AS (
    SELECT
        g.tenant_id,
        g.lead_id,
        g.duplicate_group_id,
        g.match_type,
        COUNT(*) OVER (PARTITION BY g.tenant_id, g.duplicate_group_id) AS num_leads_grupo
    FROM grupo_n2 g
),

group_portal_stats AS (
    SELECT
        g.tenant_id,
        g.duplicate_group_id,
        COUNT(DISTINCT l.source_portal) AS num_portales,
        STRING_AGG(DISTINCT l.source_portal, ', ' ORDER BY l.source_portal) AS portales
    FROM grupo_n2 g
    JOIN leads l ON l.tenant_id = g.tenant_id AND l.lead_id = g.lead_id
    GROUP BY g.tenant_id, g.duplicate_group_id
)

SELECT DISTINCT
    gs.lead_id,
    gs.tenant_id,
    gs.duplicate_group_id,
    gs.match_type,
    gs.num_leads_grupo,
    gps.num_portales,
    gps.portales
FROM group_stats gs
JOIN group_portal_stats gps
    ON gps.tenant_id = gs.tenant_id
    AND gps.duplicate_group_id = gs.duplicate_group_id
WHERE gps.num_portales > 1

{{
    config(
        materialized='table',
        schema='marts',
        tags=['marts', 'duplicates']
    )
}}

/*
    Deteccion de duplicados cross-portal.

    Estrategia de matching:
    1. Por telefono normalizado (match exacto)
    2. Por ubicacion + precio (±10%) + metros (±5%)

    Genera duplicate_group_id para agrupar leads que parecen ser el mismo inmueble.
*/

WITH leads AS (
    SELECT
        lead_id,
        tenant_id,
        source_portal,
        telefono_norm,
        LOWER(TRIM(COALESCE(ubicacion, ''))) AS ubicacion_norm,
        COALESCE(precio, 0) AS precio,
        COALESCE(superficie_m2, 0) AS metros,
        ultima_actualizacion
    FROM {{ ref('dim_leads') }}
),

-- Grupo 1: Leads con mismo telefono (match exacto)
phone_matches AS (
    SELECT
        l1.tenant_id,
        l1.lead_id,
        -- Usar el lead_id mas antiguo como grupo
        FIRST_VALUE(l1.lead_id) OVER (
            PARTITION BY l1.tenant_id, l1.telefono_norm
            ORDER BY l1.ultima_actualizacion ASC
        ) AS duplicate_group_id,
        'phone' AS match_type
    FROM leads l1
    WHERE l1.telefono_norm IS NOT NULL
      AND l1.telefono_norm != ''
),

-- Grupo 2: Leads sin telefono pero con ubicacion + precio + metros similares
location_matches AS (
    SELECT
        l1.tenant_id,
        l1.lead_id,
        FIRST_VALUE(l1.lead_id) OVER (
            PARTITION BY
                l1.tenant_id,
                l1.ubicacion_norm,
                -- Agrupar precios en rangos de ±10%
                FLOOR(l1.precio / GREATEST(l1.precio * 0.1, 1000)),
                -- Agrupar metros en rangos de ±5%
                FLOOR(l1.metros / GREATEST(l1.metros * 0.05, 5))
            ORDER BY l1.ultima_actualizacion ASC
        ) AS duplicate_group_id,
        'location' AS match_type
    FROM leads l1
    WHERE (l1.telefono_norm IS NULL OR l1.telefono_norm = '')
      AND l1.ubicacion_norm != ''
      AND l1.precio > 0
      AND l1.metros > 0
),

-- Unir ambos grupos
all_matches AS (
    SELECT * FROM phone_matches
    UNION ALL
    SELECT * FROM location_matches
),

-- Calcular estadisticas por grupo
group_stats AS (
    SELECT
        am.tenant_id,
        am.lead_id,
        am.duplicate_group_id,
        am.match_type,
        COUNT(*) OVER (PARTITION BY am.tenant_id, am.duplicate_group_id) AS num_leads_grupo,
        COUNT(DISTINCT l.source_portal) OVER (PARTITION BY am.tenant_id, am.duplicate_group_id) AS num_portales,
        STRING_AGG(DISTINCT l.source_portal, ', ') OVER (PARTITION BY am.tenant_id, am.duplicate_group_id) AS portales
    FROM all_matches am
    JOIN leads l ON am.lead_id = l.lead_id AND am.tenant_id = l.tenant_id
)

SELECT DISTINCT
    lead_id,
    tenant_id,
    duplicate_group_id,
    match_type,
    num_leads_grupo,
    num_portales,
    portales
FROM group_stats
WHERE num_portales > 1  -- Solo grupos con multiples portales

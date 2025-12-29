{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard', 'mercado']
    )
}}

/*
    Análisis de precios por zona - para gráficos de barras y mapas de calor
    Muestra estadísticas de precios por zona geográfica
*/

SELECT
    tenant_id,
    zona_clasificada,
    tipo_propiedad,
    COUNT(*) AS num_inmuebles,

    -- Estadísticas de precio
    MIN(precio) AS precio_min,
    MAX(precio) AS precio_max,
    AVG(precio)::INTEGER AS precio_medio,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)::INTEGER AS precio_mediana,

    -- Estadísticas de precio por m2
    AVG(precio_por_m2)::INTEGER AS precio_m2_medio,
    MIN(precio_por_m2)::INTEGER AS precio_m2_min,
    MAX(precio_por_m2)::INTEGER AS precio_m2_max,

    -- Características medias
    AVG(superficie_m2)::INTEGER AS superficie_media,
    AVG(habitaciones)::NUMERIC(3,1) AS habitaciones_media,

    -- Calidad de los leads
    AVG(lead_score)::INTEGER AS lead_score_medio

FROM {{ ref('dim_leads') }}

WHERE precio > 0

GROUP BY
    tenant_id,
    zona_clasificada,
    tipo_propiedad

HAVING COUNT(*) >= 1

ORDER BY tenant_id, num_inmuebles DESC

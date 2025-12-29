{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard', 'mercado']
    )
}}

/*
    Distribución por tipología de inmuebles - para gráficos de pie/donut
    Muestra qué tipos de inmuebles se captan más
*/

SELECT
    tenant_id,
    tipo_propiedad,
    zona_clasificada,

    COUNT(*) AS total,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY tenant_id), 2) AS porcentaje,

    AVG(precio)::INTEGER AS precio_medio,
    AVG(precio_por_m2)::INTEGER AS precio_m2_medio,
    AVG(superficie_m2)::INTEGER AS superficie_media,
    AVG(habitaciones)::NUMERIC(3,1) AS habitaciones_media,

    -- Rango de precios
    MIN(precio)::INTEGER AS precio_min,
    MAX(precio)::INTEGER AS precio_max

FROM {{ ref('dim_leads') }}

WHERE precio > 0

GROUP BY
    tenant_id,
    tipo_propiedad,
    zona_clasificada

ORDER BY tenant_id, total DESC

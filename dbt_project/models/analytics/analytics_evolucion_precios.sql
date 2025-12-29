{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard', 'mercado']
    )
}}

/*
    Evolución de precios en el tiempo - para gráfico de tendencias
    Muestra cómo cambian los precios semana a semana
*/

SELECT
    tenant_id,
    DATE_TRUNC('week', fecha_primera_captura)::DATE AS semana,
    zona_clasificada,
    tipo_propiedad,

    COUNT(*) AS num_inmuebles,
    AVG(precio)::INTEGER AS precio_medio,
    AVG(precio_por_m2)::INTEGER AS precio_m2_medio,

    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY precio)::INTEGER AS precio_p25,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio)::INTEGER AS precio_mediana,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY precio)::INTEGER AS precio_p75,

    AVG(superficie_m2)::INTEGER AS superficie_media

FROM {{ ref('dim_leads') }}

WHERE
    precio > 0
    AND fecha_primera_captura >= CURRENT_DATE - INTERVAL '6 months'

GROUP BY
    tenant_id,
    DATE_TRUNC('week', fecha_primera_captura),
    zona_clasificada,
    tipo_propiedad

HAVING COUNT(*) >= 1

ORDER BY semana DESC, num_inmuebles DESC

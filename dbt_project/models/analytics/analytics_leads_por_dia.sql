{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard']
    )
}}

/*
    Leads captados por día - para gráfico de línea temporal
    Muestra la evolución de captación de leads por tenant y portal
*/

SELECT
    tenant_id,
    DATE(fecha_primera_captura) AS fecha,
    source_portal AS portal,
    zona_clasificada,
    COUNT(*) AS leads_captados,
    COUNT(DISTINCT telefono_norm) AS leads_unicos,
    AVG(precio) AS precio_medio,
    AVG(lead_score) AS score_medio

FROM {{ ref('dim_leads') }}

GROUP BY
    tenant_id,
    DATE(fecha_primera_captura),
    source_portal,
    zona_clasificada

ORDER BY fecha DESC

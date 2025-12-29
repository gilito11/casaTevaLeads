{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard', 'conversion']
    )
}}

/*
    Embudo de conversión - para gráfico de funnel
    Muestra el estado de los leads por tenant
*/

WITH estados AS (
    SELECT
        tenant_id,
        estado,
        COUNT(*) AS total_leads,
        AVG(lead_score) AS score_medio,
        AVG(precio) AS precio_medio

    FROM {{ ref('dim_leads') }}

    GROUP BY tenant_id, estado
),

totales AS (
    SELECT
        tenant_id,
        SUM(total_leads) AS total_tenant
    FROM estados
    GROUP BY tenant_id
)

SELECT
    e.tenant_id,
    e.estado,
    e.total_leads,
    e.score_medio,
    e.precio_medio,
    t.total_tenant,
    ROUND(100.0 * e.total_leads / NULLIF(t.total_tenant, 0), 2) AS porcentaje,

    -- Orden para el embudo
    CASE e.estado
        WHEN 'NUEVO' THEN 1
        WHEN 'EN_PROCESO' THEN 2
        WHEN 'CONTACTADO_SIN_RESPUESTA' THEN 3
        WHEN 'INTERESADO' THEN 4
        WHEN 'EN_ESPERA' THEN 5
        WHEN 'NO_INTERESADO' THEN 6
        WHEN 'NO_CONTACTAR' THEN 7
        WHEN 'YA_VENDIDO' THEN 8
        WHEN 'CLIENTE' THEN 9
        ELSE 10
    END AS orden_embudo

FROM estados e
JOIN totales t ON e.tenant_id = t.tenant_id

ORDER BY e.tenant_id, orden_embudo

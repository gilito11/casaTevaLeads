{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard', 'kpis']
    )
}}

/*
    KPIs principales por tenant - para cards de resumen
    Métricas clave del negocio
*/

WITH base AS (
    SELECT
        tenant_id,
        lead_id,
        estado,
        lead_score,
        precio,
        fecha_primera_captura,
        fecha_primer_contacto,
        fecha_ultimo_contacto,
        source_portal
    FROM {{ ref('dim_leads') }}
),

metricas AS (
    SELECT
        tenant_id,

        -- Volumen total
        COUNT(*) AS total_leads,

        -- Por estado
        SUM(CASE WHEN estado = 'NUEVO' THEN 1 ELSE 0 END) AS leads_nuevos,
        SUM(CASE WHEN estado = 'EN_PROCESO' THEN 1 ELSE 0 END) AS leads_en_proceso,
        SUM(CASE WHEN estado = 'INTERESADO' THEN 1 ELSE 0 END) AS leads_interesados,
        SUM(CASE WHEN estado = 'CLIENTE' THEN 1 ELSE 0 END) AS leads_convertidos,
        SUM(CASE WHEN estado IN ('NO_INTERESADO', 'NO_CONTACTAR', 'YA_VENDIDO') THEN 1 ELSE 0 END) AS leads_descartados,

        -- Valor potencial (suma de precios de leads activos)
        SUM(CASE WHEN estado NOT IN ('NO_INTERESADO', 'NO_CONTACTAR', 'YA_VENDIDO', 'CLIENTE') THEN precio ELSE 0 END) AS valor_pipeline,

        -- Valor convertido
        SUM(CASE WHEN estado = 'CLIENTE' THEN precio ELSE 0 END) AS valor_convertido,

        -- Calidad
        AVG(lead_score)::INTEGER AS score_medio,

        -- Tiempo medio de respuesta (días desde captura hasta primer contacto)
        AVG(
            CASE
                WHEN fecha_primer_contacto IS NOT NULL
                THEN EXTRACT(EPOCH FROM (fecha_primer_contacto - fecha_primera_captura)) / 86400
                ELSE NULL
            END
        )::NUMERIC(5,1) AS dias_medio_primer_contacto,

        -- Esta semana
        SUM(CASE WHEN fecha_primera_captura >= CURRENT_DATE - INTERVAL '7 days' THEN 1 ELSE 0 END) AS leads_ultima_semana,

        -- Este mes
        SUM(CASE WHEN fecha_primera_captura >= DATE_TRUNC('month', CURRENT_DATE) THEN 1 ELSE 0 END) AS leads_este_mes

    FROM base
    GROUP BY tenant_id
)

SELECT
    tenant_id,
    total_leads,
    leads_nuevos,
    leads_en_proceso,
    leads_interesados,
    leads_convertidos,
    leads_descartados,

    -- Tasas
    ROUND(100.0 * leads_convertidos / NULLIF(total_leads, 0), 2) AS tasa_conversion,
    ROUND(100.0 * leads_descartados / NULLIF(total_leads, 0), 2) AS tasa_descarte,
    ROUND(100.0 * (total_leads - leads_nuevos) / NULLIF(total_leads, 0), 2) AS tasa_gestion,

    -- Valores
    valor_pipeline,
    valor_convertido,
    score_medio,
    dias_medio_primer_contacto,

    -- Actividad reciente
    leads_ultima_semana,
    leads_este_mes

FROM metricas

ORDER BY tenant_id

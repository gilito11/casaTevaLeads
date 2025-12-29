{{
    config(
        materialized='view',
        schema='analytics',
        tags=['analytics', 'dashboard', 'portales']
    )
}}

/*
    Comparativa entre portales - para gráficos comparativos
    Muestra rendimiento de cada portal por tenant
*/

SELECT
    tenant_id,
    source_portal AS portal,

    -- Volumen
    COUNT(*) AS total_leads,
    COUNT(DISTINCT telefono_norm) AS leads_unicos,
    COUNT(DISTINCT zona_clasificada) AS zonas_cubiertas,

    -- Conversión
    SUM(CASE WHEN estado = 'CLIENTE' THEN 1 ELSE 0 END) AS convertidos,
    ROUND(100.0 * SUM(CASE WHEN estado = 'CLIENTE' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS tasa_conversion,

    -- Contactabilidad
    SUM(CASE WHEN estado NOT IN ('NUEVO') THEN 1 ELSE 0 END) AS contactados,
    ROUND(100.0 * SUM(CASE WHEN estado NOT IN ('NUEVO') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS tasa_contacto,

    -- Calidad
    AVG(lead_score)::INTEGER AS score_medio,
    AVG(precio)::INTEGER AS precio_medio,
    AVG(precio_por_m2)::INTEGER AS precio_m2_medio,

    -- Completitud de datos
    ROUND(100.0 * SUM(CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS pct_con_email,
    ROUND(100.0 * SUM(CASE WHEN nombre_contacto IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS pct_con_nombre,

    -- Fechas
    MIN(fecha_primera_captura) AS primera_captura,
    MAX(fecha_primera_captura) AS ultima_captura

FROM {{ ref('dim_leads') }}

GROUP BY tenant_id, source_portal

ORDER BY tenant_id, total_leads DESC

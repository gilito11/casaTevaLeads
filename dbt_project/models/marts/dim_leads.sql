{{
    config(
        materialized='incremental',
        unique_key=['tenant_id', 'lead_unique_key'],
        schema='marts',
        tags=['marts', 'leads', 'incremental'],
        on_schema_change='sync_all_columns'
    )
}}

/*
    Dimension table for leads from all portals.

    This model:
    - Unions all staging models (Fotocasa, Milanuncios, Habitaclia, Idealista)
    - Deduplicates by tenant_id + telefono_norm (keeps most recent)
    - Adds CRM fields for lead management
    - Uses incremental materialization for efficiency

    Data sources:
    - Botasaurus scrapers: Fotocasa, Habitaclia (free)
    - ScrapingBee scrapers: Milanuncios, Idealista (paid API - stealth proxy)
*/

WITH all_staging_sources AS (
    -- Fotocasa listings
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion, fotos_json
    FROM {{ ref('stg_fotocasa') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}

    UNION ALL

    -- Milanuncios listings
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion, fotos_json
    FROM {{ ref('stg_milanuncios') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}

    UNION ALL

    -- Habitaclia listings
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion, fotos_json
    FROM {{ ref('stg_habitaclia') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}

    UNION ALL

    -- Idealista listings (ScrapingBee)
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion, fotos_json
    FROM {{ ref('stg_idealista') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}
),

deduplicated AS (
    SELECT
        *,
        -- Create a unique key: use phone when available, otherwise use URL
        -- NULLIF handles empty strings ('') that COALESCE would not catch
        COALESCE(NULLIF(telefono_norm, ''), MD5(url)) AS lead_unique_key,
        -- Use ROW_NUMBER to keep most recent listing per tenant + unique key
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, COALESCE(NULLIF(telefono_norm, ''), MD5(url))
            ORDER BY scraping_timestamp DESC, created_at DESC
        ) AS rn
    FROM all_staging_sources
),

enriched AS (
    SELECT
        -- Generate a unique lead_id using MD5 hash
        MD5(tenant_id::TEXT || '-' || lead_unique_key) AS lead_id,
        lead_unique_key,

        -- Source information
        raw_listing_id AS source_listing_id,
        tenant_id,
        portal AS source_portal,
        data_lake_path,

        -- Contact information
        telefono_norm,
        telefono_raw,
        email,
        nombre_contacto,
        anunciante,

        -- Property information
        titulo,
        descripcion,
        url AS listing_url,
        ubicacion,
        zona_clasificada,
        tipo_propiedad,
        superficie_m2,
        habitaciones,
        banos,
        precio,
        precio_por_m2,
        fotos_json,

        -- Lead classification
        es_particular,
        permite_inmobiliarias,

        -- CRM fields - initialize for new leads
        'NUEVO' AS estado,
        NULL::INTEGER AS asignado_a,
        NULL::TIMESTAMP AS fecha_asignacion,
        NULL::TIMESTAMP AS fecha_primer_contacto,
        NULL::TIMESTAMP AS fecha_ultimo_contacto,
        0 AS num_contactos,
        NULL::TEXT AS notas,
        NULL::TEXT AS motivo_descarte,

        -- Lead quality score (0-100)
        -- Criterios: telefono (+30), precio (<100k:+20, 100-200k:+15, >200k:+10),
        -- zona prioritaria (+15), antiguedad (<24h:+20, <7d:+10, >7d:+5), particular (+10)
        (
            -- Telefono disponible: +30pts (lo mas importante)
            CASE WHEN telefono_norm IS NOT NULL AND telefono_norm != '' THEN 30 ELSE 0 END
            -- Precio: <100k:+20, 100-200k:+15, >200k:+10
            + CASE
                WHEN precio IS NULL THEN 0
                WHEN precio < 100000 THEN 20
                WHEN precio <= 200000 THEN 15
                ELSE 10
            END
            -- Zona prioritaria (Salou, Cambrils, Tarragona): +15pts
            + CASE
                WHEN LOWER(COALESCE(zona_clasificada, '')) LIKE '%salou%'
                     OR LOWER(COALESCE(zona_clasificada, '')) LIKE '%cambrils%'
                     OR LOWER(COALESCE(zona_clasificada, '')) LIKE '%tarragona%'
                     OR LOWER(COALESCE(ubicacion, '')) LIKE '%salou%'
                     OR LOWER(COALESCE(ubicacion, '')) LIKE '%cambrils%'
                     OR LOWER(COALESCE(ubicacion, '')) LIKE '%tarragona%'
                THEN 15 ELSE 0
            END
            -- Antiguedad: <24h:+20, <7d:+10, >7d:+5
            + CASE
                WHEN fecha_publicacion IS NULL THEN 5
                WHEN fecha_publicacion >= NOW() - INTERVAL '24 hours' THEN 20
                WHEN fecha_publicacion >= NOW() - INTERVAL '7 days' THEN 10
                ELSE 5
            END
            -- Particular confirmado: +10pts
            + CASE WHEN es_particular = TRUE THEN 10 ELSE 0 END
        ) AS lead_score,

        -- Timestamps
        fecha_publicacion,
        scraping_timestamp AS fecha_primera_captura,
        scraping_timestamp AS ultima_actualizacion,
        CURRENT_TIMESTAMP AS created_at_marts

    FROM deduplicated
    WHERE rn = 1  -- Keep only the most recent record per tenant + phone
),

final AS (
    SELECT
        -- Primary key
        lead_id,
        lead_unique_key,
        tenant_id,

        -- Source tracking
        source_listing_id,
        source_portal,
        data_lake_path,

        -- Contact information (PII)
        telefono_norm,
        telefono_raw,
        email,
        nombre_contacto,
        anunciante,

        -- Property interest
        titulo,
        descripcion,
        listing_url,
        ubicacion,
        zona_clasificada,
        tipo_propiedad,
        superficie_m2,
        habitaciones,
        banos,
        precio,
        precio_por_m2,
        fotos_json,

        -- Lead metadata
        es_particular,
        permite_inmobiliarias,
        lead_score,

        -- CRM workflow fields
        estado,
        asignado_a,
        fecha_asignacion,
        fecha_primer_contacto,
        fecha_ultimo_contacto,
        num_contactos,
        notas,
        motivo_descarte,

        -- Timestamps
        fecha_publicacion,
        fecha_primera_captura,
        ultima_actualizacion,
        created_at_marts

    FROM enriched
)

SELECT * FROM final

{% if is_incremental() %}
    -- On incremental runs, update existing records or insert new ones
    -- This is handled by dbt's unique_key configuration
{% endif %}

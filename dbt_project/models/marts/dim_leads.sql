{{
    config(
        materialized='incremental',
        unique_key=['tenant_id', 'telefono_norm'],
        schema='marts',
        tags=['marts', 'leads', 'incremental'],
        on_schema_change='sync_all_columns'
    )
}}

/*
    Dimension table for leads from all portals.

    This model:
    - Unions all staging models (Fotocasa, Milanuncios, Wallapop, Pisos, Habitaclia, Idealista)
    - Deduplicates by tenant_id + telefono_norm (keeps most recent)
    - Adds CRM fields for lead management
    - Uses incremental materialization for efficiency

    Data sources:
    - Botasaurus scrapers: Fotocasa, Pisos.com, Habitaclia (free)
    - ScrapingBee scrapers: Milanuncios, Idealista (paid API - stealth proxy)
*/

WITH all_staging_sources AS (
    -- Fotocasa listings
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion
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
        es_particular, permite_inmobiliarias, fecha_publicacion
    FROM {{ ref('stg_milanuncios') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}

    UNION ALL

    -- Wallapop listings
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion
    FROM {{ ref('stg_wallapop') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}

    UNION ALL

    -- Pisos.com listings
    SELECT
        raw_listing_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion
    FROM {{ ref('stg_pisos') }}
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
        es_particular, permite_inmobiliarias, fecha_publicacion
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
        es_particular, permite_inmobiliarias, fecha_publicacion
    FROM {{ ref('stg_idealista') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}
),

deduplicated AS (
    SELECT
        *,
        -- Use ROW_NUMBER to keep most recent listing per tenant + phone
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, telefono_norm
            ORDER BY scraping_timestamp DESC, created_at DESC
        ) AS rn
    FROM all_staging_sources
),

enriched AS (
    SELECT
        -- Generate a unique lead_id using MD5 hash
        MD5(tenant_id::TEXT || '-' || telefono_norm) AS lead_id,

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

        -- Lead classification
        es_particular,
        permite_inmobiliarias,

        -- CRM fields - initialize for new leads
        'NUEVO' AS estado,
        NULL AS asignado_a,
        NULL AS fecha_asignacion,
        NULL AS fecha_primer_contacto,
        NULL AS fecha_ultimo_contacto,
        0 AS num_contactos,
        NULL AS notas,
        NULL AS motivo_descarte,

        -- Lead quality score (0-100)
        CASE
            -- Higher score for complete information
            WHEN email IS NOT NULL AND nombre_contacto IS NOT NULL THEN 85
            WHEN email IS NOT NULL OR nombre_contacto IS NOT NULL THEN 70
            ELSE 50
        END +
        CASE
            -- Bonus for good zones
            WHEN zona_clasificada LIKE 'Barcelona - Eixample' THEN 10
            WHEN zona_clasificada LIKE 'Barcelona -%' THEN 5
            ELSE 0
        END AS lead_score,

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

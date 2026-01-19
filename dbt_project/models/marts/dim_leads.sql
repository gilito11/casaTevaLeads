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
        -- Normalize tipo_propiedad to Title Case and merge variants
        CASE
            WHEN LOWER(tipo_propiedad) IN ('piso', 'pisos') THEN 'Piso'
            WHEN LOWER(tipo_propiedad) IN ('apartamento', 'apartamentos') THEN 'Apartamento'
            WHEN LOWER(tipo_propiedad) IN ('casa', 'casas', 'chalet', 'chalets') THEN 'Casa'
            WHEN LOWER(tipo_propiedad) IN ('ático', 'atico', 'áticos', 'aticos') THEN 'Ático'
            WHEN LOWER(tipo_propiedad) IN ('dúplex', 'duplex') THEN 'Dúplex'
            WHEN LOWER(tipo_propiedad) IN ('estudio', 'estudios') THEN 'Estudio'
            WHEN LOWER(tipo_propiedad) IN ('local', 'locales') THEN 'Local'
            WHEN LOWER(tipo_propiedad) IN ('garaje', 'garajes', 'parking') THEN 'Garaje'
            WHEN LOWER(tipo_propiedad) IN ('terreno', 'terrenos', 'parcela', 'parcelas') THEN 'Terreno'
            WHEN LOWER(tipo_propiedad) IN ('finca', 'fincas') THEN 'Finca'
            ELSE 'Otros'
        END AS tipo_propiedad,
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
        -- Criterios optimizados para detectar vendedores receptivos:
        -- 1. dias_en_mercado: >30 dias = mas receptivo (+30 pts max)
        -- 2. tiene_telefono: telefono visible = menos spam recibido (+20 pts)
        -- 3. num_fotos: pocas fotos = particular amateur (+10 pts si <5 fotos)
        -- 4. precio_bajo: <100k = vendedor motivado (+20 pts)
        (
            -- 1. Dias en mercado: mas tiempo = mas receptivo (0-30 pts)
            -- Usando fecha_publicacion si existe, sino scraping_timestamp
            CASE
                WHEN fecha_publicacion IS NOT NULL THEN
                    LEAST(30, EXTRACT(DAY FROM NOW() - fecha_publicacion)::INTEGER)
                ELSE
                    LEAST(30, EXTRACT(DAY FROM NOW() - scraping_timestamp)::INTEGER)
            END
            -- 2. Tiene telefono visible: +20pts (menos spam recibido)
            + CASE WHEN telefono_norm IS NOT NULL AND telefono_norm != '' THEN 20 ELSE 0 END
            -- 3. Pocas fotos (<5): +10pts (particular amateur, no agencia)
            + CASE
                WHEN fotos_json IS NULL THEN 10
                WHEN jsonb_array_length(fotos_json) < 5 THEN 10
                ELSE 0
            END
            -- 4. Precio bajo (<100k): +20pts (vendedor motivado)
            + CASE
                WHEN precio IS NOT NULL AND precio < 100000 THEN 20
                ELSE 0
            END
            -- Bonus: particular confirmado +10pts
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

-- Image scores from staging (table created via pre_hook if not exists)
image_scores AS (
    SELECT
        lead_id,
        image_score,
        images_analyzed
    FROM {{ ref('stg_lead_image_scores') }}
),

-- Price history for detecting price drops
price_history AS (
    SELECT
        tenant_id,
        portal,
        anuncio_id,
        precio,
        fecha_captura,
        LAG(precio) OVER (
            PARTITION BY tenant_id, portal, anuncio_id
            ORDER BY fecha_captura
        ) AS precio_anterior
    FROM raw.listing_price_history
),

-- Get most recent price change per listing
price_changes AS (
    SELECT DISTINCT ON (tenant_id, portal, anuncio_id)
        tenant_id,
        portal,
        anuncio_id,
        precio AS precio_actual,
        precio_anterior,
        CASE
            WHEN precio_anterior IS NOT NULL AND precio_anterior > 0
            THEN ROUND(((precio - precio_anterior) / precio_anterior * 100)::NUMERIC, 1)
            ELSE NULL
        END AS precio_cambio_pct
    FROM price_history
    WHERE precio_anterior IS NOT NULL
    ORDER BY tenant_id, portal, anuncio_id, fecha_captura DESC
),

final AS (
    SELECT
        -- Primary key
        e.lead_id,
        e.lead_unique_key,
        e.tenant_id,

        -- Source tracking
        e.source_listing_id,
        e.source_portal,
        e.data_lake_path,

        -- Contact information (PII)
        e.telefono_norm,
        e.telefono_raw,
        e.email,
        e.nombre_contacto,
        e.anunciante,

        -- Property interest
        e.titulo,
        e.descripcion,
        e.listing_url,
        e.ubicacion,
        e.zona_clasificada,
        e.tipo_propiedad,
        e.superficie_m2,
        e.habitaciones,
        e.banos,
        e.precio,
        e.precio_por_m2,
        e.fotos_json,

        -- Price tracking (for detecting price drops)
        pc.precio_anterior,
        pc.precio_cambio_pct,

        -- Days on market (since first capture)
        EXTRACT(DAY FROM NOW() - e.fecha_primera_captura)::INTEGER AS dias_en_mercado,

        -- Lead metadata
        e.es_particular,
        e.permite_inmobiliarias,
        e.lead_score,

        -- Image analysis score (0-30 from Ollama Vision, NULL if not analyzed)
        lis.image_score,
        lis.images_analyzed,

        -- Combined score: lead_score + image_score (max 130 = 100 + 30)
        -- Bonus +15 if price dropped (motivated seller)
        e.lead_score + COALESCE(lis.image_score, 0)
            + CASE WHEN pc.precio_cambio_pct < 0 THEN 15 ELSE 0 END AS lead_score_total,

        -- CRM workflow fields
        e.estado,
        e.asignado_a,
        e.fecha_asignacion,
        e.fecha_primer_contacto,
        e.fecha_ultimo_contacto,
        e.num_contactos,
        e.notas,
        e.motivo_descarte,

        -- Timestamps
        e.fecha_publicacion,
        e.fecha_primera_captura,
        e.ultima_actualizacion,
        e.created_at_marts

    FROM enriched e
    LEFT JOIN image_scores lis ON e.lead_id = lis.lead_id
    LEFT JOIN price_changes pc ON e.tenant_id = pc.tenant_id
        AND e.source_portal = pc.portal
        AND e.source_listing_id::TEXT = pc.anuncio_id
)

SELECT * FROM final

{% if is_incremental() %}
    -- On incremental runs, update existing records or insert new ones
    -- This is handled by dbt's unique_key configuration
{% endif %}

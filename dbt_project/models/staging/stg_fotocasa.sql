{{
    config(
        materialized='view',
        schema='staging',
        tags=['staging', 'fotocasa']
    )
}}

/*
    Staging model for Fotocasa listings.

    This model:
    - Extracts fields from JSONB raw_data
    - Normalizes phone numbers
    - Classifies zones
    - Filters for particular sellers who allow real estate agencies
*/

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'fotocasa'
),

extracted AS (
    SELECT
        -- IDs and metadata
        id AS raw_listing_id,
        tenant_id,
        portal,
        data_lake_path,
        scraping_timestamp,
        created_at,

        -- Extract fields from JSONB (using actual field names from scraper)
        raw_data->>'url' AS url,
        raw_data->>'titulo' AS titulo,
        raw_data->>'descripcion' AS descripcion,
        COALESCE(raw_data->>'direccion', raw_data->>'zona_geografica') AS ubicacion,
        raw_data->>'telefono' AS telefono_raw,
        raw_data->>'email' AS email,
        raw_data->>'nombre' AS nombre_contacto,
        raw_data->>'vendedor' AS anunciante,
        raw_data->>'zona_geografica' AS zona_geografica,

        -- Numeric fields (already stored as numbers by scraper)
        (raw_data->>'precio')::NUMERIC AS precio_num,
        (raw_data->>'metros')::INTEGER AS metros,
        (raw_data->>'habitaciones')::INTEGER AS habitaciones_num,

        -- Type extraction from title or tipo_inmueble
        COALESCE(raw_data->>'tipo_inmueble', raw_data->>'tipo_propiedad') AS tipo_inmueble,

        -- Boolean fields
        (raw_data->>'es_particular')::BOOLEAN AS es_particular_bool,

        -- Photos
        raw_data->'fotos' AS fotos_json,

        -- Store entire raw_data for reference
        raw_data

    FROM source
),

normalized AS (
    SELECT
        *,

        -- Normalize phone number: remove spaces, +34, 0034, parentheses, dashes
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    COALESCE(telefono_raw, ''),
                    '(\+34|0034)',  -- Remove country code
                    '',
                    'g'
                ),
                '[\s\(\)\-]',  -- Remove spaces, parentheses, dashes
                '',
                'g'
            ),
            '^0+',  -- Remove leading zeros
            ''
        ) AS telefono_norm,

        -- Price already numeric from scraper
        COALESCE(precio_num, 0)::INTEGER AS precio,

        -- Metros already extracted
        COALESCE(metros, 0) AS superficie_m2,

        -- Habitaciones already extracted
        COALESCE(habitaciones_num, 0) AS habitaciones,

        -- Banos not available in current scraper
        0 AS banos,

        -- Es particular already boolean
        COALESCE(es_particular_bool, TRUE) AS es_particular,

        -- Not applicable for Fotocasa
        NULL::BOOLEAN AS permite_inmobiliarias,

        -- Extract property type from title
        CASE
            WHEN LOWER(titulo) LIKE '%piso%' THEN 'piso'
            WHEN LOWER(titulo) LIKE '%apartamento%' THEN 'apartamento'
            WHEN LOWER(titulo) LIKE '%casa%' OR LOWER(titulo) LIKE '%chalet%' THEN 'casa'
            WHEN LOWER(titulo) LIKE '%ático%' OR LOWER(titulo) LIKE '%atico%' THEN 'atico'
            WHEN LOWER(titulo) LIKE '%dúplex%' OR LOWER(titulo) LIKE '%duplex%' THEN 'duplex'
            WHEN LOWER(titulo) LIKE '%estudio%' THEN 'estudio'
            WHEN LOWER(titulo) LIKE '%local%' THEN 'local'
            WHEN LOWER(titulo) LIKE '%terreno%' OR LOWER(titulo) LIKE '%parcela%' THEN 'terreno'
            WHEN tipo_inmueble IS NOT NULL THEN LOWER(tipo_inmueble)
            ELSE 'otros'
        END AS tipo_propiedad

    FROM extracted
),

classified AS (
    SELECT
        *,

        -- Use zona_geografica from scraper (already has good zone names)
        COALESCE(zona_geografica, 'Otros') AS zona_clasificada,

        -- Calculate price per m2
        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2,

        -- Fecha publicacion not available
        NULL::TIMESTAMP AS fecha_publicacion

    FROM normalized
),

final AS (
    SELECT
        -- Primary keys
        raw_listing_id,
        tenant_id,

        -- Source metadata
        portal,
        data_lake_path,
        scraping_timestamp,
        created_at,

        -- Listing details
        url,
        titulo,
        descripcion,
        ubicacion,
        zona_clasificada,

        -- Contact information
        telefono_raw,
        telefono_norm,
        email,
        nombre_contacto,
        anunciante,

        -- Property details
        tipo_propiedad,
        superficie_m2,
        habitaciones,
        banos,
        precio,
        precio_por_m2,

        -- Flags
        es_particular,
        permite_inmobiliarias,

        -- Publishing info
        fecha_publicacion,

        -- Photos
        fotos_json,

        -- Raw data for reference
        raw_data

    FROM classified

    -- Apply filters as specified
    WHERE
        precio > 0  -- Must have a valid price
)

SELECT * FROM final

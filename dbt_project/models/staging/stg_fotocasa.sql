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

        -- Extract fields from JSONB
        raw_data->>'url' AS url,
        raw_data->>'titulo' AS titulo,
        raw_data->>'precio' AS precio_text,
        raw_data->>'descripcion' AS descripcion,
        raw_data->>'ubicacion' AS ubicacion,
        raw_data->>'telefono' AS telefono_raw,
        raw_data->>'email' AS email,
        raw_data->>'nombre_contacto' AS nombre_contacto,
        raw_data->>'tipo_propiedad' AS tipo_propiedad,
        raw_data->>'superficie' AS superficie_text,
        raw_data->>'habitaciones' AS habitaciones_text,
        raw_data->>'banos' AS banos_text,
        raw_data->>'es_particular' AS es_particular_text,
        raw_data->>'permite_inmobiliarias' AS permite_inmobiliarias_text,
        raw_data->>'anunciante' AS anunciante,
        raw_data->>'fecha_publicacion' AS fecha_publicacion,

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
                    '(\\+34|0034)',  -- Remove country code
                    '',
                    'g'
                ),
                '[\\s\\(\\)\\-]',  -- Remove spaces, parentheses, dashes
                '',
                'g'
            ),
            '^0+',  -- Remove leading zeros
            ''
        ) AS telefono_norm,

        -- Parse numeric fields
        CAST(
            REGEXP_REPLACE(COALESCE(precio_text, '0'), '[^0-9]', '', 'g')
            AS INTEGER
        ) AS precio,

        CAST(
            REGEXP_REPLACE(COALESCE(superficie_text, '0'), '[^0-9]', '', 'g')
            AS INTEGER
        ) AS superficie_m2,

        CAST(
            REGEXP_REPLACE(COALESCE(habitaciones_text, '0'), '[^0-9]', '', 'g')
            AS INTEGER
        ) AS habitaciones,

        CAST(
            REGEXP_REPLACE(COALESCE(banos_text, '0'), '[^0-9]', '', 'g')
            AS INTEGER
        ) AS banos,

        -- Parse boolean fields
        CASE
            WHEN LOWER(es_particular_text) IN ('true', 'si', 'sí', 's', '1', 'yes') THEN TRUE
            WHEN LOWER(es_particular_text) IN ('false', 'no', 'n', '0') THEN FALSE
            ELSE NULL
        END AS es_particular,

        CASE
            WHEN LOWER(permite_inmobiliarias_text) IN ('true', 'si', 'sí', 's', '1', 'yes') THEN TRUE
            WHEN LOWER(permite_inmobiliarias_text) IN ('false', 'no', 'n', '0') THEN FALSE
            ELSE NULL
        END AS permite_inmobiliarias

    FROM extracted
),

classified AS (
    SELECT
        *,

        -- Classify zone based on ubicacion
        CASE
            -- Barcelona zones
            WHEN LOWER(ubicacion) LIKE '%eixample%' THEN 'Barcelona - Eixample'
            WHEN LOWER(ubicacion) LIKE '%gràcia%' OR LOWER(ubicacion) LIKE '%gracia%' THEN 'Barcelona - Gràcia'
            WHEN LOWER(ubicacion) LIKE '%sant%' AND LOWER(ubicacion) LIKE '%martí%' THEN 'Barcelona - Sant Martí'
            WHEN LOWER(ubicacion) LIKE '%sants%' THEN 'Barcelona - Sants'
            WHEN LOWER(ubicacion) LIKE '%les corts%' THEN 'Barcelona - Les Corts'
            WHEN LOWER(ubicacion) LIKE '%sarrià%' OR LOWER(ubicacion) LIKE '%sarria%' THEN 'Barcelona - Sarrià-Sant Gervasi'
            WHEN LOWER(ubicacion) LIKE '%ciutat vella%' THEN 'Barcelona - Ciutat Vella'
            WHEN LOWER(ubicacion) LIKE '%horta%' THEN 'Barcelona - Horta-Guinardó'
            WHEN LOWER(ubicacion) LIKE '%nou barris%' THEN 'Barcelona - Nou Barris'
            WHEN LOWER(ubicacion) LIKE '%barcelona%' THEN 'Barcelona - Otros'

            -- Metropolitan area
            WHEN LOWER(ubicacion) LIKE '%hospitalet%' OR LOWER(ubicacion) LIKE '%l''hospitalet%' THEN 'L''Hospitalet de Llobregat'
            WHEN LOWER(ubicacion) LIKE '%badalona%' THEN 'Badalona'
            WHEN LOWER(ubicacion) LIKE '%santa coloma%' THEN 'Santa Coloma de Gramenet'
            WHEN LOWER(ubicacion) LIKE '%cornellà%' OR LOWER(ubicacion) LIKE '%cornella%' THEN 'Cornellà de Llobregat'
            WHEN LOWER(ubicacion) LIKE '%terrassa%' THEN 'Terrassa'
            WHEN LOWER(ubicacion) LIKE '%sabadell%' THEN 'Sabadell'

            ELSE 'Otros'
        END AS zona_clasificada,

        -- Calculate price per m2
        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2

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

        -- Raw data for reference
        raw_data

    FROM classified

    -- Apply filters as specified
    WHERE
        es_particular = TRUE
        AND permite_inmobiliarias = TRUE
        AND telefono_norm IS NOT NULL  -- Must have a phone number
        AND LENGTH(telefono_norm) >= 9  -- Valid phone number length
        AND precio > 0  -- Must have a valid price
)

SELECT * FROM final

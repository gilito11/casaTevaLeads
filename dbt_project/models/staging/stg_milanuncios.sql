{{
    config(
        materialized='view',
        schema='staging',
        tags=['staging', 'milanuncios']
    )
}}

/*
    Staging model for Milanuncios listings.

    This model:
    - Extracts fields from JSONB raw_data
    - Normalizes phone numbers
    - Classifies zones
    - Filters for particular sellers
*/

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'milanuncios'
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

        -- Extract fields from JSONB (campos del scraper de Milanuncios)
        raw_data->>'anuncio_id' AS anuncio_id,
        COALESCE(raw_data->>'url', raw_data->>'url_anuncio', raw_data->>'detail_url') AS url,
        raw_data->>'titulo' AS titulo,
        COALESCE(raw_data->>'precio', (raw_data->'precio')::TEXT) AS precio_text,
        raw_data->>'descripcion' AS descripcion,
        COALESCE(raw_data->>'ubicacion', raw_data->>'direccion') AS ubicacion,
        raw_data->>'codigo_postal' AS codigo_postal,
        COALESCE(raw_data->>'telefono', raw_data->>'telefono_norm') AS telefono_raw,
        raw_data->>'email' AS email,
        COALESCE(raw_data->>'vendedor', raw_data->>'nombre', 'Particular') AS vendedor,
        COALESCE(raw_data->>'metros', (raw_data->'metros')::TEXT) AS metros_text,
        COALESCE(raw_data->>'habitaciones', (raw_data->'habitaciones')::TEXT) AS habitaciones_text,
        COALESCE(raw_data->>'banos', (raw_data->'banos')::TEXT) AS banos_text,
        raw_data->>'certificado_energetico' AS certificado_energetico,
        COALESCE(raw_data->>'zona_busqueda', raw_data->>'zona_geografica', raw_data->>'zona') AS zona_busqueda,
        raw_data->>'imagen_principal' AS imagen_principal,
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

        -- Parse numeric fields
        CAST(
            NULLIF(REGEXP_REPLACE(COALESCE(precio_text, ''), '[^0-9.]', '', 'g'), '')
            AS NUMERIC
        ) AS precio,

        CAST(
            NULLIF(REGEXP_REPLACE(COALESCE(metros_text, ''), '[^0-9]', '', 'g'), '')
            AS INTEGER
        ) AS superficie_m2,

        CAST(
            NULLIF(REGEXP_REPLACE(COALESCE(habitaciones_text, ''), '[^0-9]', '', 'g'), '')
            AS INTEGER
        ) AS habitaciones,

        CAST(
            NULLIF(REGEXP_REPLACE(COALESCE(banos_text, ''), '[^0-9]', '', 'g'), '')
            AS INTEGER
        ) AS banos,

        -- Milanuncios filtra por particulares en la URL (vendedor=part)
        TRUE AS es_particular,
        TRUE AS permite_inmobiliarias

    FROM extracted
),

classified AS (
    SELECT
        *,

        -- Classify zone based on ubicacion or zona_busqueda
        CASE
            -- Lleida zones
            WHEN LOWER(ubicacion) LIKE '%bordeta%' THEN 'Lleida - La Bordeta'
            WHEN LOWER(ubicacion) LIKE '%lleida%' OR LOWER(ubicacion) LIKE '%lerida%' THEN 'Lleida Ciudad'

            -- Tarragona Costa Dorada
            WHEN LOWER(ubicacion) LIKE '%salou%' THEN 'Costa Dorada - Salou'
            WHEN LOWER(ubicacion) LIKE '%cambrils%' THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(ubicacion) LIKE '%tarragona%' THEN 'Tarragona Ciudad'
            WHEN LOWER(ubicacion) LIKE '%reus%' THEN 'Tarragona - Reus'
            WHEN LOWER(ubicacion) LIKE '%vila-seca%' OR LOWER(ubicacion) LIKE '%vilaseca%' THEN 'Costa Dorada - Vila-seca'
            WHEN LOWER(ubicacion) LIKE '%torredembarra%' THEN 'Costa Dorada - Torredembarra'

            -- Fallback to zona_busqueda from scraper
            WHEN zona_busqueda IS NOT NULL THEN zona_busqueda

            ELSE 'Otros'
        END AS zona_clasificada,

        -- Calculate price per m2
        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2,

        -- Tipo de inmueble basado en URL o título
        CASE
            WHEN LOWER(url) LIKE '%pisos%' OR LOWER(titulo) LIKE '%piso%' THEN 'Piso'
            WHEN LOWER(url) LIKE '%casas%' OR LOWER(titulo) LIKE '%casa%' OR LOWER(titulo) LIKE '%chalet%' THEN 'Casa'
            WHEN LOWER(url) LIKE '%locales%' OR LOWER(titulo) LIKE '%local%' THEN 'Local'
            WHEN LOWER(url) LIKE '%garajes%' OR LOWER(titulo) LIKE '%garaje%' OR LOWER(titulo) LIKE '%parking%' THEN 'Garaje'
            WHEN LOWER(url) LIKE '%terrenos%' OR LOWER(titulo) LIKE '%terreno%' OR LOWER(titulo) LIKE '%parcela%' THEN 'Terreno'
            WHEN LOWER(titulo) LIKE '%finca%' THEN 'Finca'
            ELSE 'Otros'
        END AS tipo_propiedad

    FROM normalized
),

final AS (
    SELECT
        -- Primary keys
        raw_listing_id,
        tenant_id,
        anuncio_id AS external_id,

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
        codigo_postal,

        -- Contact information
        telefono_raw,
        telefono_norm,
        email,
        vendedor AS nombre_contacto,
        vendedor AS anunciante,

        -- Property details
        tipo_propiedad,
        superficie_m2,
        habitaciones,
        banos,
        precio,
        precio_por_m2,
        certificado_energetico,
        imagen_principal,

        -- Flags
        es_particular,
        permite_inmobiliarias,

        -- Publishing info (Milanuncios no lo proporciona directamente)
        NULL::TIMESTAMP AS fecha_publicacion,

        -- Photos
        fotos_json,

        -- Raw data for reference
        raw_data

    FROM classified

    -- Apply filters
    WHERE
        precio > 5000  -- Filter out rentals
)

SELECT * FROM final

{{
    config(
        materialized='view',
        schema='staging',
        tags=['staging', 'idealista']
    )
}}

/*
    Staging model for Idealista listings.

    This model:
    - Extracts fields from JSONB raw_data
    - Normalizes phone numbers
    - Classifies zones
    - Filters for particular sellers (when available)
*/

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'idealista'
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
        raw_data->>'anuncio_id' AS anuncio_id,
        raw_data->>'url' AS url,
        raw_data->>'titulo' AS titulo,
        raw_data->>'precio' AS precio_text,
        raw_data->>'descripcion' AS descripcion,
        raw_data->>'ubicacion' AS ubicacion,
        raw_data->>'codigo_postal' AS codigo_postal,
        raw_data->>'telefono' AS telefono_raw,
        raw_data->>'telefono_norm' AS telefono_norm_raw,
        raw_data->>'email' AS email,
        raw_data->>'vendedor' AS vendedor,
        raw_data->>'nombre' AS nombre,
        raw_data->>'metros' AS metros_text,
        raw_data->>'habitaciones' AS habitaciones_text,
        raw_data->>'banos' AS banos_text,
        raw_data->>'certificado_energetico' AS certificado_energetico,
        raw_data->>'zona_busqueda' AS zona_busqueda,
        raw_data->>'zona_geografica' AS zona_geografica,
        COALESCE((raw_data->>'es_particular')::BOOLEAN, TRUE) AS es_particular,
        raw_data->'fotos' AS fotos_json,

        -- ScrapingBee metadata
        raw_data->>'scraper_type' AS scraper_type,

        -- Store entire raw_data for reference
        raw_data

    FROM source
),

normalized AS (
    SELECT
        *,

        -- Use pre-normalized phone if available, otherwise normalize
        CASE
            WHEN telefono_norm_raw IS NOT NULL AND LENGTH(telefono_norm_raw) = 9
            THEN telefono_norm_raw
            ELSE
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            COALESCE(telefono_raw, ''),
                            '(\+34|0034)',
                            '',
                            'g'
                        ),
                        '[\s\(\)\-]',
                        '',
                        'g'
                    ),
                    '^0+',
                    ''
                )
        END AS telefono_norm,

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

        -- Idealista filters by particulares in URL
        TRUE AS permite_inmobiliarias

    FROM extracted
),

classified AS (
    SELECT
        *,

        -- Classify zone based on ubicacion or zona_geografica
        CASE
            -- Lleida zones
            WHEN LOWER(ubicacion) LIKE '%lleida%' OR LOWER(ubicacion) LIKE '%lerida%' THEN 'Lleida Ciudad'
            WHEN LOWER(ubicacion) LIKE '%balaguer%' THEN 'Lleida - Balaguer'
            WHEN LOWER(ubicacion) LIKE '%mollerussa%' THEN 'Lleida - Mollerussa'

            -- Tarragona Costa Dorada
            WHEN LOWER(ubicacion) LIKE '%salou%' THEN 'Costa Dorada - Salou'
            WHEN LOWER(ubicacion) LIKE '%cambrils%' THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(ubicacion) LIKE '%tarragona%' THEN 'Tarragona Ciudad'
            WHEN LOWER(ubicacion) LIKE '%reus%' THEN 'Tarragona - Reus'
            WHEN LOWER(ubicacion) LIKE '%vila-seca%' OR LOWER(ubicacion) LIKE '%vilaseca%' THEN 'Costa Dorada - Vila-seca'
            WHEN LOWER(ubicacion) LIKE '%torredembarra%' THEN 'Costa Dorada - Torredembarra'
            WHEN LOWER(ubicacion) LIKE '%calafell%' THEN 'Costa Dorada - Calafell'
            WHEN LOWER(ubicacion) LIKE '%vendrell%' THEN 'Costa Dorada - El Vendrell'

            -- Fallback to zona_geografica from scraper
            WHEN zona_geografica IS NOT NULL THEN zona_geografica

            ELSE 'Otros'
        END AS zona_clasificada,

        -- Calculate price per m2
        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2,

        -- Tipo de inmueble basado en URL o título
        CASE
            WHEN LOWER(url) LIKE '%piso%' OR LOWER(titulo) LIKE '%piso%' THEN 'Piso'
            WHEN LOWER(url) LIKE '%casa%' OR LOWER(titulo) LIKE '%casa%' OR LOWER(titulo) LIKE '%chalet%' THEN 'Casa'
            WHEN LOWER(url) LIKE '%atico%' OR LOWER(titulo) LIKE '%ático%' THEN 'Ático'
            WHEN LOWER(url) LIKE '%duplex%' OR LOWER(titulo) LIKE '%dúplex%' THEN 'Dúplex'
            WHEN LOWER(url) LIKE '%local%' OR LOWER(titulo) LIKE '%local%' THEN 'Local'
            WHEN LOWER(url) LIKE '%garaje%' OR LOWER(titulo) LIKE '%garaje%' OR LOWER(titulo) LIKE '%parking%' THEN 'Garaje'
            WHEN LOWER(url) LIKE '%terreno%' OR LOWER(titulo) LIKE '%terreno%' OR LOWER(titulo) LIKE '%parcela%' THEN 'Terreno'
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
        COALESCE(nombre, vendedor) AS nombre_contacto,
        vendedor AS anunciante,

        -- Property details
        tipo_propiedad,
        superficie_m2,
        habitaciones,
        banos,
        precio,
        precio_por_m2,
        certificado_energetico,

        -- Flags
        es_particular,
        permite_inmobiliarias,

        -- Publishing info (extracted from page)
        CASE
            WHEN raw_data->>'fecha_publicacion' IS NOT NULL
            THEN (raw_data->>'fecha_publicacion')::TIMESTAMP WITH TIME ZONE
            ELSE NULL
        END AS fecha_publicacion,

        -- Photos
        fotos_json,

        -- Raw data for reference
        raw_data

    FROM classified

    -- Apply filters
    WHERE
        precio > 5000  -- Filter out rentals
        -- Filter for particular (non-agency) listings only
        -- Note: Use COALESCE to treat NULL as TRUE (assume particular if not specified)
        -- The scraper already filters agencies, this is a backup
        AND COALESCE(es_particular, TRUE) = TRUE
        -- Filter out listings that reject agencies (they're looking for direct buyers)
        AND NOT (
            LOWER(COALESCE(descripcion, '')) LIKE '%abstener%agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%abstener%inmobiliaria%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no inmobiliaria%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%sin intermediario%'
        )
        -- Filter out agency names in vendedor/anunciante field
        AND NOT (
            LOWER(COALESCE(vendedor, '')) LIKE '%inmobiliaria%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%agencia%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%agency%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%fincas%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%gestoria%'
            OR vendedor = 'Profesional'
        )
)

SELECT * FROM final

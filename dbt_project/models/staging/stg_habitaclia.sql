{{
    config(
        materialized='view',
        schema='staging',
        tags=['staging', 'habitaclia']
    )
}}

/*
    Staging model for Habitaclia listings.

    This model:
    - Extracts fields from JSONB raw_data
    - Normalizes phone numbers
    - Classifies zones
    - Filters for particular sellers
*/

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'habitaclia'
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
        COALESCE(raw_data->>'url_anuncio', raw_data->>'url') AS url,
        raw_data->>'titulo' AS titulo,
        raw_data->>'precio' AS precio_text,
        raw_data->>'descripcion' AS descripcion,
        COALESCE(raw_data->>'ubicacion', raw_data->>'direccion', raw_data->>'zona') AS ubicacion,
        raw_data->>'codigo_postal' AS codigo_postal,
        COALESCE(raw_data->>'telefono', raw_data->>'telefono_norm') AS telefono_raw,
        raw_data->>'email' AS email,
        COALESCE(raw_data->>'vendedor', raw_data->>'nombre') AS vendedor,
        raw_data->>'metros' AS metros_text,
        raw_data->>'habitaciones' AS habitaciones_text,
        raw_data->>'banos' AS banos_text,
        COALESCE(raw_data->>'zona_busqueda', raw_data->>'zona_geografica', raw_data->>'zona') AS zona_busqueda,
        raw_data->'fotos' AS fotos_json,
        COALESCE((raw_data->>'es_particular')::BOOLEAN, TRUE) AS es_particular_raw,

        -- Store entire raw_data for reference
        raw_data

    FROM source
),

normalized AS (
    SELECT
        *,

        -- Normalize phone number
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    COALESCE(telefono_raw, ''),
                    '(\+34|0034)',
                    '',
                    'g'
                ),
                '[\s\(\)\-\.]',
                '',
                'g'
            ),
            '^0+',
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

        es_particular_raw AS es_particular,
        TRUE AS permite_inmobiliarias

    FROM extracted
),

classified AS (
    SELECT
        *,

        -- Classify zone based on ubicacion or zona_busqueda
        CASE
            -- Lleida zones
            WHEN LOWER(ubicacion) LIKE '%lleida%' OR LOWER(ubicacion) LIKE '%lerida%' THEN 'Lleida Ciudad'
            WHEN LOWER(ubicacion) LIKE '%balaguer%' THEN 'Lleida - Balaguer'
            WHEN LOWER(ubicacion) LIKE '%mollerussa%' THEN 'Lleida - Mollerussa'
            WHEN LOWER(ubicacion) LIKE '%tarrega%' OR LOWER(ubicacion) LIKE '%tàrrega%' THEN 'Lleida - Tarrega'
            WHEN LOWER(ubicacion) LIKE '%tremp%' THEN 'Lleida - Tremp'

            -- Tarragona Costa Dorada
            WHEN LOWER(ubicacion) LIKE '%salou%' THEN 'Costa Dorada - Salou'
            WHEN LOWER(ubicacion) LIKE '%cambrils%' THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(ubicacion) LIKE '%tarragona%' THEN 'Tarragona Ciudad'
            WHEN LOWER(ubicacion) LIKE '%reus%' THEN 'Tarragona - Reus'
            WHEN LOWER(ubicacion) LIKE '%vila-seca%' OR LOWER(ubicacion) LIKE '%vilaseca%' THEN 'Costa Dorada - Vila-seca'
            WHEN LOWER(ubicacion) LIKE '%torredembarra%' THEN 'Costa Dorada - Torredembarra'
            WHEN LOWER(ubicacion) LIKE '%vendrell%' THEN 'Costa Dorada - Vendrell'
            WHEN LOWER(ubicacion) LIKE '%calafell%' THEN 'Costa Dorada - Calafell'
            WHEN LOWER(ubicacion) LIKE '%altafulla%' THEN 'Costa Dorada - Altafulla'
            WHEN LOWER(ubicacion) LIKE '%miami%' THEN 'Costa Dorada - Miami Platja'
            WHEN LOWER(ubicacion) LIKE '%montblanc%' THEN 'Tarragona - Montblanc'
            WHEN LOWER(ubicacion) LIKE '%valls%' THEN 'Tarragona - Valls'

            -- Terres de l'Ebre
            WHEN LOWER(ubicacion) LIKE '%tortosa%' THEN 'Terres Ebre - Tortosa'
            WHEN LOWER(ubicacion) LIKE '%amposta%' THEN 'Terres Ebre - Amposta'
            WHEN LOWER(ubicacion) LIKE '%deltebre%' THEN 'Terres Ebre - Deltebre'
            WHEN LOWER(ubicacion) LIKE '%ametlla%' THEN 'Terres Ebre - Ametlla de Mar'
            WHEN LOWER(ubicacion) LIKE '%sant carles%' OR LOWER(ubicacion) LIKE '%rapita%' THEN 'Terres Ebre - Sant Carles'

            -- Fallback to zona_busqueda from scraper
            WHEN zona_busqueda IS NOT NULL THEN zona_busqueda

            ELSE 'Otros'
        END AS zona_clasificada,

        -- Calculate price per m2
        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2,

        -- Tipo de inmueble
        CASE
            WHEN LOWER(url) LIKE '%piso%' OR LOWER(titulo) LIKE '%piso%' THEN 'Piso'
            WHEN LOWER(url) LIKE '%casa%' OR LOWER(titulo) LIKE '%casa%' OR LOWER(titulo) LIKE '%chalet%' THEN 'Casa'
            WHEN LOWER(url) LIKE '%local%' OR LOWER(titulo) LIKE '%local%' THEN 'Local'
            WHEN LOWER(titulo) LIKE '%garaje%' OR LOWER(titulo) LIKE '%parking%' THEN 'Garaje'
            WHEN LOWER(titulo) LIKE '%terreno%' OR LOWER(titulo) LIKE '%parcela%' THEN 'Terreno'
            WHEN LOWER(titulo) LIKE '%finca%' THEN 'Finca'
            ELSE 'Piso'
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

        -- Flags
        es_particular,
        permite_inmobiliarias,

        -- Publishing info
        NULL::TIMESTAMP AS fecha_publicacion,

        -- Photos
        fotos_json,

        -- Raw data for reference
        raw_data

    FROM classified

    -- Apply filters
    -- Habitaclia hides phones behind login/AJAX, so we allow NULL phones
    WHERE
        precio > 5000
)

SELECT * FROM final

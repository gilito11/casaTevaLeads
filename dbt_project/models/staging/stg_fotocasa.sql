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

        -- Price: keep NULL for missing, filter in WHERE
        NULLIF(COALESCE(precio_num, 0), 0)::INTEGER AS precio,

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

        -- Normalize zone names consistently across portals
        CASE
            -- Lleida zones
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%lleida%' OR LOWER(COALESCE(ubicacion, '')) LIKE '%lerida%' THEN 'Lleida Ciudad'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%balaguer%' THEN 'Lleida - Balaguer'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%mollerussa%' THEN 'Lleida - Mollerussa'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%tarrega%' OR LOWER(COALESCE(ubicacion, '')) LIKE '%tàrrega%' THEN 'Lleida - Tarrega'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%tremp%' THEN 'Lleida - Tremp'

            -- Tarragona Costa Dorada
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%salou%' THEN 'Costa Dorada - Salou'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%cambrils%' THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%tarragona%' THEN 'Tarragona Ciudad'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%reus%' THEN 'Tarragona - Reus'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%vila-seca%' OR LOWER(COALESCE(ubicacion, '')) LIKE '%vilaseca%' THEN 'Costa Dorada - Vila-seca'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%torredembarra%' THEN 'Costa Dorada - Torredembarra'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%vendrell%' THEN 'Costa Dorada - El Vendrell'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%calafell%' THEN 'Costa Dorada - Calafell'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%altafulla%' THEN 'Costa Dorada - Altafulla'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%miami%' THEN 'Costa Dorada - Miami Platja'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%montblanc%' THEN 'Tarragona - Montblanc'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%valls%' THEN 'Tarragona - Valls'

            -- Terres de l'Ebre
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%tortosa%' THEN 'Terres Ebre - Tortosa'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%amposta%' THEN 'Terres Ebre - Amposta'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%deltebre%' THEN 'Terres Ebre - Deltebre'

            -- Madrid zones (Find&Look)
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%chamartin%' OR LOWER(COALESCE(ubicacion, '')) LIKE '%chamartín%' THEN 'Madrid - Chamartin'
            WHEN LOWER(COALESCE(ubicacion, '')) LIKE '%hortaleza%' THEN 'Madrid - Hortaleza'

            -- Fallback: normalize zona_geografica from scraper
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('salou', 'costa dorada - salou') THEN 'Costa Dorada - Salou'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('cambrils', 'costa dorada - cambrils') THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('tarragona', 'tarragona ciudad') THEN 'Tarragona Ciudad'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('reus', 'tarragona - reus', 'tarragona/reus') THEN 'Tarragona - Reus'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('mollerussa', 'lleida - mollerussa') THEN 'Lleida - Mollerussa'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('lleida', 'lleida ciudad') THEN 'Lleida Ciudad'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('balaguer', 'lleida - balaguer') THEN 'Lleida - Balaguer'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('tarrega', 'tàrrega', 'lleida - tarrega') THEN 'Lleida - Tarrega'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('tremp', 'lleida - tremp') THEN 'Lleida - Tremp'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('vila-seca', 'vilaseca') THEN 'Costa Dorada - Vila-seca'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('torredembarra') THEN 'Costa Dorada - Torredembarra'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('calafell') THEN 'Costa Dorada - Calafell'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('vendrell', 'el vendrell') THEN 'Costa Dorada - El Vendrell'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('chamartin', 'chamartín') THEN 'Madrid - Chamartin'
            WHEN LOWER(COALESCE(zona_geografica, '')) IN ('hortaleza') THEN 'Madrid - Hortaleza'
            WHEN zona_geografica IS NOT NULL THEN zona_geografica

            ELSE 'Otros'
        END AS zona_clasificada,

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
        precio IS NOT NULL  -- Must have a valid price
        -- Filter out listings that reject agencies (they're looking for direct buyers)
        AND NOT (
            LOWER(COALESCE(descripcion, '')) LIKE '%abstener%agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%abstener%inmobiliaria%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no inmobiliaria%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%sin intermediario%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no intermediarios%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no se atienden%agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%no se atienden%intermediario%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%exclusivamente%particular%'
        )
        -- Filter out agency listings disguised as particulars (they advertise "no agency fees")
        AND NOT (
            LOWER(COALESCE(descripcion, '')) LIKE '%sin comision%agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%sin comisiones de agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%0% comision%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%cero comision%'
        )
)

SELECT * FROM final

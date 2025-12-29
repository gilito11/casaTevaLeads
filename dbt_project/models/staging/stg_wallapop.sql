{{
    config(
        materialized='view',
        schema='staging',
        tags=['staging', 'wallapop']
    )
}}

/*
    Staging model for Wallapop Inmobiliaria listings.

    This model:
    - Extracts fields from JSONB raw_data
    - Normalizes phone numbers
    - Filters out blacklisted users (inmobiliarias encubiertas)
*/

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'wallapop'
),

-- Lista de usuarios conocidos como inmobiliarias
blacklist AS (
    SELECT LOWER(nombre_usuario) AS nombre_lower
    FROM (
        VALUES
            ('yaencontre'),
            ('yaencontre ..'),
            -- Añadir más usuarios detectados aquí
            ('__placeholder__')  -- Placeholder para evitar error si está vacío
    ) AS t(nombre_usuario)
    WHERE nombre_usuario != '__placeholder__'
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
        raw_data->>'item_id' AS item_id,
        raw_data->>'url_anuncio' AS url,
        raw_data->>'titulo' AS titulo,
        raw_data->>'precio' AS precio_text,
        raw_data->>'descripcion' AS descripcion,
        raw_data->>'ubicacion' AS ubicacion,
        raw_data->>'telefono' AS telefono_raw,
        raw_data->>'nombre_usuario' AS nombre_usuario,
        raw_data->>'user_id' AS user_id_wallapop,
        raw_data->>'metros' AS metros_text,
        raw_data->>'habitaciones' AS habitaciones_text,
        raw_data->>'tipo_propiedad' AS tipo_propiedad,
        raw_data->>'zona_busqueda' AS zona_busqueda,

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
                '[\s\(\)\-]',
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

        -- Wallapop listings son de particulares (filtrados por el scraper)
        TRUE AS es_particular,
        TRUE AS permite_inmobiliarias

    FROM extracted
),

classified AS (
    SELECT
        *,

        -- Classify zone based on ubicacion or zona_busqueda
        CASE
            WHEN LOWER(ubicacion) LIKE '%barcelona%' THEN 'Barcelona'
            WHEN LOWER(ubicacion) LIKE '%madrid%' THEN 'Madrid'
            WHEN LOWER(ubicacion) LIKE '%valencia%' THEN 'Valencia'
            WHEN LOWER(ubicacion) LIKE '%lleida%' OR LOWER(ubicacion) LIKE '%lerida%' THEN 'Lleida'
            WHEN LOWER(ubicacion) LIKE '%tarragona%' THEN 'Tarragona'
            WHEN LOWER(ubicacion) LIKE '%salou%' THEN 'Salou'
            WHEN LOWER(ubicacion) LIKE '%cambrils%' THEN 'Cambrils'
            WHEN zona_busqueda IS NOT NULL THEN zona_busqueda
            ELSE 'Otros'
        END AS zona_clasificada,

        -- Calculate price per m2
        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2,

        -- Check if user is blacklisted
        CASE
            WHEN LOWER(nombre_usuario) IN (SELECT nombre_lower FROM blacklist) THEN TRUE
            ELSE FALSE
        END AS usuario_blacklisted

    FROM normalized
),

final AS (
    SELECT
        -- Primary keys
        raw_listing_id,
        tenant_id,
        item_id AS external_id,

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
        NULL AS codigo_postal,

        -- Contact information
        telefono_raw,
        telefono_norm,
        NULL AS email,
        nombre_usuario AS nombre_contacto,
        nombre_usuario AS anunciante,
        user_id_wallapop,

        -- Property details
        tipo_propiedad,
        superficie_m2,
        habitaciones,
        NULL::INTEGER AS banos,
        precio,
        precio_por_m2,

        -- Flags
        es_particular,
        permite_inmobiliarias,

        -- Publishing info
        NULL::TIMESTAMP AS fecha_publicacion,

        raw_data

    FROM classified

    WHERE
        -- Filtrar usuarios en blacklist
        NOT usuario_blacklisted
        -- Filtrar por precio mínimo (evitar alquileres)
        AND precio > 5000
        -- Debe tener título
        AND titulo IS NOT NULL
)

SELECT * FROM final

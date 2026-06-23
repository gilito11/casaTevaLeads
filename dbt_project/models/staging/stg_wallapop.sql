{{
    config(
        materialized='view',
        schema='staging',
        tags=['staging', 'wallapop']
    )
}}

/*
    Staging model para anuncios de Wallapop.

    - Extrae campos del JSONB raw_data
    - Normaliza teléfonos y casts numéricos
    - Clasifica zona
    - Filtra particulares (segunda barrera tras el scraper): descarta agencias
      camufladas como yaencontre y otros profesionales por nombre/descripción.
*/

WITH source AS (
    SELECT *
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'wallapop'
),

extracted AS (
    SELECT
        id AS raw_listing_id,
        tenant_id,
        portal,
        data_lake_path,
        scraping_timestamp,
        created_at,

        raw_data->>'anuncio_id' AS anuncio_id,
        COALESCE(raw_data->>'url', raw_data->>'url_anuncio') AS url,
        raw_data->>'titulo' AS titulo,
        COALESCE(raw_data->>'precio', (raw_data->'precio')::TEXT) AS precio_text,
        raw_data->>'descripcion' AS descripcion,
        COALESCE(raw_data->>'ubicacion', raw_data->>'direccion') AS ubicacion,
        raw_data->>'codigo_postal' AS codigo_postal,
        COALESCE(raw_data->>'telefono', raw_data->>'telefono_norm') AS telefono_raw,
        raw_data->>'email' AS email,
        COALESCE(NULLIF(TRIM(raw_data->>'vendedor'), ''), NULLIF(TRIM(raw_data->>'nombre'), '')) AS vendedor,
        COALESCE(raw_data->>'metros', (raw_data->'metros')::TEXT) AS metros_text,
        COALESCE(raw_data->>'habitaciones', (raw_data->'habitaciones')::TEXT) AS habitaciones_text,
        COALESCE(raw_data->>'zona_busqueda', raw_data->>'zona_geografica', raw_data->>'zona') AS zona_busqueda,
        raw_data->'fotos' AS fotos_json,
        raw_data
    FROM source
),

normalized AS (
    SELECT
        *,

        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(COALESCE(telefono_raw, ''), '(\+34|0034)', '', 'g'),
                '[\s\(\)\-]', '', 'g'
            ),
            '^0+', ''
        ) AS telefono_norm,

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

        NULL::INTEGER AS banos,

        -- Señal de particular: seller_type del scraper, luego es_particular.
        CASE
            WHEN LOWER(COALESCE(raw_data->>'seller_type', '')) IN ('professional', 'profesional') THEN FALSE
            WHEN LOWER(COALESCE(raw_data->>'seller_type', '')) IN ('particular', 'private') THEN TRUE
            WHEN (raw_data->>'es_particular')::BOOLEAN = TRUE THEN TRUE
            WHEN (raw_data->>'es_particular')::BOOLEAN = FALSE THEN FALSE
            ELSE TRUE
        END AS es_particular,
        TRUE AS permite_inmobiliarias

    FROM extracted
),

classified AS (
    SELECT
        *,

        CASE
            -- Lleida (foco obra nueva: Bordeta, Cappont, Copa d'Or)
            WHEN LOWER(ubicacion) LIKE '%bordeta%' THEN 'Lleida - La Bordeta'
            WHEN LOWER(ubicacion) LIKE '%cappont%' OR LOWER(ubicacion) LIKE '%cap pont%' THEN 'Lleida - Cappont'
            WHEN LOWER(ubicacion) LIKE '%lleida%' OR LOWER(ubicacion) LIKE '%lerida%' THEN 'Lleida Ciudad'

            WHEN LOWER(ubicacion) LIKE '%salou%' THEN 'Costa Dorada - Salou'
            WHEN LOWER(ubicacion) LIKE '%cambrils%' THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(ubicacion) LIKE '%tarragona%' THEN 'Tarragona Ciudad'
            WHEN LOWER(ubicacion) LIKE '%reus%' THEN 'Tarragona - Reus'

            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('salou') THEN 'Costa Dorada - Salou'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('cambrils') THEN 'Costa Dorada - Cambrils'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('tarragona') THEN 'Tarragona Ciudad'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('reus') THEN 'Tarragona - Reus'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('mollerussa') THEN 'Lleida - Mollerussa'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('lleida') THEN 'Lleida Ciudad'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('balaguer') THEN 'Lleida - Balaguer'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('tarrega', 'tàrrega') THEN 'Lleida - Tarrega'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('les_borges_blanques') THEN 'Lleida - Les Borges Blanques'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('alpicat') THEN 'Lleida - Alpicat'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('alcarras') THEN 'Lleida - Alcarras'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('torrefarrera') THEN 'Lleida - Torrefarrera'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('tremp') THEN 'Lleida - Tremp'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('cervera') THEN 'Lleida - Cervera'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('agramunt') THEN 'Lleida - Agramunt'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('bellpuig') THEN 'Lleida - Bellpuig'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('guissona') THEN 'Lleida - Guissona'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('juneda') THEN 'Lleida - Juneda'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('almacelles') THEN 'Lleida - Almacelles'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('almenar') THEN 'Lleida - Almenar'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('bell_lloc') THEN 'Lleida - Bell-lloc d''Urgell'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('linyola') THEN 'Lleida - Linyola'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('termens') THEN 'Lleida - Termens'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('ponts') THEN 'Lleida - Ponts'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('artesa_segre') THEN 'Lleida - Artesa de Segre'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('seu_urgell') THEN 'Lleida - La Seu d''Urgell'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('solsona') THEN 'Lleida - Solsona'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('pobla_segur') THEN 'Lleida - La Pobla de Segur'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('sort') THEN 'Lleida - Sort'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('vielha') THEN 'Lleida - Vielha'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('mollerussa_rural') THEN 'Lleida - Mollerussa'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('chamartin', 'chamartín') THEN 'Madrid - Chamartin'
            WHEN LOWER(COALESCE(zona_busqueda, '')) IN ('hortaleza') THEN 'Madrid - Hortaleza'
            WHEN zona_busqueda IS NOT NULL THEN zona_busqueda

            ELSE 'Otros'
        END AS zona_clasificada,

        CASE
            WHEN superficie_m2 > 0 THEN ROUND(precio::NUMERIC / superficie_m2, 2)
            ELSE NULL
        END AS precio_por_m2,

        CASE
            WHEN LOWER(COALESCE(raw_data->>'tipo_inmueble', '')) = 'casa' OR LOWER(titulo) LIKE '%casa%' OR LOWER(titulo) LIKE '%chalet%' THEN 'Casa'
            WHEN LOWER(COALESCE(raw_data->>'tipo_inmueble', '')) = 'local' OR LOWER(titulo) LIKE '%local%' THEN 'Local'
            WHEN LOWER(COALESCE(raw_data->>'tipo_inmueble', '')) = 'terreno' OR LOWER(titulo) LIKE '%terreno%' OR LOWER(titulo) LIKE '%parcela%' THEN 'Terreno'
            WHEN LOWER(titulo) LIKE '%piso%' OR LOWER(titulo) LIKE '%[aá]tico%' OR LOWER(titulo) LIKE '%apartament%' THEN 'Piso'
            ELSE 'Piso'
        END AS tipo_propiedad

    FROM normalized
),

final AS (
    SELECT
        raw_listing_id,
        tenant_id,
        anuncio_id AS external_id,

        portal,
        data_lake_path,
        scraping_timestamp,
        created_at,

        url,
        titulo,
        descripcion,
        ubicacion,
        zona_clasificada,
        codigo_postal,

        telefono_raw,
        telefono_norm,
        email,
        vendedor AS nombre_contacto,
        vendedor AS anunciante,

        tipo_propiedad,
        superficie_m2,
        habitaciones,
        banos,
        precio,
        precio_por_m2,

        es_particular,
        permite_inmobiliarias,

        CASE
            WHEN raw_data->>'fecha_publicacion' IS NOT NULL
            THEN (raw_data->>'fecha_publicacion')::TIMESTAMP WITH TIME ZONE
            ELSE NULL
        END AS fecha_publicacion,

        fotos_json,
        raw_data

    FROM classified

    WHERE
        precio > 5000  -- descarta alquileres y precios simbólicos
        AND es_particular = TRUE
        -- Agencias por nombre de vendedor (incluye yaencontre y portales camuflados)
        AND NOT (
            LOWER(COALESCE(vendedor, '')) LIKE '%yaencontre%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%inmobiliaria%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%inmobiliari%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%inmuebles%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%fincas%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%finques%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%agencia%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%grupo %'
            OR LOWER(COALESCE(vendedor, '')) LIKE '% s.l.%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '% sl%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '% s.a.%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%real estate%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%properties%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%realty%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%homes%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%gestion%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%gestión%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%gestora%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%asesor%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%consult%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%promotora%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%promocion%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%tecnocasa%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%redpiso%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%remax%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%housfy%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%.com%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%servicios inmobiliari%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%patrimoni%'
            OR LOWER(COALESCE(vendedor, '')) LIKE '%inversion%'
        )
        -- Frases de agencia / rechazo de intermediarios
        AND NOT (
            LOWER(COALESCE(descripcion, '')) LIKE '%nuestra agencia%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%nuestra inmobiliaria%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%llámenos%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%contacte con nosotros%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%gestionamos su hipoteca%'
            OR LOWER(COALESCE(descripcion, '')) LIKE '%financiación a medida%'
        )
        AND NOT TRIM(COALESCE(descripcion, '')) ~ '^Ref[:.]\s*'
        -- Descripción mínima (vacía/cortísima = poco fiable)
        AND LENGTH(TRIM(COALESCE(descripcion, ''))) >= 20
)

SELECT * FROM final

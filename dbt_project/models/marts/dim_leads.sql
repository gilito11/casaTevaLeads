{{
    config(
        materialized='incremental',
        unique_key=['tenant_id', 'lead_unique_key'],
        schema='marts',
        tags=['marts', 'leads', 'incremental'],
        on_schema_change='sync_all_columns',
        pre_hook="CREATE TABLE IF NOT EXISTS raw.listing_price_history (
            id SERIAL PRIMARY KEY,
            tenant_id VARCHAR DEFAULT 'casa_teva',
            portal VARCHAR NOT NULL,
            anuncio_id VARCHAR NOT NULL,
            precio NUMERIC,
            fecha_captura TIMESTAMP DEFAULT NOW(),
            UNIQUE(tenant_id, portal, anuncio_id, precio)
        );"
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

{#
    ZONAS ACTIVAS (tenant 1 - Casa Teva). Mapa {variante normalizada -> nombre
    canonico}: filtra Y unifica el nombre mostrado (evita duplicados tipo
    "Bellvis"/"Bellvís" o "Mont Roig"/"Mont-roig"). Todo municipio que NO este
    aqui queda DESCARTADO de dim_leads (las busquedas provinciales de
    milanuncios/fotocasa arrastran pueblos de toda la provincia). Los datos raw
    se conservan: para reactivar una zona basta con anadirla aqui (clave
    normalizada: minusculas, sin acentos, apostrofes/guiones como espacio).
    Excepcion: leads con fila en leads_lead_estado (trabajados por el equipo)
    nunca se filtran, esten donde esten.
    Alcance decidido 26 Jun 2026: Lleida <=20km + costa Tarragona y cinturon
    inmediato de Tarragona/Reus/Cambrils.
#}
{% set zonas_activas_tenant1 = {
    'lleida': 'Lleida',
    'partida balafia': 'Lleida',
    'alpicat': 'Alpicat',
    'alcarras': 'Alcarràs',
    'torrefarrera': 'Torrefarrera',
    'bell lloc': "Bell-lloc d'Urgell",
    'bell lloc d urgell': "Bell-lloc d'Urgell",
    'termens': 'Térmens',
    'juneda': 'Juneda',
    'almacelles': 'Almacelles',
    'almenar': 'Almenar',
    'mollerussa': 'Mollerussa',
    'albatarrec': 'Albatàrrec',
    'torre serona': 'Torre-serona',
    'montoliu de lleida': 'Montoliu de Lleida',
    'alcoletge': 'Alcoletge',
    'sudanell': 'Sudanell',
    'benavent de segria': 'Benavent de Segrià',
    'rossello': 'Rosselló',
    'artesa de lleida': 'Artesa de Lleida',
    'corbins': 'Corbins',
    'vilanova de segria': 'Vilanova de Segrià',
    'alfes': 'Alfés',
    'sunyer': 'Sunyer',
    'vilanova de la barca': 'Vilanova de la Barca',
    'puigverd de lleida': 'Puigverd de Lleida',
    'torres de segre': 'Torres de Segre',
    'alguaire': 'Alguaire',
    'aspa': 'Aspa',
    'soses': 'Soses',
    'menarguens': 'Menàrguens',
    'bellvis': 'Bellvís',
    'sidamon': 'Sidamon',
    'sarroca de lleida': 'Sarroca de Lleida',
    'aitona': 'Aitona',
    'fondarella': 'Fondarella',
    'torrebesses': 'Torrebesses',
    'miralcamp': 'Miralcamp',
    'vallfogona de balaguer': 'Vallfogona de Balaguer',
    'gimenells': 'Gimenells',
    'gimenells i el pla de la font': 'Gimenells',
    'tarragona': 'Tarragona',
    'bonavista': 'Bonavista',
    'la canonja': 'La Canonja',
    'reus': 'Reus',
    'salou': 'Salou',
    'cambrils': 'Cambrils',
    'la pineda': 'La Pineda',
    'vila seca': 'Vila-seca',
    'vilaseca': 'Vila-seca',
    'miami platja': 'Miami Platja',
    'miami playa': 'Miami Platja',
    'mont roig del camp': 'Mont-roig del Camp',
    'montroig del camp': 'Mont-roig del Camp',
    'vinyols i els arcs': 'Vinyols i els Arcs',
    'montbrio del camp': 'Montbrió del Camp',
    'riudoms': 'Riudoms',
    'constanti': 'Constantí',
} %}

WITH all_staging_sources AS (
    -- Fotocasa listings
    SELECT
        raw_listing_id, external_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        latitud, longitud,
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
        raw_listing_id, external_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        NULL::FLOAT AS latitud, NULL::FLOAT AS longitud,
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
        raw_listing_id, external_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        NULL::FLOAT AS latitud, NULL::FLOAT AS longitud,
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
        raw_listing_id, external_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        NULL::FLOAT AS latitud, NULL::FLOAT AS longitud,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion, fotos_json
    FROM {{ ref('stg_idealista') }}
    {% if is_incremental() %}
    WHERE scraping_timestamp > (SELECT MAX(ultima_actualizacion) FROM {{ this }})
    {% endif %}

    UNION ALL

    -- Wallapop listings
    SELECT
        raw_listing_id, external_id, tenant_id, portal, data_lake_path, scraping_timestamp, created_at,
        url, titulo, descripcion, ubicacion, zona_clasificada,
        NULL::FLOAT AS latitud, NULL::FLOAT AS longitud,
        telefono_raw, telefono_norm, email, nombre_contacto, anunciante,
        tipo_propiedad, superficie_m2, habitaciones, banos, precio, precio_por_m2,
        es_particular, permite_inmobiliarias, fecha_publicacion, fotos_json
    FROM {{ ref('stg_wallapop') }}
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
        ) AS rn,
        -- created_at del raw NO se toca en el upsert del scraper (a diferencia
        -- de scraping_timestamp, que se machaca en cada re-scrape), asi que su
        -- MIN es la verdadera primera captura.
        MIN(created_at) OVER (
            PARTITION BY tenant_id, COALESCE(NULLIF(telefono_norm, ''), MD5(url))
        ) AS primera_captura_batch
    FROM all_staging_sources
),

{#
    fecha_primera_captura debe SOBREVIVIR a los re-scrapes. El dedup se queda
    con la fila mas reciente (rn=1), asi que su scraping_timestamp es la ULTIMA
    captura, no la primera. En incremental recuperamos la fecha ya guardada en
    la tabla; en full-refresh usamos el MIN del batch (todo el historico de
    staging). Sin esto, cada re-scrape resetea dias_en_mercado a 0 y rompe el
    lead_score.
#}
dedup_first_capture AS (
    SELECT
        d.*,
        {% if is_incremental() %}
        LEAST(
            COALESCE(prev.fecha_primera_captura, d.primera_captura_batch),
            d.primera_captura_batch
        ) AS primera_captura_real
        {% else %}
        d.primera_captura_batch AS primera_captura_real
        {% endif %}
    FROM deduplicated d
    {% if is_incremental() %}
    LEFT JOIN {{ this }} prev
        ON prev.tenant_id::TEXT = d.tenant_id::TEXT
        AND prev.lead_unique_key = d.lead_unique_key
    {% endif %}
    WHERE d.rn = 1
),

enriched AS (
    SELECT
        -- Generate a unique lead_id using MD5 hash
        MD5(tenant_id::TEXT || '-' || lead_unique_key) AS lead_id,
        lead_unique_key,

        -- Source information
        raw_listing_id AS source_listing_id,
        external_id,
        tenant_id,
        portal AS source_portal,
        data_lake_path,

        -- Contact information
        telefono_norm,
        telefono_raw,
        email,
        -- Nombre normalizado: los placeholder del portal ('Particular' en
        -- habitaclia/fotocasa, vacio en milanuncios) pasan a NULL para que la
        -- UI muestre UNA sola etiqueta consistente; los nombres reales se
        -- limpian de espacios dobles (wallapop: 'Tomas   F.').
        CASE
            WHEN LOWER(TRIM(COALESCE(nombre_contacto, ''))) IN
                 ('', 'particular', 'particulares', 'anunciante particular', 'vendedor particular')
            THEN NULL
            ELSE REGEXP_REPLACE(TRIM(nombre_contacto), '\s+', ' ', 'g')
        END AS nombre_contacto,
        anunciante,

        -- Property information
        titulo,
        descripcion,
        url AS listing_url,
        ubicacion,
        -- Quita prefijos de comarca/costa ("Lleida - ", "Costa Dorada - "...)
        -- y fusiona variantes de capital ("Tarragona Ciudad/Capital" -> "Tarragona").
        CASE
            WHEN zona_clasificada IN ('Lleida Ciudad', 'Lleida Capital') THEN 'Lleida'
            WHEN zona_clasificada IN ('Tarragona Ciudad', 'Tarragona Capital') THEN 'Tarragona'
            WHEN zona_clasificada IS NULL OR zona_clasificada = '' THEN zona_clasificada
            ELSE REGEXP_REPLACE(zona_clasificada, '^(Lleida|Costa Dorada|Tarragona|Terres Ebre|Madrid) - ', '')
        END AS zona_clasificada,
        latitud,
        longitud,
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
        -- Guarda global anti-agencia por NOMBRE de vendedor/anunciante: protege a
        -- TODOS los portales (fotocasa, wallapop, etc.). El prefijo "inmo" (inmo*,
        -- p.ej. "inmoteck2024") es señal fuerte de inmobiliaria que los filtros por
        -- portal no cazaban. Si el nombre delata agencia -> es_particular = FALSE.
        CASE
            WHEN es_particular = FALSE THEN FALSE
            WHEN LOWER(COALESCE(nombre_contacto, '')) ~ '(^| )inmo|inmobiliari|inmuebles|fincas|finques|agencia|tecnocasa|redpiso|re/?max|century ?21|housfy|housell|engel|gestio|gestora|asesor|consult|promotora|promocion|servicios inmobiliari|real ?estate|properties|realty| homes|patrimoni|inversion| s\.?l\.?( |$)| s\.?a\.?( |$)|\.com|\.es' THEN FALSE
            WHEN LOWER(COALESCE(anunciante, '')) ~ '(^| )inmo|inmobiliari|inmuebles|fincas|agencia|tecnocasa|redpiso|housfy|gestora|promotora|real ?estate|properties|realty|\.com' THEN FALSE
            ELSE es_particular
        END AS es_particular,
        -- Override permite_inmobiliarias: check description for rejection phrases
        CASE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%inmobiliarias abstenerse%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%abstenerse inmobiliarias%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%abstenerse agencias%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%agencias abstenerse%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%no inmobiliarias%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%no agencias%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%sin intermediarios%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%solo particulares%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%particular a particular%' THEN FALSE
            WHEN LOWER(COALESCE(descripcion, '')) LIKE '%no intermediarios%' THEN FALSE
            WHEN LOWER(COALESCE(titulo, '')) LIKE '%no inmobiliarias%' THEN FALSE
            WHEN LOWER(COALESCE(titulo, '')) LIKE '%abstenerse%inmobiliaria%' THEN FALSE
            WHEN LOWER(COALESCE(titulo, '')) LIKE '%abstenerse%agencia%' THEN FALSE
            ELSE COALESCE(permite_inmobiliarias, TRUE)
        END AS permite_inmobiliarias,

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
                    LEAST(30, EXTRACT(DAY FROM NOW() - primera_captura_real)::INTEGER)
            END
            -- 2. Tiene telefono visible: +20pts (menos spam recibido)
            + CASE WHEN telefono_norm IS NOT NULL AND telefono_norm != '' THEN 20 ELSE 0 END
            -- 3. Pocas fotos (<5): +10pts (particular amateur, no agencia)
            -- Defensivo: jsonb_array_length peta si fotos_json es un escalar JSON
            -- (algún portal lo guarda como string/number en vez de array). Solo
            -- llamamos array_length cuando es realmente un array.
            + CASE
                WHEN fotos_json IS NULL THEN 10
                WHEN jsonb_typeof(fotos_json) = 'array' AND jsonb_array_length(fotos_json) < 5 THEN 10
                WHEN jsonb_typeof(fotos_json) <> 'array' THEN 10
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
        primera_captura_real AS fecha_primera_captura,
        scraping_timestamp AS ultima_actualizacion,
        CURRENT_TIMESTAMP AS created_at_marts

    FROM dedup_first_capture
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
        e.external_id,
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
        -- Nombre CANONICO por municipio (mapa zonas_activas_tenant1): unifica
        -- variantes de grafia entre portales ("Bellvis"/"Bellvís",
        -- "Mont Roig"/"Mont-roig del Camp", "Vilaseca"/"Vila-seca"...).
        -- Zonas fuera del mapa (Madrid, etc.) conservan su nombre tal cual.
        CASE TRIM(REGEXP_REPLACE(
            TRANSLATE(LOWER(e.zona_clasificada),
                      'àáâäèéêëìíîïòóôöùúûüçñ''-·',
                      'aaaaeeeeiiiioooouuuucn   '),
            '\s+', ' ', 'g'))
        {% for k, v in zonas_activas_tenant1.items() %}
            WHEN '{{ k }}' THEN '{{ v | replace("'", "''") }}'
        {%- endfor %}
            ELSE e.zona_clasificada
        END AS zona_clasificada,
        e.latitud,
        e.longitud,
        e.tipo_propiedad,
        e.superficie_m2,
        e.habitaciones,
        e.banos,
        e.precio,
        e.precio_por_m2,
        e.fotos_json,

        -- Price tracking (for detecting price drops). Solo si el ultimo precio
        -- del historial coincide con el precio actual del anuncio: si el precio
        -- revirtio (A->B->A), el historial no registra la vuelta (UNIQUE por
        -- precio + DO NOTHING) y el cambio mostrado seria engañoso.
        CASE WHEN pc.precio_actual = e.precio THEN pc.precio_anterior END AS precio_anterior,
        CASE WHEN pc.precio_actual = e.precio THEN pc.precio_cambio_pct END AS precio_cambio_pct,

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
            + CASE WHEN pc.precio_actual = e.precio AND pc.precio_cambio_pct < 0
                   THEN 15 ELSE 0 END AS lead_score_total,

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
    -- OJO: price_history guarda el anuncio_id del PORTAL (external_id), no el
    -- id serial de raw_listings (source_listing_id). Con source_listing_id el
    -- join no casaba nunca y las bajadas de precio jamas llegaban al mart.
    LEFT JOIN price_changes pc ON e.tenant_id::TEXT = pc.tenant_id::TEXT
        AND e.source_portal = pc.portal
        AND e.external_id = pc.anuncio_id::TEXT
    -- Filtro ALQUILER: Casa Teva solo trabaja COMPRA/VENTA. Excluimos los anuncios
    -- que son ofertas o demandas de alquiler ("se alquila", "llogar", "se busca
    -- alquiler"...). Para evitar tumbar VENTAS que solo mencionan alquiler como
    -- reclamo de inversion ("ideal alquiler vacacional", "actualmente alquilado"),
    -- solo disparamos con frases de transaccion explicitas, y SIEMPRE conservamos
    -- el anuncio si menciona venta (incluye los "se vende o se alquila").
    WHERE NOT (
        (
            LOWER(COALESCE(e.titulo, '')) ~ '(en alquiler|alquiler de|^alquiler|\malquilo\M|se alquila|en lloguer|de lloguer|^lloguer|es lloga|per llogar)'
            OR LOWER(COALESCE(e.descripcion, '')) ~ '(se alquila|se alquilan|se busca alquiler|busco alquiler|busco piso de alquiler|busca piso de alquiler|busco para alquilar|es lloga|es lloguen|es busca lloguer|busco lloguer|cerco lloguer)'
        )
        AND NOT (
            LOWER(COALESCE(e.titulo, '') || ' ' || COALESCE(e.descripcion, '')) ~ '(\mventa\M|\mventas\M|\mvende\M|\mvenden\M|\mvendo\M|\mvendemos\M|en venta|se vende|\mvenc\M|\mvenda\M|es ven )'
        )
    )
)

SELECT * FROM final
-- Filtro ZONAS ACTIVAS (solo tenant 1): descarta municipios fuera del area de
-- trabajo (lista al inicio del fichero). Leads sin zona se conservan.
-- Leads ya trabajados por el equipo (fila en leads_lead_estado) se conservan
-- siempre, aunque su zona este descartada.
WHERE
    tenant_id::TEXT <> '1'
    OR zona_clasificada IS NULL OR zona_clasificada = ''
    OR TRIM(REGEXP_REPLACE(
        TRANSLATE(LOWER(zona_clasificada),
                  'àáâäèéêëìíîïòóôöùúûüçñ''-·',
                  'aaaaeeeeiiiioooouuuucn   '),
        '\s+', ' ', 'g'
    )) IN ({% for z in zonas_activas_tenant1 %}'{{ z }}'{% if not loop.last %}, {% endif %}{% endfor %})
    OR lead_id IN (SELECT lead_id FROM public.leads_lead_estado)

{% if is_incremental() %}
    -- On incremental runs, update existing records or insert new ones
    -- This is handled by dbt's unique_key configuration
{% endif %}

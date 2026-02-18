{% macro classify_zone(ubicacion_column, fallback_column=none) %}
{#
    Classifies a location into a standardized zone name.

    Arguments:
        ubicacion_column: The column containing the location text to classify
        fallback_column: Optional column to use if no zone pattern matches

    Returns:
        SQL CASE expression for zone classification

    Usage:
        {{ classify_zone('ubicacion', 'zona_busqueda') }} AS zona_clasificada
#}

CASE
    -- Lleida zones
    WHEN LOWER({{ ubicacion_column }}) LIKE '%lleida%' OR LOWER({{ ubicacion_column }}) LIKE '%lerida%' THEN 'Lleida Ciudad'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%balaguer%' THEN 'Lleida - Balaguer'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%mollerussa%' THEN 'Lleida - Mollerussa'

    -- Tarragona Costa Dorada
    WHEN LOWER({{ ubicacion_column }}) LIKE '%salou%' THEN 'Costa Dorada - Salou'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%cambrils%' THEN 'Costa Dorada - Cambrils'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%tarragona%' THEN 'Tarragona Ciudad'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%reus%' THEN 'Tarragona - Reus'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%vila-seca%' OR LOWER({{ ubicacion_column }}) LIKE '%vilaseca%' THEN 'Costa Dorada - Vila-seca'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%la pineda%' THEN 'Costa Dorada - La Pineda'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%torredembarra%' THEN 'Costa Dorada - Torredembarra'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%vendrell%' THEN 'Costa Dorada - Vendrell'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%calafell%' THEN 'Costa Dorada - Calafell'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%altafulla%' THEN 'Costa Dorada - Altafulla'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%coma-ruga%' THEN 'Costa Dorada - Coma-ruga'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%mont-roig%' OR LOWER({{ ubicacion_column }}) LIKE '%montroig%' THEN 'Costa Dorada - Mont-roig'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%miami playa%' OR LOWER({{ ubicacion_column }}) LIKE '%miami platja%' THEN 'Costa Dorada - Miami Platja'

    -- Terres de l'Ebre
    WHEN LOWER({{ ubicacion_column }}) LIKE '%tortosa%' THEN 'Terres Ebre - Tortosa'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%amposta%' THEN 'Terres Ebre - Amposta'

    -- Interior Tarragona
    WHEN LOWER({{ ubicacion_column }}) LIKE '%valls%' THEN 'Tarragona - Valls'

    -- Madrid Districts (Tenant 2: Look and Find)
    WHEN LOWER({{ ubicacion_column }}) LIKE '%chamartín%' OR LOWER({{ ubicacion_column }}) LIKE '%chamartin%' THEN 'Madrid - Chamartín'
    WHEN LOWER({{ ubicacion_column }}) LIKE '%hortaleza%' THEN 'Madrid - Hortaleza'

    {% if fallback_column %}
    -- Fallback to scraper zone if available
    WHEN {{ fallback_column }} IS NOT NULL THEN {{ fallback_column }}
    {% endif %}

    ELSE 'Otros'
END
{% endmacro %}

"""
Zonas geográficas para Idealista (Casa Teva tenant 1 + Find&Look tenant 2).

Módulo neutro: NO depende de camoufox/botasaurus/scrapling. Cualquier scraper
(Camoufox legacy o Scrapling moderno) lo importa idénticamente.
"""

ZONAS_GEOGRAFICAS = {
    # Provinces
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_path': 'tarragona-provincia',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'lleida-provincia',
    },
    # Cities - Lleida
    'lleida': {
        'nombre': 'Lleida',
        'url_path': 'lleida-lleida',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_path': 'balaguer-lleida',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'url_path': 'mollerussa-lleida',
    },
    'les_borges_blanques': {
        'nombre': 'Les Borges Blanques',
        'url_path': 'les-borges-blanques-lleida',
    },
    'tarrega': {
        'nombre': 'Tàrrega',
        'url_path': 'tarrega-lleida',
    },
    'tremp': {
        'nombre': 'Tremp',
        'url_path': 'tremp-lleida',
    },
    # Cities - Tarragona
    'tarragona': {
        'nombre': 'Tarragona',
        'url_path': 'tarragona-tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'reus-tarragona',
    },
    'salou': {
        'nombre': 'Salou',
        'url_path': 'salou-tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'cambrils-tarragona',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_path': 'el-vendrell-tarragona',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'calafell-tarragona',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'torredembarra-tarragona',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'url_path': 'altafulla-tarragona',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'valls-tarragona',
    },
    'tortosa': {
        'nombre': 'Tortosa',
        'url_path': 'tortosa-tarragona',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_path': 'amposta-tarragona',
    },
    'ametlla_mar': {
        'nombre': "L'Ametlla de Mar",
        'url_path': 'l-ametlla-de-mar-tarragona',
    },
    'miami_platja': {
        'nombre': 'Miami Platja',
        'url_path': 'miami-platja-tarragona',
    },
    'vila_seca': {
        'nombre': 'Vila-seca',
        'url_path': 'vila-seca-tarragona',
    },
    'la_pineda': {
        'nombre': 'La Pineda',
        'url_path': 'la-pineda-tarragona',
    },
    'montblanc': {
        'nombre': 'Montblanc',
        'url_path': 'montblanc-tarragona',
    },
    'deltebre': {
        'nombre': 'Deltebre',
        'url_path': 'deltebre-tarragona',
    },
    # Test zone
    'igualada': {
        'nombre': 'Igualada',
        'url_path': 'igualada-barcelona',
    },
    # Madrid Districts (Tenant 2: Look and Find)
    'chamartin': {
        'nombre': 'Chamartín',
        'url_path': 'madrid/chamartin',
    },
    'hortaleza': {
        'nombre': 'Hortaleza',
        'url_path': 'madrid/hortaleza',
    },
}

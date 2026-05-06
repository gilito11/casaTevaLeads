"""
Zonas geográficas para Fotocasa (Casa Teva tenant 1 + Find&Look tenant 2).

Módulo neutro: NO depende de camoufox/botasaurus/scrapling.
"""

ZONAS_GEOGRAFICAS = {
    # =============================================================
    # PROVINCES
    # =============================================================
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_path': 'tarragona-provincia/todas-las-zonas',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'lleida-provincia/todas-las-zonas',
    },

    # =============================================================
    # COMARCAS - Composite zones (list of cities to scrape)
    # =============================================================
    # -- TARRAGONA COMARCAS --
    'tarragones': {
        'nombre': 'Tarragonès',
        'composite': ['tarragona', 'torredembarra', 'altafulla'],
    },
    'baix_camp': {
        'nombre': 'Baix Camp',
        'composite': ['reus', 'cambrils', 'salou', 'vila_seca', 'miami_platja'],
    },
    'alt_camp': {
        'nombre': 'Alt Camp',
        'composite': ['valls'],
    },
    'conca_barbera': {
        'nombre': 'Conca de Barberà',
        'composite': ['montblanc'],
    },
    'baix_penedes': {
        'nombre': 'Baix Penedès',
        'composite': ['vendrell', 'calafell', 'coma_ruga'],
    },
    'baix_ebre': {
        'nombre': 'Baix Ebre',
        'composite': ['tortosa', 'deltebre', 'ametlla_mar'],
    },
    'montsia': {
        'nombre': 'Montsià',
        'composite': ['amposta', 'sant_carles_rapita'],
    },
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'composite': ['salou', 'cambrils', 'tarragona', 'torredembarra', 'altafulla', 'calafell', 'vendrell', 'miami_platja'],
    },

    # -- LLEIDA COMARCAS --
    'segria': {'nombre': 'Segrià', 'composite': ['lleida']},
    'noguera': {'nombre': 'Noguera', 'composite': ['balaguer']},
    'pla_urgell': {'nombre': "Pla d'Urgell", 'composite': ['mollerussa']},
    'urgell': {'nombre': 'Urgell', 'composite': ['tarrega']},
    'pallars_jussa': {'nombre': 'Pallars Jussà', 'composite': ['tremp']},

    # =============================================================
    # CITIES — Fotocasa URL: /es/comprar/viviendas/{url_path}/l
    # =============================================================
    # -- LLEIDA --
    'lleida': {'nombre': 'Lleida', 'url_path': 'lleida-capital/todas-las-zonas'},
    'balaguer': {'nombre': 'Balaguer', 'url_path': 'balaguer/todas-las-zonas'},
    'mollerussa': {'nombre': 'Mollerussa', 'url_path': 'mollerussa/todas-las-zonas'},
    'les_borges_blanques': {'nombre': 'Les Borges Blanques', 'url_path': 'les-borges-blanques/todas-las-zonas'},
    'tremp': {'nombre': 'Tremp', 'url_path': 'tremp/todas-las-zonas'},
    'tarrega': {'nombre': 'Tàrrega', 'url_path': 'tarrega/todas-las-zonas'},
    'alpicat': {'nombre': 'Alpicat', 'url_path': 'alpicat/todas-las-zonas'},
    'alcarras': {'nombre': 'Alcarràs', 'url_path': 'alcarras/todas-las-zonas'},
    'torrefarrera': {'nombre': 'Torrefarrera', 'url_path': 'torrefarrera/todas-las-zonas'},
    'alcoletge': {'nombre': 'Alcoletge', 'url_path': 'alcoletge/todas-las-zonas'},
    'rossello': {'nombre': 'Rosselló', 'url_path': 'rossello/todas-las-zonas'},

    # -- TARRAGONA --
    'tarragona': {'nombre': 'Tarragona', 'url_path': 'tarragona-capital/todas-las-zonas'},
    'reus': {'nombre': 'Reus', 'url_path': 'reus/todas-las-zonas'},
    'salou': {'nombre': 'Salou', 'url_path': 'salou/todas-las-zonas'},
    'cambrils': {'nombre': 'Cambrils', 'url_path': 'cambrils/todas-las-zonas'},
    'miami_platja': {'nombre': 'Miami Platja', 'url_path': 'miami-platja/todas-las-zonas'},
    'hospitalet_infant': {'nombre': "L'Hospitalet de l'Infant", 'url_path': 'l-hospitalet-de-l-infant/todas-las-zonas'},
    'calafell': {'nombre': 'Calafell', 'url_path': 'calafell/todas-las-zonas'},
    'vendrell': {'nombre': 'El Vendrell', 'url_path': 'el-vendrell/todas-las-zonas'},
    'altafulla': {'nombre': 'Altafulla', 'url_path': 'altafulla/todas-las-zonas'},
    'torredembarra': {'nombre': 'Torredembarra', 'url_path': 'torredembarra/todas-las-zonas'},
    'coma_ruga': {'nombre': 'Coma-ruga', 'url_path': 'coma-ruga/todas-las-zonas'},
    'vila_seca': {'nombre': 'Vila-seca', 'url_path': 'vila-seca/todas-las-zonas'},
    'valls': {'nombre': 'Valls', 'url_path': 'valls/todas-las-zonas'},
    'montblanc': {'nombre': 'Montblanc', 'url_path': 'montblanc/todas-las-zonas'},
    'tortosa': {'nombre': 'Tortosa', 'url_path': 'tortosa/todas-las-zonas'},
    'amposta': {'nombre': 'Amposta', 'url_path': 'amposta/todas-las-zonas'},
    'deltebre': {'nombre': 'Deltebre', 'url_path': 'deltebre/todas-las-zonas'},
    'ametlla_mar': {'nombre': "L'Ametlla de Mar", 'url_path': 'l-ametlla-de-mar/todas-las-zonas'},
    'sant_carles_rapita': {'nombre': 'Sant Carles de la Ràpita', 'url_path': 'sant-carles-de-la-rapita/todas-las-zonas'},
    'la_pineda': {'nombre': 'La Pineda', 'url_path': 'la-pineda/todas-las-zonas'},
    'montroig_camp': {'nombre': 'Mont-roig del Camp', 'url_path': 'mont-roig-del-camp/todas-las-zonas'},

    # =============================================================
    # MADRID DISTRICTS (Tenant 2: Look and Find)
    # =============================================================
    'chamartin': {'nombre': 'Chamartín', 'url_path': 'madrid-capital/chamartin'},
    'hortaleza': {'nombre': 'Hortaleza', 'url_path': 'madrid-capital/hortaleza'},
}

"""
Zonas geográficas para Wallapop (Casa Teva tenant 1 + Find&Look tenant 2).

Módulo neutro: NO depende de scrapling/camoufox.

Wallapop es un marketplace geo-based (no usa rutas de zona por URL como los
demás portales). Cada zona aporta:
  - nombre   : display name -> raw_data.zona_geografica
  - slug     : ciudad para la ruta vertical /inmobiliaria/<slug> (carga el
               contexto de inmobiliaria + cookies anti-bot del SPA)
  - lat/lng  : coordenadas para la búsqueda geolocalizada por API
  - radius_km: radio de búsqueda en km

Municipios pequeños SIN vertical SEO (la landing /inmobiliaria/<slug> devuelve
404): slug=None. Para ellos el scraper usa el API geolocalizado
api.wallapop.com/api/v3/search con lat/lng/distance + category_id=200
(ver ScraplingWallapop.build_search_url). Validado 29 Jul 2026.

Las coords son aproximadas (centro del municipio); el radio cubre el área.
"""

ZONAS_GEOGRAFICAS = {
    # ---- Lleida (incluye foco obra nueva: Copa d'Or, Bordeta, Cappont) ----
    'lleida': {'nombre': 'Lleida Ciudad', 'slug': 'lleida', 'lat': 41.6176, 'lng': 0.6200, 'radius_km': 12},
    'balaguer': {'nombre': 'Balaguer', 'slug': 'balaguer', 'lat': 41.7906, 'lng': 0.8060, 'radius_km': 8},
    'mollerussa': {'nombre': 'Mollerussa', 'slug': 'mollerussa', 'lat': 41.6300, 'lng': 0.8950, 'radius_km': 8},
    'tarrega': {'nombre': 'Tàrrega', 'slug': 'tarrega', 'lat': 41.6470, 'lng': 1.1410, 'radius_km': 8},
    'les_borges_blanques': {'nombre': 'Les Borges Blanques', 'slug': 'les-borges-blanques', 'lat': 41.5220, 'lng': 0.8670, 'radius_km': 8},
    'alpicat': {'nombre': 'Alpicat', 'slug': 'alpicat', 'lat': 41.6680, 'lng': 0.5230, 'radius_km': 6},
    'alcarras': {'nombre': 'Alcarràs', 'slug': 'alcarras', 'lat': 41.5680, 'lng': 0.5230, 'radius_km': 6},
    'torrefarrera': {'nombre': 'Torrefarrera', 'slug': 'torrefarrera', 'lat': 41.6700, 'lng': 0.5870, 'radius_km': 6},
    'tremp': {'nombre': 'Tremp', 'slug': 'tremp', 'lat': 42.1660, 'lng': 0.8950, 'radius_km': 10},
    'cervera': {'nombre': 'Cervera', 'slug': 'cervera', 'lat': 41.6700, 'lng': 1.2720, 'radius_km': 8},
    'agramunt': {'nombre': 'Agramunt', 'slug': 'agramunt', 'lat': 41.7870, 'lng': 1.0960, 'radius_km': 7},
    'bellpuig': {'nombre': 'Bellpuig', 'slug': 'bellpuig', 'lat': 41.6260, 'lng': 1.0120, 'radius_km': 6},
    'guissona': {'nombre': 'Guissona', 'slug': 'guissona', 'lat': 41.7840, 'lng': 1.2880, 'radius_km': 6},
    'juneda': {'nombre': 'Juneda', 'slug': 'juneda', 'lat': 41.5470, 'lng': 0.8230, 'radius_km': 6},
    'almacelles': {'nombre': 'Almacelles', 'slug': 'almacelles', 'lat': 41.7310, 'lng': 0.4380, 'radius_km': 6},
    'almenar': {'nombre': 'Almenar', 'slug': 'almenar', 'lat': 41.7950, 'lng': 0.5640, 'radius_km': 6},
    'bell_lloc': {'nombre': "Bell-lloc d'Urgell", 'slug': 'bell-lloc-durgell', 'lat': 41.6320, 'lng': 0.7740, 'radius_km': 6},
    'linyola': {'nombre': 'Linyola', 'slug': 'linyola', 'lat': 41.7050, 'lng': 0.9120, 'radius_km': 6},
    'termens': {'nombre': 'Térmens', 'slug': 'termens', 'lat': 41.7150, 'lng': 0.7560, 'radius_km': 6},
    'ponts': {'nombre': 'Ponts', 'slug': 'ponts', 'lat': 41.9170, 'lng': 1.1880, 'radius_km': 7},
    'artesa_segre': {'nombre': 'Artesa de Segre', 'slug': 'artesa-de-segre', 'lat': 41.8950, 'lng': 1.0470, 'radius_km': 7},
    'seu_urgell': {'nombre': "La Seu d'Urgell", 'slug': 'la-seu-durgell', 'lat': 42.3580, 'lng': 1.4590, 'radius_km': 10},
    'solsona': {'nombre': 'Solsona', 'slug': 'solsona', 'lat': 41.9940, 'lng': 1.5170, 'radius_km': 10},
    'pobla_segur': {'nombre': 'La Pobla de Segur', 'slug': 'la-pobla-de-segur', 'lat': 42.2470, 'lng': 0.9680, 'radius_km': 8},
    'sort': {'nombre': 'Sort', 'slug': 'sort', 'lat': 42.4130, 'lng': 1.1290, 'radius_km': 10},
    'vielha': {'nombre': 'Vielha', 'slug': 'vielha', 'lat': 42.7020, 'lng': 0.7960, 'radius_km': 12},
    'mollerussa_rural': {'nombre': 'Mollerussa Rural', 'slug': 'el-palau-danglesola', 'lat': 41.6510, 'lng': 0.8800, 'radius_km': 6},

    # ---- Cinturón Lleida <=20km, pueblos sin vertical SEO (slug=None -> API) ----
    # Claves idénticas a las del cron en scrape-neon.yml y al resto de portales.
    'albatarrec': {'nombre': 'Albatàrrec', 'slug': None, 'lat': 41.5730, 'lng': 0.6070, 'radius_km': 3},
    'torre_serona': {'nombre': 'Torre-serona', 'slug': None, 'lat': 41.6640, 'lng': 0.5980, 'radius_km': 3},
    'montoliu_de_lleida': {'nombre': 'Montoliu de Lleida', 'slug': None, 'lat': 41.5700, 'lng': 0.6330, 'radius_km': 3},
    'alcoletge': {'nombre': 'Alcoletge', 'slug': None, 'lat': 41.6460, 'lng': 0.6940, 'radius_km': 3},
    'sudanell': {'nombre': 'Sudanell', 'slug': None, 'lat': 41.5590, 'lng': 0.5730, 'radius_km': 3},
    'benavent_de_segria': {'nombre': 'Benavent de Segrià', 'slug': None, 'lat': 41.7120, 'lng': 0.6350, 'radius_km': 3},
    'rossello': {'nombre': 'Rosselló', 'slug': None, 'lat': 41.6900, 'lng': 0.6070, 'radius_km': 3},
    'artesa_de_lleida': {'nombre': 'Artesa de Lleida', 'slug': None, 'lat': 41.5520, 'lng': 0.7010, 'radius_km': 3},
    'corbins': {'nombre': 'Corbins', 'slug': None, 'lat': 41.6800, 'lng': 0.7000, 'radius_km': 3},
    'vilanova_de_segria': {'nombre': 'Vilanova de Segrià', 'slug': None, 'lat': 41.7230, 'lng': 0.6280, 'radius_km': 3},
    'alfes': {'nombre': 'Alfés', 'slug': None, 'lat': 41.5490, 'lng': 0.6180, 'radius_km': 3},
    'sunyer': {'nombre': 'Sunyer', 'slug': None, 'lat': 41.5420, 'lng': 0.5960, 'radius_km': 3},
    'vilanova_de_la_barca': {'nombre': 'Vilanova de la Barca', 'slug': None, 'lat': 41.6870, 'lng': 0.7230, 'radius_km': 3},
    'puigverd_de_lleida': {'nombre': 'Puigverd de Lleida', 'slug': None, 'lat': 41.5380, 'lng': 0.6930, 'radius_km': 3},
    'torres_de_segre': {'nombre': 'Torres de Segre', 'slug': None, 'lat': 41.5320, 'lng': 0.5120, 'radius_km': 3},
    'alguaire': {'nombre': 'Alguaire', 'slug': None, 'lat': 41.7350, 'lng': 0.5850, 'radius_km': 3},
    'aspa': {'nombre': 'Aspa', 'slug': None, 'lat': 41.5320, 'lng': 0.6720, 'radius_km': 3},
    'soses': {'nombre': 'Soses', 'slug': None, 'lat': 41.5360, 'lng': 0.5180, 'radius_km': 3},
    'menarguens': {'nombre': 'Menàrguens', 'slug': None, 'lat': 41.7340, 'lng': 0.7370, 'radius_km': 3},
    'bellvis': {'nombre': 'Bellvís', 'slug': None, 'lat': 41.6700, 'lng': 0.8180, 'radius_km': 3},
    'sidamon': {'nombre': 'Sidamon', 'slug': None, 'lat': 41.6320, 'lng': 0.8430, 'radius_km': 3},
    'sarroca_de_lleida': {'nombre': 'Sarroca de Lleida', 'slug': None, 'lat': 41.4430, 'lng': 0.5540, 'radius_km': 4},
    'aitona': {'nombre': 'Aitona', 'slug': None, 'lat': 41.4920, 'lng': 0.4610, 'radius_km': 4},
    'fondarella': {'nombre': 'Fondarella', 'slug': None, 'lat': 41.6340, 'lng': 0.8700, 'radius_km': 3},
    'torrebesses': {'nombre': 'Torrebesses', 'slug': None, 'lat': 41.4280, 'lng': 0.5980, 'radius_km': 4},
    'miralcamp': {'nombre': 'Miralcamp', 'slug': None, 'lat': 41.6070, 'lng': 0.8680, 'radius_km': 3},
    'vallfogona_balaguer': {'nombre': 'Vallfogona de Balaguer', 'slug': None, 'lat': 41.7710, 'lng': 0.8210, 'radius_km': 3},
    'gimenells': {'nombre': 'Gimenells', 'slug': None, 'lat': 41.6540, 'lng': 0.3900, 'radius_km': 4},

    # ---- Tarragona / Costa Dorada ----
    'tarragona': {'nombre': 'Tarragona Ciudad', 'slug': 'tarragona', 'lat': 41.1189, 'lng': 1.2445, 'radius_km': 12},
    'salou': {'nombre': 'Salou', 'slug': 'salou', 'lat': 41.0772, 'lng': 1.1417, 'radius_km': 6},
    'cambrils': {'nombre': 'Cambrils', 'slug': 'cambrils', 'lat': 41.0658, 'lng': 1.0556, 'radius_km': 6},
    'reus': {'nombre': 'Reus', 'slug': 'reus', 'lat': 41.1561, 'lng': 1.1069, 'radius_km': 8},
    'vila_seca': {'nombre': 'Vila-seca', 'slug': 'vila-seca', 'lat': 41.1110, 'lng': 1.1456, 'radius_km': 5},
    'la_pineda': {'nombre': 'La Pineda', 'slug': 'la-pineda', 'lat': 41.0840, 'lng': 1.1860, 'radius_km': 4},
    'torredembarra': {'nombre': 'Torredembarra', 'slug': 'torredembarra', 'lat': 41.1456, 'lng': 1.3995, 'radius_km': 5},
    'altafulla': {'nombre': 'Altafulla', 'slug': 'altafulla', 'lat': 41.1419, 'lng': 1.3787, 'radius_km': 4},
    'calafell': {'nombre': 'Calafell', 'slug': 'calafell', 'lat': 41.1990, 'lng': 1.5680, 'radius_km': 6},
    'vendrell': {'nombre': 'El Vendrell', 'slug': 'el-vendrell', 'lat': 41.2206, 'lng': 1.5346, 'radius_km': 6},
    'miami_platja': {'nombre': 'Miami Platja', 'slug': 'miami-platja', 'lat': 40.9930, 'lng': 0.9870, 'radius_km': 6},
    'valls': {'nombre': 'Valls', 'slug': 'valls', 'lat': 41.2860, 'lng': 1.2490, 'radius_km': 8},
    'montblanc': {'nombre': 'Montblanc', 'slug': 'montblanc', 'lat': 41.3760, 'lng': 1.1610, 'radius_km': 8},
    'ametlla_mar': {'nombre': "L'Ametlla de Mar", 'slug': 'l-ametlla-de-mar', 'lat': 40.8920, 'lng': 0.8030, 'radius_km': 6},
    'tortosa': {'nombre': 'Tortosa', 'slug': 'tortosa', 'lat': 40.8126, 'lng': 0.5211, 'radius_km': 10},
    'amposta': {'nombre': 'Amposta', 'slug': 'amposta', 'lat': 40.7130, 'lng': 0.5810, 'radius_km': 8},
    'deltebre': {'nombre': 'Deltebre', 'slug': 'deltebre', 'lat': 40.7190, 'lng': 0.7180, 'radius_km': 6},

    # ---- Costa secundaria keep-list (validado 29 Jul 2026: estos 4 SÍ tienen vertical) ----
    'constanti': {'nombre': 'Constantí', 'slug': 'constanti', 'lat': 41.1530, 'lng': 1.2130, 'radius_km': 4},
    'la_canonja': {'nombre': 'La Canonja', 'slug': 'la-canonja', 'lat': 41.1220, 'lng': 1.1960, 'radius_km': 3},
    'riudoms': {'nombre': 'Riudoms', 'slug': 'riudoms', 'lat': 41.1370, 'lng': 1.0510, 'radius_km': 4},
    'mont_roig_del_camp': {'nombre': 'Mont-roig del Camp', 'slug': 'mont-roig-del-camp', 'lat': 41.0870, 'lng': 0.9580, 'radius_km': 5},
    'montbrio_del_camp': {'nombre': 'Montbrió del Camp', 'slug': None, 'lat': 41.1210, 'lng': 1.0010, 'radius_km': 3},
    'vinyols_i_els_arcs': {'nombre': 'Vinyols i els Arcs', 'slug': None, 'lat': 41.1120, 'lng': 1.0410, 'radius_km': 3},

    # ---- Madrid (Find&Look, tenant 2) ----
    'chamartin': {'nombre': 'Chamartín', 'slug': 'madrid', 'lat': 40.4600, 'lng': -3.6770, 'radius_km': 4},
    'hortaleza': {'nombre': 'Hortaleza', 'slug': 'madrid', 'lat': 40.4730, 'lng': -3.6410, 'radius_km': 4},
}

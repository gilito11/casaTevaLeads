"""
Zonas geográficas para Wallapop (Casa Teva tenant 1 + Find&Look tenant 2).

Módulo neutro: NO depende de scrapling/camoufox.

Wallapop es un marketplace geo-based (no usa rutas de zona por URL como los
demás portales). Cada zona aporta:
  - nombre   : display name -> raw_data.zona_geografica
  - slug     : ciudad para la ruta vertical /inmobiliaria/<slug> (carga el
               contexto de inmobiliaria + cookies anti-bot del SPA)
  - lat/lng  : coordenadas para la búsqueda directa por API (fallback
               determinista cuando la vertical no existe para municipios pequeños)
  - radius_km: radio de búsqueda en km

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

    # ---- Madrid (Find&Look, tenant 2) ----
    'chamartin': {'nombre': 'Chamartín', 'slug': 'madrid', 'lat': 40.4600, 'lng': -3.6770, 'radius_km': 4},
    'hortaleza': {'nombre': 'Hortaleza', 'slug': 'madrid', 'lat': 40.4730, 'lng': -3.6410, 'radius_km': 4},
}

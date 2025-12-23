"""
Scraper de Milanuncios usando Scrapy + Playwright.

Este scraper extrae anuncios de particulares que venden viviendas en Milanuncios,
con soporte para geolocalización por coordenadas y radio de búsqueda.
"""

import logging
import os
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode, quote

import scrapy
from scrapy.http import Response
from scrapy_playwright.page import PageMethod

from scrapers.base_scraper import BaseScraper
from scrapers.utils.particular_filter import debe_scrapear

# Ruta al archivo de cookies
COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'milanuncios_cookies.json')


logger = logging.getLogger(__name__)


# Mapeo de ID de provincia a nombre
PROVINCIAS = {
    1: 'Álava', 2: 'Albacete', 3: 'Alicante', 4: 'Almería', 6: 'Badajoz',
    7: 'Baleares', 8: 'Barcelona', 9: 'Burgos', 10: 'Cáceres', 11: 'Cádiz',
    12: 'Castellón', 13: 'Ciudad Real', 14: 'Córdoba', 15: 'A Coruña',
    17: 'Girona', 18: 'Granada', 20: 'Guipúzcoa', 21: 'Huelva', 22: 'Huesca',
    24: 'León', 25: 'Lérida', 26: 'La Rioja', 28: 'Madrid', 29: 'Málaga',
    30: 'Murcia', 31: 'Navarra', 33: 'Asturias', 35: 'Las Palmas',
    36: 'Pontevedra', 37: 'Salamanca', 38: 'Sta. Cruz de Tenerife',
    39: 'Cantabria', 41: 'Sevilla', 43: 'Tarragona', 44: 'Teruel',
    45: 'Toledo', 46: 'Valencia', 47: 'Valladolid', 48: 'Vizcaya', 50: 'Zaragoza',
}


# Configuración de zonas geográficas predefinidas
# Solo zonas de Lleida y Costa Daurada (Tarragona)
ZONAS_GEOGRAFICAS = {
    # === LLEIDA (con diferentes radios) ===
    'lleida_20km': {'nombre': 'Lleida (20 km)', 'latitude': 41.6175899, 'longitude': 0.6200146, 'geoProvinceId': 25, 'geolocationTerm': 'Lleida, Lérida', 'distance': 20000},
    'lleida_30km': {'nombre': 'Lleida (30 km)', 'latitude': 41.6175899, 'longitude': 0.6200146, 'geoProvinceId': 25, 'geolocationTerm': 'Lleida, Lérida', 'distance': 30000},
    'lleida_40km': {'nombre': 'Lleida (40 km)', 'latitude': 41.6175899, 'longitude': 0.6200146, 'geoProvinceId': 25, 'geolocationTerm': 'Lleida, Lérida', 'distance': 40000},
    'lleida_50km': {'nombre': 'Lleida (50 km)', 'latitude': 41.6175899, 'longitude': 0.6200146, 'geoProvinceId': 25, 'geolocationTerm': 'Lleida, Lérida', 'distance': 50000},
    'lleida_ciudad': {'nombre': 'Lleida Ciudad', 'latitude': 41.6175899, 'longitude': 0.6200146, 'geoProvinceId': 25, 'geolocationTerm': 'Lleida, Lérida'},
    'la_bordeta': {'nombre': 'La Bordeta, Lleida', 'latitude': 41.6168393, 'longitude': 0.6204561, 'geoProvinceId': 25, 'geolocationTerm': 'La Bordeta, Lérida'},
    # Pueblos cercanos a Lleida
    'balaguer': {'nombre': 'Balaguer', 'latitude': 41.7907, 'longitude': 0.8050, 'geoProvinceId': 25, 'geolocationTerm': 'Balaguer, Lérida'},
    'mollerussa': {'nombre': 'Mollerussa', 'latitude': 41.6311, 'longitude': 0.8947, 'geoProvinceId': 25, 'geolocationTerm': 'Mollerussa, Lérida'},
    'tremp': {'nombre': 'Tremp', 'latitude': 42.1667, 'longitude': 0.8947, 'geoProvinceId': 25, 'geolocationTerm': 'Tremp, Lérida'},
    'tarrega': {'nombre': 'Tàrrega', 'latitude': 41.6472, 'longitude': 1.1392, 'geoProvinceId': 25, 'geolocationTerm': 'Tàrrega, Lérida'},

    # === TARRAGONA (con diferentes radios) ===
    'tarragona_20km': {'nombre': 'Tarragona (20 km)', 'latitude': 41.1188827, 'longitude': 1.2444909, 'geoProvinceId': 43, 'geolocationTerm': 'Tarragona, Tarragona', 'distance': 20000},
    'tarragona_30km': {'nombre': 'Tarragona (30 km)', 'latitude': 41.1188827, 'longitude': 1.2444909, 'geoProvinceId': 43, 'geolocationTerm': 'Tarragona, Tarragona', 'distance': 30000},
    'tarragona_40km': {'nombre': 'Tarragona (40 km)', 'latitude': 41.1188827, 'longitude': 1.2444909, 'geoProvinceId': 43, 'geolocationTerm': 'Tarragona, Tarragona', 'distance': 40000},
    'tarragona_50km': {'nombre': 'Tarragona (50 km)', 'latitude': 41.1188827, 'longitude': 1.2444909, 'geoProvinceId': 43, 'geolocationTerm': 'Tarragona, Tarragona', 'distance': 50000},
    'tarragona_ciudad': {'nombre': 'Tarragona Ciudad', 'latitude': 41.1188827, 'longitude': 1.2444909, 'geoProvinceId': 43, 'geolocationTerm': 'Tarragona, Tarragona'},

    # === COSTA DAURADA - Pueblos costeros ===
    'salou': {'nombre': 'Salou', 'latitude': 41.0764, 'longitude': 1.1416, 'geoProvinceId': 43, 'geolocationTerm': 'Salou, Tarragona'},
    'cambrils': {'nombre': 'Cambrils', 'latitude': 41.0672, 'longitude': 1.0597, 'geoProvinceId': 43, 'geolocationTerm': 'Cambrils, Tarragona'},
    'reus': {'nombre': 'Reus', 'latitude': 41.1548, 'longitude': 1.1078, 'geoProvinceId': 43, 'geolocationTerm': 'Reus, Tarragona'},
    'vendrell': {'nombre': 'El Vendrell', 'latitude': 41.2186, 'longitude': 1.5362, 'geoProvinceId': 43, 'geolocationTerm': 'El Vendrell, Tarragona'},
    'altafulla': {'nombre': 'Altafulla', 'latitude': 41.1417, 'longitude': 1.3778, 'geoProvinceId': 43, 'geolocationTerm': 'Altafulla, Tarragona'},
    'torredembarra': {'nombre': 'Torredembarra', 'latitude': 41.1456, 'longitude': 1.3958, 'geoProvinceId': 43, 'geolocationTerm': 'Torredembarra, Tarragona'},
    'miami_platja': {'nombre': 'Miami Platja', 'latitude': 41.0333, 'longitude': 0.9833, 'geoProvinceId': 43, 'geolocationTerm': 'Miami Platja, Tarragona'},
    'hospitalet_infant': {'nombre': "L'Hospitalet de l'Infant", 'latitude': 40.9917, 'longitude': 0.9250, 'geoProvinceId': 43, 'geolocationTerm': "L'Hospitalet de l'Infant, Tarragona"},
    'calafell': {'nombre': 'Calafell', 'latitude': 41.2003, 'longitude': 1.5681, 'geoProvinceId': 43, 'geolocationTerm': 'Calafell, Tarragona'},
    'coma_ruga': {'nombre': 'Coma-ruga', 'latitude': 41.1833, 'longitude': 1.5167, 'geoProvinceId': 43, 'geolocationTerm': 'Coma-ruga, Tarragona'},

    # === COSTA DAURADA - Pueblos interiores ===
    'valls': {'nombre': 'Valls', 'latitude': 41.2861, 'longitude': 1.2497, 'geoProvinceId': 43, 'geolocationTerm': 'Valls, Tarragona'},
    'montblanc': {'nombre': 'Montblanc', 'latitude': 41.3772, 'longitude': 1.1631, 'geoProvinceId': 43, 'geolocationTerm': 'Montblanc, Tarragona'},
    'vila_seca': {'nombre': 'Vila-seca', 'latitude': 41.1125, 'longitude': 1.1458, 'geoProvinceId': 43, 'geolocationTerm': 'Vila-seca, Tarragona'},

    # === TERRES DE L'EBRE (sur de Tarragona) ===
    'tortosa': {'nombre': 'Tortosa', 'latitude': 40.8125, 'longitude': 0.5216, 'geoProvinceId': 43, 'geolocationTerm': 'Tortosa, Tarragona'},
    'amposta': {'nombre': 'Amposta', 'latitude': 40.7125, 'longitude': 0.5811, 'geoProvinceId': 43, 'geolocationTerm': 'Amposta, Tarragona'},
    'deltebre': {'nombre': 'Deltebre', 'latitude': 40.7208, 'longitude': 0.7181, 'geoProvinceId': 43, 'geolocationTerm': 'Deltebre, Tarragona'},
    'ametlla_mar': {'nombre': "L'Ametlla de Mar", 'latitude': 40.8833, 'longitude': 0.8000, 'geoProvinceId': 43, 'geolocationTerm': "L'Ametlla de Mar, Tarragona"},
    'sant_carles_rapita': {'nombre': 'Sant Carles de la Ràpita', 'latitude': 40.6167, 'longitude': 0.5917, 'geoProvinceId': 43, 'geolocationTerm': 'Sant Carles de la Ràpita, Tarragona'},
}


class MilanunciosScraper(scrapy.Spider):
    """
    Spider de Scrapy para scrapear Milanuncios con Playwright.

    Extrae anuncios de particulares que venden viviendas,
    guarda los datos en MinIO (data lake) y PostgreSQL (raw layer).

    Attributes:
        name: Nombre del spider ('milanuncios')
        tenant_id: ID del tenant al que pertenece
        zones: Zonas geográficas a scrapear
        filters: Filtros de precio, habitaciones, etc.
    """

    name = 'milanuncios'

    custom_settings = {
        # Configuración de scrapy-playwright
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',

        # Rate limiting MUY conservador para evitar bloqueos
        'DOWNLOAD_DELAY': 10,  # 10 segundos entre requests
        'RANDOMIZE_DOWNLOAD_DELAY': 2,  # Añadir variación aleatoria
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,

        # User agent realista (Chrome 121 - Diciembre 2024)
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ),

        # No respetar robots.txt (portales suelen bloquear scrapers)
        'ROBOTSTXT_OBEY': False,

        # Retry settings
        'RETRY_TIMES': 2,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408],

        # Playwright settings - Máxima anti-detección
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 90000,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-size=1920,1080',
                '--disable-extensions',
            ],
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 90000,
        'PLAYWRIGHT_CONTEXTS': {
            'default': {
                'viewport': {'width': 1920, 'height': 1080},
                'locale': 'es-ES',
                'timezone_id': 'Europe/Madrid',
                'user_agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                ),
                # Cargar cookies si existen
                **(
                    {'storage_state': COOKIES_FILE}
                    if os.path.exists(COOKIES_FILE)
                    else {}
                ),
            }
        },
    }

    @classmethod
    def has_cookies(cls) -> bool:
        """Verifica si hay cookies guardadas."""
        return os.path.exists(COOKIES_FILE)

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        distance: int = 20000,  # Radio en metros (20km por defecto)
        *args,
        **kwargs
    ):
        """
        Inicializa el spider de Milanuncios.

        Args:
            tenant_id: ID del tenant
            zones: Lista de zonas a scrapear (keys de ZONAS_GEOGRAFICAS)
                   Ejemplo: ['la_bordeta', 'salou', 'tarragona_ciudad']
            filters: Filtros de búsqueda (precio_min, precio_max, etc.)
            postgres_config: Configuración de PostgreSQL
            distance: Radio de búsqueda en metros (default: 20000 = 20km)
        """
        super().__init__(*args, **kwargs)

        self.tenant_id = tenant_id
        self.zones = zones or ['la_bordeta']  # Por defecto La Bordeta
        self.filters = filters or {}
        self.distance = distance

        # Inicializar BaseScraper para persistencia
        self.base_scraper = BaseScraper(
            tenant_id=tenant_id,
            zones={},
            filters=filters or {},
            postgres_config=postgres_config
        )

        # Estadísticas
        self.stats = {
            'total_listings': 0,
            'filtered_out': 0,
            'saved': 0,
            'errors': 0,
            'pages_scraped': 0,
            'blocked_count': 0,
        }

        # Log de cookies
        if os.path.exists(COOKIES_FILE):
            logger.info(f"Usando cookies guardadas de: {COOKIES_FILE}")
        else:
            logger.warning(
                "No hay cookies guardadas. El scraper puede ser bloqueado. "
                "Ejecuta 'python scrapers/capture_cookies.py' para capturar cookies."
            )

        logger.info(
            f"MilanunciosScraper inicializado para tenant_id={tenant_id}, "
            f"zonas={self.zones}, distance={distance}m"
        )

    def _build_url(self, zona_key: str, page: int = 1) -> str:
        """
        Construye la URL de búsqueda para Milanuncios.

        Args:
            zona_key: Key de la zona en ZONAS_GEOGRAFICAS
            page: Número de página (1-indexed)

        Returns:
            URL completa para la búsqueda
        """
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zona no encontrada: {zona_key}. Disponibles: {list(ZONAS_GEOGRAFICAS.keys())}")

        # Usar el radio específico de la zona si existe, si no usar el default
        zone_distance = zona.get('distance', self.distance)

        params = {
            'vendedor': 'part',  # Solo particulares
            'latitude': zona['latitude'],
            'longitude': zona['longitude'],
            'distance': zone_distance,
            'geoProvinceId': zona['geoProvinceId'],
            'geolocationTerm': zona['geolocationTerm'],
            'orden': 'date',
            'fromSearch': 1,
            'hitOrigin': 'listing',
            'desde': 5000,  # Precio mínimo 5000€ para filtrar basura
        }

        # Añadir filtros de precio (sobrescribe el mínimo si es mayor)
        if self.filters.get('precio_min') and self.filters['precio_min'] > 5000:
            params['desde'] = self.filters['precio_min']
        if self.filters.get('precio_max'):
            params['hasta'] = self.filters['precio_max']

        # Añadir paginación
        if page > 1:
            params['pagina'] = page

        # Usar /inmobiliaria/ con filtros (el filtro de alquileres se hace en código)
        base_url = 'https://www.milanuncios.com/inmobiliaria/'
        return f"{base_url}?{urlencode(params, quote_via=quote)}"

    def start_requests(self):
        """
        Genera las URLs iniciales para scrapear.

        Crea URLs para cada zona configurada.

        Yields:
            scrapy.Request con metadata de Playwright
        """
        # Preparar context_kwargs con storage_state si hay cookies
        context_kwargs = {
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'es-ES',
            'timezone_id': 'Europe/Madrid',
            'user_agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ),
        }

        # Cargar cookies si existen
        if os.path.exists(COOKIES_FILE):
            context_kwargs['storage_state'] = COOKIES_FILE
            logger.info(f"Cargando cookies desde: {COOKIES_FILE}")
        else:
            logger.warning("No hay cookies - el scraper puede ser bloqueado")

        for zona_key in self.zones:
            url = self._build_url(zona_key)
            zona_nombre = ZONAS_GEOGRAFICAS.get(zona_key, {}).get('nombre', zona_key)

            logger.info(f"Iniciando scraping de zona '{zona_nombre}': {url}")

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_context_kwargs': context_kwargs,  # Cargar cookies aquí
                    'playwright_page_methods': [
                        # Anti-detección avanzada
                        PageMethod('add_init_script', '''
                            Object.defineProperty(navigator, "webdriver", {get: () => undefined});
                            Object.defineProperty(navigator, "plugins", {get: () => [1, 2, 3, 4, 5]});
                            Object.defineProperty(navigator, "languages", {get: () => ["es-ES", "es", "en"]});
                            window.chrome = {runtime: {}};
                        '''),
                        # Esperar carga completa
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_timeout', 4000),
                        # Scroll suave
                        PageMethod('evaluate', 'window.scrollTo({top: 500, behavior: "smooth"})'),
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('evaluate', 'window.scrollTo({top: document.body.scrollHeight, behavior: "smooth"})'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                    'zona_key': zona_key,
                    'current_page': 1,
                },
                errback=self.errback_close_page,
            )

    async def parse(self, response: Response):
        """
        Parsea la página de resultados de Milanuncios.

        Extrae todos los listings de la página, aplica filtros
        y guarda los que pasan el filtro.

        Args:
            response: Respuesta de Scrapy con contenido de la página

        Yields:
            Dict con datos del listing
        """
        page = response.meta.get('playwright_page')
        zona_key = response.meta.get('zona_key')
        current_page = response.meta.get('current_page', 1)

        self.stats['pages_scraped'] += 1
        logger.info(f"Parseando página {current_page} de zona {zona_key}: {response.url}")

        # Detectar si estamos bloqueados por captcha/bot detection
        blocked_indicators = [
            'Pardon Our Interruption',
            'geetest',
            'captcha',
            'cf-browser-verification',  # Cloudflare
            'challenge-platform',  # Cloudflare
        ]
        is_blocked = any(indicator.lower() in response.text.lower() for indicator in blocked_indicators)

        if is_blocked:
            self.stats['blocked_count'] += 1
            logger.error(
                f"BLOQUEADO (intento {self.stats['blocked_count']}): Milanuncios ha detectado el scraper como bot. "
                f"Zona: {zona_key}, URL: {response.url}"
            )
            logger.warning(
                "Posibles soluciones:\n"
                "  1. Ejecutar 'python scrapers/capture_cookies.py' para capturar cookies frescas\n"
                "  2. Usar proxies residenciales\n"
                "  3. Esperar unas horas antes de reintentar"
            )
            if page:
                await page.close()
            return

        # Extraer todas las cards de listings
        # Milanuncios usa data-testid="AD_CARD" para cada anuncio
        listing_cards = response.css('[data-testid="AD_CARD"]')

        logger.info(f"Encontrados {len(listing_cards)} listings en la página")

        for card in listing_cards:
            self.stats['total_listings'] += 1

            try:
                # Extraer datos básicos del listing
                listing_data = self._extract_listing_data(card, response, zona_key)

                # Omitir listings sin anuncio_id (son anuncios patrocinados o sin enlace)
                if not listing_data.get('anuncio_id'):
                    logger.debug(f"Listing sin anuncio_id omitido: {listing_data.get('titulo', 'Sin título')}")
                    self.stats['filtered_out'] += 1
                    continue

                # === FILTROS DE CALIDAD ===

                # 1. Filtrar por precio mínimo (5000€)
                precio = listing_data.get('precio')
                if precio is None or precio < 5000:
                    logger.debug(f"Filtrado por precio bajo ({precio}€): {listing_data.get('titulo', 'Sin título')}")
                    self.stats['filtered_out'] += 1
                    continue

                # 2. Filtrar anuncios de compartir piso / alquiler de habitaciones
                titulo_lower = (listing_data.get('titulo') or '').lower()
                descripcion_lower = (listing_data.get('descripcion') or '').lower()
                texto_completo = f"{titulo_lower} {descripcion_lower}"

                palabras_excluidas = [
                    'compartir', 'comparto', 'habitacion', 'habitación',
                    'alquiler', 'alquilo', 'se alquila', 'busco compañero',
                    'busco compañera', 'piso compartido', 'room', 'roommate',
                    'estudiante', 'estudiantes', 'temporal', 'por meses',
                    'amueblado', 'amueblada'  # Suelen ser alquileres
                ]

                es_compartir_piso = any(palabra in texto_completo for palabra in palabras_excluidas)
                if es_compartir_piso:
                    logger.debug(f"Filtrado por compartir/alquiler: {listing_data.get('titulo', 'Sin título')}")
                    self.stats['filtered_out'] += 1
                    continue

                # 3. Solo aceptar tipos de inmuebles válidos para compra
                tipo_inmueble = listing_data.get('tipo_inmueble', '')
                tipos_validos = ['Piso', 'Casa', 'Garaje', 'Terreno', 'Local', 'Nave', 'Ático', 'Dúplex', 'Estudio', 'Oficina', 'Otros']

                # Si no es un tipo válido, verificar que el título sugiera venta
                palabras_venta = ['vendo', 'venta', 'se vende', 'oportunidad', 'ocasión', 'precio negociable']
                es_venta = any(palabra in texto_completo for palabra in palabras_venta) or tipo_inmueble in tipos_validos

                if not es_venta and tipo_inmueble not in tipos_validos:
                    logger.debug(f"Filtrado por tipo no válido ({tipo_inmueble}): {listing_data.get('titulo', 'Sin título')}")
                    self.stats['filtered_out'] += 1
                    continue

                # NOTA: La extracción de teléfono se deshabilitó porque Milanuncios
                # bloquea el scraper al navegar a las páginas de detalle (bot detection).
                # El teléfono queda como None y el vendedor como 'Particular'.

                # Aplicar filtro de particulares
                if not self.base_scraper.should_scrape(listing_data):
                    self.stats['filtered_out'] += 1
                    logger.debug(f"Listing filtrado: {listing_data.get('titulo', 'Sin título')}")
                    continue

                # Normalizar teléfono
                if listing_data.get('telefono'):
                    listing_data['telefono_norm'] = self.base_scraper.normalize_phone(
                        listing_data['telefono']
                    )

                # Usar la zona de búsqueda como zona_geografica (más específica que classify_zone)
                # Si tenemos zona_busqueda, usarla. Si no, intentar clasificar por código postal
                if listing_data.get('zona_busqueda'):
                    listing_data['zona_geografica'] = listing_data['zona_busqueda']
                elif listing_data.get('codigo_postal'):
                    listing_data['zona_geografica'] = self.base_scraper.classify_zone(
                        listing_data['codigo_postal']
                    )

                # Guardar en data lake (opcional - solo si MinIO está configurado)
                data_lake_path = self.base_scraper.save_to_data_lake(
                    listing_data,
                    portal='milanuncios'
                )

                # Guardar en PostgreSQL (siempre intentar, independientemente de MinIO)
                success = self.base_scraper.save_to_postgres_raw(
                    listing_data,
                    data_lake_path or '',  # Usar string vacío si no hay MinIO
                    portal='milanuncios'
                )

                if success:
                    self.stats['saved'] += 1
                    logger.info(f"Listing guardado: {listing_data.get('titulo', 'Sin título')}")

                yield listing_data

            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"Error procesando listing: {e}", exc_info=True)

        # Cerrar página de Playwright
        if page:
            await page.close()

        # Log de estadísticas parciales
        logger.info(
            f"Estadísticas parciales: Total={self.stats['total_listings']}, "
            f"Filtrados={self.stats['filtered_out']}, "
            f"Guardados={self.stats['saved']}, "
            f"Errores={self.stats['errors']}"
        )

        # Buscar siguiente página
        next_page_link = response.css('a[rel="next"]::attr(href)').get()
        if not next_page_link:
            next_page_link = response.css('a.sui-AtomButton--link[aria-label*="Siguiente"]::attr(href)').get()
        if not next_page_link:
            next_page_link = response.css('a[data-testid="PAGINATION_NEXT"]::attr(href)').get()

        if next_page_link:
            next_page_num = current_page + 1
            logger.info(f"Siguiente página encontrada: {next_page_link}")

            # Reutilizar context_kwargs con cookies
            context_kwargs = {
                'viewport': {'width': 1920, 'height': 1080},
                'locale': 'es-ES',
                'timezone_id': 'Europe/Madrid',
                'user_agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
                ),
            }
            if os.path.exists(COOKIES_FILE):
                context_kwargs['storage_state'] = COOKIES_FILE

            yield response.follow(
                next_page_link,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_context_kwargs': context_kwargs,
                    'playwright_page_methods': [
                        PageMethod('add_init_script', 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'),
                        PageMethod('wait_for_load_state', 'domcontentloaded'),
                        PageMethod('wait_for_timeout', 5000),
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 3000),
                    ],
                    'zona_key': zona_key,
                    'current_page': next_page_num,
                },
                errback=self.errback_close_page,
            )

    def _extract_listing_data(self, card, response: Response, zona_key: str) -> Dict[str, Any]:
        """
        Extrae datos de un listing card de Milanuncios.

        Selectores actualizados para Milanuncios 2024:
        - Tarjeta: [data-testid="AD_CARD"]
        - Título: .ma-AdCardListingV2-TitleLink h2
        - URL: .ma-AdCardListingV2-TitleLink::attr(href)
        - Precio: .ma-AdPrice-value
        - Ubicación: .ma-AdLocation
        - Foto: .ma-AdCardV2-photo::attr(src)

        Args:
            card: Selector de Scrapy con la card del listing
            response: Response para construir URLs absolutas
            zona_key: Key de la zona actual

        Returns:
            Dict con datos extraídos del listing
        """
        # Extraer título y URL
        titulo = None
        detail_url = None

        # Selector principal para título y URL (2024)
        title_link = card.css('.ma-AdCardListingV2-TitleLink')
        if title_link:
            # El título está en un h2 dentro del enlace
            titulo = title_link.css('h2::text, .ma-AdCardV2-title::text').get()
            detail_url = title_link.css('::attr(href)').get()

        # Fallback a selectores anteriores
        if not titulo:
            title_link = card.css('.ma-AdCardV2-TitleRow a, .ma-AdCardListingV2-TitleRow a')
            if title_link:
                titulo = title_link.css('::text').get()
                detail_url = detail_url or title_link.css('::attr(href)').get()

        if detail_url:
            detail_url = response.urljoin(detail_url)

        # Extraer precio (selector actualizado 2024)
        precio_text = card.css('.ma-AdPrice-value::text').get()
        if not precio_text:
            # Buscar en todo el HTML del precio
            precio_text = card.css('.ma-AdMultiplePrice .ma-AdPrice-value::text').get()
        if not precio_text:
            precio_text = card.css('.ma-AdCardV2-price::text').get()
        precio = self._parse_price(precio_text)

        # Extraer ubicación (selector actualizado 2024)
        # El texto está dentro de spans anidados en el address
        ubicacion_texts = card.css('.ma-AdLocation *::text').getall()
        ubicacion = ' '.join([t.strip() for t in ubicacion_texts if t.strip()]) if ubicacion_texts else None
        if not ubicacion:
            ubicacion = card.css('.ma-AdLocation::text').get()
        if not ubicacion:
            ubicacion = card.css('.ma-AdCardV2-location::text').get()

        # Extraer características de los tags
        habitaciones = None
        metros = None
        banos = None
        certificado_energetico = None

        # Los features están en .ma-AdTag-label
        features = card.css('.ma-AdTag-label::text').getall()
        for feature in features:
            feature_clean = feature.strip()
            feature_lower = feature_clean.lower()

            if 'dorm' in feature_lower:
                habitaciones = self._parse_number(feature_clean)
            elif 'baño' in feature_lower:
                banos = self._parse_number(feature_clean)
            elif 'm²' in feature_lower or 'm2' in feature_lower:
                # Solo metros cuadrados, no precio/m²
                if '€' not in feature_clean:
                    metros = self._parse_number(feature_clean)
            elif feature_clean.startswith('CE:'):
                certificado_energetico = feature_clean.replace('CE:', '').strip()

        # Extraer ID del anuncio de la URL
        anuncio_id = None
        if detail_url:
            match = re.search(r'-(\d+)\.htm', detail_url)
            if match:
                anuncio_id = match.group(1)

        # Extraer imágenes (hasta 5) - selectores actualizados 2024
        fotos = []
        foto_selectors = [
            'img.ma-AdCardV2-photo::attr(src)',  # Selector principal 2024
            '.ma-AdCardV2-photoContainer img::attr(src)',
            '.ma-AdCardV2-photo::attr(src)',
            '.ma-AdCard-photo img::attr(src)',
            'img[src*="images.milanuncios"]::attr(src)',
        ]
        for sel in foto_selectors:
            imgs = card.css(sel).getall()
            for img in imgs:
                if img and 'milanuncios' in img and img not in fotos:
                    fotos.append(img)
                    if len(fotos) >= 5:
                        break
            if fotos:
                break

        imagen = fotos[0] if fotos else None

        # Extraer número total de fotos desde el caption
        num_fotos = None
        caption_text = card.css('.ma-AdCardV2-photoCaption::text').get()
        if caption_text:
            num_fotos = self._parse_number(caption_text)

        # Extraer código postal de ubicación
        codigo_postal = self._extract_postal_code(ubicacion)

        # Info de la zona
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Intentar extraer nombre del vendedor de la tarjeta
        vendedor_nombre = None
        vendedor_selectors = [
            '.ma-AdCard-sellerName::text',
            '.ma-AdCardV2-sellerName::text',
            '[class*="SellerName"]::text',
            '[class*="UserName"]::text',
            '.ma-AdCard-user::text',
        ]
        for selector in vendedor_selectors:
            vendedor_nombre = card.css(selector).get()
            if vendedor_nombre and vendedor_nombre.strip():
                vendedor_nombre = vendedor_nombre.strip()
                break
        else:
            vendedor_nombre = 'Particular'

        # Extraer fecha de publicación
        fecha_publicacion = None
        fecha_selectors = [
            '.ma-AdCard-date::text',
            '.ma-AdCardV2-date::text',
            '[class*="Date"]::text',
            'time::attr(datetime)',
            'time::text',
        ]
        for selector in fecha_selectors:
            fecha_text = card.css(selector).get()
            if fecha_text and fecha_text.strip():
                fecha_publicacion = fecha_text.strip()
                break

        # Extraer descripción breve (si existe en la card)
        descripcion = None
        desc_selectors = [
            '.ma-AdCard-description::text',
            '.ma-AdCardV2-description::text',
            '[class*="Description"]::text',
        ]
        for selector in desc_selectors:
            descripcion = card.css(selector).get()
            if descripcion and descripcion.strip():
                descripcion = descripcion.strip()
                break

        # Detectar tipo de inmueble del título
        tipo_inmueble = self._detectar_tipo_inmueble(titulo or '')

        data = {
            'anuncio_id': anuncio_id,
            'titulo': titulo.strip() if titulo else None,
            'precio': precio,
            'ubicacion': ubicacion.strip() if ubicacion else None,
            'codigo_postal': codigo_postal,
            'habitaciones': habitaciones,
            'metros': metros,
            'banos': banos,
            'certificado_energetico': certificado_energetico,
            'tipo_inmueble': tipo_inmueble,
            'descripcion': descripcion,
            'fecha_publicacion': fecha_publicacion,
            'imagen_principal': imagen,
            'fotos': fotos,  # Lista de hasta 5 fotos
            'detail_url': detail_url,
            'url_anuncio': detail_url,  # Alias para compatibilidad
            'portal': 'milanuncios',
            'vendedor': vendedor_nombre,
            'zona_busqueda': zona_info.get('nombre', zona_key),
            'telefono': None,
            'email': None,
        }

        return data

    async def _extract_phone_from_detail(self, page, detail_url: str) -> Optional[dict]:
        """
        Navega a la página de detalle para extraer el teléfono y nombre del vendedor.

        En Milanuncios hay que hacer click en un botón para abrir un modal
        con clase sui-MoleculeModal-dialog que muestra nombre y teléfono.

        Args:
            page: Page object de Playwright
            detail_url: URL de la página de detalle

        Returns:
            dict: {'telefono': str, 'nombre_vendedor': str} o None
        """
        new_page = None
        try:
            logger.info(f"Extrayendo contacto de: {detail_url}")

            # Abrir nueva página para no perder el contexto
            new_page = await page.context.new_page()
            await new_page.goto(detail_url, wait_until='domcontentloaded', timeout=30000)

            # Esperar a que cargue la página
            await new_page.wait_for_timeout(3000)

            # Detectar si estamos bloqueados
            page_content = await new_page.content()
            if 'Pardon Our Interruption' in page_content or 'geetest' in page_content.lower():
                logger.warning(f"Bloqueado por bot detection al visitar: {detail_url}")
                await new_page.close()
                return None

            # Buscar botón de teléfono/contacto - selectores actualizados 2024
            phone_button_selectors = [
                'button[data-testid="AD_DETAIL_CONTACT_PHONE_BUTTON"]',
                '[data-testid="PHONE_BUTTON"]',
                '.ma-ButtonPhone',
                'button.sui-AtomButton:has-text("Ver teléfono")',
                'button.sui-AtomButton:has-text("Llamar")',
                'button:has-text("Ver teléfono")',
                'button:has-text("Llamar")',
                '[class*="ContactButton"]',
                '[class*="PhoneButton"]',
            ]

            phone_button = None
            for selector in phone_button_selectors:
                try:
                    phone_button = await new_page.query_selector(selector)
                    if phone_button:
                        logger.info(f"Botón de teléfono encontrado con selector: {selector}")
                        break
                except:
                    continue

            if not phone_button:
                logger.warning(f"No se encontró botón de teléfono en {detail_url}")
                await new_page.close()
                return None

            # Click en el botón
            await phone_button.click()
            logger.info("Click en botón de teléfono realizado")
            await new_page.wait_for_timeout(2000)

            # Esperar el modal - múltiples selectores
            modal_selectors = [
                '.sui-MoleculeModal-dialog',
                '[class*="MoleculeModal-dialog"]',
                '[class*="Modal-dialog"]',
                '.sui-MoleculeModal',
                '[role="dialog"]',
            ]

            modal = None
            for selector in modal_selectors:
                try:
                    modal = await new_page.wait_for_selector(selector, timeout=3000)
                    if modal:
                        logger.info(f"Modal encontrado con selector: {selector}")
                        break
                except:
                    continue

            if not modal:
                logger.warning(f"No se encontró modal en {detail_url}")
                await new_page.close()
                return None

            # Extraer todo el texto del modal
            modal_text = await modal.text_content()
            logger.info(f"Texto del modal: {modal_text[:200] if modal_text else 'vacío'}...")

            # Buscar teléfono (9 dígitos españoles, con o sin espacios)
            phone = None
            # Primero intentar enlace tel:
            phone_link = await modal.query_selector('a[href^="tel:"]')
            if phone_link:
                href = await phone_link.get_attribute('href')
                if href:
                    phone = href.replace('tel:', '').replace('+34', '').replace(' ', '').strip()
                    logger.info(f"Teléfono extraído de enlace tel: {phone}")

            # Si no hay enlace, buscar en el texto
            if not phone and modal_text:
                # Buscar patrón de teléfono español (6xx xxx xxx o 9xx xxx xxx)
                phone_patterns = [
                    r'([679]\d{2}[\s\.]?\d{3}[\s\.]?\d{3})',  # Móvil o fijo
                    r'(\d{3}[\s\.]?\d{3}[\s\.]?\d{3})',  # Cualquier 9 dígitos
                    r'(\d{9})',  # 9 dígitos seguidos
                ]
                for pattern in phone_patterns:
                    match = re.search(pattern, modal_text)
                    if match:
                        phone = re.sub(r'[\s\.]', '', match.group(1))
                        logger.info(f"Teléfono extraído de texto: {phone}")
                        break

            # Extraer nombre del vendedor
            nombre_vendedor = None
            if modal_text:
                # El nombre suele estar en las primeras líneas del modal
                lines = [l.strip() for l in modal_text.split('\n') if l.strip()]
                for line in lines[:5]:
                    # Ignorar líneas que son teléfonos, botones o textos de UI
                    if len(line) < 30 and not re.match(r'^[\d\s\.\+\-\(\)]+$', line):
                        if not any(x in line.lower() for x in [
                            'ver', 'llamar', 'contactar', 'teléfono', 'cerrar',
                            'whatsapp', 'chat', 'mensaje', 'email', 'correo', 'enviar'
                        ]):
                            nombre_vendedor = line
                            logger.info(f"Nombre del vendedor extraído: {nombre_vendedor}")
                            break

            await new_page.close()

            if phone or nombre_vendedor:
                return {'telefono': phone, 'nombre_vendedor': nombre_vendedor}

            return None

        except Exception as e:
            logger.warning(f"Error extrayendo contacto de {detail_url}: {e}")
            if new_page:
                try:
                    await new_page.close()
                except:
                    pass

        return None

    def _parse_price(self, price_text: Optional[str]) -> Optional[float]:
        """Parsea texto de precio a float."""
        if not price_text:
            return None

        try:
            # Quitar símbolos de moneda, puntos de miles, etc.
            cleaned = re.sub(r'[€$\s]', '', price_text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _parse_number(self, text: Optional[str]) -> Optional[int]:
        """Extrae el primer número de un texto."""
        if not text:
            return None

        match = re.search(r'\d+', text)
        if match:
            return int(match.group())
        return None

    def _extract_postal_code(self, address: Optional[str]) -> Optional[str]:
        """Extrae código postal de una dirección."""
        if not address:
            return None

        # Buscar patrón de 5 dígitos (códigos postales españoles)
        match = re.search(r'\b(\d{5})\b', address)
        if match:
            return match.group(1)
        return None

    def _detectar_tipo_inmueble(self, texto: str) -> str:
        """Detecta el tipo de inmueble del texto del título."""
        texto_lower = texto.lower()

        if 'piso' in texto_lower or 'apartamento' in texto_lower:
            return 'Piso'
        elif 'casa' in texto_lower or 'chalet' in texto_lower or 'villa' in texto_lower:
            return 'Casa'
        elif 'local' in texto_lower:
            return 'Local'
        elif 'garaje' in texto_lower or 'parking' in texto_lower or 'plaza' in texto_lower:
            return 'Garaje'
        elif 'terreno' in texto_lower or 'parcela' in texto_lower or 'solar' in texto_lower:
            return 'Terreno'
        elif 'nave' in texto_lower:
            return 'Nave'
        elif 'oficina' in texto_lower or 'despacho' in texto_lower:
            return 'Oficina'
        elif 'atico' in texto_lower or 'ático' in texto_lower:
            return 'Ático'
        elif 'duplex' in texto_lower or 'dúplex' in texto_lower:
            return 'Dúplex'
        elif 'estudio' in texto_lower or 'loft' in texto_lower:
            return 'Estudio'
        else:
            return 'Otros'

    async def errback_close_page(self, failure):
        """Callback de error que cierra la página de Playwright."""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()

        logger.error(f"Error en request: {failure.request.url} - {failure.value}")

    def closed(self, reason):
        """Se llama cuando el spider termina."""
        logger.info(
            f"Spider cerrado. Razón: {reason}\n"
            f"Estadísticas finales:\n"
            f"  - Páginas scrapeadas: {self.stats['pages_scraped']}\n"
            f"  - Total listings procesados: {self.stats['total_listings']}\n"
            f"  - Filtrados (rechazados): {self.stats['filtered_out']}\n"
            f"  - Guardados exitosamente: {self.stats['saved']}\n"
            f"  - Errores: {self.stats['errors']}\n"
            f"  - Bloqueos por bot detection: {self.stats['blocked_count']}\n"
            f"  - Tasa de filtrado: {self.stats['filtered_out'] / max(self.stats['total_listings'], 1) * 100:.1f}%"
        )
        if self.stats['blocked_count'] > 0:
            logger.warning(
                f"El scraper fue bloqueado {self.stats['blocked_count']} veces. "
                f"Considera capturar cookies nuevas o usar proxies."
            )

        # Cerrar conexiones de BaseScraper
        if hasattr(self, 'base_scraper'):
            self.base_scraper.close()


# Función de conveniencia para ejecutar el scraper
def run_milanuncios_scraper(
    zones: List[str] = None,
    precio_min: int = None,
    precio_max: int = None,
    distance: int = 20000,
    **kwargs
):
    """
    Ejecuta el scraper de Milanuncios.

    Args:
        zones: Lista de zonas a scrapear. Opciones disponibles:
               - 'la_bordeta': La Bordeta, Lleida
               - 'lleida_ciudad': Lleida capital
               - 'tarragona_ciudad': Tarragona capital
               - 'salou': Salou
               - 'cambrils': Cambrils
               - 'costa_dorada': Costa Dorada (centro en Salou)
               - 'reus': Reus
        precio_min: Precio mínimo en euros
        precio_max: Precio máximo en euros
        distance: Radio de búsqueda en metros (default: 20000 = 20km)
        **kwargs: Argumentos adicionales para el spider

    Example:
        >>> run_milanuncios_scraper(
        ...     zones=['salou', 'tarragona_ciudad'],
        ...     precio_min=50000,
        ...     precio_max=300000,
        ...     distance=15000
        ... )
    """
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()

    filters = {}
    if precio_min:
        filters['precio_min'] = precio_min
    if precio_max:
        filters['precio_max'] = precio_max

    process = CrawlerProcess(settings)
    process.crawl(
        MilanunciosScraper,
        zones=zones or ['la_bordeta'],
        filters=filters,
        distance=distance,
        **kwargs
    )
    process.start()


if __name__ == '__main__':
    # Ejemplo de uso: scrapear La Bordeta y Salou
    import sys

    # Zonas a scrapear (se pueden pasar por línea de comandos)
    zones_to_scrape = sys.argv[1:] if len(sys.argv) > 1 else ['la_bordeta']

    print(f"Zonas disponibles: {list(ZONAS_GEOGRAFICAS.keys())}")
    print(f"Scrapeando zonas: {zones_to_scrape}")

    run_milanuncios_scraper(
        zones=zones_to_scrape,
        precio_min=5000,
        distance=20000
    )

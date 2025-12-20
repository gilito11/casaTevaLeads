"""
Scraper de Fotocasa usando Scrapy + Playwright.

Este scraper extrae anuncios de particulares que venden viviendas en Fotocasa,
aplicando filtros para rechazar inmobiliarias y anuncios que no permiten contacto.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

import scrapy
from scrapy.http import Response
from scrapy_playwright.page import PageMethod

from scrapers.base_scraper import BaseScraper
from scrapers.utils.particular_filter import debe_scrapear


logger = logging.getLogger(__name__)


# Zonas predefinidas con sus URLs de Fotocasa
FOTOCASA_ZONES = {
    'tarragona_ciudad': {
        'slug': 'tarragona-capital',
        'nombre': 'Tarragona Ciudad',
    },
    'tarragona_provincia': {
        'slug': 'tarragona-provincia',
        'nombre': 'Tarragona Provincia',
    },
    'lleida_ciudad': {
        'slug': 'lleida-capital',
        'nombre': 'Lleida Ciudad',
    },
    'lleida_provincia': {
        'slug': 'lleida-provincia',
        'nombre': 'Lleida Provincia',
    },
    'barcelona_ciudad': {
        'slug': 'barcelona-capital',
        'nombre': 'Barcelona Ciudad',
    },
    'barcelona_provincia': {
        'slug': 'barcelona-provincia',
        'nombre': 'Barcelona Provincia',
    },
    'girona_provincia': {
        'slug': 'girona-provincia',
        'nombre': 'Girona Provincia',
    },
    'espana': {
        'slug': 'espana',
        'nombre': 'España',
    },
}


class FotocasaScraper(scrapy.Spider):
    """
    Spider de Scrapy para scrapear Fotocasa con Playwright.

    Extrae anuncios de particulares que venden viviendas en Lleida,
    guarda los datos en MinIO (data lake) y PostgreSQL (raw layer).

    Attributes:
        name: Nombre del spider ('fotocasa')
        tenant_id: ID del tenant al que pertenece
        zones: Zonas geográficas a scrapear
        filters: Filtros de precio, habitaciones, etc.
    """

    name = 'fotocasa'

    custom_settings = {
        # Configuración de scrapy-playwright
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',

        # Configuración de rate limiting
        'DOWNLOAD_DELAY': 3,  # 3 segundos entre requests
        'CONCURRENT_REQUESTS': 1,  # 1 request concurrente para evitar baneos
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,

        # User agent realista
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),

        # Respetar robots.txt
        'ROBOTSTXT_OBEY': False,  # Fotocasa bloquea scrapers en robots.txt

        # Retry settings
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],

        # Playwright settings
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 60000,  # 60 segundos
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
    }

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        minio_config: Optional[Dict[str, str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        *args,
        **kwargs
    ):
        """
        Inicializa el spider de Fotocasa.

        Args:
            tenant_id: ID del tenant
            zones: Lista de claves de zona de FOTOCASA_ZONES (ej: ['tarragona_ciudad'])
            filters: Filtros de búsqueda (precio, habitaciones, etc.)
            minio_config: Configuración de MinIO
            postgres_config: Configuración de PostgreSQL
        """
        super().__init__(*args, **kwargs)

        self.tenant_id = tenant_id
        # Zonas como lista de claves
        self.zone_keys = zones or ['tarragona_provincia']
        self.filters = filters or {}

        # Inicializar BaseScraper para persistencia
        self.base_scraper = BaseScraper(
            tenant_id=tenant_id,
            zones={},
            filters=filters or {},
            minio_config=minio_config,
            postgres_config=postgres_config
        )

        # Estadísticas
        self.stats = {
            'total_listings': 0,
            'filtered_out': 0,
            'saved': 0,
            'errors': 0
        }

        zone_names = [FOTOCASA_ZONES.get(z, {}).get('nombre', z) for z in self.zone_keys]
        logger.info(f"FotocasaScraper inicializado para tenant_id={tenant_id}, zonas={zone_names}")

    def start_requests(self):
        """
        Genera las URLs iniciales para scrapear.

        Crea URLs para cada zona configurada en self.zone_keys,
        aplicando los filtros de precio configurados.

        Yields:
            scrapy.Request con metadata de Playwright
        """
        # Construir parámetros de query según filtros
        params = {}

        if self.filters.get('filtros_precio'):
            precio_min = self.filters['filtros_precio'].get('min')
            precio_max = self.filters['filtros_precio'].get('max')

            if precio_min:
                params['minPrice'] = precio_min
            if precio_max:
                params['maxPrice'] = precio_max

        # Generar request para cada zona
        for zone_key in self.zone_keys:
            zone_config = FOTOCASA_ZONES.get(zone_key)
            if not zone_config:
                logger.warning(f"Zona desconocida: {zone_key}")
                continue

            zone_slug = zone_config['slug']

            # URL de Fotocasa actualizada (2024/2025)
            # Formato: /es/comprar/viviendas/{zona}/todas-las-zonas/l
            base_url = f'https://www.fotocasa.es/es/comprar/viviendas/{zone_slug}/todas-las-zonas/l'

            # Construir URL completa
            if params:
                url = f"{base_url}?{urlencode(params)}"
            else:
                url = base_url

            logger.info(f"Iniciando scraping de: {url}")

            # Request con Playwright usando PageMethod objects
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        # Esperar a que se carguen los listings (buscar article dentro de section)
                        PageMethod('wait_for_selector', 'section article', timeout=30000),
                        # Scroll para cargar lazy loading
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                    'zone_key': zone_key,
                },
                errback=self.errback_close_page,
            )

    async def parse(self, response: Response):
        """
        Parsea la página de resultados de Fotocasa.

        Extrae todos los listings de la página, aplica filtros
        y guarda los que pasan el filtro.

        Args:
            response: Respuesta de Scrapy con contenido de la página

        Yields:
            Dict con datos del listing (para estadísticas)
        """
        page = response.meta.get('playwright_page')
        zone_key = response.meta.get('zone_key', 'unknown')

        logger.info(f"Parseando página: {response.url}")

        # Detectar si estamos bloqueados o hay error
        if response.status == 404:
            logger.error(f"Página no encontrada (404): {response.url}")
            if page:
                await page.close()
            return

        if response.status != 200:
            logger.error(f"Error HTTP {response.status} en {response.url}")
            if page:
                await page.close()
            return

        # Detectar si estamos bloqueados por bot detection
        bot_detection_patterns = [
            'sentimos la interrupci',
            'pardon our interruption',
            'captcha',
            'verificación',
            'robot',
            'bot detection',
        ]

        page_title = response.css('title::text').get() or ''
        page_text = response.text.lower()

        for pattern in bot_detection_patterns:
            if pattern in page_title.lower() or pattern in page_text[:5000]:
                logger.error(
                    f"BLOQUEADO: Fotocasa ha detectado el scraper como bot. "
                    f"Page title: '{page_title}'. "
                    f"Considera usar proxies residenciales o reducir la frecuencia de scraping."
                )
                if page:
                    await page.close()
                return

        # Probar múltiples selectores para extraer las cards
        listing_cards = []
        selectors_to_try = [
            'section article',
            'article',
            'article[data-type="ad"]',
            '.re-Card',
            'article.re-SearchResult',
            '[data-testid="listing-card"]',
            '.sui-AtomCard',
            'article[class*="Card"]',
        ]

        for selector in selectors_to_try:
            listing_cards = response.css(selector)
            if listing_cards:
                logger.info(f"Usando selector: {selector} - Encontrados {len(listing_cards)} listings")
                break

        if not listing_cards:
            # Debug: guardar HTML para análisis
            logger.warning(f"No se encontraron listings con ningún selector. Guardando HTML para debug...")
            html_preview = response.text[:2000]
            logger.debug(f"HTML preview: {html_preview}")
            if page:
                await page.close()
            return

        logger.info(f"Encontrados {len(listing_cards)} listings en la página")

        for card in listing_cards:
            self.stats['total_listings'] += 1

            try:
                # Extraer datos básicos del listing
                listing_data = self._extract_listing_data(card, response)

                # Intentar extraer teléfono con Playwright si está disponible
                if page:
                    phone = await self._extract_phone_with_playwright(page, card)
                    if phone:
                        listing_data['telefono'] = phone

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

                # Clasificar zona
                if listing_data.get('codigo_postal'):
                    listing_data['zona_geografica'] = self.base_scraper.classify_zone(
                        listing_data['codigo_postal']
                    )

                # Guardar en data lake
                data_lake_path = self.base_scraper.save_to_data_lake(
                    listing_data,
                    portal='fotocasa'
                )

                # Guardar en PostgreSQL
                if data_lake_path:
                    success = self.base_scraper.save_to_postgres_raw(
                        listing_data,
                        data_lake_path,
                        portal='fotocasa'
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

        # Log de estadísticas
        logger.info(
            f"Estadísticas: Total={self.stats['total_listings']}, "
            f"Filtrados={self.stats['filtered_out']}, "
            f"Guardados={self.stats['saved']}, "
            f"Errores={self.stats['errors']}"
        )

        # Buscar siguiente página (paginación)
        next_page_selectors = [
            'a[rel="next"]::attr(href)',
            'a.sui-AtomButton--link[aria-label*="Siguiente"]::attr(href)',
            'a[aria-label*="siguiente"]::attr(href)',
            'a[title*="Siguiente"]::attr(href)',
        ]

        next_page = None
        for sel in next_page_selectors:
            next_page = response.css(sel).get()
            if next_page:
                break

        if next_page:
            logger.info(f"Siguiente página encontrada: {next_page}")
            yield response.follow(
                next_page,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_selector', 'section article', timeout=30000),
                    ],
                    'zone_key': zone_key,
                },
                errback=self.errback_close_page,
            )

    def _extract_listing_data(self, card, response: Response) -> Dict[str, Any]:
        """
        Extrae datos de un listing card.

        Intenta múltiples selectores para adaptarse a cambios en la estructura
        del HTML de Fotocasa.

        Args:
            card: Selector de Scrapy con la card del listing
            response: Response para construir URLs absolutas

        Returns:
            Dict con datos extraídos del listing
        """
        # Extraer URL del anuncio (primero para obtener anuncio_id)
        url_anuncio = None
        url_selectors = [
            'a.re-Card-link::attr(href)',
            'a[href*="/inmueble/"]::attr(href)',
            'a::attr(href)',
        ]
        for sel in url_selectors:
            url_anuncio = card.css(sel).get()
            if url_anuncio and '/inmueble/' in url_anuncio:
                url_anuncio = response.urljoin(url_anuncio)
                break

        # Extraer anuncio_id de la URL para deduplicación
        anuncio_id = None
        if url_anuncio:
            # URL formato: .../inmueble/12345678/
            match = re.search(r'/inmueble/(\d+)', url_anuncio)
            if match:
                anuncio_id = match.group(1)

        # También intentar extraer del data attribute
        if not anuncio_id:
            anuncio_id = card.css('::attr(data-id)').get()
        if not anuncio_id:
            anuncio_id = card.css('::attr(data-ad-id)').get()

        # Extraer título
        titulo = None
        titulo_selectors = [
            '.re-Card-title::text',
            'a.re-Card-link::attr(title)',
            '[class*="CardTitle"]::text',
            'h3::text',
            'a::attr(title)',
        ]
        for sel in titulo_selectors:
            titulo = card.css(sel).get()
            if titulo and titulo.strip():
                titulo = titulo.strip()
                break

        # Extraer precio
        precio_text = None
        precio_selectors = [
            '.re-Card-price::text',
            '[class*="Price"]::text',
            '[class*="price"]::text',
            'span[data-testid="price"]::text',
        ]
        for sel in precio_selectors:
            precio_text = card.css(sel).get()
            if precio_text:
                break
        precio = self._parse_price(precio_text)

        # Extraer dirección/ubicación
        direccion = None
        direccion_selectors = [
            '.re-Card-location::text',
            '[class*="Location"]::text',
            '[class*="location"]::text',
            '[class*="Address"]::text',
        ]
        for sel in direccion_selectors:
            direccion = card.css(sel).get()
            if direccion and direccion.strip():
                direccion = direccion.strip()
                break

        # Extraer características (habitaciones, metros)
        habitaciones = None
        metros = None

        # Intentar múltiples selectores para features
        features_selectors = [
            '.re-Card-features span::text',
            '[class*="Feature"] span::text',
            '[class*="feature"]::text',
            'li[class*="feature"]::text',
        ]
        features = []
        for sel in features_selectors:
            features = card.css(sel).getall()
            if features:
                break

        for feature in features:
            if 'hab' in feature.lower():
                habitaciones = self._parse_number(feature)
            elif 'm²' in feature.lower() or 'm2' in feature.lower():
                metros = self._parse_number(feature)

        # Extraer fotos
        fotos = []
        foto_selectors = [
            '.re-Card-multimedia img::attr(src)',
            'img[class*="Card"]::attr(src)',
            'img::attr(data-src)',
            'img::attr(src)',
        ]
        for sel in foto_selectors:
            fotos = card.css(sel).getall()
            if fotos:
                break

        # Extraer descripción (si está disponible)
        descripcion = None
        desc_selectors = [
            '.re-Card-description::text',
            '[class*="Description"]::text',
        ]
        for sel in desc_selectors:
            descripcion = card.css(sel).get()
            if descripcion:
                descripcion = descripcion.strip()
                break

        # Extraer código postal de la dirección (si es posible)
        codigo_postal = self._extract_postal_code(direccion)

        # Construir diccionario de datos
        data = {
            'anuncio_id': anuncio_id,
            'titulo': titulo,
            'precio': precio,
            'direccion': direccion or '',
            'codigo_postal': codigo_postal,
            'habitaciones': habitaciones,
            'metros': metros,
            'descripcion': descripcion or '',
            'fotos': fotos,
            'url_anuncio': url_anuncio,
            'portal': 'fotocasa',
            # Estos campos se rellenarán después si se puede extraer
            'telefono': None,
            'nombre': 'Particular',  # Fotocasa no muestra nombre por defecto
            'email': None,
        }

        return data

    async def _extract_phone_with_playwright(self, page, card) -> Optional[str]:
        """
        Extrae el teléfono usando Playwright haciendo click en el botón.

        NOTA: Esta funcionalidad puede requerir login o estar limitada.
        Fotocasa suele mostrar teléfonos solo después de hacer click.

        Args:
            page: Page object de Playwright
            card: Selector de la card

        Returns:
            str: Número de teléfono o None
        """
        try:
            # Intentar encontrar botón de teléfono
            # NOTA: Selector aproximado, ajustar según Fotocasa real
            phone_button = await page.query_selector('.re-ContactButton--phone')

            if phone_button:
                await phone_button.click()
                await page.wait_for_timeout(1000)  # Esperar a que se muestre

                # Extraer teléfono
                phone_text = await page.eval_on_selector(
                    '.re-ContactDetail-phone',
                    'element => element.textContent'
                )

                return phone_text

        except Exception as e:
            logger.debug(f"No se pudo extraer teléfono con Playwright: {e}")

        return None

    def _parse_price(self, price_text: Optional[str]) -> Optional[float]:
        """Parsea texto de precio a float"""
        if not price_text:
            return None

        try:
            # Quitar símbolos y convertir
            cleaned = price_text.replace('€', '').replace('.', '').replace(',', '.').strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _parse_number(self, text: Optional[str]) -> Optional[int]:
        """Extrae el primer número de un texto"""
        if not text:
            return None

        import re
        match = re.search(r'\d+', text)
        if match:
            return int(match.group())
        return None

    def _extract_postal_code(self, address: Optional[str]) -> Optional[str]:
        """Extrae código postal de una dirección"""
        if not address:
            return None

        import re
        # Buscar patrón de 5 dígitos
        match = re.search(r'\b(\d{5})\b', address)
        if match:
            return match.group(1)
        return None

    async def errback_close_page(self, failure):
        """Callback de error que cierra la página de Playwright"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()

        logger.error(f"Error en request: {failure.request.url} - {failure.value}")

    def closed(self, reason):
        """Se llama cuando el spider termina"""
        logger.info(
            f"Spider cerrado. Razón: {reason}\n"
            f"Estadísticas finales:\n"
            f"  - Total listings procesados: {self.stats['total_listings']}\n"
            f"  - Filtrados (rechazados): {self.stats['filtered_out']}\n"
            f"  - Guardados exitosamente: {self.stats['saved']}\n"
            f"  - Errores: {self.stats['errors']}\n"
            f"  - Tasa de filtrado: {self.stats['filtered_out'] / max(self.stats['total_listings'], 1) * 100:.1f}%"
        )

        # Cerrar conexiones de BaseScraper
        if hasattr(self, 'base_scraper'):
            self.base_scraper.close()

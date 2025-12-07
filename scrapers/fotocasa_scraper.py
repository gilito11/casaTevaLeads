"""
Scraper de Fotocasa usando Scrapy + Playwright.

Este scraper extrae anuncios de particulares que venden viviendas en Fotocasa,
aplicando filtros para rechazar inmobiliarias y anuncios que no permiten contacto.
"""

import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode

import scrapy
from scrapy.http import Response

from scrapers.base_scraper import BaseScraper
from scrapers.utils.particular_filter import debe_scrapear


logger = logging.getLogger(__name__)


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
        zones: Optional[Dict[str, Any]] = None,
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
            zones: Zonas geográficas a scrapear
            filters: Filtros de búsqueda (precio, habitaciones, etc.)
            minio_config: Configuración de MinIO
            postgres_config: Configuración de PostgreSQL
        """
        super().__init__(*args, **kwargs)

        self.tenant_id = tenant_id
        self.zones = zones or {}
        self.filters = filters or {}

        # Inicializar BaseScraper para persistencia
        self.base_scraper = BaseScraper(
            tenant_id=tenant_id,
            zones=zones or {},
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

        logger.info(f"FotocasaScraper inicializado para tenant_id={tenant_id}")

    def start_requests(self):
        """
        Genera las URLs iniciales para scrapear.

        Crea URLs para cada zona configurada en self.zones,
        aplicando los filtros de precio configurados.

        Yields:
            scrapy.Request con metadata de Playwright
        """
        # URL base de Fotocasa para comprar viviendas de particulares en Lleida
        base_url = 'https://www.fotocasa.es/es/comprar/vivienda/lleida-capital/particulares/todas/l'

        # Construir parámetros de query según filtros
        params = {}

        if self.filters.get('filtros_precio'):
            precio_min = self.filters['filtros_precio'].get('min')
            precio_max = self.filters['filtros_precio'].get('max')

            if precio_min:
                params['minPrice'] = precio_min
            if precio_max:
                params['maxPrice'] = precio_max

        # Construir URL completa
        if params:
            url = f"{base_url}?{urlencode(params)}"
        else:
            url = base_url

        logger.info(f"Iniciando scraping de: {url}")

        # Request con Playwright
        yield scrapy.Request(
            url=url,
            callback=self.parse,
            meta={
                'playwright': True,
                'playwright_include_page': True,  # Incluir page object
                'playwright_page_methods': [
                    # Esperar a que se carguen las cards
                    {'method': 'wait_for_selector', 'args': ['.re-Card'], 'kwargs': {'timeout': 30000}},
                    # Scroll para cargar lazy loading
                    {'method': 'evaluate', 'args': ['window.scrollTo(0, document.body.scrollHeight)']},
                    {'method': 'wait_for_timeout', 'args': [2000]},  # Esperar 2 segundos
                ],
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

        logger.info(f"Parseando página: {response.url}")

        # Extraer todas las cards de listings
        # NOTA: Estos selectores son aproximados y deben ajustarse según la estructura real de Fotocasa
        listing_cards = response.css('.re-Card')

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
        next_page = response.css('a.sui-AtomButton--link[aria-label*="Siguiente"]::attr(href)').get()
        if next_page:
            logger.info(f"Siguiente página encontrada: {next_page}")
            yield response.follow(
                next_page,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        {'method': 'wait_for_selector', 'args': ['.re-Card'], 'kwargs': {'timeout': 30000}},
                    ],
                },
                errback=self.errback_close_page,
            )

    def _extract_listing_data(self, card, response: Response) -> Dict[str, Any]:
        """
        Extrae datos de un listing card.

        IMPORTANTE: Estos selectores son aproximados y deben ajustarse
        según la estructura real actual de Fotocasa.

        Args:
            card: Selector de Scrapy con la card del listing
            response: Response para construir URLs absolutas

        Returns:
            Dict con datos extraídos del listing
        """
        # Extraer título
        titulo = card.css('.re-Card-title::text').get()
        if not titulo:
            titulo = card.css('a.re-Card-link::attr(title)').get()

        # Extraer precio
        precio_text = card.css('.re-Card-price::text').get()
        precio = self._parse_price(precio_text)

        # Extraer dirección/ubicación
        direccion = card.css('.re-Card-location::text').get()

        # Extraer características (habitaciones, metros)
        habitaciones = None
        metros = None

        features = card.css('.re-Card-features span::text').getall()
        for feature in features:
            if 'hab' in feature.lower():
                habitaciones = self._parse_number(feature)
            elif 'm²' in feature.lower() or 'm2' in feature.lower():
                metros = self._parse_number(feature)

        # Extraer fotos
        fotos = card.css('.re-Card-multimedia img::attr(src)').getall()

        # Extraer URL del anuncio
        url_anuncio = card.css('a.re-Card-link::attr(href)').get()
        if url_anuncio:
            url_anuncio = response.urljoin(url_anuncio)

        # Extraer descripción (si está disponible)
        descripcion = card.css('.re-Card-description::text').get()

        # Extraer código postal de la dirección (si es posible)
        codigo_postal = self._extract_postal_code(direccion)

        # Construir diccionario de datos
        data = {
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
            'nombre': 'Fotocasa User',  # Fotocasa no muestra nombre por defecto
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

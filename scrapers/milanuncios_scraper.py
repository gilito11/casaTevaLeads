"""
Scraper de Milanuncios usando Scrapy + Playwright.

Este scraper extrae anuncios de particulares que venden viviendas en Milanuncios,
con soporte para geolocalización por coordenadas y radio de búsqueda.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode, quote

import scrapy
from scrapy.http import Response
from scrapy_playwright.page import PageMethod

from scrapers.base_scraper import BaseScraper
from scrapers.utils.particular_filter import debe_scrapear


logger = logging.getLogger(__name__)


# Configuración de zonas geográficas predefinidas
ZONAS_GEOGRAFICAS = {
    'la_bordeta': {
        'nombre': 'La Bordeta, Lleida',
        'latitude': 41.6168393,
        'longitude': 0.6204561,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lérida',
    },
    'lleida_ciudad': {
        'nombre': 'Lleida Ciudad',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lérida',
    },
    'tarragona_ciudad': {
        'nombre': 'Tarragona Ciudad',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
    },
    'salou': {
        'nombre': 'Salou',
        'latitude': 41.0747326,
        'longitude': 1.1413905,
        'geoProvinceId': 43,
        'geolocationTerm': 'Salou, Tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'latitude': 41.0670881,
        'longitude': 1.0570748,
        'geoProvinceId': 43,
        'geolocationTerm': 'Cambrils, Tarragona',
    },
    'costa_dorada': {
        'nombre': 'Costa Dorada (Salou centro)',
        'latitude': 41.0747326,
        'longitude': 1.1413905,
        'geoProvinceId': 43,
        'geolocationTerm': 'Salou, Tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'latitude': 41.1548727,
        'longitude': 1.1069153,
        'geoProvinceId': 43,
        'geolocationTerm': 'Reus, Tarragona',
    },
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

        # Rate limiting más conservador para Milanuncios
        'DOWNLOAD_DELAY': 5,  # 5 segundos entre requests
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,

        # User agent realista
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),

        # No respetar robots.txt (portales suelen bloquear scrapers)
        'ROBOTSTXT_OBEY': False,

        # Retry settings
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],

        # Playwright settings - Anti-detección
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 60000,
            'args': ['--disable-blink-features=AutomationControlled'],
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'PLAYWRIGHT_CONTEXTS': {
            'default': {
                'viewport': {'width': 1920, 'height': 1080},
                'locale': 'es-ES',
            }
        },
    }

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        minio_config: Optional[Dict[str, str]] = None,
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
            minio_config: Configuración de MinIO
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
            minio_config=minio_config,
            postgres_config=postgres_config
        )

        # Estadísticas
        self.stats = {
            'total_listings': 0,
            'filtered_out': 0,
            'saved': 0,
            'errors': 0,
            'pages_scraped': 0
        }

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

        params = {
            'vendedor': 'part',  # Solo particulares
            'latitude': zona['latitude'],
            'longitude': zona['longitude'],
            'distance': self.distance,
            'geoProvinceId': zona['geoProvinceId'],
            'geolocationTerm': zona['geolocationTerm'],
            'orden': 'date',
            'fromSearch': 1,
            'hitOrigin': 'listing',
        }

        # Añadir filtros de precio
        if self.filters.get('precio_min'):
            params['desde'] = self.filters['precio_min']
        if self.filters.get('precio_max'):
            params['hasta'] = self.filters['precio_max']

        # Añadir paginación
        if page > 1:
            params['pagina'] = page

        base_url = 'https://www.milanuncios.com/inmobiliaria/'
        return f"{base_url}?{urlencode(params, quote_via=quote)}"

    def start_requests(self):
        """
        Genera las URLs iniciales para scrapear.

        Crea URLs para cada zona configurada.

        Yields:
            scrapy.Request con metadata de Playwright
        """
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
                    'playwright_page_methods': [
                        # Anti-detección: ocultar webdriver
                        PageMethod('add_init_script', 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'),
                        # Esperar a que carguen los anuncios (selector correcto)
                        PageMethod('wait_for_selector', '[data-testid="AD_CARD"]', timeout=30000),
                        # Scroll para cargar lazy loading
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 3000),
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
        if 'Pardon Our Interruption' in response.text or 'geetest' in response.text.lower():
            logger.error(
                "BLOQUEADO: Milanuncios ha detectado el scraper como bot. "
                "Considera usar proxies residenciales o reducir la frecuencia de scraping."
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

                # Intentar extraer teléfono y nombre con Playwright
                if page and listing_data.get('detail_url'):
                    contact_info = await self._extract_phone_from_detail(page, listing_data['detail_url'])
                    if contact_info:
                        if contact_info.get('telefono'):
                            listing_data['telefono'] = contact_info['telefono']
                        if contact_info.get('nombre_vendedor'):
                            listing_data['vendedor'] = contact_info['nombre_vendedor']

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
                    portal='milanuncios'
                )

                # Guardar en PostgreSQL
                if data_lake_path:
                    success = self.base_scraper.save_to_postgres_raw(
                        listing_data,
                        data_lake_path,
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

            yield response.follow(
                next_page_link,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('add_init_script', 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'),
                        PageMethod('wait_for_selector', '[data-testid="AD_CARD"]', timeout=30000),
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

        Args:
            card: Selector de Scrapy con la card del listing
            response: Response para construir URLs absolutas
            zona_key: Key de la zona actual

        Returns:
            Dict con datos extraídos del listing
        """
        # Extraer título y URL (están en el mismo enlace)
        titulo = None
        detail_url = None

        # Selectores actualizados para Milanuncios 2024
        title_link = card.css('.ma-AdCardV2-TitleRow a, .ma-AdCardListingV2-TitleRow a')
        if title_link:
            titulo = title_link.css('::text').get()
            detail_url = title_link.css('::attr(href)').get()

        if detail_url:
            detail_url = response.urljoin(detail_url)

        # Extraer precio
        precio_text = card.css('.ma-AdPrice-value::text').get()
        if not precio_text:
            precio_text = card.css('.ma-AdCardV2-price::text').get()
        precio = self._parse_price(precio_text)

        # Extraer ubicación
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

        # Extraer imágenes (hasta 5)
        fotos = []
        foto_selectors = [
            '.ma-AdCardV2-photo img::attr(src)',
            '.ma-AdCard-photo img::attr(src)',
            'img[src*="images.milanuncios"]::attr(src)',
            'img::attr(src)',
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

        # Extraer código postal de ubicación
        codigo_postal = self._extract_postal_code(ubicacion)

        # Info de la zona
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Intentar extraer nombre del vendedor de la tarjeta
        # Milanuncios a veces muestra el nombre del usuario en la card
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
            f"  - Tasa de filtrado: {self.stats['filtered_out'] / max(self.stats['total_listings'], 1) * 100:.1f}%"
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

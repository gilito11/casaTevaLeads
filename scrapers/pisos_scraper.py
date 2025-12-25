"""
Scraper de Pisos.com usando Scrapy + Playwright.

Extrae anuncios de viviendas en venta con soporte para filtrar particulares.
"""

import logging
import os
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import scrapy
from scrapy.http import Response
from scrapy_playwright.page import PageMethod

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


# Configuración de zonas geográficas para Pisos.com
# Formato de URL: https://www.pisos.com/venta/pisos-{zona}/
ZONAS_PISOS = {
    # === LLEIDA ===
    'lleida_capital': {
        'nombre': 'Lleida Capital',
        'slug': 'lleida_capital',
        'url_path': 'pisos-lleida_capital'
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'slug': 'lleida',
        'url_path': 'pisos-lleida'
    },

    # === TARRAGONA ===
    'tarragona_capital': {
        'nombre': 'Tarragona Capital',
        'slug': 'tarragona_capital',
        'url_path': 'pisos-tarragona_capital'
    },
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'slug': 'tarragona',
        'url_path': 'pisos-tarragona'
    },

    # === COSTA DAURADA ===
    'salou': {
        'nombre': 'Salou',
        'slug': 'salou',
        'url_path': 'pisos-salou'
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'slug': 'cambrils',
        'url_path': 'pisos-cambrils'
    },
    'reus': {
        'nombre': 'Reus',
        'slug': 'reus',
        'url_path': 'pisos-reus'
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'slug': 'el_vendrell',
        'url_path': 'pisos-el_vendrell'
    },
    'calafell': {
        'nombre': 'Calafell',
        'slug': 'calafell',
        'url_path': 'pisos-calafell'
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'slug': 'torredembarra',
        'url_path': 'pisos-torredembarra'
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'slug': 'altafulla',
        'url_path': 'pisos-altafulla'
    },
    'valls': {
        'nombre': 'Valls',
        'slug': 'valls',
        'url_path': 'pisos-valls'
    },

    # === MÁS COSTA DAURADA ===
    'miami_platja': {
        'nombre': 'Miami Platja',
        'slug': 'miami_platja',
        'url_path': 'pisos-miami_platja'
    },
    'hospitalet_infant': {
        'nombre': "L'Hospitalet de l'Infant",
        'slug': 'hospitalet_de_linfant',
        'url_path': 'pisos-hospitalet_de_linfant'
    },
    'coma_ruga': {
        'nombre': 'Coma-ruga',
        'slug': 'coma_ruga',
        'url_path': 'pisos-coma_ruga'
    },
    'montblanc': {
        'nombre': 'Montblanc',
        'slug': 'montblanc',
        'url_path': 'pisos-montblanc'
    },
    'vila_seca': {
        'nombre': 'Vila-seca',
        'slug': 'vila_seca',
        'url_path': 'pisos-vila_seca'
    },

    # === TERRES DE L'EBRE ===
    'tortosa': {
        'nombre': 'Tortosa',
        'slug': 'tortosa',
        'url_path': 'pisos-tortosa'
    },
    'amposta': {
        'nombre': 'Amposta',
        'slug': 'amposta',
        'url_path': 'pisos-amposta'
    },
    'deltebre': {
        'nombre': 'Deltebre',
        'slug': 'deltebre',
        'url_path': 'pisos-deltebre'
    },
    'ametlla_mar': {
        'nombre': "L'Ametlla de Mar",
        'slug': 'ametlla_de_mar',
        'url_path': 'pisos-ametlla_de_mar'
    },
    'sant_carles_rapita': {
        'nombre': 'Sant Carles de la Ràpita',
        'slug': 'sant_carles_de_la_rapita',
        'url_path': 'pisos-sant_carles_de_la_rapita'
    },

    # === MÁS LLEIDA ===
    'balaguer': {
        'nombre': 'Balaguer',
        'slug': 'balaguer',
        'url_path': 'pisos-balaguer'
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'slug': 'mollerussa',
        'url_path': 'pisos-mollerussa'
    },
    'tremp': {
        'nombre': 'Tremp',
        'slug': 'tremp',
        'url_path': 'pisos-tremp'
    },
    'tarrega': {
        'nombre': 'Tàrrega',
        'slug': 'tarrega',
        'url_path': 'pisos-tarrega'
    },

    # === BARCELONA (para testing) ===
    'barcelona_capital': {
        'nombre': 'Barcelona Capital',
        'slug': 'barcelona_capital',
        'url_path': 'pisos-barcelona_702'
    },
}


class PisosScraper(scrapy.Spider):
    """
    Spider de Scrapy para scrapear Pisos.com con Playwright.
    """

    name = 'pisos'
    allowed_domains = ['pisos.com', 'www.pisos.com']

    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ],
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'COOKIES_ENABLED': True,
        'RETRY_TIMES': 3,
        'LOG_LEVEL': 'INFO',
    }

    def __init__(
        self,
        tenant_id: int = 1,
        zones: List[str] = None,
        filters: Dict[str, Any] = None,
        minio_config: Dict[str, str] = None,
        postgres_config: Dict[str, str] = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.tenant_id = tenant_id
        self.zones = zones or ['tarragona_capital']
        self.filters = filters or {}
        self.minio_config = minio_config
        self.postgres_config = postgres_config

        # Contadores
        self.items_scraped = 0
        self.items_saved = 0
        self.items_skipped_inmobiliaria = 0
        self.items_skipped_inmobiliaria_detail = 0  # Filtrados en página de detalle
        self.pages_scraped = 0
        self.detail_pages_checked = 0

        # Base scraper para guardar datos
        if minio_config or postgres_config:
            self.base_scraper = BaseScraper(
                tenant_id=tenant_id,
                portal='pisos',
                minio_config=minio_config,
                postgres_config=postgres_config
            )
        else:
            self.base_scraper = None

        logger.info(f"PisosScraper inicializado - Tenant: {tenant_id}, Zonas: {zones}")

    def start_requests(self):
        """Genera las requests iniciales para cada zona configurada."""
        for zona_key in self.zones:
            if zona_key not in ZONAS_PISOS:
                logger.warning(f"Zona desconocida: {zona_key}")
                continue

            zona = ZONAS_PISOS[zona_key]
            url = f"https://www.pisos.com/venta/{zona['url_path']}/"

            # Añadir filtros de precio si existen
            params = []
            if self.filters.get('precio_min'):
                params.append(f"precio_min={self.filters['precio_min']}")
            if self.filters.get('precio_max'):
                params.append(f"precio_max={self.filters['precio_max']}")

            if params:
                url += '?' + '&'.join(params)

            logger.info(f"Iniciando scraping de zona '{zona['nombre']}': {url}")

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                    'zona_key': zona_key,
                    'zona_nombre': zona['nombre'],
                    'current_page': 1,
                },
                errback=self.errback,
                dont_filter=True
            )

    async def parse(self, response: Response):
        """Parsea la página de resultados de Pisos.com usando Playwright."""
        page = response.meta.get('playwright_page')
        zona_key = response.meta.get('zona_key')
        zona_nombre = response.meta.get('zona_nombre')
        current_page = response.meta.get('current_page', 1)

        self.pages_scraped += 1
        logger.info(f"Parseando página {current_page} de zona {zona_key}: {response.url}")

        try:
            if not page:
                logger.error("No se obtuvo el objeto page de Playwright")
                return

            # Esperar a que carguen los anuncios
            await page.wait_for_selector('div.ad-preview', timeout=10000)

            # Obtener tarjetas usando Playwright directamente (no response.css)
            cards = await page.query_selector_all('div.ad-preview')
            logger.info(f"Encontradas {len(cards)} tarjetas con Playwright")

            if not cards:
                logger.warning(f"No se encontraron anuncios en {response.url}")

            # Procesar cada tarjeta
            for card in cards:
                try:
                    listing_data = await self._extract_listing_data_playwright(card, zona_key, zona_nombre)

                    if listing_data and listing_data.get('titulo'):
                        self.items_scraped += 1

                        # Filtrar inmobiliarias obvias desde la tarjeta
                        if not listing_data.get('es_particular', True):
                            vendedor = listing_data.get('vendedor', 'Desconocido')
                            logger.debug(f"Saltando inmobiliaria (tarjeta): {vendedor} - {listing_data.get('titulo', '')[:40]}")
                            self.items_skipped_inmobiliaria += 1
                            continue

                        # Verificación final: visitar página de detalle para confirmar
                        # Esto también extrae el teléfono si está disponible
                        # Usamos una nueva página para no perder el contexto del listado
                        if listing_data.get('url_anuncio'):
                            self.detail_pages_checked += 1
                            browser_context = page.context
                            detail_page = await browser_context.new_page()

                            try:
                                detail_result = await self._verify_particular_on_detail_page(
                                    detail_page,
                                    listing_data['url_anuncio'],
                                    listing_data.get('anuncio_id', 'unknown')
                                )

                                if detail_result:
                                    if not detail_result.get('es_particular', True):
                                        vendedor = detail_result.get('vendedor', 'Inmobiliaria')
                                        logger.info(f"Saltando inmobiliaria (detalle): {vendedor} - {listing_data.get('titulo', '')[:40]}")
                                        self.items_skipped_inmobiliaria_detail += 1
                                        await detail_page.close()
                                        continue

                                    # Actualizar datos con info del detalle
                                    if detail_result.get('telefono'):
                                        listing_data['telefono'] = detail_result['telefono']
                                    if detail_result.get('vendedor') and detail_result['vendedor'] != 'Particular':
                                        listing_data['vendedor'] = detail_result['vendedor']

                            finally:
                                await detail_page.close()

                        # Guardar en base de datos
                        if self.base_scraper:
                            saved = self.base_scraper.save_listing(listing_data)
                            if saved:
                                self.items_saved += 1
                                logger.info(f"Guardado: {listing_data.get('titulo', 'Sin título')[:50]}")

                        yield listing_data

                except Exception as e:
                    logger.error(f"Error procesando tarjeta: {e}")
                    continue

            # Buscar paginación
            next_page_url = None

            # Buscar enlace "Siguiente"
            next_selectors = [
                'a.pager__next',
                'a[rel="next"]',
                'a.pagination__next',
            ]

            for selector in next_selectors:
                next_link = await page.query_selector(selector)
                if next_link:
                    href = await next_link.get_attribute('href')
                    if href:
                        next_page_url = response.urljoin(href)
                        break

            # También buscar por número de página
            if not next_page_url:
                next_page_num = current_page + 1
                page_link = await page.query_selector(f'a[href*="/{next_page_num}/"]')
                if page_link:
                    href = await page_link.get_attribute('href')
                    if href:
                        next_page_url = response.urljoin(href)

            if next_page_url and current_page < 10:  # Limitar a 10 páginas por zona
                logger.info(f"Siguiente página encontrada: {next_page_url}")

                yield scrapy.Request(
                    url=next_page_url,
                    callback=self.parse,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                            PageMethod('wait_for_timeout', 2000),
                        ],
                        'zona_key': zona_key,
                        'zona_nombre': zona_nombre,
                        'current_page': current_page + 1,
                    },
                    errback=self.errback,
                    dont_filter=True
                )
            else:
                logger.info(f"Fin de paginación para zona {zona_key}")

        except Exception as e:
            logger.error(f"Error en parse: {e}")
        finally:
            if page:
                await page.close()

    async def _extract_listing_data_playwright(
        self,
        card,
        zona_key: str,
        zona_nombre: str
    ) -> Optional[Dict[str, Any]]:
        """Extrae datos de una tarjeta usando Playwright."""

        try:
            # URL y título del anuncio
            title_link = await card.query_selector('.ad-preview__title')
            url_anuncio = None
            titulo = None

            if title_link:
                href = await title_link.get_attribute('href')
                if href:
                    url_anuncio = f"https://www.pisos.com{href}" if href.startswith('/') else href
                titulo = await title_link.inner_text()
                if titulo:
                    titulo = titulo.strip()

            # ID del anuncio desde la URL
            anuncio_id = None
            if url_anuncio:
                match = re.search(r'-(\d+)(?:_\d+)?/?$', url_anuncio)
                if match:
                    anuncio_id = match.group(1)
                else:
                    # Intentar extraer de otra forma
                    match = re.search(r'/(\d+)/?$', url_anuncio)
                    if match:
                        anuncio_id = match.group(1)

            # Precio
            precio = None
            price_elem = await card.query_selector('.ad-preview__price')
            if price_elem:
                precio_text = await price_elem.inner_text()
                if precio_text:
                    precio_clean = re.sub(r'[^\d]', '', precio_text)
                    if precio_clean:
                        precio = float(precio_clean)

            # Ubicación
            ubicacion = None
            location_elem = await card.query_selector('.ad-preview__subtitle')
            if location_elem:
                ubicacion = await location_elem.inner_text()
                if ubicacion:
                    ubicacion = ubicacion.strip()

            # Características (metros, habitaciones, baños)
            metros = None
            habitaciones = None
            banos = None

            char_elems = await card.query_selector_all('.ad-preview__char')
            for char_elem in char_elems:
                feat = await char_elem.inner_text()
                if feat:
                    feat = feat.strip().lower()

                    # Metros cuadrados
                    if 'm²' in feat or 'm2' in feat:
                        match = re.search(r'(\d+(?:[.,]\d+)?)', feat)
                        if match:
                            metros = float(match.group(1).replace(',', '.'))

                    # Habitaciones
                    if 'hab' in feat or 'dorm' in feat:
                        match = re.search(r'(\d+)', feat)
                        if match:
                            habitaciones = int(match.group(1))

                    # Baños
                    if 'baño' in feat or 'wc' in feat:
                        match = re.search(r'(\d+)', feat)
                        if match:
                            banos = int(match.group(1))

            # Fotos (hasta 5)
            fotos = []
            img_elems = await card.query_selector_all('img[src*="imghs.net"]')
            for img in img_elems[:5]:
                src = await img.get_attribute('src')
                if src and src.startswith('http'):
                    fotos.append(src)

            # Si no encontramos fotos, buscar en data-src
            if not fotos:
                img_elems = await card.query_selector_all('img[data-src*="imghs.net"]')
                for img in img_elems[:5]:
                    src = await img.get_attribute('data-src')
                    if src and src.startswith('http'):
                        fotos.append(src)

            # Detectar si es inmobiliaria o particular
            # Múltiples métodos de detección para mayor fiabilidad
            es_particular = None  # None = no determinado aún
            vendedor = 'Particular'

            # Método 1: Buscar "particular" o "profesional" en el HTML de la tarjeta
            # Esto es más fiable que buscar elementos específicos
            try:
                card_html = await card.inner_html()
                if 'venta-particular' in card_html.lower():
                    es_particular = True
                    vendedor = 'Particular'
                elif 'venta-profesional' in card_html.lower():
                    es_particular = False
                    vendedor = 'Profesional'
            except Exception as e:
                logger.debug(f"Error obteniendo HTML de tarjeta: {e}")

            # Método 2: Buscar enlace a /inmobiliaria-{nombre}/
            if es_particular is None or es_particular:
                logo_elem = await card.query_selector('[data-lnk-href*="inmobiliaria"]')
                if logo_elem:
                    es_particular = False
                    logo_href = await logo_elem.get_attribute('data-lnk-href')
                    if logo_href:
                        match = re.search(r'/inmobiliaria-([^/]+)/', logo_href)
                        if match:
                            vendedor = match.group(1).replace('_', ' ').title()
                        else:
                            vendedor = 'Inmobiliaria'

            # Método 3: Verificar si hay logo de agencia (imagen en .ad-preview__logo con 'prof' en URL)
            if es_particular is None or es_particular:
                logo_img = await card.query_selector('.ad-preview__logo img[src*="prof"], .ad-preview__logo img[data-src*="prof"]')
                if logo_img:
                    es_particular = False
                    if vendedor == 'Particular':
                        vendedor = 'Profesional'

            # Default: si no pudimos determinar, asumir particular
            if es_particular is None:
                es_particular = True

            # Log para debug
            logger.debug(f"Anuncio {anuncio_id}: es_particular={es_particular}, vendedor={vendedor}")

            # Si es profesional, intentar extraer nombre de la inmobiliaria
            if not es_particular and vendedor in ['Profesional', 'Inmobiliaria']:
                logo_elem = await card.query_selector('.ad-preview__logo span[data-lnk-href]')
                if logo_elem:
                    logo_href = await logo_elem.get_attribute('data-lnk-href')
                    if logo_href and '/inmobiliaria' in logo_href.lower():
                        match = re.search(r'/inmobiliaria-([^/]+)/', logo_href)
                        if match:
                            vendedor = match.group(1).replace('_', ' ').title()

            return {
                'tenant_id': self.tenant_id,
                'portal': 'pisos',
                'anuncio_id': anuncio_id,
                'titulo': titulo,
                'descripcion': titulo or '',
                'precio': precio,
                'ubicacion': ubicacion,
                'direccion': ubicacion,
                'zona_busqueda': zona_nombre,
                'zona_geografica': zona_nombre,
                'habitaciones': habitaciones,
                'banos': banos,
                'metros': metros,
                'fotos': fotos,
                'vendedor': vendedor,
                'es_particular': es_particular,
                'url_anuncio': url_anuncio,
                'detail_url': url_anuncio,
                'telefono': None,
            }

        except Exception as e:
            logger.error(f"Error extrayendo datos: {e}")
            return None

    async def _verify_particular_on_detail_page(
        self,
        page,
        url: str,
        anuncio_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Visita la página de detalle para verificar si es particular o inmobiliaria.
        Revisa la sección "Contacta con el Anunciante" para detectar logos/nombres de agencias.
        También extrae el teléfono si está disponible.

        Returns:
            Dict con 'es_particular', 'vendedor', 'telefono' o None si hay error
        """
        try:
            logger.debug(f"Verificando detalle de anuncio {anuncio_id}: {url}")

            # Navegar a la página de detalle
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(1500)

            result = {
                'es_particular': True,
                'vendedor': 'Particular',
                'telefono': None
            }

            # === DETECTAR INMOBILIARIA EN "CONTACTA CON EL ANUNCIANTE" ===

            # Buscar el contenedor de contacto del anunciante
            contact_selectors = [
                '.contact-box',
                '.advertiser-box',
                '.owner-info',
                '[class*="contact"]',
                '[class*="advertiser"]',
                '.ad-detail__contact',
                '.detail-contact',
            ]

            contact_section = None
            for selector in contact_selectors:
                contact_section = await page.query_selector(selector)
                if contact_section:
                    break

            if contact_section:
                # Método 1: Buscar logo de inmobiliaria (imagen con link a /inmobiliaria-)
                agency_logo = await contact_section.query_selector('a[href*="/inmobiliaria-"] img')
                if agency_logo:
                    result['es_particular'] = False
                    # Extraer nombre de la inmobiliaria del link
                    parent_link = await contact_section.query_selector('a[href*="/inmobiliaria-"]')
                    if parent_link:
                        href = await parent_link.get_attribute('href')
                        if href:
                            match = re.search(r'/inmobiliaria-([^/]+)/?', href)
                            if match:
                                result['vendedor'] = match.group(1).replace('_', ' ').replace('-', ' ').title()
                    logger.debug(f"Detectada inmobiliaria por logo: {result['vendedor']}")

                # Método 2: Buscar link directo a inmobiliaria
                if result['es_particular']:
                    agency_link = await contact_section.query_selector('a[href*="/inmobiliaria-"]')
                    if agency_link:
                        result['es_particular'] = False
                        href = await agency_link.get_attribute('href')
                        if href:
                            match = re.search(r'/inmobiliaria-([^/]+)/?', href)
                            if match:
                                result['vendedor'] = match.group(1).replace('_', ' ').replace('-', ' ').title()
                        else:
                            agency_text = await agency_link.inner_text()
                            if agency_text:
                                result['vendedor'] = agency_text.strip()
                        logger.debug(f"Detectada inmobiliaria por link: {result['vendedor']}")

                # Método 3: Buscar texto que indique profesional/inmobiliaria
                if result['es_particular']:
                    section_html = await contact_section.inner_html()
                    section_html_lower = section_html.lower()

                    agency_keywords = [
                        'inmobiliaria', 'agencia', 'real estate', 'profesional',
                        'promotora', 'gestora', 'consulting', 'properties',
                        'fincas', 'inmuebles', 'inversiones'
                    ]

                    for keyword in agency_keywords:
                        if keyword in section_html_lower:
                            result['es_particular'] = False
                            result['vendedor'] = 'Profesional'
                            logger.debug(f"Detectada inmobiliaria por keyword '{keyword}'")
                            break

            # === BÚSQUEDA ADICIONAL FUERA DEL CONTENEDOR DE CONTACTO ===

            # Buscar en toda la página por logo/link de inmobiliaria
            if result['es_particular']:
                page_agency_link = await page.query_selector('.ad-detail a[href*="/inmobiliaria-"]')
                if page_agency_link:
                    result['es_particular'] = False
                    href = await page_agency_link.get_attribute('href')
                    if href:
                        match = re.search(r'/inmobiliaria-([^/]+)/?', href)
                        if match:
                            result['vendedor'] = match.group(1).replace('_', ' ').replace('-', ' ').title()
                    logger.debug(f"Detectada inmobiliaria en página: {result['vendedor']}")

            # === EXTRAER TELÉFONO ===

            phone_selectors = [
                'a[href^="tel:"]',
                '.phone-number',
                '[class*="phone"]',
                '[class*="telefono"]',
                'a[data-phone]',
            ]

            for selector in phone_selectors:
                phone_elem = await page.query_selector(selector)
                if phone_elem:
                    # Intentar obtener del href tel:
                    href = await phone_elem.get_attribute('href')
                    if href and href.startswith('tel:'):
                        phone = href.replace('tel:', '').strip()
                        if phone and len(phone) >= 9:
                            result['telefono'] = phone
                            break

                    # Intentar obtener del texto
                    phone_text = await phone_elem.inner_text()
                    if phone_text:
                        phone_clean = re.sub(r'[^\d+]', '', phone_text)
                        if phone_clean and len(phone_clean) >= 9:
                            result['telefono'] = phone_clean
                            break

            # Intentar hacer clic en "Ver teléfono" si existe
            if not result['telefono']:
                show_phone_btn = await page.query_selector('button[class*="phone"], a[class*="show-phone"], [data-action="show-phone"]')
                if show_phone_btn:
                    try:
                        await show_phone_btn.click()
                        await page.wait_for_timeout(1000)

                        # Buscar teléfono de nuevo después del clic
                        for selector in phone_selectors:
                            phone_elem = await page.query_selector(selector)
                            if phone_elem:
                                href = await phone_elem.get_attribute('href')
                                if href and href.startswith('tel:'):
                                    result['telefono'] = href.replace('tel:', '').strip()
                                    break
                    except Exception as e:
                        logger.debug(f"No se pudo hacer clic en mostrar teléfono: {e}")

            logger.debug(f"Resultado verificación {anuncio_id}: particular={result['es_particular']}, "
                        f"vendedor={result['vendedor']}, tel={result['telefono']}")

            return result

        except Exception as e:
            logger.warning(f"Error verificando detalle de {anuncio_id}: {e}")
            # En caso de error, devolver None para no filtrar el lead
            return None

    def _extract_listing_data(
        self,
        card,
        response: Response,
        zona_key: str,
        zona_nombre: str
    ) -> Optional[Dict[str, Any]]:
        """Extrae datos de una tarjeta de anuncio (método legacy, no usado)."""

        # URL del anuncio
        url_selectors = [
            'a.ad-preview__title::attr(href)',
            'a[class*="title"]::attr(href)',
            'a::attr(href)',
        ]
        url_anuncio = None
        for selector in url_selectors:
            url_anuncio = card.css(selector).get()
            if url_anuncio and '/comprar/' in url_anuncio:
                url_anuncio = response.urljoin(url_anuncio)
                break

        # ID del anuncio desde la URL
        anuncio_id = None
        if url_anuncio:
            match = re.search(r'/(\d+)/?$', url_anuncio)
            if match:
                anuncio_id = match.group(1)

        # Título
        titulo_selectors = [
            '.ad-preview__title::text',
            'a[class*="title"]::text',
            'h2::text',
            'h3::text',
            '.title::text',
        ]
        titulo = None
        for selector in titulo_selectors:
            titulo = card.css(selector).get()
            if titulo:
                titulo = titulo.strip()
                break

        # Precio
        precio_selectors = [
            '.ad-preview__price::text',
            '.price::text',
            '[class*="price"]::text',
            '.ad-preview__price span::text',
        ]
        precio = None
        for selector in precio_selectors:
            precio_text = card.css(selector).get()
            if precio_text:
                # Extraer solo números
                precio_clean = re.sub(r'[^\d]', '', precio_text)
                if precio_clean:
                    precio = float(precio_clean)
                    break

        # Ubicación
        ubicacion_selectors = [
            '.ad-preview__subtitle::text',
            '.location::text',
            '[class*="location"]::text',
            '.ad-preview__location::text',
        ]
        ubicacion = None
        for selector in ubicacion_selectors:
            ubicacion = card.css(selector).get()
            if ubicacion:
                ubicacion = ubicacion.strip()
                break

        # Características (metros, habitaciones, baños)
        metros = None
        habitaciones = None
        banos = None

        features_selectors = [
            '.ad-preview__char::text',
            '.ad-preview__info span::text',
            '[class*="feature"]::text',
            '.characteristics span::text',
        ]

        for selector in features_selectors:
            features = card.css(selector).getall()
            for feat in features:
                feat = feat.strip().lower()

                # Metros cuadrados
                if 'm²' in feat or 'm2' in feat:
                    match = re.search(r'(\d+(?:[.,]\d+)?)', feat)
                    if match:
                        metros = float(match.group(1).replace(',', '.'))

                # Habitaciones
                if 'hab' in feat or 'dorm' in feat:
                    match = re.search(r'(\d+)', feat)
                    if match:
                        habitaciones = int(match.group(1))

                # Baños
                if 'baño' in feat or 'wc' in feat:
                    match = re.search(r'(\d+)', feat)
                    if match:
                        banos = int(match.group(1))

        # Foto principal
        foto_selectors = [
            '.ad-preview__img img::attr(src)',
            '.ad-preview__image img::attr(src)',
            'img::attr(src)',
            'img::attr(data-src)',
        ]
        fotos = []
        for selector in foto_selectors:
            foto = card.css(selector).get()
            if foto and foto.startswith('http'):
                fotos.append(foto)
                break

        # Tipo de vendedor (particular o inmobiliaria)
        vendedor_selectors = [
            '.ad-preview__agency::text',
            '.agency::text',
            '[class*="agency"]::text',
            '.advertiser::text',
        ]
        vendedor = 'Particular'  # Por defecto
        for selector in vendedor_selectors:
            vendedor_text = card.css(selector).get()
            if vendedor_text:
                vendedor = vendedor_text.strip()
                break

        # Determinar si es particular
        es_particular = True
        if vendedor and any(x in vendedor.lower() for x in ['inmobiliaria', 'agencia', 'inmo', 'real estate']):
            es_particular = False

        # Descripción (puede no estar en el listado)
        descripcion = titulo or ''

        return {
            'tenant_id': self.tenant_id,
            'portal': 'pisos',
            'anuncio_id': anuncio_id,
            'titulo': titulo,
            'descripcion': descripcion,
            'precio': precio,
            'ubicacion': ubicacion,
            'direccion': ubicacion,
            'zona_busqueda': zona_nombre,
            'zona_geografica': zona_nombre,
            'habitaciones': habitaciones,
            'banos': banos,
            'metros': metros,
            'fotos': fotos,
            'vendedor': vendedor,
            'es_particular': es_particular,
            'url_anuncio': url_anuncio,
            'detail_url': url_anuncio,
            'telefono': None,  # Se extrae en página de detalle
        }

    def errback(self, failure):
        """Maneja errores en las requests."""
        logger.error(f"Error en request: {failure.request.url} - {failure.value}")

    def closed(self, reason):
        """Se ejecuta cuando el spider termina."""
        logger.info(f"Spider cerrado: {reason}")
        logger.info(f"=== ESTADÍSTICAS PISOS.COM ===")
        logger.info(f"  Páginas de listado: {self.pages_scraped}")
        logger.info(f"  Anuncios encontrados: {self.items_scraped}")
        logger.info(f"  Inmobiliarias filtradas (tarjeta): {self.items_skipped_inmobiliaria}")
        logger.info(f"  Páginas de detalle verificadas: {self.detail_pages_checked}")
        logger.info(f"  Inmobiliarias filtradas (detalle): {self.items_skipped_inmobiliaria_detail}")
        logger.info(f"  Leads guardados: {self.items_saved}")
        total_filtered = self.items_skipped_inmobiliaria + self.items_skipped_inmobiliaria_detail
        logger.info(f"  Total inmobiliarias filtradas: {total_filtered}")

        if self.base_scraper:
            self.base_scraper.close()

"""
Scraper de Wallapop Inmobiliaria usando Scrapy + Playwright.

Este scraper extrae anuncios de compraventa de inmuebles en Wallapop,
con sistema de blacklist para detectar inmobiliarias encubiertas.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Set
from urllib.parse import urlencode, quote

import scrapy
from scrapy.http import Response
from scrapy_playwright.page import PageMethod

from scrapers.base_scraper import BaseScraper


logger = logging.getLogger(__name__)


# Usuarios conocidos como inmobiliarias encubiertas (blacklist inicial)
USUARIOS_BLACKLIST_INICIAL = {
    'Yaencontre ..',
    'yaencontre',
    # Añadir más según se detecten
}

# Configuración de zonas geográficas para Wallapop
ZONAS_WALLAPOP = {
    'barcelona': {
        'nombre': 'Barcelona',
        'latitude': 41.3873974,
        'longitude': 2.168568,
    },
    'madrid': {
        'nombre': 'Madrid',
        'latitude': 40.4167754,
        'longitude': -3.7037902,
    },
    'valencia': {
        'nombre': 'Valencia',
        'latitude': 39.4699075,
        'longitude': -0.3762881,
    },
    'lleida': {
        'nombre': 'Lleida',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
    },
    'tarragona': {
        'nombre': 'Tarragona',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
    },
    'salou': {
        'nombre': 'Salou',
        'latitude': 41.0747326,
        'longitude': 1.1413905,
    },
}


class WallapopScraper(scrapy.Spider):
    """
    Spider de Scrapy para scrapear Wallapop Inmobiliaria con Playwright.

    Incluye sistema de blacklist para filtrar inmobiliarias encubiertas.
    Un usuario que aparece en 5+ anuncios se marca automáticamente.
    """

    name = 'wallapop'

    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',

        # Rate limiting conservador
        'DOWNLOAD_DELAY': 5,
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,

        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),

        'ROBOTSTXT_OBEY': False,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],

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

    # Contador de anuncios por usuario para detección automática
    usuario_contador: Dict[str, int] = {}
    usuarios_blacklist: Set[str] = set()
    UMBRAL_BLACKLIST = 5

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        minio_config: Optional[Dict[str, str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        distance_km: int = 30,
        usuarios_blacklist_extra: Optional[List[str]] = None,
        *args,
        **kwargs
    ):
        """
        Inicializa el spider de Wallapop.

        Args:
            tenant_id: ID del tenant
            zones: Lista de zonas a scrapear (keys de ZONAS_WALLAPOP)
            filters: Filtros de búsqueda (precio_min)
            distance_km: Radio de búsqueda en km (default: 30)
            usuarios_blacklist_extra: Usuarios adicionales a bloquear
        """
        super().__init__(*args, **kwargs)

        self.tenant_id = tenant_id
        self.zones = zones or ['barcelona']
        self.filters = filters or {}
        self.distance_km = distance_km

        # Inicializar blacklist: usuarios conocidos + extras + desde BD (per-tenant)
        self.usuarios_blacklist = USUARIOS_BLACKLIST_INICIAL.copy()
        if usuarios_blacklist_extra:
            self.usuarios_blacklist.update(usuarios_blacklist_extra)

        # Cargar blacklist desde BD para este tenant
        self._cargar_blacklist_desde_bd()

        # Inicializar BaseScraper
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
            'filtered_blacklist': 0,
            'filtered_price': 0,
            'saved': 0,
            'errors': 0,
            'usuarios_detectados': 0,
        }

        logger.info(
            f"WallapopScraper inicializado para tenant_id={tenant_id}, "
            f"zonas={self.zones}, distance={distance_km}km, "
            f"blacklist inicial: {len(self.usuarios_blacklist)} usuarios"
        )

    def _build_url(self, zona_key: str) -> str:
        """Construye la URL de búsqueda para Wallapop."""
        zona = ZONAS_WALLAPOP.get(zona_key)
        if not zona:
            raise ValueError(f"Zona no encontrada: {zona_key}")

        params = {
            'category_id': 200,  # Inmobiliaria
            'operation': 'buy',  # Comprar (no alquilar)
            'latitude': zona['latitude'],
            'longitude': zona['longitude'],
            'distance_in_km': self.distance_km,
            'order_by': 'newest',  # Más recientes primero
        }

        # Filtro de precio mínimo
        if self.filters.get('precio_min'):
            params['min_sale_price'] = self.filters['precio_min']

        return f"https://es.wallapop.com/search?{urlencode(params)}"

    async def _extract_items_with_playwright(self, page) -> List[Dict[str, Any]]:
        """Extrae items directamente desde la página de Playwright."""
        items = []

        try:
            # Esperar para que cargue el contenido dinámico
            await page.wait_for_timeout(3000)

            # Hacer scroll para cargar contenido lazy
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(2000)
            await page.evaluate('window.scrollTo(0, 0)')
            await page.wait_for_timeout(1000)

            # Buscar todos los items de la lista
            item_elements = await page.query_selector_all('a[href*="/item/"]')

            for element in item_elements:
                try:
                    href = await element.get_attribute('href')
                    title = await element.get_attribute('title')

                    if not href or '/item/' not in href:
                        continue

                    # Extraer precio del elemento padre o hermanos
                    parent = await element.evaluate_handle('el => el.closest("div")')
                    precio_text = None
                    if parent:
                        # Buscar elemento de precio cercano
                        price_el = await page.evaluate('''
                            (href) => {
                                const link = document.querySelector(`a[href="${href}"]`);
                                if (!link) return null;
                                const card = link.closest('div[class*="ItemCard"]') || link.parentElement.parentElement;
                                if (!card) return null;
                                const priceEl = card.querySelector('[class*="price" i], [class*="Price" i]');
                                return priceEl ? priceEl.textContent : null;
                            }
                        ''', href)
                        precio_text = price_el

                    items.append({
                        'href': href,
                        'titulo': title,
                        'precio_text': precio_text,
                    })

                except Exception as e:
                    logger.debug(f"Error extrayendo item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extrayendo items con Playwright: {e}")

        return items

    def _extract_items_from_response(self, response: Response) -> List[Dict[str, Any]]:
        """Fallback: extrae items del response de Scrapy (menos fiable para SPA)."""
        items = []

        for link in response.css('a[href*="/item/"]'):
            href = link.css('::attr(href)').get()
            title = link.css('::attr(title)').get()

            if href and '/item/' in href:
                items.append({
                    'href': href,
                    'titulo': title,
                    'precio_text': None,
                })

        return items

    def _process_item_data(self, item_data: Dict[str, Any], zona_key: str) -> Optional[Dict[str, Any]]:
        """Procesa los datos extraídos de un item."""
        href = item_data.get('href')
        titulo = item_data.get('titulo')
        precio_text = item_data.get('precio_text')

        if not href:
            return None

        # Construir URL completa
        if href.startswith('/'):
            detail_url = f"https://es.wallapop.com{href}"
        else:
            detail_url = href

        # Extraer ID del item de la URL
        item_id = None
        match = re.search(r'-(\d+)$', href)
        if match:
            item_id = match.group(1)

        # Parsear precio
        precio = self._parse_price(precio_text)

        # Extraer ubicación del título si es posible
        ubicacion = None
        if titulo:
            match = re.search(r' en (.+)$', titulo)
            if match:
                ubicacion = match.group(1)

        # Tipo de inmueble del título
        tipo_propiedad = self._detectar_tipo_inmueble(titulo or href)

        zona_info = ZONAS_WALLAPOP.get(zona_key, {})

        return {
            'item_id': item_id,
            'titulo': titulo,
            'precio': precio,
            'ubicacion': ubicacion,
            'tipo_propiedad': tipo_propiedad,
            'detail_url': detail_url,
            'url_anuncio': detail_url,
            'portal': 'wallapop',
            'zona_busqueda': zona_info.get('nombre', zona_key),
            'nombre_usuario': None,
            'user_id': None,
            'telefono': None,
            'descripcion': None,
        }

    def start_requests(self):
        """Genera las URLs iniciales para scrapear."""
        for zona_key in self.zones:
            url = self._build_url(zona_key)
            zona_nombre = ZONAS_WALLAPOP.get(zona_key, {}).get('nombre', zona_key)

            logger.info(f"Iniciando scraping de zona '{zona_nombre}': {url}")

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('add_init_script', 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'),
                        # Esperar más tiempo para que cargue el contenido dinámico
                        PageMethod('wait_for_timeout', 5000),
                        # Scroll para cargar más contenido
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 3000),
                        # Scroll de nuevo
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight / 2)'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                    'zona_key': zona_key,
                },
                errback=self.errback_close_page,
            )

    async def parse(self, response: Response):
        """Parsea la página de resultados de Wallapop."""
        page = response.meta.get('playwright_page')
        zona_key = response.meta.get('zona_key')

        logger.info(f"Parseando zona {zona_key}: {response.url}")

        # Usar Playwright directamente para extraer los items (HTML dinámico)
        if page:
            items_data = await self._extract_items_with_playwright(page)
            logger.info(f"Encontrados {len(items_data)} items con Playwright")
        else:
            logger.warning("No hay playwright_page en response.meta - usando fallback")
            items_data = self._extract_items_from_response(response)
            logger.info(f"Encontrados {len(items_data)} items con Scrapy")

        for item_data in items_data:
            self.stats['total_listings'] += 1

            try:
                listing_data = self._process_item_data(item_data, zona_key)

                if not listing_data:
                    continue

                # Si tiene URL de detalle, obtener más info
                if page and listing_data.get('detail_url'):
                    detail_data = await self._extract_from_detail_page(page, listing_data['detail_url'])
                    if detail_data:
                        listing_data.update(detail_data)

                # Verificar blacklist por nombre de usuario
                usuario = listing_data.get('nombre_usuario', '')
                if self._esta_en_blacklist(usuario):
                    self.stats['filtered_blacklist'] += 1
                    logger.debug(f"Usuario en blacklist: {usuario}")
                    continue

                # Actualizar contador de usuario
                if usuario:
                    self._incrementar_contador_usuario(usuario, listing_data.get('detail_url', ''))

                # Verificar precio mínimo
                precio_min = self.filters.get('precio_min', 5000)
                if listing_data.get('precio') and listing_data['precio'] < precio_min:
                    self.stats['filtered_price'] += 1
                    continue

                # Normalizar teléfono si existe
                if listing_data.get('telefono'):
                    listing_data['telefono_norm'] = self.base_scraper.normalize_phone(
                        listing_data['telefono']
                    )

                # Guardar en data lake
                data_lake_path = self.base_scraper.save_to_data_lake(
                    listing_data,
                    portal='wallapop'
                )

                if data_lake_path:
                    success = self.base_scraper.save_to_postgres_raw(
                        listing_data,
                        data_lake_path,
                        portal='wallapop'
                    )

                    if success:
                        self.stats['saved'] += 1

                yield listing_data

            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"Error procesando item: {e}", exc_info=True)

        if page:
            await page.close()

        # Log estadísticas
        logger.info(
            f"Estadísticas: Total={self.stats['total_listings']}, "
            f"Blacklist={self.stats['filtered_blacklist']}, "
            f"Precio={self.stats['filtered_price']}, "
            f"Guardados={self.stats['saved']}"
        )

    async def _extract_from_detail_page(self, page, detail_url: str) -> Optional[Dict[str, Any]]:
        """Navega a la página de detalle para extraer más información."""
        try:
            new_page = await page.context.new_page()
            await new_page.goto(detail_url, wait_until='domcontentloaded', timeout=30000)
            await new_page.wait_for_timeout(2000)

            data = {}

            # Extraer nombre del usuario/vendedor
            html = await new_page.content()

            # Buscar user_id en el HTML
            user_id_match = re.search(r'user[_-]?id["\']?[:=]["\']?([a-z0-9-]+)', html, re.I)
            if user_id_match:
                data['user_id'] = user_id_match.group(1)

            # Buscar nombre de usuario
            # El patrón típico es el nombre del usuario antes del título
            user_name_match = re.search(r'"sellerName"\s*:\s*"([^"]+)"', html)
            if user_name_match:
                data['nombre_usuario'] = user_name_match.group(1)
            else:
                # Intentar otro patrón
                user_el = await new_page.query_selector('[class*="user" i] span, [class*="seller" i] span')
                if user_el:
                    name = await user_el.text_content()
                    if name:
                        data['nombre_usuario'] = name.strip()

            # Buscar descripción
            desc_el = await new_page.query_selector('[class*="description" i], [class*="Description" i]')
            if desc_el:
                desc = await desc_el.text_content()
                if desc:
                    data['descripcion'] = desc.strip()[:1000]

            # Buscar características (m2, habitaciones)
            features_text = await new_page.text_content('body')
            if features_text:
                # Buscar metros cuadrados
                m2_match = re.search(r'(\d+)\s*m[²2]', features_text)
                if m2_match:
                    data['metros'] = int(m2_match.group(1))

                # Buscar habitaciones
                hab_match = re.search(r'(\d+)\s*(?:hab|dormitorio|habitacion)', features_text, re.I)
                if hab_match:
                    data['habitaciones'] = int(hab_match.group(1))

            await new_page.close()
            return data

        except Exception as e:
            logger.debug(f"Error extrayendo detalle de {detail_url}: {e}")
            return None

    def _esta_en_blacklist(self, nombre_usuario: str) -> bool:
        """Verifica si un usuario está en la blacklist."""
        if not nombre_usuario:
            return False

        nombre_lower = nombre_usuario.lower().strip()

        for blacklisted in self.usuarios_blacklist:
            if blacklisted.lower() in nombre_lower or nombre_lower in blacklisted.lower():
                return True

        return False

    def _cargar_blacklist_desde_bd(self):
        """Carga usuarios en blacklist desde la BD para este tenant."""
        try:
            import django
            django.setup()
            from backend.apps.core.models import UsuarioBlacklist

            # Cargar blacklist global (tenant=None) y específica del tenant
            blacklisted = UsuarioBlacklist.objects.filter(
                portal='wallapop',
                activo=True
            ).filter(
                # Global OR tenant-specific
                tenant__isnull=True
            ) | UsuarioBlacklist.objects.filter(
                portal='wallapop',
                activo=True,
                tenant_id=self.tenant_id
            )

            for usuario in blacklisted:
                self.usuarios_blacklist.add(usuario.nombre_usuario)

            logger.info(f"Cargados {blacklisted.count()} usuarios en blacklist desde BD")

        except Exception as e:
            logger.debug(f"No se pudo cargar blacklist desde BD: {e}")

    def _guardar_usuario_blacklist_bd(self, nombre_usuario: str, user_id: str = '', num_anuncios: int = 0):
        """Guarda un usuario detectado en la blacklist de la BD (per-tenant)."""
        try:
            import django
            django.setup()
            from backend.apps.core.models import UsuarioBlacklist, Tenant

            tenant = Tenant.objects.filter(tenant_id=self.tenant_id).first()

            UsuarioBlacklist.objects.get_or_create(
                portal='wallapop',
                usuario_id=user_id or nombre_usuario.lower(),
                tenant=tenant,  # Per-tenant blacklist
                defaults={
                    'nombre_usuario': nombre_usuario,
                    'motivo': 'automatico',
                    'num_anuncios_detectados': num_anuncios,
                    'notas': f'Detectado automáticamente con {num_anuncios} anuncios (tenant {self.tenant_id})',
                }
            )
            logger.info(f"Usuario {nombre_usuario} guardado en blacklist BD para tenant {self.tenant_id}")

        except Exception as e:
            logger.debug(f"No se pudo guardar en BD: {e}")

    def _incrementar_contador_usuario(self, nombre_usuario: str, url: str = ''):
        """Incrementa el contador y añade a blacklist si supera umbral."""
        if not nombre_usuario:
            return

        nombre_key = nombre_usuario.lower().strip()

        if nombre_key not in self.usuario_contador:
            self.usuario_contador[nombre_key] = 0

        self.usuario_contador[nombre_key] += 1

        if self.usuario_contador[nombre_key] >= self.UMBRAL_BLACKLIST:
            if nombre_usuario not in self.usuarios_blacklist:
                self.usuarios_blacklist.add(nombre_usuario)
                self.stats['usuarios_detectados'] += 1
                logger.warning(
                    f"Usuario añadido a blacklist automáticamente: {nombre_usuario} "
                    f"({self.usuario_contador[nombre_key]} anuncios)"
                )
                # Guardar en BD per-tenant
                self._guardar_usuario_blacklist_bd(
                    nombre_usuario,
                    num_anuncios=self.usuario_contador[nombre_key]
                )

    def _detectar_tipo_inmueble(self, texto: str) -> str:
        """Detecta el tipo de inmueble del texto."""
        texto_lower = texto.lower()

        if 'piso' in texto_lower:
            return 'Piso'
        elif 'casa' in texto_lower or 'chalet' in texto_lower:
            return 'Casa'
        elif 'local' in texto_lower:
            return 'Local'
        elif 'garaje' in texto_lower or 'parking' in texto_lower:
            return 'Garaje'
        elif 'terreno' in texto_lower or 'parcela' in texto_lower:
            return 'Terreno'
        elif 'nave' in texto_lower:
            return 'Nave'
        elif 'oficina' in texto_lower:
            return 'Oficina'
        else:
            return 'Otros'

    def _parse_price(self, price_text: Optional[str]) -> Optional[float]:
        """Parsea texto de precio a float."""
        if not price_text:
            return None

        try:
            cleaned = re.sub(r'[€$\s.]', '', price_text)
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    async def errback_close_page(self, failure):
        """Callback de error que cierra la página."""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        logger.error(f"Error en request: {failure.request.url} - {failure.value}")

    def closed(self, reason):
        """Se llama cuando el spider termina."""
        logger.info(
            f"Spider cerrado. Razón: {reason}\n"
            f"Estadísticas finales:\n"
            f"  - Total items procesados: {self.stats['total_listings']}\n"
            f"  - Filtrados por blacklist: {self.stats['filtered_blacklist']}\n"
            f"  - Filtrados por precio: {self.stats['filtered_price']}\n"
            f"  - Guardados: {self.stats['saved']}\n"
            f"  - Errores: {self.stats['errors']}\n"
            f"  - Usuarios detectados como inmobiliarias: {self.stats['usuarios_detectados']}\n"
            f"  - Total usuarios en blacklist: {len(self.usuarios_blacklist)}"
        )

        if hasattr(self, 'base_scraper'):
            self.base_scraper.close()


if __name__ == '__main__':
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    process = CrawlerProcess(get_project_settings())
    process.crawl(
        WallapopScraper,
        zones=['barcelona'],
        filters={'precio_min': 5000},
        distance_km=30
    )
    process.start()

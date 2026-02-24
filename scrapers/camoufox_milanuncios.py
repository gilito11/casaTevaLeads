"""
Milanuncios scraper using Camoufox anti-detect browser.

Bypasses GeeTest captcha through C++ level fingerprint injection.
Replaces the ScrapingBee version - completely FREE.

Cost: $0 (no API credits needed)
"""

import json
import logging
import os
import random
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import psycopg2

from scrapers.watermark_detector import has_watermark
from scrapers.camoufox_idealista import parse_proxy

logger = logging.getLogger(__name__)


ZONAS_GEOGRAFICAS = {
    # LLEIDA
    'lleida': {
        'nombre': 'Lleida',
        'url_path': 'pisos-en-lleida-lleida/',
    },
    'lleida_ciudad': {
        'nombre': 'Lleida Ciudad',
        'url_path': 'pisos-en-lleida-lleida/',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_path': 'pisos-en-balaguer-lleida/',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'url_path': 'pisos-en-mollerussa-lleida/',
    },
    'les_borges_blanques': {
        'nombre': 'Les Borges Blanques',
        'url_path': 'pisos-en-les-borges-blanques-lleida/',
    },
    'tremp': {
        'nombre': 'Tremp',
        'url_path': 'pisos-en-tremp-lleida/',
    },
    'tarrega': {
        'nombre': 'Tàrrega',
        'url_path': 'pisos-en-tarrega-lleida/',
    },
    'alpicat': {
        'nombre': 'Alpicat',
        'url_path': 'pisos-en-alpicat-lleida/',
    },
    'alcarras': {
        'nombre': 'Alcarràs',
        'url_path': 'pisos-en-alcarras-lleida/',
    },
    'torrefarrera': {
        'nombre': 'Torrefarrera',
        'url_path': 'pisos-en-torrefarrera-lleida/',
    },
    # TARRAGONA
    'tarragona': {
        'nombre': 'Tarragona',
        'url_path': 'pisos-en-tarragona-tarragona/',
    },
    'tarragona_ciudad': {
        'nombre': 'Tarragona Ciudad',
        'url_path': 'pisos-en-tarragona-tarragona/',
    },
    # COSTA DAURADA
    'salou': {
        'nombre': 'Salou',
        'url_path': 'pisos-en-salou-tarragona/',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'pisos-en-cambrils-tarragona/',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'pisos-en-reus-tarragona/',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_path': 'pisos-en-el-vendrell-tarragona/',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'url_path': 'pisos-en-altafulla-tarragona/',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'pisos-en-torredembarra-tarragona/',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'pisos-en-calafell-tarragona/',
    },
    'la_pineda': {
        'nombre': 'La Pineda',
        'url_path': 'pisos-en-la-pineda-tarragona/',
    },
    'miami_platja': {
        'nombre': 'Miami Platja',
        'url_path': 'pisos-en-miami-platja-tarragona/',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'pisos-en-valls-tarragona/',
    },
    'montblanc': {
        'nombre': 'Montblanc',
        'url_path': 'pisos-en-montblanc-tarragona/',
    },
    'vila_seca': {
        'nombre': 'Vila-seca',
        'url_path': 'pisos-en-vila-seca-tarragona/',
    },
    # TERRES DE L'EBRE
    'tortosa': {
        'nombre': 'Tortosa',
        'url_path': 'pisos-en-tortosa-tarragona/',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_path': 'pisos-en-amposta-tarragona/',
    },
    'deltebre': {
        'nombre': 'Deltebre',
        'url_path': 'pisos-en-deltebre-tarragona/',
    },
    # Madrid Districts (Tenant 2: Look and Find)
    'chamartin': {
        'nombre': 'Chamartín',
        'url_path': 'venta-de-pisos-en-chamartin-madrid-madrid/',
    },
    'hortaleza': {
        'nombre': 'Hortaleza',
        'url_path': 'venta-de-pisos-en-hortaleza-madrid-madrid/',
    },
}


def get_postgres_config() -> Dict[str, Any]:
    """Get PostgreSQL configuration from DATABASE_URL or NEON_DATABASE_URL."""
    database_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL', '')

    if database_url:
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/').split('?')[0],
            'user': parsed.username,
            'password': parsed.password,
            'sslmode': 'require',
        }

    return {
        'host': os.environ.get('POSTGRES_HOST', 'localhost'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
        'database': os.environ.get('POSTGRES_DB', 'casa_teva_db'),
        'user': os.environ.get('POSTGRES_USER', 'casa_teva'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'casateva2024'),
    }


def extract_phone_from_description(description: str) -> Optional[str]:
    """Extract Spanish phone number from listing description."""
    if not description:
        return None

    clean_desc = description.replace(' ', '').replace('.', '').replace('-', '').replace('/', '')
    phones = re.findall(r'[679]\d{8}', clean_desc)

    BLACKLIST = {
        '666666666', '777777777', '999999999',
        '600000000', '700000000', '900000000',
        '123456789', '987654321',
    }

    for phone in phones:
        if phone not in BLACKLIST and len(set(phone)) > 2:
            return phone

    return None


class CamoufoxMilanuncios:
    """
    Milanuncios scraper using Camoufox anti-detect browser.
    Bypasses GeeTest captcha for free.
    """

    BASE_URL = "https://www.milanuncios.com"
    PORTAL_NAME = "milanuncios"

    def __init__(
        self,
        zones: List[str] = None,
        tenant_id: int = 1,
        max_pages_per_zone: int = 3,
        only_particulares: bool = True,
        headless: bool = True,
        filter_watermarks: bool = True,
        proxy: str = None,
    ):
        self.zones = zones or ['salou']
        self.tenant_id = tenant_id
        self.max_pages_per_zone = max_pages_per_zone
        self.only_particulares = only_particulares
        self.headless = headless
        self.filter_watermarks = filter_watermarks
        self.proxy = proxy or os.environ.get('DATADOME_PROXY')

        self.postgres_conn = None
        self._scraped_listings = []
        self.stats = {
            'pages_scraped': 0,
            'listings_found': 0,
            'listings_saved': 0,
            'listings_skipped_watermark': 0,
            'errors': 0,
        }

    def _init_postgres(self):
        """Initialize PostgreSQL connection."""
        config = get_postgres_config()
        conn_params = {
            'host': config['host'],
            'port': config['port'],
            'database': config['database'],
            'user': config['user'],
            'password': config['password'],
        }
        if config.get('sslmode'):
            conn_params['sslmode'] = config['sslmode']

        self.postgres_conn = psycopg2.connect(**conn_params)
        logger.info(f"PostgreSQL connected: {config['host']}")

    def normalize_phone(self, phone_str: str) -> Optional[str]:
        """Normalize Spanish phone to 9 digits."""
        if not phone_str:
            return None

        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone_str)

        if cleaned.startswith('+34'):
            cleaned = cleaned[3:]
        elif cleaned.startswith('0034'):
            cleaned = cleaned[4:]
        elif cleaned.startswith('34') and len(cleaned) == 11:
            cleaned = cleaned[2:]

        digits = re.sub(r'\D', '', cleaned)

        if len(digits) == 9 and digits[0] in '679':
            return digits
        return None

    def _human_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        env_min = float(os.environ.get('SCRAPER_MIN_DELAY', '0'))
        min_sec = max(min_sec, env_min)
        max_sec = max(max_sec, min_sec)
        time.sleep(random.uniform(min_sec, max_sec))

    def _warmup_navigation(self, page):
        """Visit homepage first to build trust."""
        logger.info("Warming up: visiting homepage...")

        page.goto(self.BASE_URL, wait_until='domcontentloaded')
        self._human_delay(4, 7)

        for _ in range(random.randint(2, 4)):
            page.mouse.wheel(0, random.randint(150, 400))
            self._human_delay(1.5, 3)

        # Accept cookies
        try:
            accept_btn = page.query_selector('button[id*="accept"], button:has-text("Aceptar")')
            if accept_btn:
                accept_btn.click()
                self._human_delay(2, 4)
        except:
            pass

        logger.info("Warmup complete")

    def build_search_url(self, zona_key: str, page_num: int = 1) -> str:
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        # Milanuncios no longer supports ?vendedor=particular (redirects/strips it)
        # Particular filtering is done via DOM/JSON instead
        url = f"{self.BASE_URL}/{zona['url_path']}"

        if page_num > 1:
            # Milanuncios uses /pagina-N/ in the URL path, not query params
            url = url.rstrip('/') + f'?pagina={page_num}'

        return url

    def _extract_listings_from_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listings from search page. Try JSON first, then DOM fallback."""
        listings = []

        # Method 1: Extract from __INITIAL_PROPS__ JSON
        try:
            json_data = page.evaluate("""
                () => {
                    if (window.__INITIAL_PROPS__) return window.__INITIAL_PROPS__;
                    if (window.__NEXT_DATA__) return window.__NEXT_DATA__.props;
                    const scripts = document.querySelectorAll('script');
                    for (const script of scripts) {
                        const text = script.textContent || '';
                        if (text.includes('__INITIAL_PROPS__')) {
                            try {
                                const match = text.match(/window\\.__INITIAL_PROPS__\\s*=\\s*JSON\\.parse\\("(.+?)"\\)/);
                                if (match) {
                                    return JSON.parse(match[1].replace(/\\\\"/g, '"').replace(/\\\\\\\\/g, '\\\\'));
                                }
                            } catch (e) {}
                        }
                    }
                    return null;
                }
            """)

            if json_data:
                listings, json_had_ads = self._parse_json_listings(json_data, zona_key)
                if listings:
                    logger.info(f"Extracted {len(listings)} listings from JSON")
                    return listings
                if json_had_ads:
                    # JSON found ads but all filtered as professional/low price - trust it
                    logger.info("JSON found ads but all filtered (professional/low price) - skipping DOM fallback")
                    return []

        except Exception as e:
            logger.warning(f"JSON extraction failed: {e}")

        # Method 2: DOM fallback (only when JSON extraction completely failed)
        selectors = [
            'article[data-testid="ad-card"]',
            'article[class*="AdCard"]',
            'div[class*="AdCard"]',
            'article.ma-AdCard',
            '.ma-AdCardV2',
            '[data-testid="listing"]',
            'article[data-ad-id]',
        ]

        items = []
        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=5000)
                items = page.query_selector_all(selector)
                if items:
                    logger.info(f"Found {len(items)} cards via DOM ({selector})")
                    break
            except:
                continue

        if not items:
            logger.warning("No listing cards found via JSON or DOM")
            return []

        for item in items:
            try:
                listing = self._parse_listing_card(item, zona_key)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Error parsing card: {e}")

        return listings

    def _parse_json_listings(self, json_data: Dict, zona_key: str) -> tuple:
        """Parse listings from Milanuncios JSON structure.
        Returns (listings, json_had_ads) tuple."""
        listings = []

        ads = None
        if isinstance(json_data, dict):
            # Primary path: adListPagination.adList.ads
            if 'adListPagination' in json_data:
                pagination = json_data['adListPagination']
                if isinstance(pagination, dict) and 'adList' in pagination:
                    ad_list = pagination['adList']
                    if isinstance(ad_list, dict) and 'ads' in ad_list:
                        ads = ad_list['ads']

            # Fallbacks
            if not ads and 'ads' in json_data:
                ads = json_data['ads']
            if not ads and 'pageProps' in json_data and 'ads' in json_data.get('pageProps', {}):
                ads = json_data['pageProps']['ads']

        if not ads:
            logger.warning(f"No ads found in JSON. Keys: {list(json_data.keys()) if isinstance(json_data, dict) else type(json_data)}")
            return [], False

        logger.info(f"Found {len(ads)} ads in JSON")
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
        skipped_pro = 0
        skipped_price = 0

        for ad in ads:
            try:
                # Check seller type from multiple fields
                # sellerType can be string OR object {"value": "professional", "isPrivate": false}
                raw_seller_type = ad.get('sellerType', '')
                is_private = None
                if isinstance(raw_seller_type, dict):
                    seller_type = str(raw_seller_type.get('value', '')).lower()
                    is_private = raw_seller_type.get('isPrivate')
                else:
                    seller_type = str(raw_seller_type).lower()
                seller_badge = str(ad.get('sellerBadge', '')).lower()
                user_type = str(ad.get('userType', '')).lower()
                has_shop = bool(ad.get('shop'))

                is_professional = (
                    seller_type in ('professional', 'profesional')
                    or is_private is False
                    or has_shop
                    or 'pro' in seller_badge
                    or user_type in ('professional', 'profesional')
                )

                if self.only_particulares and is_professional:
                    skipped_pro += 1
                    continue

                anuncio_id = str(ad.get('id', ''))
                if not anuncio_id:
                    continue

                # Price
                precio = None
                price_data = ad.get('price', {})
                if isinstance(price_data, dict):
                    cash_price = price_data.get('cashPrice', {})
                    if isinstance(cash_price, dict):
                        precio = cash_price.get('value')
                    elif 'value' in price_data:
                        precio = price_data.get('value')
                elif isinstance(price_data, (int, float)):
                    precio = price_data

                # Skip listings under 10000€
                if precio is not None and precio < 10000:
                    skipped_price += 1
                    continue

                # URL
                url_path = ad.get('url', '')
                url_anuncio = f"{self.BASE_URL}{url_path}" if url_path.startswith('/') else url_path

                # Location
                ubicacion = ''
                if 'city' in ad and isinstance(ad['city'], dict):
                    ubicacion = ad['city'].get('name', '')
                elif 'location' in ad:
                    ubicacion = ad.get('location', '')

                # Images - handle both old and new domain
                fotos = []
                if 'images' in ad and ad['images']:
                    for img in ad['images'][:10]:
                        if isinstance(img, dict):
                            img_url = img.get('url', '') or img.get('src', '')
                        else:
                            img_url = str(img)
                        if img_url:
                            img_url = self._fix_image_url(img_url)
                            fotos.append(img_url)

                listing = {
                    'anuncio_id': anuncio_id,
                    'titulo': ad.get('title', ''),
                    'precio': precio,
                    'descripcion': (ad.get('description', '') or '')[:2000],
                    'ubicacion': ubicacion,
                    'zona_geografica': zona_info.get('nombre', zona_key),
                    'zona_busqueda': zona_key,
                    'url_anuncio': url_anuncio,
                    'es_particular': not is_professional,
                    'seller_type': seller_type or ('professional' if is_professional else ''),
                    'tipo_inmueble': 'piso',
                    'fotos': fotos,
                }

                listings.append(listing)

            except Exception as e:
                logger.debug(f"Error parsing JSON ad: {e}")

        logger.info(f"JSON filter: {len(listings)} kept, {skipped_pro} professional, {skipped_price} low price (of {len(ads)} total)")
        return listings, True

    def _parse_listing_card(self, item, zona_key: str) -> Optional[Dict[str, Any]]:
        """Parse a single listing card from DOM (fallback)."""
        try:
            # Detect professional seller from card HTML
            is_professional = False
            try:
                card_html = item.inner_html().lower()
                card_text = item.inner_text().lower()
                pro_indicators = [
                    'profesional', 'professional', 'inmobiliaria',
                    'adtag--pro', 'seller-type="pro', 'sellerbadge',
                ]
                for indicator in pro_indicators:
                    if indicator in card_html or indicator in card_text:
                        is_professional = True
                        break
            except:
                pass

            # Also check CSS selectors
            if not is_professional:
                pro_selectors = [
                    '[class*="professional"]', '[class*="Professional"]',
                    '.ma-AdTag--pro', '[data-seller-type="professional"]',
                    '[class*="ProBadge"]', '[class*="SellerBadge"]',
                ]
                for sel in pro_selectors:
                    try:
                        if item.query_selector(sel):
                            is_professional = True
                            break
                    except:
                        continue

            if is_professional and self.only_particulares:
                logger.debug("Skipping professional listing (DOM)")
                return None

            # Get link
            link = None
            for sel in ['a[href*=".htm"]', 'a[data-testid="ad-link"]', 'a[class*="Link"]', 'a']:
                try:
                    link = item.query_selector(sel)
                    if link:
                        break
                except:
                    continue

            if not link:
                return None

            href = link.get_attribute('href')
            if not href:
                return None

            # Extract ID
            anuncio_id = None
            for pattern in [r'-(\d{6,})\.htm', r'/(\d{6,})\.htm', r'-(\d{6,})$', r'(\d{6,})']:
                match = re.search(pattern, href)
                if match:
                    anuncio_id = match.group(1)
                    break

            if not anuncio_id:
                anuncio_id = item.get_attribute('data-ad-id') or item.get_attribute('data-id')
            if not anuncio_id:
                return None

            # Title
            titulo = ''
            for sel in ['h2', 'h3', '[class*="title"]', '[class*="Title"]']:
                try:
                    elem = item.query_selector(sel)
                    if elem:
                        titulo = elem.inner_text().strip()
                        if titulo:
                            break
                except:
                    continue

            # Price
            precio = None
            for sel in ['[class*="price"]', '[class*="Price"]', '[data-testid="ad-price"]']:
                try:
                    elem = item.query_selector(sel)
                    if elem:
                        precio = self._parse_price(elem.inner_text())
                        if precio:
                            break
                except:
                    continue

            # Skip listings under 10000€
            if precio is not None and precio < 10000:
                logger.debug(f"Skipping low price ({precio}€): {anuncio_id}")
                return None

            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            return {
                'anuncio_id': anuncio_id,
                'titulo': titulo,
                'precio': precio,
                'descripcion': '',
                'ubicacion': '',
                'zona_geografica': zona_info.get('nombre', zona_key),
                'zona_busqueda': zona_key,
                'url_anuncio': f"{self.BASE_URL}{href}" if href.startswith('/') else href,
                'es_particular': not is_professional,
                'seller_type': 'professional' if is_professional else '',
                'tipo_inmueble': 'piso',
                'fotos': [],
            }

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        if not price_text:
            return None
        try:
            cleaned = re.sub(r'[€$\s\xa0.]', '', price_text)
            cleaned = cleaned.replace(',', '.')
            match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

    def _fix_image_url(self, url: str) -> str:
        """Fix image URL: ensure https:// prefix and handle domain changes."""
        if not url:
            return url
        # Add protocol if missing
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = 'https://' + url
        # Handle both old and new image domains
        # images.milanuncios.com -> images-re.milanuncios.com (new)
        # Both domains work, just normalize
        return url

    def _scrape_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Visit detail page to get phone, description, photos, and verify seller type."""
        url = listing.get('url_anuncio')
        if not url:
            return listing

        try:
            page.goto(url, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            self._human_delay(2, 4)

            page.mouse.wheel(0, random.randint(200, 400))
            self._human_delay(1, 2)

            # Verify seller type from detail page JSON first (most reliable)
            try:
                seller_info = page.evaluate("""
                    () => {
                        try {
                            let ad = null;
                            if (window.__INITIAL_PROPS__) {
                                const p = window.__INITIAL_PROPS__;
                                ad = p.adDetail || p.ad || p;
                            }
                            if (!ad && window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                                const pp = window.__NEXT_DATA__.props.pageProps;
                                ad = pp && (pp.ad || pp.adDetail);
                            }
                            if (ad) {
                                return {
                                    sellerType: ad.sellerType || ad.seller_type || '',
                                    userType: ad.userType || ad.user_type || '',
                                    sellerBadge: ad.sellerBadge || ad.seller_badge || '',
                                    sellerName: (ad.seller && ad.seller.name) || ad.sellerName || ad.advertiserName || '',
                                    isPro: ad.isProfessional || ad.is_professional || false,
                                    hasShop: !!(ad.shop),
                                    shopName: (ad.shop && ad.shop.name) || '',
                                };
                            }
                        } catch(e) {}
                        return null;
                    }
                """)
                if seller_info:
                    # sellerType can be string OR object {"value": "professional", "isPrivate": false}
                    raw_st = seller_info.get('sellerType', '')
                    is_private_detail = None
                    if isinstance(raw_st, dict):
                        st = str(raw_st.get('value', '')).lower()
                        is_private_detail = raw_st.get('isPrivate')
                    else:
                        st = str(raw_st).lower()
                    ut = str(seller_info.get('userType', '')).lower()
                    sb = str(seller_info.get('sellerBadge', '')).lower()
                    sn = seller_info.get('sellerName', '')
                    is_pro_json = seller_info.get('isPro', False)
                    has_shop = seller_info.get('hasShop', False)
                    shop_name = seller_info.get('shopName', '')

                    if (st in ('professional', 'profesional')
                            or is_private_detail is False
                            or has_shop
                            or ut in ('professional', 'profesional')
                            or 'pro' in sb
                            or is_pro_json):
                        listing['es_particular'] = False
                        listing['seller_type'] = 'professional'
                        listing['vendedor'] = shop_name or sn or listing.get('vendedor', '')
                        logger.info(f"Detail JSON: professional (type={st}, isPrivate={is_private_detail}, shop={has_shop}, name={shop_name or sn}) - {listing.get('anuncio_id')}")
                    elif sn:
                        listing['vendedor'] = sn
                        if not listing.get('seller_type') and st:
                            listing['seller_type'] = st
            except:
                pass

            # Verify seller type from DOM - look for visible "Profesional" badge
            try:
                # Direct check: the "Profesional" badge text visible on the page
                pro_badge = page.evaluate("""
                    () => {
                        const all = document.querySelectorAll('*');
                        for (const el of all) {
                            if (el.children.length === 0 || el.tagName === 'SPAN' || el.tagName === 'P') {
                                const txt = (el.textContent || '').trim();
                                if (txt === 'Profesional' || txt === 'Professional') {
                                    return txt;
                                }
                            }
                        }
                        return null;
                    }
                """)
                if pro_badge:
                    listing['es_particular'] = False
                    listing['seller_type'] = 'professional'
                    logger.info(f"Detail DOM: '{pro_badge}' badge found - {listing.get('anuncio_id')}")

                # Also try to get seller name from DOM if not yet set
                if not listing.get('vendedor'):
                    seller_selectors = [
                        '[class*="SellerBadge"]', '[class*="seller-badge"]',
                        '[class*="Seller"]', '[class*="seller"]',
                        '[class*="advertiser"]', '[class*="Advertiser"]',
                        '[data-testid*="seller"]', '[data-testid*="Seller"]',
                    ]
                    for sel in seller_selectors:
                        try:
                            elem = page.query_selector(sel)
                            if elem:
                                seller_text = elem.inner_text().strip()
                                if seller_text and len(seller_text) < 100:
                                    listing['vendedor'] = seller_text
                                    break
                        except:
                            continue
            except:
                pass

            # Final check: regex scan page HTML for sellerType in any JSON blob
            if listing.get('es_particular', True):
                try:
                    content = page.content()
                    seller_match = re.search(r'"sellerType"\s*:\s*"(professional)"', content, re.IGNORECASE)
                    if seller_match:
                        listing['es_particular'] = False
                        listing['seller_type'] = 'professional'
                        logger.info(f"Detail regex: professional found in HTML - {listing.get('anuncio_id')}")
                except:
                    pass

            # Try to get phone via button click
            try:
                phone_btn = page.query_selector(
                    'button[class*="phone"], [data-testid*="phone"], .ma-ContactButtons-phone'
                )
                if phone_btn:
                    phone_btn.click()
                    self._human_delay(1, 2)

                    phone_elem = page.query_selector(
                        '[class*="phone-number"], [class*="PhoneNumber"], a[href^="tel:"]'
                    )
                    if phone_elem:
                        phone_text = phone_elem.inner_text() or phone_elem.get_attribute('href') or ''
                        phone_text = phone_text.replace('tel:', '')
                        normalized = self.normalize_phone(phone_text)
                        if normalized:
                            listing['telefono'] = phone_text
                            listing['telefono_norm'] = normalized
                            logger.info(f"Phone from button: {normalized}")
            except Exception as e:
                logger.debug(f"Could not get phone from button: {e}")

            # Get full description
            try:
                # Method 1: Extract from __INITIAL_PROPS__ or __NEXT_DATA__ JSON on detail page
                detail_json = page.evaluate("""
                    () => {
                        try {
                            if (window.__INITIAL_PROPS__) {
                                const p = window.__INITIAL_PROPS__;
                                if (p.adDetail && p.adDetail.description) return p.adDetail.description;
                                if (p.ad && p.ad.description) return p.ad.description;
                                if (p.description) return p.description;
                            }
                            if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                                const pp = window.__NEXT_DATA__.props.pageProps;
                                if (pp && pp.ad && pp.ad.description) return pp.ad.description;
                                if (pp && pp.adDetail && pp.adDetail.description) return pp.adDetail.description;
                            }
                        } catch(e) {}
                        return null;
                    }
                """)
                if detail_json and len(str(detail_json)) > len(listing.get('descripcion', '')):
                    listing['descripcion'] = str(detail_json)[:2000]

                # Method 2: DOM selectors
                if not listing.get('descripcion') or len(listing.get('descripcion', '')) < 20:
                    desc_selectors = [
                        '[data-testid="AD_DESCRIPTION"]',
                        '[class*="AdDescription"]',
                        '[class*="adDescription"]',
                        '[class*="Description__container"]',
                        '[class*="description-content"]',
                        '.ma-AdDetail-description',
                        'section[class*="description"] p',
                        '[class*="Description"] p',
                        '[class*="description"]:not(meta)',
                    ]
                    for desc_sel in desc_selectors:
                        try:
                            desc_elem = page.query_selector(desc_sel)
                            if desc_elem:
                                full_desc = desc_elem.inner_text().strip()
                                if full_desc and len(full_desc) > len(listing.get('descripcion', '')):
                                    listing['descripcion'] = full_desc[:2000]
                                    break
                        except:
                            continue

                # Method 3: Regex fallback on raw HTML
                if not listing.get('descripcion') or len(listing.get('descripcion', '')) < 20:
                    try:
                        content = page.content()
                        desc_match = re.search(
                            r'"description"\s*:\s*"([^"]{20,})"',
                            content
                        )
                        if desc_match:
                            desc_text = desc_match.group(1).replace('\\n', '\n').replace('\\"', '"')
                            listing['descripcion'] = desc_text[:2000]
                    except:
                        pass

                if not listing.get('descripcion'):
                    logger.debug(f"No description found for {url}")
            except:
                pass

            # Extract phone from description if not found via button
            if not listing.get('telefono_norm'):
                phone = extract_phone_from_description(listing.get('descripcion', ''))
                if phone:
                    listing['telefono'] = phone
                    listing['telefono_norm'] = phone
                    logger.info(f"Phone from description: {phone}")

            # Extract photos from detail page if not already present
            if not listing.get('fotos'):
                try:
                    content = page.content()
                    # Match both old and new image domains
                    photo_ids = set(re.findall(
                        r'https?://images(?:-re)?\.milanuncios\.com/api/v1/ma-ad-media-pro/images/([a-f0-9-]{36})',
                        content, re.IGNORECASE
                    ))
                    listing['fotos'] = [
                        f"https://images-re.milanuncios.com/api/v1/ma-ad-media-pro/images/{pid}?rule=detail_640x480"
                        for pid in list(photo_ids)[:10]
                    ]
                except:
                    pass

            return listing

        except Exception as e:
            logger.warning(f"Error on detail page: {e}")
            return listing

    def save_to_postgres(self, listing: Dict[str, Any]) -> bool:
        """Save listing to PostgreSQL with ON CONFLICT dedup."""
        if not self.postgres_conn:
            return False

        try:
            cursor = self.postgres_conn.cursor()

            anuncio_id = str(listing.get('anuncio_id', ''))
            if not anuncio_id:
                return False

            raw_data = {
                'anuncio_id': anuncio_id,
                'titulo': listing.get('titulo', ''),
                'telefono': listing.get('telefono', ''),
                'telefono_norm': listing.get('telefono_norm', ''),
                'direccion': listing.get('ubicacion', ''),
                'zona': listing.get('zona_geografica', ''),
                'zona_busqueda': listing.get('zona_busqueda', ''),
                'zona_geografica': listing.get('zona_geografica', ''),
                'tipo_inmueble': listing.get('tipo_inmueble', 'piso'),
                'precio': listing.get('precio'),
                'descripcion': listing.get('descripcion', ''),
                'fotos': listing.get('fotos', []),
                'url': listing.get('url_anuncio', ''),
                'es_particular': listing.get('es_particular', True),
                'vendedor': listing.get('vendedor', ''),
                'seller_type': listing.get('seller_type', ''),
                'scraper_type': 'camoufox',
            }

            sql = """
                INSERT INTO raw.raw_listings (
                    tenant_id, portal, data_lake_path, raw_data, scraping_timestamp
                ) VALUES (
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
                WHERE raw_data->>'anuncio_id' IS NOT NULL
                DO UPDATE SET
                    raw_data = EXCLUDED.raw_data,
                    scraping_timestamp = EXCLUDED.scraping_timestamp
            """

            now = datetime.now()
            data_lake_path = f"camoufox/{self.PORTAL_NAME}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"

            cursor.execute(sql, (
                self.tenant_id,
                self.PORTAL_NAME,
                data_lake_path,
                json.dumps(raw_data),
                now,
            ))

            rows_affected = cursor.rowcount
            self.postgres_conn.commit()

            # Track price history for price drop detection
            precio = listing.get('precio')
            if precio and anuncio_id:
                try:
                    cursor2 = self.postgres_conn.cursor()
                    cursor2.execute("""
                        INSERT INTO raw.listing_price_history (tenant_id, portal, anuncio_id, precio)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (tenant_id, portal, anuncio_id, precio) DO NOTHING
                    """, (self.tenant_id, self.PORTAL_NAME, anuncio_id, precio))
                    self.postgres_conn.commit()
                    cursor2.close()
                except Exception as e:
                    logger.debug(f"Price history insert skipped: {e}")

            cursor.close()

            if rows_affected > 0:
                logger.info(f"Saved: {self.PORTAL_NAME} - {anuncio_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error saving: {e}")
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def scrape(self) -> Dict[str, Any]:
        """Main scraping method."""
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            logger.error("Camoufox not installed. Run: pip install camoufox && camoufox fetch")
            raise

        self._init_postgres()

        # Build Camoufox options
        camoufox_opts = {
            "humanize": 2.5,
            "headless": self.headless,
            "geoip": True,
            "os": "windows",
            "block_webrtc": True,
            "locale": ["es-ES", "es"],
        }

        # Add proxy if configured (needed for datacenter IPs like GitHub Actions)
        proxy_config = parse_proxy(self.proxy)
        if proxy_config:
            camoufox_opts["proxy"] = proxy_config
            logger.info(f"Using proxy: {proxy_config['server']}")
        else:
            logger.warning("No proxy configured - may be blocked from datacenter IPs")

        logger.info(f"Starting Camoufox Milanuncios scraper")
        logger.info(f"  Zones: {self.zones}")
        logger.info(f"  Max pages: {self.max_pages_per_zone}")
        logger.info(f"  Headless: {self.headless}")
        logger.info(f"  Proxy: {'configured' if proxy_config else 'none'}")

        try:
            with Camoufox(**camoufox_opts) as browser:
                page = browser.new_page()

                self._warmup_navigation(page)

                for zona_key in self.zones:
                    zona_info = ZONAS_GEOGRAFICAS.get(zona_key)
                    if not zona_info:
                        logger.warning(f"Zone not found: {zona_key}")
                        continue

                    logger.info(f"Scraping zone: {zona_info['nombre']}")
                    seen_ad_ids = set()

                    for page_num in range(1, self.max_pages_per_zone + 1):
                        try:
                            url = self.build_search_url(zona_key, page_num)
                            logger.info(f"Page {page_num}: {url}")

                            page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            self._human_delay(3, 5)

                            # Wait for React to hydrate
                            try:
                                page.wait_for_load_state('networkidle', timeout=15000)
                            except:
                                logger.debug("networkidle timeout, continuing...")

                            # Scroll to load lazy content
                            for _ in range(3):
                                page.mouse.wheel(0, random.randint(300, 600))
                                self._human_delay(0.5, 1)

                            # Extra wait for React re-render after scroll
                            self._human_delay(2, 3)

                            self.stats['pages_scraped'] += 1

                            # Log actual URL (detect redirects)
                            current_url = page.url
                            if current_url != url:
                                logger.warning(f"Redirected to: {current_url}")

                                # Check if redirected to generic page (lost zone filter)
                                zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
                                zona_url_path = zona_info.get('url_path', '')
                                if zona_url_path and zona_url_path.rstrip('/') not in current_url:
                                    logger.error(f"REDIRECT DETECTED: Lost zone filter! Expected '{zona_url_path}' in URL")
                                    logger.error("Skipping this page to avoid saving wrong location data")
                                    self.stats['errors'] += 1
                                    break  # Skip to next zone

                            # Check for GeeTest / blocking
                            try:
                                captcha = page.query_selector(
                                    '.geetest_holder, [class*="geetest"], iframe[src*="geetest"], '
                                    '.geetest_challenge, #geetest-wrap'
                                )
                                if captcha:
                                    logger.warning("GeeTest captcha detected!")
                                    self.stats['errors'] += 1
                                    break

                                # Check for empty/error page
                                body_text = page.evaluate("() => document.body.innerText.substring(0, 500)")
                                if 'error' in body_text.lower() or len(body_text.strip()) < 50:
                                    logger.warning(f"Possible block/error page. Body preview: {body_text[:200]}")
                            except Exception as e:
                                logger.debug(f"Block check error: {e}")

                            # Extract listings
                            listings = self._extract_listings_from_page(page, zona_key)
                            logger.info(f"Found {len(listings)} particular listings")

                            # Debug: if no listings, log page diagnostics
                            if not listings:
                                try:
                                    title = page.title()
                                    html_len = page.evaluate("() => document.body.innerHTML.length")
                                    scripts_with_data = page.evaluate("""
                                        () => {
                                            const scripts = document.querySelectorAll('script');
                                            const info = [];
                                            for (const s of scripts) {
                                                const t = s.textContent || '';
                                                if (t.includes('INITIAL') || t.includes('ads') || t.includes('__NEXT'))
                                                    info.push(t.substring(0, 100));
                                            }
                                            return info;
                                        }
                                    """)
                                    logger.warning(
                                        f"DIAG: title='{title}', html_len={html_len}, "
                                        f"data_scripts={len(scripts_with_data)}, "
                                        f"previews={scripts_with_data[:3]}"
                                    )
                                except Exception as e:
                                    logger.debug(f"Diagnostics failed: {e}")

                            if not listings:
                                break

                            # Detect pagination duplicates (milanuncios may redirect pagina=N to page 1)
                            current_ids = {l.get('anuncio_id') for l in listings}
                            new_ids = current_ids - seen_ad_ids
                            if page_num > 1 and len(new_ids) == 0:
                                logger.warning(f"Page {page_num} returned all duplicate ads - pagination broken, stopping")
                                break
                            seen_ad_ids.update(current_ids)

                            # Filter out already-seen listings
                            new_listings = [l for l in listings if l.get('anuncio_id') in new_ids]
                            if page_num > 1:
                                logger.info(f"New listings on page {page_num}: {len(new_listings)} (filtered {len(listings) - len(new_listings)} duplicates)")

                            # Get details for each listing
                            for listing in new_listings[:15]:
                                self.stats['listings_found'] += 1

                                listing = self._scrape_detail_page(page, listing)

                                # Skip professionals detected on detail page
                                if self.only_particulares and not listing.get('es_particular'):
                                    logger.debug(f"Skipping professional (detail): {listing.get('anuncio_id')}")
                                    continue

                                # Watermark check on first photo
                                if self.filter_watermarks and listing.get('fotos'):
                                    try:
                                        if has_watermark(listing['fotos'][0]):
                                            logger.info(f"Skipping watermarked: {listing.get('anuncio_id')}")
                                            self.stats['listings_skipped_watermark'] += 1
                                            continue
                                    except:
                                        pass

                                self._scraped_listings.append(listing)
                                if self.save_to_postgres(listing):
                                    self.stats['listings_saved'] += 1

                                self._human_delay(1, 2)

                        except Exception as e:
                            logger.error(f"Error on page {page_num}: {e}")
                            self.stats['errors'] += 1
                            continue

                    self._human_delay(3, 6)

        except Exception as e:
            logger.error(f"Camoufox error: {e}")
            self.stats['errors'] += 1
            raise

        finally:
            if self.postgres_conn:
                self.postgres_conn.close()

        # Validate results and log run
        try:
            from scrapers.error_handling import validate_scraping_results, log_scraper_run
            validate_scraping_results(
                listings=self._scraped_listings,
                portal_name=self.PORTAL_NAME,
                expected_min_count=3,
                required_fields=['titulo', 'precio', 'url_anuncio'],
            )
            log_scraper_run(self.PORTAL_NAME, self.stats, self.tenant_id)
        except Exception as e:
            logger.debug(f"Post-scrape validation/logging error: {e}")

        logger.info(f"Scraping complete. Stats: {self.stats}")
        return self.stats


def run_camoufox_milanuncios(
    zones: List[str] = None,
    tenant_id: int = 1,
    max_pages_per_zone: int = 2,
    headless: bool = True,
) -> Dict[str, Any]:
    """Run the Camoufox Milanuncios scraper."""
    scraper = CamoufoxMilanuncios(
        zones=zones or ['salou'],
        tenant_id=tenant_id,
        max_pages_per_zone=max_pages_per_zone,
        headless=headless,
    )
    return scraper.scrape()


if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")

    stats = run_camoufox_milanuncios(
        zones=zones,
        max_pages_per_zone=2,
        headless=True,
    )
    print(f"\nStats: {stats}")

"""
Fotocasa scraper using Botasaurus.

This scraper extracts real estate listings from Fotocasa.es
using Botasaurus for anti-bot bypass (free, open-source).
"""

import logging
import re
from typing import Dict, Any, List, Optional

from botasaurus.browser import browser, Driver

from scrapers.botasaurus_base import BotasaurusBaseScraper, CONTAINER_CHROME_ARGS

logger = logging.getLogger(__name__)


# Geographic zones configuration
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
    # Costa Daurada (tourist area grouping)
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'composite': ['salou', 'cambrils', 'tarragona', 'torredembarra', 'altafulla', 'calafell', 'vendrell', 'miami_platja'],
    },

    # -- LLEIDA COMARCAS --
    'segria': {
        'nombre': 'Segrià',
        'composite': ['lleida'],
    },
    'noguera': {
        'nombre': 'Noguera',
        'composite': ['balaguer'],
    },
    'pla_urgell': {
        'nombre': "Pla d'Urgell",
        'composite': ['mollerussa'],
    },
    'urgell': {
        'nombre': 'Urgell',
        'composite': ['tarrega'],
    },
    'pallars_jussa': {
        'nombre': 'Pallars Jussà',
        'composite': ['tremp'],
    },

    # =============================================================
    # CITIES - Single municipality searches
    # Fotocasa URL format: /es/comprar/viviendas/particulares/{city}/todas-las-zonas/pl
    # =============================================================
    # -- LLEIDA CITIES --
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

    # -- TARRAGONA CITIES --
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


class BotasaurusFotocasa(BotasaurusBaseScraper):
    """Fotocasa scraper using Botasaurus."""

    PORTAL_NAME = 'fotocasa'
    BASE_URL = 'https://www.fotocasa.es'

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        headless: bool = True,
        only_private: bool = True,
        quick_scan: bool = False,
    ):
        super().__init__(tenant_id, postgres_config, headless)
        self.zones = zones or ['tarragona_provincia']
        self.only_private = only_private
        self.quick_scan = quick_scan

    def build_url(self, zona_key: str, page: int = 1) -> str:
        """Build search URL for Fotocasa."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        # Fotocasa URL format for particulares:
        # /es/comprar/viviendas/particulares/{city}/todas-las-zonas/pl
        url = f"{self.BASE_URL}/es/comprar/viviendas/particulares/{zona['url_path']}/pl"

        if page > 1:
            url += f'?pageNumber={page}'

        return url

    def scrape(self) -> List[Dict[str, Any]]:
        """Run the scraper and return all listings."""
        all_listings = []

        for zona_key in self.zones:
            logger.info(f"Scraping zone: {zona_key}")
            try:
                listings = self._scrape_zone(zona_key)
                all_listings.extend(listings)
                logger.info(f"Zone {zona_key}: {len(listings)} listings")
            except Exception as e:
                logger.error(f"Failed to scrape zone {zona_key}: {e}")
                continue  # Continue with next zone

        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    def _scrape_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape a single zone (or composite zone with multiple cities)."""
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Handle composite zones (comarcas) - scrape each city
        if 'composite' in zona_info:
            logger.info(f"Composite zone {zona_key}: {zona_info['composite']}")
            all_listings = []
            for city_key in zona_info['composite']:
                if city_key in ZONAS_GEOGRAFICAS:
                    logger.info(f"  Scraping city: {city_key}")
                    city_listings = self._scrape_single_zone(city_key, zona_info['nombre'])
                    all_listings.extend(city_listings)
                else:
                    logger.warning(f"  City not found in config: {city_key}")
            return all_listings

        # Single zone
        return self._scrape_single_zone(zona_key)

    def _scrape_single_zone(self, zona_key: str, parent_zone_name: str = None) -> List[Dict[str, Any]]:
        """Scrape a single municipality zone."""
        url = self.build_url(zona_key)
        headless = self.headless
        base_url = self.BASE_URL
        portal = self.PORTAL_NAME
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})
        # Use parent zone name for composite zones (comarca name)
        zone_display_name = parent_zone_name or zona_info.get('nombre', zona_key)

        @browser(headless=headless, block_images=False, add_arguments=CONTAINER_CHROME_ARGS)
        def scrape_page(driver: Driver, data: dict):
            url = data['url']

            logger.info(f"Loading: {url}")
            driver.get(url)
            driver.sleep(3)

            # Accept cookies via TCF API (Fotocasa uses iframe-based TCF consent)
            def _accept_consent(drv):
                try:
                    result = drv.run_js('''
                        let accepted = false;
                        // Method 1: Use TCF API directly to grant all consent
                        if (window.__tcfapi) {
                            window.__tcfapi('postCustomConsent', 2, function(){}, [1,2,3,4,5,6,7,8,9,10], [1,2,3,4,5,6,7,8,9,10], [1,2,3,4,5,6,7,8,9,10]);
                            accepted = true;
                        }
                        // Method 2: Click any visible accept/consent button
                        const selectors = [
                            '[data-testid="TcfAccept"]',
                            'button[id*="accept"]',
                            'button[class*="accept"]',
                            '.sui-AtomButton--primary',
                            '#didomi-notice-agree-button',
                            'button[aria-label*="accept" i]',
                            'button[aria-label*="aceptar" i]',
                            '.fc-button-label',
                            '[class*="consent"] button',
                            '[class*="cookie"] button',
                        ];
                        for (const sel of selectors) {
                            const btn = document.querySelector(sel);
                            if (btn && btn.offsetParent !== null) { btn.click(); accepted = true; break; }
                        }
                        return accepted;
                    ''')
                    if result:
                        logger.info("Consent accepted via TCF API or button click")
                    else:
                        logger.warning("No consent banner found (may already be accepted)")
                except Exception as e:
                    logger.warning(f"Consent handling error: {e}")

            _accept_consent(driver)
            driver.sleep(3)

            # Wait for React to hydrate and listing links to appear
            content_loaded = False
            for attempt in range(15):
                has_content = driver.run_js('''
                    return document.querySelectorAll('a[href*="/es/comprar/vivienda/"]').length;
                ''')
                if has_content and has_content > 0:
                    logger.info(f"Content loaded after {(attempt+1)*2}s: {has_content} listing links found")
                    content_loaded = True
                    break
                # Re-try consent every 10s in case it reappeared
                if attempt == 5:
                    logger.info("Retrying consent acceptance...")
                    _accept_consent(driver)
                driver.sleep(2)

            if not content_loaded:
                logger.warning("Content did not load after 30s - reloading page and retrying")
                driver.run_js('location.reload()')
                driver.sleep(5)
                _accept_consent(driver)
                driver.sleep(3)
                # Final wait attempt
                for attempt in range(10):
                    has_content = driver.run_js('''
                        return document.querySelectorAll('a[href*="/es/comprar/vivienda/"]').length;
                    ''')
                    if has_content and has_content > 0:
                        logger.info(f"Content loaded after reload + {(attempt+1)*2}s: {has_content} links")
                        content_loaded = True
                        break
                    driver.sleep(2)
                if not content_loaded:
                    logger.error("Content failed to load after retry - possible anti-bot blocking")

            # Scroll to load lazy content
            for i in range(6):
                scroll_pos = 800 * (i + 1)
                driver.run_js(f'window.scrollTo({{top: {scroll_pos}, behavior: "smooth"}})')
                driver.sleep(1)

            driver.run_js('window.scrollTo({top: document.body.scrollHeight, behavior: "smooth"})')
            driver.sleep(2)

            html = driver.page_html
            logger.info(f"HTML length: {len(html)}")

            # Try JSON-LD extraction first (available even in SSR HTML)
            json_ld_listings = []
            try:
                import json as json_mod
                ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
                for ld_text in ld_matches:
                    ld_data = json_mod.loads(ld_text)
                    if ld_data.get('@type') == 'RealEstateListing':
                        logger.info("Found JSON-LD RealEstateListing data")
            except:
                pass

            # Check for blocking
            if len(html) < 10000:
                logger.warning(f"Possible blocking (HTML: {len(html)} bytes)")
                return []

            # If HTML is small (SSR only, React didn't hydrate), still try to extract links
            if len(html) < 30000:
                logger.warning(f"Small HTML ({len(html)} bytes) - React may not have hydrated, trying SSR extraction")

            # Fotocasa page structure:
            # 1. First section: PARTICULARES listings (what we want)
            # 2. Divider text: "Mira algunos de los anuncios de inmobiliarias"
            # 3. Second section: AGENCY listings (skip these)

            # Find the divider position and only use HTML before it
            html_lower = html.lower()
            divider_markers = [
                'anuncios de inmobiliarias',
                'ver más anuncios',
                'mira algunos de los anuncios',
            ]

            divider_pos = len(html)  # Default: use all HTML
            for marker in divider_markers:
                pos = html_lower.find(marker)
                if pos > 0 and pos < divider_pos:
                    divider_pos = pos
                    logger.info(f"Found divider '{marker}' at position {pos}")

            # Only search for links in the particulares section (before divider)
            particulares_html = html[:divider_pos]
            logger.info(f"Searching in first {len(particulares_html)} chars (before agency section)")

            # Extract listing URLs from particulares section only
            # Links have format: /es/comprar/vivienda/.../ID/d?from=pl&amp;...
            links = re.findall(r'href="(/es/comprar/vivienda/[^"]+/\d{7,}/d)', particulares_html)

            # Deduplicate (same listing appears multiple times with different params)
            filtered_links = list(dict.fromkeys(links))

            unique_links = list(dict.fromkeys(filtered_links))
            logger.info(f"Found {len(unique_links)} PARTICULAR listing links (before agency divider)")

            listings = []
            for link in unique_links[:20]:  # Limit to avoid timeout
                detail_url = f"{base_url}{link}"

                # Extract ID from URL - handle multiple formats:
                # - /zona/ID/d -> take ID
                # - /zona/projectID/unitID -> take unitID (last number)
                # - /zona/ID -> take ID
                id_matches = re.findall(r'/(\d{7,})', link)
                if not id_matches:
                    continue

                # Use the last (most specific) ID
                anuncio_id = id_matches[-1]

                listings.append({
                    'anuncio_id': anuncio_id,
                    'detail_url': detail_url,
                    'url_anuncio': detail_url,
                    'portal': portal,
                    'zona_busqueda': zone_display_name,
                    'zona_geografica': zone_display_name,
                })

            return listings

        try:
            basic_listings = scrape_page({'url': url})
        except Exception as e:
            logger.error(f"Error scraping {zona_key}: {e}")
            return []

        if not basic_listings:
            return []

        # Quick scan: skip detail page enrichment for speed (~3x faster)
        if self.quick_scan:
            logger.info(f"Quick scan: returning {len(basic_listings)} basic listings (no enrichment)")
            return basic_listings[:20]

        # Enrich with detail page data
        try:
            enriched_listings = self._enrich_listings(basic_listings[:10])  # Limit for speed
        except Exception as e:
            logger.error(f"Error enriching listings for {zona_key}: {e}")
            # Return basic listings without enrichment
            return basic_listings[:10]

        return enriched_listings

    def _enrich_listings(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch detail pages to extract more info - one browser per listing."""
        import random
        import time
        headless = self.headless
        results = []

        for i, listing in enumerate(listings):
            url = listing['detail_url']
            logger.info(f"Fetching detail {i+1}/{len(listings)}: {url[:60]}...")

            # Random delay between requests (3-8 seconds)
            if i > 0:
                delay = random.uniform(3, 8)
                logger.info(f"Waiting {delay:.1f}s before next request...")
                time.sleep(delay)

            # Create a new browser session for each listing
            @browser(headless=headless, block_images=False, reuse_driver=False, add_arguments=CONTAINER_CHROME_ARGS)
            def fetch_single_detail(driver: Driver, data: dict):
                try:
                    driver.get(data['url'])
                    driver.sleep(random.uniform(3, 5))

                    # Human-like scrolling
                    for pos in [300, 600, 900]:
                        driver.run_js(f'window.scrollTo({{top: {pos}, behavior: "smooth"}})')
                        driver.sleep(random.uniform(0.5, 1.0))

                    return driver.page_html
                except Exception as e:
                    logger.error(f"Error in browser: {e}")
                    return None

            html = fetch_single_detail({'url': url})

            if not html:
                continue

            # Check for blocking
            if 'SENTIMOS LA INTERRUPCIÓN' in html or 'captcha' in html.lower():
                logger.warning("Fotocasa anti-bot detected, skipping this listing")
                continue

            try:
                # Extract title
                title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                listing['titulo'] = title_match.group(1).strip() if title_match else None

                # Extract price - try multiple patterns
                price_patterns = [
                    # React class (may change between deploys)
                    r'class="[^"]*(?:re-DetailHeader-price|DetailHeader-price|price)[^"]*"[^>]*>([^<]+)',
                    # Generic price near EUR/€ symbol
                    r'(\d{1,3}(?:\.\d{3})*)\s*(?:EUR|€)',
                    # Price in JSON-LD
                    r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?',
                ]
                for pattern in price_patterns:
                    price_header = re.search(pattern, html, re.IGNORECASE)
                    if price_header:
                        raw = price_header.group(1)
                        price_match = re.search(r'(\d{1,3}(?:[.\s]\d{3})*)', raw)
                        if price_match:
                            price_str = price_match.group(1).replace('.', '').replace(' ', '')
                            if price_str.isdigit() and int(price_str) > 10000:
                                listing['precio'] = float(price_str)
                                break

                # Extract metros - multiple patterns
                metros_patterns = [
                    r'<span[^>]*>\s*<span>(\d+)</span>\s*m[²2]',
                    r'(\d+)\s*m[²2]',
                    r'(\d+)\s*m&sup2;',
                ]
                for pattern in metros_patterns:
                    metros_match = re.search(pattern, html)
                    if metros_match:
                        val = int(metros_match.group(1))
                        if 10 < val < 10000:
                            listing['metros'] = val
                            break

                # Extract habitaciones - multiple patterns
                habs_patterns = [
                    r'<span[^>]*>\s*<span>(\d+)</span>\s*hab',
                    r'(\d+)\s*hab',
                ]
                for pattern in habs_patterns:
                    habs_match = re.search(pattern, html, re.IGNORECASE)
                    if habs_match:
                        val = int(habs_match.group(1))
                        if 0 < val < 50:
                            listing['habitaciones'] = val
                            break

                # Extract description - try structured selectors then text blocks
                desc_patterns = [
                    r'class="[^"]*(?:re-DetailDescription|DetailDescription|description|comment|detalle)[^"]*"[^>]*>(.*?)</(?:div|p|section)',
                    r'<meta\s+name="description"\s+content="([^"]{50,})"',
                ]
                for pattern in desc_patterns:
                    desc_match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                    if desc_match:
                        desc_text = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
                        desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                        if len(desc_text) > 50:
                            listing['descripcion'] = desc_text[:2000]
                            break
                if 'descripcion' not in listing:
                    text_blocks = re.findall(r'>([^<]{100,})<', html)
                    for block in text_blocks:
                        clean_text = block.strip()
                        if (clean_text and
                            'cookie' not in clean_text.lower() and
                            'javascript' not in clean_text.lower() and
                            'privacy' not in clean_text.lower()):
                            listing['descripcion'] = clean_text[:2000]
                            break

                # Try to extract phone from description (many sellers put it there)
                descripcion = listing.get('descripcion', '')
                phone = self.extract_phone_from_description(descripcion)
                if phone:
                    listing['telefono'] = phone
                    listing['telefono_norm'] = phone
                    logger.info(f"Phone found in description: {phone}")
                else:
                    listing['telefono'] = None
                    listing['telefono_norm'] = None

                # Extract photos - Fotocasa uses static.fotocasa.es/images/
                # Match full UUIDs and paths
                photos = re.findall(
                    r'(https?://static\.fotocasa\.es/images/[^"\'<>\s]+)',
                    html, re.IGNORECASE
                )
                unique_photos = []
                seen = set()
                for photo in photos:
                    # Remove query params for dedup
                    photo_base = re.sub(r'\?.*$', '', photo)
                    if photo_base not in seen and len(photo_base) > 50:
                        # Add original quality param
                        unique_photos.append(photo_base + '?rule=original')
                        seen.add(photo_base)
                listing['fotos'] = unique_photos[:10]

                # Detect if listing is from agency or particular
                # Fotocasa shows "Anuncio Particular" for private sellers
                is_particular = False

                # Check for particular indicators (exact text from Fotocasa)
                particular_indicators = [
                    'anuncio particular',  # Main indicator
                    'particular_user_icon',  # SVG icon
                    'anunciante particular',
                ]
                html_lower = html.lower()
                for indicator in particular_indicators:
                    if indicator in html_lower:
                        is_particular = True
                        break

                # If no particular indicator found, check if it's clearly an agency
                if not is_particular:
                    # Check for agency names/indicators near contact section
                    agency_patterns = [
                        r'partner\s+inmobiliario',
                        r'inmuebles\s+\w+',  # "Inmuebles [company name]"
                        r'servicios\s+integrales',
                        r'tu\s+agente',
                    ]
                    for pattern in agency_patterns:
                        if re.search(pattern, html_lower):
                            logger.info(f"SKIPPED (agency pattern): {listing.get('titulo', 'N/A')[:50]}")
                            break
                    else:
                        # No clear agency indicator, might be particular without badge
                        # Accept if we're using /particulares/ URL
                        is_particular = True

                if is_particular:
                    listing['vendedor'] = 'Particular'
                    listing['es_particular'] = True
                    logger.info(f"ACCEPTED: {listing.get('titulo', 'N/A')[:50]}")
                    results.append(listing)
                else:
                    listing['vendedor'] = 'Agencia'
                    listing['es_particular'] = False
                    logger.info(f"SKIPPED (agency): {listing.get('titulo', 'N/A')[:50]}")

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")

        # No filtering - return all listings
        return results

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()
        duplicates = 0

        for listing in listings:
            self.stats['total_listings'] = self.stats.get('total_listings', 0) + 1
            if self.save_to_postgres(listing, self.PORTAL_NAME):
                self.stats['saved'] += 1
            else:
                duplicates += 1

        self.stats['duplicates'] = duplicates
        if duplicates > 0:
            logger.info(f"Skipped {duplicates} duplicate listings (already in DB)")
        logger.info(f"Stats: {self.stats}")
        return self.stats


def run_fotocasa_botasaurus(
    zones: List[str] = None,
    postgres: bool = False,
    headless: bool = True,
    only_private: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convenience function to run the Fotocasa scraper.

    Args:
        zones: List of zones to scrape
        postgres: Enable PostgreSQL saving
        headless: Run in headless mode
        only_private: Only scrape particular listings

    Returns:
        List of scraped listings
    """
    postgres_config = None
    if postgres:
        postgres_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'casa_teva_db',
            'user': 'casa_teva',
            'password': 'casateva2024',
        }

    with BotasaurusFotocasa(
        zones=zones or ['tarragona_provincia'],
        postgres_config=postgres_config,
        headless=headless,
        only_private=only_private,
    ) as scraper:
        if postgres:
            scraper.scrape_and_save()
        return scraper.scrape()


if __name__ == '__main__':
    import sys

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['tarragona_provincia']
    print(f"Scraping zones: {zones}")
    print(f"Available zones: {list(ZONAS_GEOGRAFICAS.keys())}")

    listings = run_fotocasa_botasaurus(zones=zones, headless=True)

    print(f"\nFound {len(listings)} listings:")
    for l in listings[:5]:
        print(f"  - {l.get('titulo', 'N/A')[:50]}... | {l.get('precio')}€ | {l.get('vendedor')}")

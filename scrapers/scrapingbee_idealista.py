"""
Idealista scraper using ScrapingBee API.

This scraper extracts real estate listings from Idealista.com
using ScrapingBee's stealth proxy to bypass DataDome protection.

Cost: 75 credits per page (stealth mode)
"""

import logging
import re
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode

from scrapers.scrapingbee_base import ScrapingBeeClient

logger = logging.getLogger(__name__)


# Geographic zones configuration for Idealista
ZONAS_GEOGRAFICAS = {
    # =============================================================
    # PROVINCES
    # =============================================================
    'tarragona_provincia': {
        'nombre': 'Tarragona Provincia',
        'url_path': 'tarragona-provincia',
        'url_code': 'tarragona-provincia',
    },
    'lleida_provincia': {
        'nombre': 'Lleida Provincia',
        'url_path': 'lleida-provincia',
        'url_code': 'lleida-provincia',
    },

    # =============================================================
    # COMARCAS - Composite zones
    # =============================================================
    'tarragones': {
        'nombre': 'Tarragonès',
        'composite': ['tarragona', 'torredembarra', 'altafulla'],
    },
    'baix_camp': {
        'nombre': 'Baix Camp',
        'composite': ['reus', 'cambrils', 'salou', 'vila_seca'],
    },
    'baix_penedes': {
        'nombre': 'Baix Penedès',
        'composite': ['vendrell', 'calafell'],
    },
    'costa_daurada': {
        'nombre': 'Costa Daurada',
        'composite': ['salou', 'cambrils', 'tarragona', 'torredembarra', 'calafell', 'vendrell'],
    },
    'segria': {
        'nombre': 'Segrià',
        'composite': ['lleida'],
    },

    # =============================================================
    # CITIES - Lleida
    # =============================================================
    'lleida': {
        'nombre': 'Lleida',
        'url_path': 'lleida-lleida',
        'url_code': 'lleida-lleida',
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'url_path': 'balaguer-lleida',
        'url_code': 'balaguer-lleida',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'url_path': 'mollerussa-lleida',
        'url_code': 'mollerussa-lleida',
    },
    'tremp': {
        'nombre': 'Tremp',
        'url_path': 'tremp-lleida',
        'url_code': 'tremp-lleida',
    },
    'tarrega': {
        'nombre': 'Tàrrega',
        'url_path': 'tarrega-lleida',
        'url_code': 'tarrega-lleida',
    },
    'alpicat': {
        'nombre': 'Alpicat',
        'url_path': 'alpicat-lleida',
        'url_code': 'alpicat-lleida',
    },
    'torrefarrera': {
        'nombre': 'Torrefarrera',
        'url_path': 'torrefarrera-lleida',
        'url_code': 'torrefarrera-lleida',
    },
    'alcarras': {
        'nombre': 'Alcarràs',
        'url_path': 'alcarras-lleida',
        'url_code': 'alcarras-lleida',
    },
    'alcoletge': {
        'nombre': 'Alcoletge',
        'url_path': 'alcoletge-lleida',
        'url_code': 'alcoletge-lleida',
    },
    'rossello': {
        'nombre': 'Rosselló',
        'url_path': 'rossello-lleida',
        'url_code': 'rossello-lleida',
    },
    'alamus': {
        'nombre': 'Alamús',
        'url_path': 'els-alamus-lleida',
        'url_code': 'els-alamus-lleida',
    },

    # =============================================================
    # CITIES - Tarragona
    # =============================================================
    'tarragona': {
        'nombre': 'Tarragona',
        'url_path': 'tarragona-tarragona',
        'url_code': 'tarragona-tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'url_path': 'reus-tarragona',
        'url_code': 'reus-tarragona',
    },
    'salou': {
        'nombre': 'Salou',
        'url_path': 'salou-tarragona',
        'url_code': 'salou-tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'url_path': 'cambrils-tarragona',
        'url_code': 'cambrils-tarragona',
    },
    'calafell': {
        'nombre': 'Calafell',
        'url_path': 'calafell-tarragona',
        'url_code': 'calafell-tarragona',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'url_path': 'el-vendrell-tarragona',
        'url_code': 'el-vendrell-tarragona',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'url_path': 'torredembarra-tarragona',
        'url_code': 'torredembarra-tarragona',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'url_path': 'altafulla-tarragona',
        'url_code': 'altafulla-tarragona',
    },
    'miami_platja': {
        'nombre': 'Miami Platja',
        'url_path': 'miami-platja-tarragona',
        'url_code': 'miami-platja-tarragona',
    },
    'vila_seca': {
        'nombre': 'Vila-seca',
        'url_path': 'vila-seca-tarragona',
        'url_code': 'vila-seca-tarragona',
    },
    'valls': {
        'nombre': 'Valls',
        'url_path': 'valls-tarragona',
        'url_code': 'valls-tarragona',
    },
    'montblanc': {
        'nombre': 'Montblanc',
        'url_path': 'montblanc-tarragona',
        'url_code': 'montblanc-tarragona',
    },
    'hospitalet_infant': {
        'nombre': "L'Hospitalet de l'Infant",
        'url_path': 'l-hospitalet-de-l-infant-tarragona',
        'url_code': 'l-hospitalet-de-l-infant-tarragona',
    },
    'coma_ruga': {
        'nombre': 'Coma-ruga',
        'url_path': 'coma-ruga-tarragona',
        'url_code': 'coma-ruga-tarragona',
    },
    'la_pineda': {
        'nombre': 'La Pineda',
        'url_path': 'la-pineda-tarragona',
        'url_code': 'la-pineda-tarragona',
    },
    'montroig_camp': {
        'nombre': 'Mont-roig del Camp',
        'url_path': 'mont-roig-del-camp-tarragona',
        'url_code': 'mont-roig-del-camp-tarragona',
    },

    # Terres de l'Ebre
    'tortosa': {
        'nombre': 'Tortosa',
        'url_path': 'tortosa-tarragona',
        'url_code': 'tortosa-tarragona',
    },
    'amposta': {
        'nombre': 'Amposta',
        'url_path': 'amposta-tarragona',
        'url_code': 'amposta-tarragona',
    },
    'deltebre': {
        'nombre': 'Deltebre',
        'url_path': 'deltebre-tarragona',
        'url_code': 'deltebre-tarragona',
    },
    'sant_carles_rapita': {
        'nombre': 'Sant Carles de la Ràpita',
        'url_path': 'sant-carles-de-la-rapita-tarragona',
        'url_code': 'sant-carles-de-la-rapita-tarragona',
    },
    'ametlla_mar': {
        'nombre': "L'Ametlla de Mar",
        'url_path': 'l-ametlla-de-mar-tarragona',
        'url_code': 'l-ametlla-de-mar-tarragona',
    },
}


class ScrapingBeeIdealista(ScrapingBeeClient):
    """
    Idealista scraper using ScrapingBee API.

    Uses stealth proxy to bypass DataDome protection.
    """

    PORTAL_NAME = 'idealista'
    BASE_URL = 'https://www.idealista.com'

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        use_stealth: bool = True,
        max_pages_per_zone: int = 2,
        only_particulares: bool = True,
    ):
        """
        Initialize Idealista scraper.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            zones: List of zones to scrape
            postgres_config: PostgreSQL config (auto-detected if None)
            use_stealth: Use stealth proxy (required for Idealista)
            max_pages_per_zone: Maximum pages per zone (budget control)
            only_particulares: Only scrape particular listings (not agencies)
        """
        super().__init__(
            portal_name=self.PORTAL_NAME,
            tenant_id=tenant_id,
            use_stealth=use_stealth,
            postgres_config=postgres_config,
        )
        self.zones = zones or ['salou']
        self.max_pages_per_zone = max_pages_per_zone
        self.only_particulares = only_particulares

    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        """Build Idealista search URL for a zone."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        url_path = zona['url_path']
        base_url = f"{self.BASE_URL}/venta-viviendas/{url_path}/"

        if page > 1:
            base_url += f'pagina-{page}.htm'

        return base_url

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to float."""
        if not price_text:
            return None
        try:
            # Remove currency symbols, spaces, dots (thousand separators)
            cleaned = re.sub(r'[€$\s\xa0.]', '', price_text)
            # Replace comma with dot if it's a decimal separator
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except:
            return None

    def _extract_listings_from_html(self, html: str, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listing URLs and basic data from search results HTML."""
        listings = []

        # Check for actual blocking indicators (DataDome, access denied, etc.)
        # Note: "blocked" and "captcha" appear in normal page content (CSS classes, URL configs)
        blocking_patterns = [
            r'access.denied|acceso.denegado',
            r'you.have.been.blocked',
            r'datadome.*blocked',
            r'<title>.*blocked.*</title>',
            r'please.complete.*captcha.*to.continue',
        ]
        for pattern in blocking_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                logger.warning(f"Blocking detected: {pattern}")
                return []

        # Find listing URLs in article elements
        # Idealista format: /inmueble/ID/
        url_pattern = r'href="(/inmueble/(\d+)/)"'
        matches = re.findall(url_pattern, html)

        if not matches:
            # Alternative pattern for listing cards
            url_pattern = r'href="(/venta-viviendas/[^"]+/(\d{5,})/)"'
            matches = re.findall(url_pattern, html)

        seen_ids = set()
        particulares_count = 0
        agencies_count = 0

        for path, anuncio_id in matches:
            if anuncio_id in seen_ids:
                continue
            seen_ids.add(anuncio_id)

            detail_url = f"{self.BASE_URL}{path}"
            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            # Pre-detect agency from search results HTML (look for agency markers near the listing)
            # Search for agency indicators within ~1000 chars around the listing URL
            url_pos = html.find(path)
            if url_pos > 0:
                context = html[max(0, url_pos-500):url_pos+1000]
                # Expanded agency detection patterns for search results
                agency_search_patterns = [
                    r'professional-name',
                    r'logo-profesional',
                    r'item-link-professional',
                    r'advertiser-professional',
                    r'professional-logo',
                    r'data-is-professional',
                    r'profesional',  # Generic match
                    r'item-highlight.*inmobiliaria',
                    r'item-highlight.*agencia',
                    r'<span[^>]*class="[^"]*item-highlight-phrase[^"]*"[^>]*>\s*(?:inmobiliaria|agencia)',
                    r'<img[^>]*class="[^"]*logo[^"]*"',  # Logo image = agency
                    r'src="[^"]*logo[^"]*inmobiliaria',  # Logo URL
                ]
                is_likely_agency = any(re.search(p, context, re.IGNORECASE) for p in agency_search_patterns)
                if is_likely_agency and self.only_particulares:
                    agencies_count += 1
                    self.stats['credits_saved'] += 75
                    continue  # Skip agency, save 75 credits!

            particulares_count += 1
            listings.append({
                'anuncio_id': anuncio_id,
                'detail_url': detail_url,
                'url_anuncio': detail_url,
                'portal': self.PORTAL_NAME,
                'zona_busqueda': zona_info.get('nombre', zona_key),
                'zona_geografica': zona_info.get('nombre', zona_key),
            })

        if agencies_count > 0:
            logger.info(f"Pre-filtered {agencies_count} agency listings from search (saved {agencies_count * 75} credits)")
        logger.info(f"Found {len(listings)} particular listing URLs in search results")
        return listings

    def _scrape_detail_page(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape detail page to extract full listing data."""
        detail_url = listing['detail_url']

        html = self.fetch_page(
            detail_url,
            wait_for='.detail-info',
        )

        if not html:
            return listing

        # Check if agency listing (skip if only_particulares)
        # Comprehensive agency detection patterns for Idealista
        agency_patterns = [
            # CSS classes and attributes - Professional/Agency markers
            r'class="[^"]*professional-info[^"]*"',  # Agency info section
            r'class="[^"]*logo-profesional[^"]*"',  # Agency logo
            r'class="[^"]*professional-logo[^"]*"',  # Professional logo
            r'class="[^"]*advertiser-professional[^"]*"',  # Professional advertiser
            r'class="[^"]*contact-request-profe[^"]*"',  # Professional contact section
            r'class="[^"]*profesional[^"]*"',  # Any class containing "profesional"
            r'class="[^"]*agency[^"]*"',  # Any class containing "agency"
            # Data attributes
            r'data-seller-type=["\']?professional',  # Seller type attribute
            r'data-advertiser-type=["\']?professional',
            r'data-is-professional=["\']?true',
            # Agency image/logo detection
            r'<img[^>]*alt="[^"]*(?:inmobiliaria|logo|agencia)[^"]*"',
            r'<img[^>]*class="[^"]*logo[^"]*"[^>]*>',
            # Text patterns in advertiser section
            r'<[^>]*class="[^"]*advertiser[^"]*"[^>]*>.*?(?:inmobiliaria|agencia|fincas|gestora|real\s*estate)',
            # JSON-LD data
            r'"@type"\s*:\s*"RealEstateAgent"',
            r'"seller"\s*:\s*\{[^}]*"@type"\s*:\s*"Organization"',
            # Phone number patterns typical of agencies (multiple lines, etc)
            r'ver\s+tel[eé]fonos?\s+de\s+la\s+inmobiliaria',
            # Contact form for professionals
            r'contactar\s+(?:con\s+)?(?:el\s+)?anunciante\s+profesional',
            r'formulario\s+de\s+contacto.*profesional',
        ]
        is_agency = any(re.search(pattern, html, re.IGNORECASE | re.DOTALL) for pattern in agency_patterns)

        if is_agency and self.only_particulares:
            logger.info(f"Skipping agency listing: {listing['anuncio_id']}")
            listing['es_particular'] = False
            listing['vendedor'] = 'Profesional'
            return listing

        listing['es_particular'] = not is_agency
        listing['vendedor'] = 'Particular' if not is_agency else 'Profesional'

        # Extract title - look for span with main-info__title-main class
        title_match = re.search(
            r'<span[^>]*class="[^"]*main-info__title-main[^"]*"[^>]*>([^<]+)</span>',
            html
        )
        if not title_match:
            # Fallback to h1
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            listing['titulo'] = title_match.group(1).strip()

        # Extract description - look for adCommentsLanguage div (actual description content)
        desc_match = re.search(
            r'<div[^>]*class="[^"]*adCommentsLanguage[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if not desc_match:
            # Fallback to comment div
            desc_match = re.search(
                r'<div[^>]*class="[^"]*comment[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL
            )
        if desc_match:
            # Remove HTML tags and clean up
            desc_text = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
            desc_text = re.sub(r'\s+', ' ', desc_text)  # Normalize whitespace
            listing['descripcion'] = desc_text.strip()[:2000]

        # Extract price
        price_match = re.search(
            r'class="[^"]*info-data-price[^"]*"[^>]*>([^<]+)',
            html
        )
        if not price_match:
            price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*€', html)
        if price_match:
            listing['precio'] = self._parse_price(price_match.group(1))

        # Extract location
        location_match = re.search(
            r'class="[^"]*main-info__title-minor[^"]*"[^>]*>([^<]+)',
            html
        )
        if location_match:
            listing['ubicacion'] = location_match.group(1).strip()

        # Extract publication/update date (for analytics)
        # Idealista shows "Anuncio actualizado el DD de mes de YYYY"
        date_patterns = [
            # "actualizado el 5 de enero de 2026" or similar
            r'actualizado?\s+(?:el\s+)?(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
            # ISO date in JSON if available
            r'"datePosted"\s*:\s*"([^"]+)"',
            r'"dateModified"\s*:\s*"([^"]+)"',
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, html, re.IGNORECASE)
            if date_match:
                if len(date_match.groups()) == 3:
                    # Spanish date format - convert to ISO
                    day, month_name, year = date_match.groups()
                    months = {
                        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                    }
                    month = months.get(month_name.lower(), '01')
                    listing['fecha_publicacion'] = f"{year}-{month}-{day.zfill(2)}T00:00:00Z"
                else:
                    listing['fecha_publicacion'] = date_match.group(1)
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

        # Extract features from info-features section (most reliable)
        # The info-features section contains the main listing data
        info_features = re.search(
            r'class="[^"]*info-features[^"]*"[^>]*>(.*?)</(?:div|section|ul)',
            html, re.DOTALL
        )
        features_section = info_features.group(1) if info_features else html

        # Metros cuadrados - from info-features first, fallback to full HTML
        metros_match = re.search(r'(\d+)\s*m[²2]', features_section)
        if metros_match:
            listing['metros'] = int(metros_match.group(1))
        else:
            # Fallback to first m² in page (might get description values)
            metros_fallback = re.search(r'(\d+)\s*m[²2]', html)
            if metros_fallback:
                listing['metros'] = int(metros_fallback.group(1))

        # Habitaciones - from info-features first
        habs_match = re.search(r'(\d+)\s*(?:hab|habitaci|dormitor)', features_section, re.IGNORECASE)
        if habs_match:
            listing['habitaciones'] = int(habs_match.group(1))
        else:
            habs_fallback = re.search(r'(\d+)\s*(?:hab|habitaci|dormitor)', html, re.IGNORECASE)
            if habs_fallback:
                listing['habitaciones'] = int(habs_fallback.group(1))

        # Baños - from info-features first
        banos_match = re.search(r'(\d+)\s*(?:baño|wc)', features_section, re.IGNORECASE)
        if banos_match:
            listing['banos'] = int(banos_match.group(1))
        else:
            banos_fallback = re.search(r'(\d+)\s*(?:baño|wc)', html, re.IGNORECASE)
            if banos_fallback:
                listing['banos'] = int(banos_fallback.group(1))

        # Extract photos (Idealista CDN: img3.idealista.com)
        # ISSUE: Same image appears with different size prefixes:
        #   WEB_LISTING, WEB_DETAIL, WEB_DETAIL_LARGE, etc.
        # FIX: Extract unique image ID ignoring size prefix
        photos = re.findall(
            r'(https://img\d*\.idealista\.com/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp))',
            html, re.IGNORECASE
        )
        unique_photos = []
        seen_ids = set()
        for photo in photos:
            if 'logo' in photo.lower():
                continue
            # Extract unique image ID by removing size prefix
            # Pattern: /blur/WEB_DETAIL_LARGE/0/id123456.jpg -> id123456.jpg
            # Also handles: /pictures/id123456.jpg
            id_match = re.search(r'/([^/]+\.(?:jpg|jpeg|png|webp))(?:\?.*)?$', photo, re.IGNORECASE)
            if id_match:
                image_id = id_match.group(1).lower()
                if image_id not in seen_ids:
                    seen_ids.add(image_id)
                    # Prefer larger version - replace size prefix with WEB_DETAIL_LARGE
                    large_url = re.sub(
                        r'/blur/[^/]+/',
                        '/blur/WEB_DETAIL_LARGE/',
                        photo
                    )
                    # Remove query params for cleaner URL
                    large_url = re.sub(r'\?.*$', '', large_url)
                    unique_photos.append(large_url)
        listing['fotos'] = unique_photos[:10]

        # Extract energy certificate
        energy_match = re.search(
            r'class="[^"]*energy[^"]*"[^>]*>([A-G])</span>',
            html, re.IGNORECASE
        )
        if energy_match:
            listing['certificado_energetico'] = energy_match.group(1).upper()

        return listing

    def scrape_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape all listings from a zone (handles composite zones)."""
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        # Handle composite zones (comarcas)
        if 'composite' in zona_info:
            logger.info(f"Composite zone {zona_key}: {zona_info['composite']}")
            all_listings = []
            for city_key in zona_info['composite']:
                if city_key in ZONAS_GEOGRAFICAS:
                    logger.info(f"  Scraping city: {city_key}")
                    city_listings = self._scrape_single_zone(city_key)
                    all_listings.extend(city_listings)
                else:
                    logger.warning(f"  City not found: {city_key}")
            return all_listings

        return self._scrape_single_zone(zona_key)

    def _scrape_single_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape a single municipality zone."""
        all_listings = []
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        logger.info(f"Scraping zone: {zona_info.get('nombre', zona_key)}")

        for page in range(1, self.max_pages_per_zone + 1):
            search_url = self.build_search_url(zona_key, page)
            logger.info(f"Scraping page {page} of {zona_key}")

            html = self.fetch_page(
                search_url,
                wait_for='.items-list',
            )

            if not html:
                logger.warning(f"Failed to fetch page {page}")
                break

            # Extract listing URLs from search results
            basic_listings = self._extract_listings_from_html(html, zona_key)

            if not basic_listings:
                logger.info(f"No more listings found on page {page}")
                break

            self.stats['pages_scraped'] += 1

            # Scrape each detail page (skip if already in DB)
            # Limit to 3 detail pages per search page to avoid timeout
            # (each detail page takes ~60-120s with stealth proxy)
            skipped = 0
            for i, listing in enumerate(basic_listings[:3]):  # Reduced from 10 to avoid timeout
                url = listing.get('detail_url') or listing.get('url_anuncio')

                # Skip if URL already exists in database
                if url and self.url_exists_in_db(url):
                    skipped += 1
                    self.stats['listings_skipped'] += 1
                    self.stats['credits_saved'] += 75
                    logger.debug(f"Skipping existing URL: {url[:50]}...")
                    continue

                logger.info(f"Detail page {i+1}/{len(basic_listings[:10])} (skipped {skipped})")

                enriched = self._scrape_detail_page(listing)
                self.stats['listings_found'] += 1

                # Only keep particular listings if filter is enabled
                if self.only_particulares and not enriched.get('es_particular', True):
                    continue

                all_listings.append(enriched)

                # Delay between requests
                time.sleep(0.5)

            if skipped > 0:
                logger.info(f"Skipped {skipped} already-scraped listings (saved {skipped * 75} credits)")

            # Check if we should continue to next page
            if len(basic_listings) < 10:
                logger.info("Less than 10 listings, assuming last page")
                break

            # Delay between pages
            time.sleep(1)

        return all_listings

    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape all configured zones."""
        all_listings = []

        for zona_key in self.zones:
            try:
                listings = self.scrape_zone(zona_key)
                all_listings.extend(listings)
                logger.info(f"Zone {zona_key}: {len(listings)} listings")
            except Exception as e:
                logger.error(f"Error scraping zone {zona_key}: {e}")
                self.stats['errors'] += 1

        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    def scrape_and_save(self) -> Dict[str, int]:
        """Scrape all zones and save to PostgreSQL."""
        listings = self.scrape()

        for listing in listings:
            # Save all listings (phone filtering done later in dbt pipeline)
            self.save_to_postgres(listing)

        logger.info(f"Scraping complete. Stats: {self.get_stats()}")
        return self.get_stats()


def run_scrapingbee_idealista(
    zones: List[str] = None,
    tenant_id: int = 1,
    max_pages_per_zone: int = 2,
    only_particulares: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to run ScrapingBee Idealista scraper.

    Args:
        zones: List of zones to scrape
        tenant_id: Tenant ID
        max_pages_per_zone: Max pages per zone (budget control)
        only_particulares: Only scrape particular listings

    Returns:
        Scraping statistics
    """
    with ScrapingBeeIdealista(
        zones=zones or ['salou', 'cambrils'],
        tenant_id=tenant_id,
        max_pages_per_zone=max_pages_per_zone,
        only_particulares=only_particulares,
    ) as scraper:
        scraper.scrape_and_save()
        return scraper.get_stats()


if __name__ == '__main__':
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    zones = sys.argv[1:] if len(sys.argv) > 1 else ['salou']
    print(f"Scraping zones: {zones}")
    print(f"Available zones: {list(ZONAS_GEOGRAFICAS.keys())}")

    stats = run_scrapingbee_idealista(zones=zones, max_pages_per_zone=2)
    print(f"\nStats: {stats}")

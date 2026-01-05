"""
Milanuncios scraper using ScrapingBee API.

This scraper extracts real estate listings from Milanuncios.com
using ScrapingBee's stealth proxy to bypass GeeTest captcha.

Cost: 75 credits per page (stealth mode)
"""

import logging
import re
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode, quote

from scrapers.scrapingbee_base import ScrapingBeeClient

logger = logging.getLogger(__name__)


# Geographic zones configuration (same as Botasaurus scraper)
ZONAS_GEOGRAFICAS = {
    # LLEIDA
    'lleida_ciudad': {
        'nombre': 'Lleida Ciudad',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
    },
    'lleida_20km': {
        'nombre': 'Lleida (20 km)',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
        'distance': 20000,
    },
    'lleida_30km': {
        'nombre': 'Lleida (30 km)',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
        'distance': 30000,
    },
    'lleida_40km': {
        'nombre': 'Lleida (40 km)',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
        'distance': 40000,
    },
    'lleida_50km': {
        'nombre': 'Lleida (50 km)',
        'latitude': 41.6175899,
        'longitude': 0.6200146,
        'geoProvinceId': 25,
        'geolocationTerm': 'Lleida, Lerida',
        'distance': 50000,
    },
    'balaguer': {
        'nombre': 'Balaguer',
        'latitude': 41.7906,
        'longitude': 0.8056,
        'geoProvinceId': 25,
        'geolocationTerm': 'Balaguer, Lerida',
    },
    'mollerussa': {
        'nombre': 'Mollerussa',
        'latitude': 41.6311,
        'longitude': 0.8933,
        'geoProvinceId': 25,
        'geolocationTerm': 'Mollerussa, Lerida',
    },
    'tremp': {
        'nombre': 'Tremp',
        'latitude': 42.1656,
        'longitude': 0.8953,
        'geoProvinceId': 25,
        'geolocationTerm': 'Tremp, Lerida',
    },
    'tarrega': {
        'nombre': 'Tàrrega',
        'latitude': 41.6475,
        'longitude': 1.1394,
        'geoProvinceId': 25,
        'geolocationTerm': 'Tarrega, Lerida',
    },

    # TARRAGONA
    'tarragona_ciudad': {
        'nombre': 'Tarragona Ciudad',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
    },
    'tarragona_20km': {
        'nombre': 'Tarragona (20 km)',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
        'distance': 20000,
    },
    'tarragona_30km': {
        'nombre': 'Tarragona (30 km)',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
        'distance': 30000,
    },
    'tarragona_40km': {
        'nombre': 'Tarragona (40 km)',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
        'distance': 40000,
    },
    'tarragona_50km': {
        'nombre': 'Tarragona (50 km)',
        'latitude': 41.1188827,
        'longitude': 1.2444909,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tarragona, Tarragona',
        'distance': 50000,
    },

    # COSTA DAURADA
    'salou': {
        'nombre': 'Salou',
        'latitude': 41.0764,
        'longitude': 1.1416,
        'geoProvinceId': 43,
        'geolocationTerm': 'Salou, Tarragona',
    },
    'cambrils': {
        'nombre': 'Cambrils',
        'latitude': 41.0672,
        'longitude': 1.0597,
        'geoProvinceId': 43,
        'geolocationTerm': 'Cambrils, Tarragona',
    },
    'reus': {
        'nombre': 'Reus',
        'latitude': 41.1548,
        'longitude': 1.1078,
        'geoProvinceId': 43,
        'geolocationTerm': 'Reus, Tarragona',
    },
    'vendrell': {
        'nombre': 'El Vendrell',
        'latitude': 41.2186,
        'longitude': 1.5350,
        'geoProvinceId': 43,
        'geolocationTerm': 'El Vendrell, Tarragona',
    },
    'altafulla': {
        'nombre': 'Altafulla',
        'latitude': 41.1425,
        'longitude': 1.3761,
        'geoProvinceId': 43,
        'geolocationTerm': 'Altafulla, Tarragona',
    },
    'torredembarra': {
        'nombre': 'Torredembarra',
        'latitude': 41.1453,
        'longitude': 1.3975,
        'geoProvinceId': 43,
        'geolocationTerm': 'Torredembarra, Tarragona',
    },
    'miami_platja': {
        'nombre': 'Miami Platja',
        'latitude': 41.0217,
        'longitude': 0.9731,
        'geoProvinceId': 43,
        'geolocationTerm': 'Miami Platja, Tarragona',
    },
    'hospitalet_infant': {
        'nombre': "L'Hospitalet de l'Infant",
        'latitude': 40.9903,
        'longitude': 0.9194,
        'geoProvinceId': 43,
        'geolocationTerm': "L'Hospitalet de l'Infant, Tarragona",
    },
    'calafell': {
        'nombre': 'Calafell',
        'latitude': 41.2006,
        'longitude': 1.5678,
        'geoProvinceId': 43,
        'geolocationTerm': 'Calafell, Tarragona',
    },
    'coma_ruga': {
        'nombre': 'Coma-ruga',
        'latitude': 41.1817,
        'longitude': 1.5256,
        'geoProvinceId': 43,
        'geolocationTerm': 'Coma-ruga, Tarragona',
    },
    'valls': {
        'nombre': 'Valls',
        'latitude': 41.2861,
        'longitude': 1.2500,
        'geoProvinceId': 43,
        'geolocationTerm': 'Valls, Tarragona',
    },
    'montblanc': {
        'nombre': 'Montblanc',
        'latitude': 41.3761,
        'longitude': 1.1631,
        'geoProvinceId': 43,
        'geolocationTerm': 'Montblanc, Tarragona',
    },
    'vila_seca': {
        'nombre': 'Vila-seca',
        'latitude': 41.1097,
        'longitude': 1.1450,
        'geoProvinceId': 43,
        'geolocationTerm': 'Vila-seca, Tarragona',
    },

    # TERRES DE L'EBRE
    'tortosa': {
        'nombre': 'Tortosa',
        'latitude': 40.8125,
        'longitude': 0.5214,
        'geoProvinceId': 43,
        'geolocationTerm': 'Tortosa, Tarragona',
    },
    'amposta': {
        'nombre': 'Amposta',
        'latitude': 40.7131,
        'longitude': 0.5806,
        'geoProvinceId': 43,
        'geolocationTerm': 'Amposta, Tarragona',
    },
    'deltebre': {
        'nombre': 'Deltebre',
        'latitude': 40.7214,
        'longitude': 0.7183,
        'geoProvinceId': 43,
        'geolocationTerm': 'Deltebre, Tarragona',
    },
    'ametlla_mar': {
        'nombre': "L'Ametlla de Mar",
        'latitude': 40.8831,
        'longitude': 0.8036,
        'geoProvinceId': 43,
        'geolocationTerm': "L'Ametlla de Mar, Tarragona",
    },
    'sant_carles_rapita': {
        'nombre': 'Sant Carles de la Ràpita',
        'latitude': 40.6167,
        'longitude': 0.5917,
        'geoProvinceId': 43,
        'geolocationTerm': 'Sant Carles de la Rapita, Tarragona',
    },
}


class ScrapingBeeMilanuncios(ScrapingBeeClient):
    """
    Milanuncios scraper using ScrapingBee API.

    Uses stealth proxy to bypass GeeTest captcha protection.
    """

    PORTAL_NAME = 'milanuncios'
    BASE_URL = 'https://www.milanuncios.com'
    DEFAULT_DISTANCE = 20000

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        postgres_config: Optional[Dict[str, str]] = None,
        use_stealth: bool = True,
        max_pages_per_zone: int = 3,
    ):
        """
        Initialize Milanuncios scraper.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            zones: List of zones to scrape
            postgres_config: PostgreSQL config (auto-detected if None)
            use_stealth: Use stealth proxy (recommended for Milanuncios)
            max_pages_per_zone: Maximum pages to scrape per zone (budget control)
        """
        super().__init__(
            portal_name=self.PORTAL_NAME,
            tenant_id=tenant_id,
            use_stealth=use_stealth,
            postgres_config=postgres_config,
        )
        self.zones = zones or ['salou']
        self.max_pages_per_zone = max_pages_per_zone

    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        """Build Milanuncios search URL for a zone."""
        zona = ZONAS_GEOGRAFICAS.get(zona_key)
        if not zona:
            raise ValueError(f"Zone not found: {zona_key}")

        zone_distance = zona.get('distance', self.DEFAULT_DISTANCE)

        params = {
            'vendedor': 'part',  # Only particulares
            'latitude': zona['latitude'],
            'longitude': zona['longitude'],
            'distance': zone_distance,
            'geoProvinceId': zona['geoProvinceId'],
            'geolocationTerm': zona['geolocationTerm'],
            'orden': 'date',
            'fromSearch': 1,
            'desde': 5000,  # Min price filter (exclude rentals)
        }

        if page > 1:
            params['pagina'] = page

        return f"{self.BASE_URL}/inmobiliaria/?{urlencode(params, quote_via=quote)}"

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to float."""
        if not price_text:
            return None
        try:
            cleaned = re.sub(r'[€$\s\xa0]', '', price_text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            return float(cleaned)
        except:
            return None

    def _extract_listings_from_html(self, html: str, zona_key: str) -> List[Dict[str, Any]]:
        """Extract listing URLs and basic data from search results HTML."""
        listings = []

        # Check for blocking indicators
        if 'captcha' in html.lower() or 'geetest' in html.lower():
            logger.warning("Captcha detected in response")
            return []

        # Find listing URLs (format: /venta-de-*-ID.htm or /alquiler-de-*-ID.htm)
        url_pattern = r'href="(/(?:venta|alquiler)-de-[^"]+?-(\d{6,})\.htm)"'
        matches = re.findall(url_pattern, html)

        seen_ids = set()
        for path, anuncio_id in matches:
            if anuncio_id in seen_ids:
                continue
            seen_ids.add(anuncio_id)

            detail_url = f"{self.BASE_URL}{path}"
            zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

            listings.append({
                'anuncio_id': anuncio_id,
                'detail_url': detail_url,
                'url_anuncio': detail_url,
                'portal': self.PORTAL_NAME,
                'zona_busqueda': zona_info.get('nombre', zona_key),
                'zona_geografica': zona_info.get('nombre', zona_key),
            })

        logger.info(f"Found {len(listings)} listing URLs in search results")
        return listings

    def _scrape_detail_page(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape detail page to extract full listing data."""
        detail_url = listing['detail_url']

        html = self.fetch_page(
            detail_url,
            wait_for='[data-testid="AD_DETAIL"]',
        )

        if not html:
            return listing

        # Extract title from og:title (most reliable)
        title_match = re.search(
            r'(?:property="og:title"|name="og:title")\s+content="([^"]+)"',
            html, re.IGNORECASE
        )
        if not title_match:
            title_match = re.search(r'content="([^"]+)"[^>]*property="og:title"', html)
        if title_match:
            titulo = title_match.group(1).strip()
            # Remove "Milanuncios" suffix if present
            titulo = re.sub(r'\s*[-|]\s*[Mm]ilanuncios.*$', '', titulo)
            if titulo and len(titulo) > 5:
                listing['titulo'] = titulo

        # Extract description - Milanuncios specific patterns
        desc_patterns = [
            # Main description container
            r'<div[^>]*class="[^"]*ma-AdDescription[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*data-testid="AD_DESCRIPTION"[^>]*>(.*?)</div>',
            # Fallback to og:description
            r'(?:property="og:description"|name="description")\s+content="([^"]+)"',
            r'content="([^"]+)"[^>]*(?:property="og:description"|name="description")',
            # JSON-LD description
            r'"description"\s*:\s*"([^"]{50,})"',
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if desc_match:
                desc_text = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                # Skip if it's just a reference number
                if len(desc_text) > 50 and not desc_text.startswith('Descripción'):
                    listing['descripcion'] = desc_text[:2000]
                    break

        # Extract price from JSON-LD or structured data (most reliable)
        price_patterns = [
            r'"price"\s*:\s*"?(\d+)"?',
            r'"price"\s*:\s*\{\s*[^}]*"value"\s*:\s*"?(\d+)"?',
            r'data-price="(\d+)"',
            r'class="[^"]*[Pp]rice[^"]*"[^>]*>\s*(\d{1,3}(?:[.,]\d{3})*)',
        ]
        for pattern in price_patterns:
            price_match = re.search(pattern, html)
            if price_match:
                precio = self._parse_price(price_match.group(1))
                if precio and precio > 5000:
                    listing['precio'] = precio
                    break

        # Extract location from structured data or visible elements
        location_patterns = [
            r'"addressLocality"\s*:\s*"([^"]+)"',
            r'class="[^"]*[Ll]ocation[^"]*"[^>]*>\s*([^<]+)',
        ]
        for pattern in location_patterns:
            location_match = re.search(pattern, html)
            if location_match:
                listing['ubicacion'] = location_match.group(1).strip()
                break

        # Extract publication date (for analytics)
        # Milanuncios provides ISO 8601 dates in escaped JSON: \\\"publishDate\\\":\\\"2025-10-12T08:57:52Z\\\"
        publish_date_match = re.search(r'\\"publishDate\\":\\"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)\\"', html)
        if publish_date_match:
            listing['fecha_publicacion'] = publish_date_match.group(1)
            if not listing['fecha_publicacion'].endswith('Z'):
                listing['fecha_publicacion'] += 'Z'
            logger.debug(f"Publication date: {listing['fecha_publicacion']}")

        update_date_match = re.search(r'\\"updateDate\\":\\"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)\\"', html)
        if update_date_match:
            listing['fecha_actualizacion'] = update_date_match.group(1)
            if not listing['fecha_actualizacion'].endswith('Z'):
                listing['fecha_actualizacion'] += 'Z'

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

        # Extract features
        metros_match = re.search(r'(\d+)\s*m[²2]', html)
        if metros_match:
            listing['metros'] = int(metros_match.group(1))

        habs_match = re.search(r'(\d+)\s*(?:hab|dorm)', html, re.IGNORECASE)
        if habs_match:
            listing['habitaciones'] = int(habs_match.group(1))

        banos_match = re.search(r'(\d+)\s*(?:baño|wc)', html, re.IGNORECASE)
        if banos_match:
            listing['banos'] = int(banos_match.group(1))

        # Extract photos from images.milanuncios.com CDN
        # Milanuncios uses UUID-based URLs: https://images.milanuncios.com/api/v1/ma-ad-media-pro/images/{UUID}
        photo_patterns = [
            # New format (2025+): API-based image URLs
            r'https://images\.milanuncios\.com/api/v1/ma-ad-media-pro/images/([a-f0-9-]{36})(?:\?rule=[^"\'<>\s]*)?',
            # Legacy format (fallback)
            r'https://images-re\.milanuncios\.com/images/ads/([a-f0-9-]{36})(?:\?rule=[^"\'<>\s]*)?',
        ]

        all_photo_ids = set()
        for pattern in photo_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            all_photo_ids.update(matches)

        # Build full URLs with high-quality size rule
        unique_photos = []
        for photo_id in all_photo_ids:
            # Use new API format with detail_640x480 for good quality
            photo_url = f"https://images.milanuncios.com/api/v1/ma-ad-media-pro/images/{photo_id}?rule=detail_640x480"
            unique_photos.append(photo_url)

        listing['fotos'] = unique_photos[:10]

        # Extract seller name
        seller_match = re.search(
            r'class="[^"]*[Ss]eller[Nn]ame[^"]*"[^>]*>([^<]+)',
            html
        )
        if seller_match:
            listing['vendedor'] = seller_match.group(1).strip()
        else:
            listing['vendedor'] = 'Particular'

        listing['es_particular'] = True

        return listing

    def scrape_zone(self, zona_key: str) -> List[Dict[str, Any]]:
        """Scrape all listings from a zone."""
        all_listings = []
        zona_info = ZONAS_GEOGRAFICAS.get(zona_key, {})

        logger.info(f"Scraping zone: {zona_info.get('nombre', zona_key)}")

        for page in range(1, self.max_pages_per_zone + 1):
            search_url = self.build_search_url(zona_key, page)
            logger.info(f"Scraping page {page} of {zona_key}")

            html = self.fetch_page(
                search_url,
                wait_for='[data-testid="AD_CARD"]',
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
            skipped = 0
            for i, listing in enumerate(basic_listings[:15]):  # Limit per page
                url = listing.get('detail_url') or listing.get('url_anuncio')

                # Skip if URL already exists in database
                if url and self.url_exists_in_db(url):
                    skipped += 1
                    self.stats['listings_skipped'] += 1
                    self.stats['credits_saved'] += 75
                    logger.debug(f"Skipping existing URL: {url[:50]}...")
                    continue

                logger.info(f"Detail page {i+1}/{len(basic_listings[:15])} (skipped {skipped})")

                enriched = self._scrape_detail_page(listing)
                self.stats['listings_found'] += 1
                all_listings.append(enriched)

                # Small delay between requests
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
            self.save_to_postgres(listing)

        logger.info(f"Scraping complete. Stats: {self.get_stats()}")
        return self.get_stats()


def run_scrapingbee_milanuncios(
    zones: List[str] = None,
    tenant_id: int = 1,
    max_pages_per_zone: int = 3,
) -> Dict[str, Any]:
    """
    Convenience function to run ScrapingBee Milanuncios scraper.

    Args:
        zones: List of zones to scrape
        tenant_id: Tenant ID
        max_pages_per_zone: Max pages per zone (budget control)

    Returns:
        Scraping statistics
    """
    with ScrapingBeeMilanuncios(
        zones=zones or ['salou', 'cambrils'],
        tenant_id=tenant_id,
        max_pages_per_zone=max_pages_per_zone,
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

    stats = run_scrapingbee_milanuncios(zones=zones, max_pages_per_zone=2)
    print(f"\nStats: {stats}")

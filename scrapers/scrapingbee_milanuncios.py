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
            wait_for='.AdDetail',  # Wait for detail content
        )

        if not html:
            return listing

        # Extract title - multiple patterns for Milanuncios
        title_patterns = [
            # og:title meta tag is the cleanest source
            r'property="og:title"\s+content="([^"]+)"',
            r'content="([^"]+)"\s+property="og:title"',
            # H1 tag (may have nested content)
            r'<h1[^>]*>(.*?)</h1>',
            # Clean title tag (remove "Milanuncios - " prefix)
            r'<title>(?:Milanuncios\s*[-:]\s*)?([^<]+)</title>',
        ]
        for pattern in title_patterns:
            title_match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if title_match:
                titulo = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                # Clean up extra characters at end
                titulo = re.sub(r'\d$', '', titulo).strip()
                if titulo and len(titulo) > 5 and 'milanuncios' not in titulo.lower():
                    listing['titulo'] = titulo
                    break

        # Extract description - multiple patterns
        desc_patterns = [
            r'class="[^"]*AdDetail-description[^"]*"[^>]*>(.*?)</div>',
            r'class="[^"]*[Dd]escription[^"]*"[^>]*>(.*?)</(?:div|section)',
            r'"description"\s*:\s*"([^"]{50,})"',  # JSON-LD
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, html, re.DOTALL)
            if desc_match:
                desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1))
                desc_text = desc_text.strip()
                if len(desc_text) > 30:
                    listing['descripcion'] = desc_text[:2000]
                    break

        # Extract price - multiple patterns for Milanuncios
        # Milanuncios uses format: 800.000&nbsp;€ or 800.000 €
        price_patterns = [
            # ma-AdPrice section with &nbsp; before euro
            r'class="[^"]*ma-AdPrice[^"]*"[^>]*>\s*(\d{1,3}(?:\.\d{3})*)(?:&nbsp;|\s)*(?:€|&euro;)',
            # Any price followed by &nbsp;€
            r'(\d{1,3}(?:\.\d{3})*)(?:&nbsp;|\xa0|\s)*(?:€|&euro;|EUR)',
            # JSON format
            r'"price"\s*:\s*["\']?(\d+(?:\.\d+)?)',
            r'"price"\s*:\s*\{\s*"value"\s*:\s*(\d+)',
            # data-price attribute
            r'data-price="(\d+)"',
        ]
        for pattern in price_patterns:
            price_match = re.search(pattern, html)
            if price_match:
                precio = self._parse_price(price_match.group(1))
                if precio and precio > 1000:  # Sanity check - real estate > 1000€
                    listing['precio'] = precio
                    break

        # Extract location
        location_match = re.search(
            r'class="[^"]*[Ll]ocation[^"]*"[^>]*>([^<]+)',
            html
        )
        if location_match:
            listing['ubicacion'] = location_match.group(1).strip()

        # Extract phone
        phones = self.extract_phones_from_html(html)
        if phones:
            listing['telefono'] = phones[0]
            listing['telefono_norm'] = self.normalize_phone(phones[0])

        # Also try tel: links
        tel_match = re.search(r'tel:(\d{9,})', html)
        if tel_match and 'telefono' not in listing:
            listing['telefono'] = tel_match.group(1)
            listing['telefono_norm'] = self.normalize_phone(tel_match.group(1))

        # Extract features (metros, habitaciones)
        metros_match = re.search(r'(\d+)\s*m[²2]', html)
        if metros_match:
            listing['metros'] = int(metros_match.group(1))

        habs_match = re.search(r'(\d+)\s*(?:hab|dorm)', html, re.IGNORECASE)
        if habs_match:
            listing['habitaciones'] = int(habs_match.group(1))

        banos_match = re.search(r'(\d+)\s*(?:baño|wc)', html, re.IGNORECASE)
        if banos_match:
            listing['banos'] = int(banos_match.group(1))

        # Extract photos (Milanuncios CDN)
        photos = re.findall(
            r'(https://[^"\']+milanuncios[^"\']+\.(?:jpg|jpeg|png|webp))',
            html, re.IGNORECASE
        )
        unique_photos = []
        seen = set()
        for photo in photos:
            photo_clean = re.sub(r'\?.*$', '', photo)
            if photo_clean not in seen and 'thumbnail' not in photo.lower():
                unique_photos.append(photo)
                seen.add(photo_clean)
        listing['fotos'] = unique_photos[:10]

        # Extract seller name
        seller_match = re.search(
            r'class="[^"]*AdDetail-sellerName[^"]*"[^>]*>([^<]+)',
            html
        )
        if seller_match:
            listing['vendedor'] = seller_match.group(1).strip()
        else:
            listing['vendedor'] = 'Particular'  # URL filter ensures this

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

            # Scrape each detail page
            for i, listing in enumerate(basic_listings[:15]):  # Limit per page
                logger.info(f"Detail page {i+1}/{len(basic_listings[:15])}")

                enriched = self._scrape_detail_page(listing)
                self.stats['listings_found'] += 1
                all_listings.append(enriched)

                # Small delay between requests
                time.sleep(0.5)

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

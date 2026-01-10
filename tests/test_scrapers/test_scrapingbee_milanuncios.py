"""
Integration tests for Milanuncios ScrapingBee scraper.

Tests scraper functionality with mock responses.
No real web connections or API calls.
"""
import pytest
import re
import json
from unittest.mock import MagicMock, patch


class TestMilanunciosScraper:
    """Tests for ScrapingBeeMilanuncios scraper."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {'SCRAPINGBEE_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def milanuncios_scraper(self, mock_env):
        """Create Milanuncios scraper with mocked connections."""
        with patch('scrapers.scrapingbee_base.psycopg2'):
            with patch('scrapers.scrapingbee_base.get_postgres_config') as mock_pg:
                mock_pg.return_value = {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'test_db',
                    'user': 'test',
                    'password': 'test',
                }
                from scrapers.scrapingbee_milanuncios import ScrapingBeeMilanuncios
                scraper = ScrapingBeeMilanuncios(
                    tenant_id=1,
                    zones=['salou'],
                    use_stealth=True,
                    max_pages_per_zone=2,
                )
                scraper.postgres_conn = None
                return scraper

    @pytest.fixture
    def mock_search_html(self):
        """Mock Milanuncios search page HTML."""
        return '''
        <html>
        <body>
            <div data-testid="AD_CARD">
                <a href="/venta-de-piso-salou-123456.htm">Piso en Salou</a>
            </div>
            <div data-testid="AD_CARD">
                <a href="/venta-de-casa-cambrils-234567.htm">Casa en Cambrils</a>
            </div>
            <div data-testid="AD_CARD">
                <a href="/venta-de-piso-tarragona-345678.htm">Piso en Tarragona</a>
            </div>
        </body>
        </html>
        '''

    @pytest.fixture
    def mock_detail_html(self):
        """Mock Milanuncios detail page HTML."""
        return '''
        <html>
        <head>
            <meta property="og:title" content="Piso en venta Reus centro - Milanuncios" />
            <meta property="og:description" content="Vendo piso por traslado. 75m2, 2 habitaciones." />
            <script type="application/ld+json">
            {
                "@type": "Product",
                "name": "Piso en venta Reus",
                "offers": {
                    "price": "120000",
                    "priceCurrency": "EUR"
                }
            }
            </script>
        </head>
        <body>
            <div data-testid="AD_DETAIL">
                <h1>Piso en venta Reus centro</h1>
                <div class="ma-AdDescription">
                    Vendo piso por traslado. 75m2, 2 habitaciones.
                    Interesados contactar 666777888. No agencias.
                </div>
                <span>\\"publishDate\\":\\"2026-01-05T10:30:00Z\\"</span>
                <img src="https://images.milanuncios.com/api/v1/ma-ad-media-pro/images/abc12345-1234-5678-abcd-123456789012" />
            </div>
        </body>
        </html>
        '''

    def test_build_search_url(self, milanuncios_scraper):
        """Should build correct search URL with geolocation params."""
        url = milanuncios_scraper.build_search_url('salou')
        assert 'milanuncios.com' in url
        assert 'inmobiliaria' in url
        assert 'vendedor=part' in url  # particulares only
        assert 'latitude=' in url
        assert 'longitude=' in url

    def test_build_search_url_with_pagination(self, milanuncios_scraper):
        """Should add page parameter for page > 1."""
        url = milanuncios_scraper.build_search_url('salou', page=2)
        assert 'pagina=2' in url

    def test_build_search_url_raises_for_invalid_zone(self, milanuncios_scraper):
        """Should raise ValueError for unknown zone."""
        with pytest.raises(ValueError, match="Zone not found"):
            milanuncios_scraper.build_search_url('zona_inexistente')

    def test_extract_listings_from_search(self, milanuncios_scraper, mock_search_html):
        """Should extract listing URLs from search results."""
        listings = milanuncios_scraper._extract_listings_from_html(mock_search_html, 'salou')
        assert len(listings) == 3

        # Check structure
        for listing in listings:
            assert 'anuncio_id' in listing
            assert 'detail_url' in listing
            assert 'portal' in listing
            assert listing['portal'] == 'milanuncios'

    def test_extract_listings_detects_captcha(self, milanuncios_scraper):
        """Should return empty list when captcha is detected."""
        html_with_captcha = '<html><body>GeeTest captcha required</body></html>'
        listings = milanuncios_scraper._extract_listings_from_html(html_with_captcha, 'salou')
        assert listings == []

    def test_extract_price_from_json_ld(self, mock_detail_html):
        """Should extract price from JSON-LD structured data."""
        json_ld_match = re.search(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            mock_detail_html, re.DOTALL
        )
        assert json_ld_match is not None

        data = json.loads(json_ld_match.group(1))
        assert data['offers']['price'] == "120000"

    def test_extract_title_from_og_meta(self, mock_detail_html):
        """Should extract title from og:title meta tag."""
        title_match = re.search(
            r'property="og:title"\s+content="([^"]+)"',
            mock_detail_html, re.IGNORECASE
        )
        assert title_match is not None
        assert 'Piso en venta Reus' in title_match.group(1)

    def test_extract_publication_date(self, mock_detail_html):
        """Should extract publication date from escaped JSON."""
        date_match = re.search(r'\\"publishDate\\":\\"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)\\"', mock_detail_html)
        assert date_match is not None
        assert date_match.group(1) == '2026-01-05T10:30:00Z'

    def test_extract_phone_from_description(self, milanuncios_scraper, mock_detail_html):
        """Should extract phone from description."""
        desc_match = re.search(
            r'<div[^>]*class="[^"]*ma-AdDescription[^"]*"[^>]*>(.*?)</div>',
            mock_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert desc_match is not None

        description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        phone = milanuncios_scraper.extract_phone_from_description(description)
        assert phone == "666777888"

    def test_extract_photos_from_cdn(self, mock_detail_html):
        """Should extract photos from Milanuncios CDN."""
        photo_pattern = r'https://images\.milanuncios\.com/api/v1/ma-ad-media-pro/images/([a-f0-9-]{36})'
        matches = re.findall(photo_pattern, mock_detail_html, re.IGNORECASE)
        assert len(matches) == 1

    def test_zones_config_has_salou(self):
        """Should have Salou in zones configuration."""
        from scrapers.scrapingbee_milanuncios import ZONAS_GEOGRAFICAS
        assert 'salou' in ZONAS_GEOGRAFICAS
        assert ZONAS_GEOGRAFICAS['salou']['nombre'] == 'Salou'
        assert 'latitude' in ZONAS_GEOGRAFICAS['salou']
        assert 'longitude' in ZONAS_GEOGRAFICAS['salou']

    def test_zones_config_has_distance_variants(self):
        """Should have zones with different distance radii."""
        from scrapers.scrapingbee_milanuncios import ZONAS_GEOGRAFICAS
        assert 'lleida_20km' in ZONAS_GEOGRAFICAS
        assert 'lleida_30km' in ZONAS_GEOGRAFICAS
        assert ZONAS_GEOGRAFICAS['lleida_20km'].get('distance') == 20000

    def test_portal_name_is_correct(self, milanuncios_scraper):
        """Should have correct portal name."""
        assert milanuncios_scraper.PORTAL_NAME == 'milanuncios'


class TestMilanunciosPhoneExtraction:
    """Tests for phone extraction from Milanuncios descriptions."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {'SCRAPINGBEE_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def milanuncios_scraper(self, mock_env):
        """Create scraper for phone tests."""
        with patch('scrapers.scrapingbee_base.psycopg2'):
            with patch('scrapers.scrapingbee_base.get_postgres_config') as mock_pg:
                mock_pg.return_value = {'host': 'localhost', 'port': 5432, 'database': 'test', 'user': 'test', 'password': 'test'}
                from scrapers.scrapingbee_milanuncios import ScrapingBeeMilanuncios
                scraper = ScrapingBeeMilanuncios(tenant_id=1, zones=['salou'])
                scraper.postgres_conn = None
                return scraper

    def test_extract_phone_from_text(self, milanuncios_scraper):
        """Should extract phone from text."""
        desc = "Contactar al 612345678"
        phone = milanuncios_scraper.extract_phone_from_description(desc)
        assert phone == "612345678"

    def test_normalize_phone_removes_prefix(self, milanuncios_scraper):
        """Should normalize phone removing country code."""
        assert milanuncios_scraper.normalize_phone("+34612345678") == "612345678"
        assert milanuncios_scraper.normalize_phone("0034612345678") == "612345678"

    def test_parse_price(self, milanuncios_scraper):
        """Should parse price text to float."""
        assert milanuncios_scraper._parse_price("120.000") == 120000.0
        assert milanuncios_scraper._parse_price("150000") == 150000.0
        assert milanuncios_scraper._parse_price("99.500 €") == 99500.0


class TestScrapingBeeStats:
    """Tests for ScrapingBee credit tracking."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {'SCRAPINGBEE_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def milanuncios_scraper(self, mock_env):
        """Create scraper with mocked connections."""
        with patch('scrapers.scrapingbee_base.psycopg2'):
            with patch('scrapers.scrapingbee_base.get_postgres_config') as mock_pg:
                mock_pg.return_value = {'host': 'localhost', 'port': 5432, 'database': 'test', 'user': 'test', 'password': 'test'}
                from scrapers.scrapingbee_milanuncios import ScrapingBeeMilanuncios
                scraper = ScrapingBeeMilanuncios(tenant_id=1, zones=['salou'], use_stealth=True)
                scraper.postgres_conn = None
                return scraper

    def test_initial_stats_are_zero(self, milanuncios_scraper):
        """Should start with zero stats."""
        stats = milanuncios_scraper.get_stats()
        assert stats['requests'] == 0
        assert stats['credits_used'] == 0
        assert stats['listings_found'] == 0

    def test_stats_include_portal_info(self, milanuncios_scraper):
        """Should include portal and tenant info in stats."""
        stats = milanuncios_scraper.get_stats()
        assert stats['portal'] == 'milanuncios'
        assert stats['tenant_id'] == 1

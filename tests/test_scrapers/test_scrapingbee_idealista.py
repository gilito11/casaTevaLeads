"""
Integration tests for Idealista ScrapingBee scraper.

Tests scraper functionality with mock responses.
No real web connections or API calls.
"""
import pytest
import re
from unittest.mock import MagicMock, patch


class TestIdealistaScraper:
    """Tests for ScrapingBeeIdealista scraper."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {'SCRAPINGBEE_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def idealista_scraper(self, mock_env):
        """Create Idealista scraper with mocked connections."""
        with patch('scrapers.scrapingbee_base.psycopg2'):
            with patch('scrapers.scrapingbee_base.get_postgres_config') as mock_pg:
                mock_pg.return_value = {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'test_db',
                    'user': 'test',
                    'password': 'test',
                }
                from scrapers.scrapingbee_idealista import ScrapingBeeIdealista
                scraper = ScrapingBeeIdealista(
                    tenant_id=1,
                    zones=['salou'],
                    use_stealth=True,
                    max_pages_per_zone=2,
                    only_particulares=True,
                )
                scraper.postgres_conn = None
                return scraper

    @pytest.fixture
    def mock_search_html(self):
        """Mock Idealista search page HTML with proper spacing for agency detection."""
        # Need >500 chars between particulares and agency section for agency detection to work
        padding = "<!-- spacing -->" * 50
        return f'''<html>
<body>
<div class="items-list">
<article class="item particular">
<a href="/inmueble/12345678/" class="item-link">Piso en Salou</a>
<span class="price">185.000</span>
</article>
<article class="item particular">
<a href="/inmueble/23456789/" class="item-link">Casa en Cambrils</a>
<span class="price">220.000</span>
</article>
{padding}
<article class="item agency">
<span class="professional-name">Agencia XYZ</span>
<a href="/inmueble/34567890/" class="item-link-professional">Agency listing</a>
</article>
</div>
</body>
</html>'''

    @pytest.fixture
    def mock_detail_html(self):
        """Mock Idealista detail page HTML."""
        return '''
        <html>
        <head><title>Casa en venta en Tarragona</title></head>
        <body>
            <div class="detail-info">
                <h1 class="main-info__title">Casa adosada en venta en Tarragona centro</h1>
                <span class="main-info__title-minor">Tarragona, El Serrallo</span>
                <span class="info-data-price">275.000&euro;</span>
                <div class="info-features">
                    <span>120 m2</span>
                    <span>4 hab.</span>
                    <span>2 banos</span>
                </div>
                <div class="comment">
                    Casa adosada en excelente estado. Garaje incluido.
                    Contacto: 677889900. No agencias.
                </div>
                <span class="energy">B</span>
                <img src="https://img3.idealista.com/blur/HOME_WEB_L/0/id.pro.es.image.master/1234567890.jpg" />
            </div>
        </body>
        </html>
        '''

    def test_build_search_url(self, idealista_scraper):
        """Should build correct search URL."""
        url = idealista_scraper.build_search_url('salou')
        assert 'idealista.com' in url
        assert 'venta-viviendas' in url
        assert 'salou-tarragona' in url

    def test_build_search_url_with_pagination(self, idealista_scraper):
        """Should add page suffix for page > 1."""
        url = idealista_scraper.build_search_url('salou', page=2)
        assert 'pagina-2' in url

    def test_build_search_url_raises_for_invalid_zone(self, idealista_scraper):
        """Should raise ValueError for unknown zone."""
        with pytest.raises(ValueError, match="Zone not found"):
            idealista_scraper.build_search_url('zona_inexistente')

    def test_extract_listings_from_search(self, idealista_scraper, mock_search_html):
        """Should extract listing URLs from search results."""
        listings = idealista_scraper._extract_listings_from_html(mock_search_html, 'salou')

        # Should skip agency listing when only_particulares=True
        assert len(listings) == 2

        for listing in listings:
            assert 'anuncio_id' in listing
            assert 'detail_url' in listing
            assert listing['portal'] == 'idealista'

    def test_extract_listings_filters_agencies_in_search(self, idealista_scraper, mock_search_html):
        """Should filter agency listings from search results."""
        listings = idealista_scraper._extract_listings_from_html(mock_search_html, 'salou')

        # Agency listing (34567890) should be filtered out
        listing_ids = [l['anuncio_id'] for l in listings]
        assert '34567890' not in listing_ids

    def test_extract_price_from_info_data(self, mock_detail_html):
        """Should extract price from info-data-price class."""
        price_match = re.search(
            r'class="[^"]*info-data-price[^"]*"[^>]*>([^<]+)',
            mock_detail_html, re.IGNORECASE
        )
        assert price_match is not None

        price_str = re.sub(r'[^\d]', '', price_match.group(1))
        assert int(price_str) == 275000

    def test_extract_features_from_info_section(self, mock_detail_html):
        """Should extract features from info-features section."""
        info_features = re.search(
            r'class="[^"]*info-features[^"]*"[^>]*>(.*?)</div>',
            mock_detail_html, re.DOTALL
        )
        assert info_features is not None

        features_text = info_features.group(1)

        # Metros
        metros_match = re.search(r'(\d+)\s*m2', features_text)
        assert metros_match is not None
        assert int(metros_match.group(1)) == 120

        # Habitaciones
        habs_match = re.search(r'(\d+)\s*hab', features_text, re.IGNORECASE)
        assert habs_match is not None
        assert int(habs_match.group(1)) == 4

    def test_extract_location(self, mock_detail_html):
        """Should extract location from title-minor class."""
        location_match = re.search(
            r'class="[^"]*main-info__title-minor[^"]*"[^>]*>([^<]+)',
            mock_detail_html
        )
        assert location_match is not None
        assert 'Tarragona' in location_match.group(1)

    def test_extract_phone_from_description(self, idealista_scraper, mock_detail_html):
        """Should extract phone from description."""
        desc_match = re.search(
            r'class="[^"]*comment[^"]*"[^>]*>(.*?)</div>',
            mock_detail_html, re.DOTALL
        )
        assert desc_match is not None

        description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        phone = idealista_scraper.extract_phone_from_description(description)
        assert phone == "677889900"

    def test_extract_energy_certificate(self, mock_detail_html):
        """Should extract energy certificate rating."""
        energy_match = re.search(
            r'class="[^"]*energy[^"]*"[^>]*>([A-G])</span>',
            mock_detail_html, re.IGNORECASE
        )
        assert energy_match is not None
        assert energy_match.group(1).upper() == 'B'

    def test_extract_photos_from_cdn(self, mock_detail_html):
        """Should extract photos from Idealista CDN."""
        photos = re.findall(
            r'(https://img\d*\.idealista\.com/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp))',
            mock_detail_html, re.IGNORECASE
        )
        assert len(photos) == 1
        assert 'idealista.com' in photos[0]

    def test_zones_config_has_salou(self):
        """Should have Salou in zones configuration."""
        from scrapers.scrapingbee_idealista import ZONAS_GEOGRAFICAS
        assert 'salou' in ZONAS_GEOGRAFICAS
        assert ZONAS_GEOGRAFICAS['salou']['nombre'] == 'Salou'
        assert 'url_path' in ZONAS_GEOGRAFICAS['salou']

    def test_zones_config_has_composite_zones(self):
        """Should have composite zones (comarcas) in configuration."""
        from scrapers.scrapingbee_idealista import ZONAS_GEOGRAFICAS
        assert 'costa_daurada' in ZONAS_GEOGRAFICAS
        assert 'composite' in ZONAS_GEOGRAFICAS['costa_daurada']
        assert 'salou' in ZONAS_GEOGRAFICAS['costa_daurada']['composite']

    def test_zones_config_has_provinces(self):
        """Should have province zones in configuration."""
        from scrapers.scrapingbee_idealista import ZONAS_GEOGRAFICAS
        assert 'tarragona_provincia' in ZONAS_GEOGRAFICAS
        assert 'lleida_provincia' in ZONAS_GEOGRAFICAS

    def test_portal_name_is_correct(self, idealista_scraper):
        """Should have correct portal name."""
        assert idealista_scraper.PORTAL_NAME == 'idealista'


class TestIdealistaPhoneExtraction:
    """Tests for phone extraction from Idealista descriptions."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {'SCRAPINGBEE_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def idealista_scraper(self, mock_env):
        """Create scraper for phone tests."""
        with patch('scrapers.scrapingbee_base.psycopg2'):
            with patch('scrapers.scrapingbee_base.get_postgres_config') as mock_pg:
                mock_pg.return_value = {'host': 'localhost', 'port': 5432, 'database': 'test', 'user': 'test', 'password': 'test'}
                from scrapers.scrapingbee_idealista import ScrapingBeeIdealista
                scraper = ScrapingBeeIdealista(tenant_id=1, zones=['salou'])
                scraper.postgres_conn = None
                return scraper

    def test_extract_phone_from_text(self, idealista_scraper):
        """Should extract phone from text."""
        desc = "Contactar al 612345678"
        phone = idealista_scraper.extract_phone_from_description(desc)
        assert phone == "612345678"

    def test_normalize_phone_removes_prefix(self, idealista_scraper):
        """Should normalize phone removing country code."""
        assert idealista_scraper.normalize_phone("+34612345678") == "612345678"
        assert idealista_scraper.normalize_phone("0034612345678") == "612345678"

    def test_parse_price(self, idealista_scraper):
        """Should parse price text to float."""
        assert idealista_scraper._parse_price("275.000") == 275000.0
        assert idealista_scraper._parse_price("150000") == 150000.0


class TestIdealistaBlockingDetection:
    """Tests for DataDome blocking detection."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict('os.environ', {'SCRAPINGBEE_API_KEY': 'test_api_key'}):
            yield

    @pytest.fixture
    def idealista_scraper(self, mock_env):
        """Create scraper for blocking tests."""
        with patch('scrapers.scrapingbee_base.psycopg2'):
            with patch('scrapers.scrapingbee_base.get_postgres_config') as mock_pg:
                mock_pg.return_value = {'host': 'localhost', 'port': 5432, 'database': 'test', 'user': 'test', 'password': 'test'}
                from scrapers.scrapingbee_idealista import ScrapingBeeIdealista
                scraper = ScrapingBeeIdealista(tenant_id=1, zones=['salou'])
                scraper.postgres_conn = None
                return scraper

    def test_detects_access_denied(self, idealista_scraper):
        """Should detect access denied blocking."""
        html_blocked = '<html><title>Access Denied</title><body>You have been blocked</body></html>'
        listings = idealista_scraper._extract_listings_from_html(html_blocked, 'salou')
        assert listings == []

    def test_normal_page_not_blocked(self, idealista_scraper):
        """Should not falsely detect blocking on normal pages."""
        # Normal page with "blocked" in CSS class name (common pattern)
        html_normal = '''
        <html>
        <body>
            <style>.blocked-element { display: none; }</style>
            <a href="/inmueble/12345678/">Listing</a>
        </body>
        </html>
        '''
        listings = idealista_scraper._extract_listings_from_html(html_normal, 'salou')
        # Should find the listing, not return empty due to false positive
        assert len(listings) == 1

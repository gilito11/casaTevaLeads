"""
Integration tests for Fotocasa Botasaurus scraper.

Tests scraper functionality with mock HTML responses.
No real web connections or browser automation.
"""
import pytest
import re
from unittest.mock import MagicMock, patch

# Check if botasaurus is available
try:
    import botasaurus
    BOTASAURUS_AVAILABLE = True
except ImportError:
    BOTASAURUS_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not BOTASAURUS_AVAILABLE,
    reason="Botasaurus module not installed"
)


class TestFotocasaScraper:
    """Tests for BotasaurusFotocasa scraper."""

    @pytest.fixture
    def fotocasa_scraper(self):
        """Create Fotocasa scraper with mocked browser."""
        with patch('scrapers.botasaurus_base.psycopg2'):
            from scrapers.botasaurus_fotocasa import BotasaurusFotocasa
            scraper = BotasaurusFotocasa(
                tenant_id=1,
                zones=['salou'],
                postgres_config=None,
                headless=True,
                only_private=True,
            )
            scraper.postgres_conn = None
            return scraper

    @pytest.fixture
    def mock_search_html(self):
        """Mock Fotocasa search page HTML."""
        return '''
        <html>
        <body>
            <div class="search-results">
                <a href="/es/comprar/vivienda/salou/centro/1234567/d?from=pl">Piso 1</a>
                <a href="/es/comprar/vivienda/salou/playa/2345678/d?from=pl">Piso 2</a>
                <a href="/es/comprar/vivienda/salou/norte/3456789/d?from=pl">Piso 3</a>
            </div>
            <div>Mira algunos de los anuncios de inmobiliarias</div>
            <a href="/es/comprar/vivienda/salou/agency/9999999/d?from=pl">Agency listing</a>
        </body>
        </html>
        '''

    @pytest.fixture
    def mock_detail_html(self):
        """Mock Fotocasa detail page HTML."""
        return '''
        <html>
        <head><title>Piso en venta en Salou</title></head>
        <body>
            <h1>Piso en venta en Salou centro</h1>
            <span class="re-DetailHeader-price">189.000 &euro;</span>
            <span><span>95</span> m2</span>
            <span><span>3</span> hab</span>
            <div class="re-DetailDescription">
                Piso reformado cerca del puerto. Para visitas llamar 634567890.
                Tres habitaciones, dos banos, terraza con vistas al mar.
            </div>
            <span>Anuncio Particular</span>
            <img src="https://static.fotocasa.es/images/uuid-12345/photo1.jpg" />
            <img src="https://static.fotocasa.es/images/uuid-67890/photo2.jpg" />
        </body>
        </html>
        '''

    def test_build_url_for_city(self, fotocasa_scraper):
        """Should build correct URL for a city zone."""
        url = fotocasa_scraper.build_url('salou')
        assert 'fotocasa.es' in url
        assert 'salou' in url
        assert 'particulares' in url

    def test_build_url_with_pagination(self, fotocasa_scraper):
        """Should add page parameter for page > 1."""
        url = fotocasa_scraper.build_url('salou', page=2)
        assert 'pageNumber=2' in url

    def test_build_url_raises_for_invalid_zone(self, fotocasa_scraper):
        """Should raise ValueError for unknown zone."""
        with pytest.raises(ValueError, match="Zone not found"):
            fotocasa_scraper.build_url('zona_inexistente')

    def test_extract_price_from_header(self, mock_detail_html):
        """Should extract price from re-DetailHeader-price class."""
        price_header = re.search(
            r'class="[^"]*re-DetailHeader-price[^"]*"[^>]*>([^<]+)',
            mock_detail_html, re.IGNORECASE
        )
        assert price_header is not None

        price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)', price_header.group(1))
        assert price_match is not None

        price_str = price_match.group(1).replace('.', '')
        assert float(price_str) == 189000.0

    def test_extract_metros_from_span(self, mock_detail_html):
        """Should extract metros from span structure."""
        metros_span = re.search(r'<span[^>]*>\s*<span>(\d+)</span>\s*m2', mock_detail_html)
        assert metros_span is not None
        assert int(metros_span.group(1)) == 95

    def test_extract_habitaciones_from_span(self, mock_detail_html):
        """Should extract habitaciones from span structure."""
        habs_span = re.search(r'<span[^>]*>\s*<span>(\d+)</span>\s*hab', mock_detail_html, re.IGNORECASE)
        assert habs_span is not None
        assert int(habs_span.group(1)) == 3

    def test_detect_particular_listing(self, mock_detail_html):
        """Should detect particular listing indicator."""
        is_particular = 'anuncio particular' in mock_detail_html.lower()
        assert is_particular is True

    def test_extract_phone_from_description(self, fotocasa_scraper, mock_detail_html):
        """Should extract phone from description text."""
        desc_match = re.search(
            r'class="[^"]*re-DetailDescription[^"]*"[^>]*>(.*?)</div>',
            mock_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert desc_match is not None

        description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        phone = fotocasa_scraper.extract_phone_from_description(description)
        assert phone == "634567890"

    def test_extract_photos_from_html(self, mock_detail_html):
        """Should extract Fotocasa CDN photo URLs."""
        photos = re.findall(
            r'(https?://static\.fotocasa\.es/images/[^"\'<>\s]+)',
            mock_detail_html, re.IGNORECASE
        )
        assert len(photos) == 2
        assert all('static.fotocasa.es' in p for p in photos)

    def test_filter_agency_listings_from_search(self, mock_search_html):
        """Should find divider and limit search to particulares section."""
        html_lower = mock_search_html.lower()

        divider_pos = html_lower.find('anuncios de inmobiliarias')
        assert divider_pos > 0

        particulares_html = mock_search_html[:divider_pos]

        # Should find 3 particular listings before divider
        links = re.findall(r'href="(/es/comprar/vivienda/[^"]+/\d{7,}/d)', particulares_html)
        assert len(links) == 3

        # Agency listing should not be in particulares section
        assert '9999999' not in particulares_html

    def test_zones_config_has_salou(self):
        """Should have Salou in zones configuration."""
        from scrapers.botasaurus_fotocasa import ZONAS_GEOGRAFICAS
        assert 'salou' in ZONAS_GEOGRAFICAS
        assert ZONAS_GEOGRAFICAS['salou']['nombre'] == 'Salou'

    def test_zones_config_has_composite_zones(self):
        """Should have composite zones (comarcas) in configuration."""
        from scrapers.botasaurus_fotocasa import ZONAS_GEOGRAFICAS
        assert 'costa_daurada' in ZONAS_GEOGRAFICAS
        assert 'composite' in ZONAS_GEOGRAFICAS['costa_daurada']
        assert 'salou' in ZONAS_GEOGRAFICAS['costa_daurada']['composite']

    def test_portal_name_is_correct(self, fotocasa_scraper):
        """Should have correct portal name."""
        assert fotocasa_scraper.PORTAL_NAME == 'fotocasa'


class TestFotocasaPhoneExtraction:
    """Tests for phone extraction from Fotocasa descriptions."""

    @pytest.fixture
    def fotocasa_scraper(self):
        """Create scraper for phone tests."""
        with patch('scrapers.botasaurus_base.psycopg2'):
            from scrapers.botasaurus_fotocasa import BotasaurusFotocasa
            scraper = BotasaurusFotocasa(
                tenant_id=1,
                zones=['salou'],
                postgres_config=None,
            )
            scraper.postgres_conn = None
            return scraper

    def test_extract_phone_with_spaces(self, fotocasa_scraper):
        """Should extract phone with spaces."""
        desc = "Llamar al 612 345 678"
        phone = fotocasa_scraper.extract_phone_from_description(desc)
        assert phone == "612345678"

    def test_extract_phone_with_dots(self, fotocasa_scraper):
        """Should extract phone with dots."""
        desc = "Contacto: 612.345.678"
        phone = fotocasa_scraper.extract_phone_from_description(desc)
        assert phone == "612345678"

    def test_extract_phone_rejects_fake_numbers(self, fotocasa_scraper):
        """Should reject fake/repeated digit numbers."""
        desc = "Llamar 666666666 para info"
        phone = fotocasa_scraper.extract_phone_from_description(desc)
        assert phone is None

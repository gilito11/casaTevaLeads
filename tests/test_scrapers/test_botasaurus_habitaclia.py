"""
Integration tests for Habitaclia Botasaurus scraper.

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


class TestHabitacliaScraper:
    """Tests for BotasaurusHabitaclia scraper."""

    @pytest.fixture
    def habitaclia_scraper(self):
        """Create Habitaclia scraper with mocked browser."""
        with patch('scrapers.botasaurus_base.psycopg2'):
            from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia
            scraper = BotasaurusHabitaclia(
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
        """Mock Habitaclia search page HTML."""
        return '''
        <html>
        <body>
            <div class="listings">
                <a href="https://www.habitaclia.com/comprar-piso-salou-centro-i500123456789.htm">Piso 1</a>
                <a href="https://www.habitaclia.com/comprar-casa-salou-playa-i500234567890.htm">Casa 2</a>
                <a href="https://www.habitaclia.com/comprar-vivienda-salou-norte-i500345678901.htm">Vivienda 3</a>
            </div>
        </body>
        </html>
        '''

    @pytest.fixture
    def mock_detail_html(self):
        """Mock Habitaclia detail page HTML."""
        return '''
        <html>
        <head><title>Piso en venta en Salou</title></head>
        <body>
            <h1>Piso en venta en Salou centro</h1>
            <ul class="feature-container">
                <li class="feature"><strong>145.600 &euro;</strong></li>
            </ul>
            <li>2 habitaciones</li>
            <li>Superficie 83 m<sup>2</sup></li>
            <li>1 Bano</li>
            <p id="js-detail-description" class="detail-description">
                Magnifico piso en el centro de Salou. Contactar al 612345678 o 973123456.
                Ideal para vacaciones o inversion.
            </p>
            <img src="//images.habimg.com/imgh/500-6030072/foto1_XXL.jpg" />
            <img src="//images.habimg.com/imgh/500-6030072/foto2_XXL.jpg" />
        </body>
        </html>
        '''

    def test_build_url_for_city_particulares(self, habitaclia_scraper):
        """Should build correct URL with particulares filter for city."""
        url = habitaclia_scraper.build_url('salou')
        assert 'habitaclia.com' in url
        assert 'particulares' in url
        assert 'salou' in url

    def test_build_url_for_province_no_particulares(self, habitaclia_scraper):
        """Province URLs should not have particulares filter."""
        url = habitaclia_scraper.build_url('tarragona_provincia')
        assert 'habitaclia.com' in url
        assert 'viviendas-tarragona' in url
        # Province searches don't support -particulares- filter
        assert 'particulares' not in url

    def test_build_url_with_pagination(self, habitaclia_scraper):
        """Should add page suffix for page > 1."""
        url = habitaclia_scraper.build_url('salou', page=2)
        assert 'pag2' in url

    def test_build_url_raises_for_invalid_zone(self, habitaclia_scraper):
        """Should raise ValueError for unknown zone."""
        with pytest.raises(ValueError, match="Zone not found"):
            habitaclia_scraper.build_url('zona_inexistente')

    def test_extract_price_from_feature_container(self, mock_detail_html):
        """Should extract price from feature-container class."""
        feature_container = re.search(
            r'class="[^"]*feature-container[^"]*"[^>]*>(.*?)</ul>',
            mock_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert feature_container is not None

        price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*(?:&euro;|EUR|€)', feature_container.group(1))
        assert price_match is not None

        price_str = price_match.group(1).replace('.', '')
        assert float(price_str) == 145600.0

    def test_extract_habitaciones_from_li(self, mock_detail_html):
        """Should extract habitaciones from <li> tags."""
        habs_li = re.search(r'<li>(\d+)\s*habitacion', mock_detail_html, re.IGNORECASE)
        assert habs_li is not None
        assert int(habs_li.group(1)) == 2

    def test_extract_metros_from_li(self, mock_detail_html):
        """Should extract metros from <li> tags."""
        metros_li = re.search(r'<li>Superficie\s*(\d+)', mock_detail_html, re.IGNORECASE)
        assert metros_li is not None
        assert int(metros_li.group(1)) == 83

    def test_extract_banos_from_li(self, mock_detail_html):
        """Should extract banos from <li> tags."""
        banos_li = re.search(r'<li>(\d+)\s*Ba[ñn]o', mock_detail_html, re.IGNORECASE)
        assert banos_li is not None
        assert int(banos_li.group(1)) == 1

    def test_extract_description(self, mock_detail_html):
        """Should extract description from detail-description class."""
        detail_desc = re.search(
            r'<p[^>]*class="[^"]*detail-description[^"]*"[^>]*>(.*?)</p>',
            mock_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert detail_desc is not None
        assert 'Magnifico piso' in detail_desc.group(1)

    def test_extract_phone_from_description(self, habitaclia_scraper, mock_detail_html):
        """Should extract phone from Habitaclia description."""
        desc_match = re.search(
            r'<p[^>]*class="[^"]*detail-description[^"]*"[^>]*>(.*?)</p>',
            mock_detail_html, re.DOTALL | re.IGNORECASE
        )
        description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        phone = habitaclia_scraper.extract_phone_from_description(description)
        assert phone == "612345678"

    def test_extract_listing_urls_from_search(self, mock_search_html):
        """Should extract listing URLs from search results."""
        links = re.findall(
            r'href="(https://www\.habitaclia\.com/comprar-(?:piso|casa|chalet|vivienda)[^"]+\.htm)',
            mock_search_html
        )
        assert len(links) == 3

        # Should extract listing IDs
        ids = []
        for link in links:
            id_match = re.search(r'-i(\d{9,})', link)
            if id_match:
                ids.append(id_match.group(1))
        assert len(ids) == 3

    def test_extract_photos_from_html(self, mock_detail_html):
        """Should extract Habitaclia CDN photo URLs."""
        photos = re.findall(
            r'(?:https?:)?//images\.habimg\.com/imgh/[^"\'<>\s]+\.(?:jpg|jpeg|png|webp)',
            mock_detail_html, re.IGNORECASE
        )
        assert len(photos) == 2

    def test_zones_config_has_salou(self):
        """Should have Salou in zones configuration."""
        from scrapers.botasaurus_habitaclia import ZONAS_GEOGRAFICAS
        assert 'salou' in ZONAS_GEOGRAFICAS
        assert ZONAS_GEOGRAFICAS['salou']['nombre'] == 'Salou'

    def test_zones_config_has_province(self):
        """Should have province zones in configuration."""
        from scrapers.botasaurus_habitaclia import ZONAS_GEOGRAFICAS
        assert 'tarragona_provincia' in ZONAS_GEOGRAFICAS
        assert ZONAS_GEOGRAFICAS['tarragona_provincia'].get('is_province') is True

    def test_zones_config_has_composite_zones(self):
        """Should have composite zones (comarcas) in configuration."""
        from scrapers.botasaurus_habitaclia import ZONAS_GEOGRAFICAS
        assert 'costa_daurada' in ZONAS_GEOGRAFICAS
        assert 'composite' in ZONAS_GEOGRAFICAS['costa_daurada']
        assert 'salou' in ZONAS_GEOGRAFICAS['costa_daurada']['composite']

    def test_portal_name_is_correct(self, habitaclia_scraper):
        """Should have correct portal name."""
        assert habitaclia_scraper.PORTAL_NAME == 'habitaclia'


class TestHabitacliaPhoneExtraction:
    """Tests for phone extraction from Habitaclia descriptions."""

    @pytest.fixture
    def habitaclia_scraper(self):
        """Create scraper for phone tests."""
        with patch('scrapers.botasaurus_base.psycopg2'):
            from scrapers.botasaurus_habitaclia import BotasaurusHabitaclia
            scraper = BotasaurusHabitaclia(
                tenant_id=1,
                zones=['salou'],
                postgres_config=None,
            )
            scraper.postgres_conn = None
            return scraper

    def test_extract_phone_mobile(self, habitaclia_scraper):
        """Should extract mobile phone (6xx)."""
        desc = "Interesados contactar 612345678"
        phone = habitaclia_scraper.extract_phone_from_description(desc)
        assert phone == "612345678"

    def test_extract_phone_landline(self, habitaclia_scraper):
        """Should extract landline phone (9xx)."""
        desc = "Oficina: 973123456"
        phone = habitaclia_scraper.extract_phone_from_description(desc)
        assert phone == "973123456"

    def test_extract_phone_prefers_first_valid(self, habitaclia_scraper):
        """Should extract first valid phone when multiple present."""
        desc = "Llamar 612345678 o 666666666"
        phone = habitaclia_scraper.extract_phone_from_description(desc)
        assert phone == "612345678"

    def test_normalize_phone_with_country_code(self, habitaclia_scraper):
        """Should normalize phone with +34 prefix."""
        result = habitaclia_scraper.normalize_phone("+34 612 345 678")
        assert result == "612345678"

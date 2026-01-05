"""
Unit tests for scrapers.

Tests extraction logic using mock HTML - NO real web connections.
"""
import pytest
import re
from unittest.mock import MagicMock, patch


class TestPhoneNormalization:
    """Tests for phone number normalization."""

    def test_normalize_phone_with_prefix_plus34(self, botasaurus_base_scraper):
        """Should normalize phone with +34 prefix."""
        result = botasaurus_base_scraper.normalize_phone("+34 612 345 678")
        assert result == "612345678"

    def test_normalize_phone_with_prefix_0034(self, botasaurus_base_scraper):
        """Should normalize phone with 0034 prefix."""
        result = botasaurus_base_scraper.normalize_phone("0034 612 345 678")
        assert result == "612345678"

    def test_normalize_phone_with_prefix_34(self, botasaurus_base_scraper):
        """Should normalize phone with 34 prefix (11 digits)."""
        result = botasaurus_base_scraper.normalize_phone("34612345678")
        assert result == "612345678"

    def test_normalize_phone_with_spaces(self, botasaurus_base_scraper):
        """Should remove spaces from phone."""
        result = botasaurus_base_scraper.normalize_phone("612 345 678")
        assert result == "612345678"

    def test_normalize_phone_with_dashes(self, botasaurus_base_scraper):
        """Should remove dashes from phone."""
        result = botasaurus_base_scraper.normalize_phone("612-345-678")
        assert result == "612345678"

    def test_normalize_phone_with_dots(self, botasaurus_base_scraper):
        """Should remove dots from phone."""
        result = botasaurus_base_scraper.normalize_phone("612.345.678")
        assert result == "612345678"

    def test_normalize_phone_with_parentheses(self, botasaurus_base_scraper):
        """Should remove parentheses from phone."""
        result = botasaurus_base_scraper.normalize_phone("(612) 345-678")
        assert result == "612345678"

    def test_normalize_phone_landline(self, botasaurus_base_scraper):
        """Should normalize landline numbers (9xx)."""
        result = botasaurus_base_scraper.normalize_phone("973 123 456")
        assert result == "973123456"

    def test_normalize_phone_returns_none_for_empty(self, botasaurus_base_scraper):
        """Should return None for empty string."""
        assert botasaurus_base_scraper.normalize_phone("") is None

    def test_normalize_phone_returns_none_for_none(self, botasaurus_base_scraper):
        """Should return None for None input."""
        assert botasaurus_base_scraper.normalize_phone(None) is None

    def test_normalize_phone_returns_none_for_short(self, botasaurus_base_scraper):
        """Should return None for phone shorter than 9 digits."""
        assert botasaurus_base_scraper.normalize_phone("12345") is None

    def test_normalize_phone_mixed_format(self, botasaurus_base_scraper):
        """Should normalize phone with mixed format."""
        result = botasaurus_base_scraper.normalize_phone("+34 (612) 345-678")
        assert result == "612345678"


class TestPhoneExtractionFromDescription:
    """Tests for extracting phones from description text."""

    def test_extract_phone_simple(self, botasaurus_base_scraper):
        """Should extract simple phone from description."""
        desc = "Contactar al 612345678 para visitas"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "612345678"

    def test_extract_phone_with_spaces(self, botasaurus_base_scraper):
        """Should extract phone with spaces in description."""
        desc = "Llamar al 612 345 678"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "612345678"

    def test_extract_phone_with_dots(self, botasaurus_base_scraper):
        """Should extract phone with dots in description."""
        desc = "Telefono: 612.345.678"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "612345678"

    def test_extract_phone_with_dashes(self, botasaurus_base_scraper):
        """Should extract phone with dashes in description."""
        desc = "Mi numero es 612-345-678"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "612345678"

    def test_extract_phone_landline(self, botasaurus_base_scraper):
        """Should extract landline from description."""
        desc = "Oficina: 973123456"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "973123456"

    def test_extract_phone_8xx(self, botasaurus_base_scraper):
        """Should extract 8xx numbers."""
        desc = "Llamar 812345678"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "812345678"

    def test_extract_phone_skips_blacklisted(self, botasaurus_base_scraper):
        """Should skip blacklisted numbers like 666666666."""
        desc = "Contactar 666666666 o 612345678"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "612345678"

    def test_extract_phone_skips_repeated_digits(self, botasaurus_base_scraper):
        """Should skip numbers with 6+ consecutive repeated digits."""
        # Regex only filters numbers with 6+ consecutive same digits
        desc = "Llamar 666666688 o 634567890"
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result == "634567890"

    def test_extract_phone_returns_none_for_no_phone(self, botasaurus_base_scraper):
        """Should return None when no phone in description."""
        desc = "Piso en venta, muy luminoso, reformado."
        result = botasaurus_base_scraper.extract_phone_from_description(desc)
        assert result is None

    def test_extract_phone_returns_none_for_empty(self, botasaurus_base_scraper):
        """Should return None for empty description."""
        assert botasaurus_base_scraper.extract_phone_from_description("") is None
        assert botasaurus_base_scraper.extract_phone_from_description(None) is None


class TestHabitacliaExtraction:
    """Tests for Habitaclia HTML extraction."""

    def test_extract_price_from_feature_container(self, habitaclia_detail_html):
        """Should extract price from feature-container class."""
        # Pattern from habitaclia scraper
        feature_container = re.search(
            r'class="[^"]*feature-container[^"]*"[^>]*>(.*?)</ul>',
            habitaclia_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert feature_container is not None

        price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*(?:&euro;|EUR|€)', feature_container.group(1))
        assert price_match is not None

        price_str = price_match.group(1).replace('.', '')
        assert float(price_str) == 145600.0

    def test_extract_habitaciones_from_li(self, habitaclia_detail_html):
        """Should extract habitaciones from <li> tags."""
        habs_li = re.search(r'<li>(\d+)\s*habitacion', habitaclia_detail_html, re.IGNORECASE)
        assert habs_li is not None
        assert int(habs_li.group(1)) == 2

    def test_extract_metros_from_li(self, habitaclia_detail_html):
        """Should extract metros from <li> tags."""
        metros_li = re.search(r'<li>Superficie\s*(\d+)', habitaclia_detail_html, re.IGNORECASE)
        assert metros_li is not None
        assert int(metros_li.group(1)) == 83

    def test_extract_phone_from_habitaclia_description(self, habitaclia_detail_html, botasaurus_base_scraper):
        """Should extract phone from Habitaclia description."""
        desc_match = re.search(
            r'<p[^>]*class="[^"]*detail-description[^"]*"[^>]*>(.*?)</p>',
            habitaclia_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert desc_match is not None

        description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        phone = botasaurus_base_scraper.extract_phone_from_description(description)
        assert phone == "612345678"


class TestFotocasaExtraction:
    """Tests for Fotocasa HTML extraction."""

    def test_extract_price_from_header(self, fotocasa_detail_html):
        """Should extract price from re-DetailHeader-price class."""
        price_header = re.search(
            r'class="[^"]*re-DetailHeader-price[^"]*"[^>]*>([^<]+)',
            fotocasa_detail_html, re.IGNORECASE
        )
        assert price_header is not None

        price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*(?:&euro;|EUR|€)', price_header.group(1))
        assert price_match is not None

        price_str = price_match.group(1).replace('.', '')
        assert float(price_str) == 189000.0

    def test_extract_metros_from_span(self, fotocasa_detail_html):
        """Should extract metros from span structure."""
        metros_span = re.search(r'<span[^>]*>\s*<span>(\d+)</span>\s*m2', fotocasa_detail_html)
        assert metros_span is not None
        assert int(metros_span.group(1)) == 95

    def test_extract_habitaciones_from_span(self, fotocasa_detail_html):
        """Should extract habitaciones from span structure."""
        habs_span = re.search(r'<span[^>]*>\s*<span>(\d+)</span>\s*hab', fotocasa_detail_html, re.IGNORECASE)
        assert habs_span is not None
        assert int(habs_span.group(1)) == 3

    def test_detect_particular_listing(self, fotocasa_detail_html):
        """Should detect particular listing indicator."""
        is_particular = 'anuncio particular' in fotocasa_detail_html.lower()
        assert is_particular is True


class TestIdealistaExtraction:
    """Tests for Idealista HTML extraction."""

    def test_extract_price_from_info_data(self, idealista_detail_html):
        """Should extract price from info-data-price class."""
        price_match = re.search(
            r'class="[^"]*info-data-price[^"]*"[^>]*>([^<]+)',
            idealista_detail_html, re.IGNORECASE
        )
        assert price_match is not None

        price_str = re.sub(r'[^\d]', '', price_match.group(1))
        assert int(price_str) == 275000


class TestMilanunciosExtraction:
    """Tests for Milanuncios HTML extraction."""

    def test_extract_price_from_json_ld(self, milanuncios_detail_html):
        """Should extract price from JSON-LD structured data."""
        import json

        json_ld_match = re.search(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            milanuncios_detail_html, re.DOTALL
        )
        assert json_ld_match is not None

        data = json.loads(json_ld_match.group(1))
        assert data['offers']['price'] == "120000"

    def test_extract_phone_from_milanuncios_description(self, milanuncios_detail_html, botasaurus_base_scraper):
        """Should extract phone from Milanuncios description."""
        desc_match = re.search(
            r'<div[^>]*class="[^"]*ad-description[^"]*"[^>]*>(.*?)</div>',
            milanuncios_detail_html, re.DOTALL | re.IGNORECASE
        )
        assert desc_match is not None

        description = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        phone = botasaurus_base_scraper.extract_phone_from_description(description)
        assert phone == "666777888"


class TestPhonesFromHTML:
    """Tests for extracting multiple phones from HTML."""

    def test_extract_phones_finds_mobiles(self, botasaurus_base_scraper):
        """Should extract mobile phone numbers (6xx, 7xx)."""
        html = "Contactar 612345678 o 712345678 o fijo 912345678"
        phones = botasaurus_base_scraper.extract_phones_from_html(html)

        assert "612345678" in phones
        assert "712345678" in phones
        # Should NOT include 9xx (landlines) in mobile filter
        assert "912345678" not in phones

    def test_extract_phones_removes_duplicates(self, botasaurus_base_scraper):
        """Should return unique phone numbers."""
        html = "Llamar 612345678 o 612345678"
        phones = botasaurus_base_scraper.extract_phones_from_html(html)

        assert len(phones) == 1
        assert "612345678" in phones

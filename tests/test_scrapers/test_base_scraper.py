"""
Tests para la clase BaseScraper.

Prueba funcionalidad de normalización, clasificación y lógica base.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scrapers.base_scraper import BaseScraper


@pytest.fixture
def scraper():
    """Fixture que crea un BaseScraper sin conexiones reales"""
    return BaseScraper(
        tenant_id=1,
        zones={"lleida_ciudad": {"enabled": True}},
        filters={"filtros_precio": {"min": 50000, "max": 1000000}},
        minio_config=None,  # Sin MinIO para tests
        postgres_config=None  # Sin PostgreSQL para tests
    )


class TestNormalizePhone:
    """Tests para el método normalize_phone()"""

    def test_phone_con_prefijo_mas_34(self, scraper):
        """Debe normalizar teléfono con +34"""
        assert scraper.normalize_phone("+34 973 12 34 56") == "973123456"

    def test_phone_con_prefijo_0034(self, scraper):
        """Debe normalizar teléfono con 0034"""
        assert scraper.normalize_phone("0034 973 12 34 56") == "973123456"

    def test_phone_con_prefijo_34(self, scraper):
        """Debe normalizar teléfono con 34"""
        assert scraper.normalize_phone("34 973 12 34 56") == "973123456"

    def test_phone_con_espacios(self, scraper):
        """Debe quitar espacios"""
        assert scraper.normalize_phone("973 123 456") == "973123456"

    def test_phone_con_guiones(self, scraper):
        """Debe quitar guiones"""
        assert scraper.normalize_phone("973-123-456") == "973123456"

    def test_phone_con_parentesis(self, scraper):
        """Debe quitar paréntesis"""
        assert scraper.normalize_phone("(973) 123-456") == "973123456"

    def test_movil_con_prefijo(self, scraper):
        """Debe normalizar móvil con +34"""
        assert scraper.normalize_phone("+34 612 345 678") == "612345678"

    def test_phone_sin_prefijo(self, scraper):
        """Debe normalizar teléfono sin prefijo"""
        assert scraper.normalize_phone("973123456") == "973123456"

    def test_phone_formato_mixto(self, scraper):
        """Debe normalizar teléfono con formato mixto"""
        assert scraper.normalize_phone("+34 (973) 12-34-56") == "973123456"

    def test_phone_none(self, scraper):
        """Debe retornar None si phone es None"""
        assert scraper.normalize_phone(None) is None

    def test_phone_vacio(self, scraper):
        """Debe retornar None si phone está vacío"""
        assert scraper.normalize_phone("") is None

    def test_phone_no_string(self, scraper):
        """Debe retornar None si no es string"""
        assert scraper.normalize_phone(123456789) is None

    def test_phone_invalido_corto(self, scraper):
        """Debe retornar los dígitos aunque no tenga 9"""
        result = scraper.normalize_phone("+34 123")
        assert result == "123"

    def test_phone_con_letras(self, scraper):
        """Debe quitar letras y quedarse con dígitos"""
        assert scraper.normalize_phone("+34 973 ABC 123 456") == "973123456"


class TestClassifyZone:
    """Tests para el método classify_zone()"""

    def test_lleida_ciudad_25001(self, scraper):
        """Código postal 25001 debe ser Lleida Ciudad"""
        assert scraper.classify_zone("25001") == "Lleida Ciudad"

    def test_lleida_ciudad_25008(self, scraper):
        """Código postal 25008 debe ser Lleida Ciudad"""
        assert scraper.classify_zone("25008") == "Lleida Ciudad"

    def test_lleida_provincia_25100(self, scraper):
        """Código postal 25100 debe ser Lleida Provincia"""
        assert scraper.classify_zone("25100") == "Lleida Provincia"

    def test_lleida_provincia_25200(self, scraper):
        """Código postal 25200 debe ser Lleida Provincia"""
        assert scraper.classify_zone("25200") == "Lleida Provincia"

    def test_tarragona_costa_43001(self, scraper):
        """Código postal 43001 debe ser Tarragona Costa"""
        assert scraper.classify_zone("43001") == "Tarragona Costa"

    def test_tarragona_costa_43500(self, scraper):
        """Código postal 43500 debe ser Tarragona Costa"""
        assert scraper.classify_zone("43500") == "Tarragona Costa"

    def test_otro_codigo_postal(self, scraper):
        """Otros códigos postales deben ser Lleida Provincia"""
        assert scraper.classify_zone("08001") == "Lleida Provincia"

    def test_codigo_postal_none(self, scraper):
        """None debe retornar Desconocida"""
        assert scraper.classify_zone(None) == "Desconocida"

    def test_codigo_postal_vacio(self, scraper):
        """String vacío debe retornar Desconocida"""
        assert scraper.classify_zone("") == "Desconocida"

    def test_codigo_postal_no_string(self, scraper):
        """No string debe retornar Desconocida"""
        assert scraper.classify_zone(25001) == "Desconocida"

    def test_codigo_postal_invalido(self, scraper):
        """Código postal con letras debe clasificarse según prefijo"""
        assert scraper.classify_zone("25ABC") == "Lleida Provincia"


class TestShouldScrape:
    """Tests para el método should_scrape()"""

    def test_particular_valido(self, scraper):
        """Particular válido debe scrapearse"""
        data = {
            'nombre': 'Juan Pérez',
            'titulo': 'Piso en venta',
            'descripcion': 'Vendo piso por traslado'
        }
        assert scraper.should_scrape(data) is True

    def test_inmobiliaria_no_scrape(self, scraper):
        """Inmobiliaria NO debe scrapearse"""
        data = {
            'nombre': 'Inmobiliaria Casa Bonita',
            'titulo': 'Piso en venta'
        }
        assert scraper.should_scrape(data) is False

    def test_particular_rechaza_no_scrape(self, scraper):
        """Particular que rechaza NO debe scrapearse"""
        data = {
            'nombre': 'María García',
            'descripcion': 'Piso en venta - NO INMOBILIARIAS'
        }
        assert scraper.should_scrape(data) is False


class TestBaseScraper:
    """Tests generales para BaseScraper"""

    def test_init_sin_conexiones(self):
        """Debe inicializar sin conexiones"""
        scraper = BaseScraper(
            tenant_id=1,
            zones={},
            filters={},
            minio_config=None,
            postgres_config=None
        )
        assert scraper.tenant_id == 1
        assert scraper.minio_client is None
        assert scraper.postgres_conn is None

    def test_scrape_not_implemented(self, scraper):
        """Método scrape() debe lanzar NotImplementedError"""
        with pytest.raises(NotImplementedError):
            scraper.scrape()

    def test_context_manager(self):
        """Debe funcionar como context manager"""
        with BaseScraper(1, {}, {}) as scraper:
            assert scraper.tenant_id == 1

    @patch('scrapers.base_scraper.psycopg2.connect')
    def test_init_postgres(self, mock_connect):
        """Debe inicializar conexión PostgreSQL"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        scraper = BaseScraper(
            tenant_id=1,
            zones={},
            filters={},
            postgres_config={
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'user': 'test_user',
                'password': 'test_pass'
            }
        )

        assert scraper.postgres_conn == mock_conn
        mock_connect.assert_called_once()

    def test_close(self, scraper):
        """Debe cerrar conexiones"""
        # Mock postgres_conn
        scraper.postgres_conn = MagicMock()
        scraper.close()
        scraper.postgres_conn.close.assert_called_once()


class TestSaveToDataLake:
    """Tests para save_to_data_lake()"""

    def test_sin_minio_client(self, scraper):
        """Sin MinIO debe retornar None"""
        result = scraper.save_to_data_lake({'precio': 100000}, 'fotocasa')
        assert result is None

    @patch('scrapers.base_scraper.Minio')
    def test_con_minio_client(self, mock_minio_class):
        """Con MinIO debe guardar y retornar path"""
        # Setup mock
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        scraper = BaseScraper(
            tenant_id=1,
            zones={},
            filters={},
            minio_config={
                'endpoint': 'localhost:9000',
                'access_key': 'test',
                'secret_key': 'test'
            }
        )

        # Test
        result = scraper.save_to_data_lake({'precio': 100000}, 'fotocasa')

        # Verificar
        assert result is not None
        assert result.startswith('bronze/tenant_1/fotocasa/')
        assert result.endswith('.json')
        mock_client.put_object.assert_called_once()


class TestSaveToPostgresRaw:
    """Tests para save_to_postgres_raw()"""

    def test_sin_postgres_conn(self, scraper):
        """Sin PostgreSQL debe retornar False"""
        result = scraper.save_to_postgres_raw(
            {'precio': 100000},
            'path/to/file.json',
            'fotocasa'
        )
        assert result is False

    @patch('scrapers.base_scraper.psycopg2.connect')
    def test_con_postgres_conn(self, mock_connect):
        """Con PostgreSQL debe guardar y retornar True"""
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        scraper = BaseScraper(
            tenant_id=1,
            zones={},
            filters={},
            postgres_config={
                'host': 'localhost',
                'database': 'test_db',
                'user': 'test_user',
                'password': 'test_pass'
            }
        )

        # Test
        result = scraper.save_to_postgres_raw(
            {'precio': 100000},
            'bronze/tenant_1/fotocasa/2025-12-07/listing_abc.json',
            'fotocasa'
        )

        # Verificar
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

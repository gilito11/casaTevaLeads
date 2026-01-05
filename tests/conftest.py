"""
Pytest fixtures for Casa Teva Lead System tests.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add backend to path
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configure Django settings before importing Django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'casa_teva.settings')

import django
django.setup()


# ============================================================
# HTML Mock Fixtures for Scrapers
# ============================================================

@pytest.fixture
def habitaclia_detail_html():
    """Mock HTML from Habitaclia detail page."""
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
        <img src="https://images.habimg.com/imgh/500-6030072/foto1_XXL.jpg" />
        <img src="https://images.habimg.com/imgh/500-6030072/foto2_XXL.jpg" />
    </body>
    </html>
    '''


@pytest.fixture
def fotocasa_detail_html():
    """Mock HTML from Fotocasa detail page."""
    return '''
    <html>
    <head><title>Piso en venta en Cambrils</title></head>
    <body>
        <h1>Piso en venta en Cambrils, zona puerto</h1>
        <span class="re-DetailHeader-price">189.000 &euro;</span>
        <span><span>95</span> m2</span>
        <span><span>3</span> hab</span>
        <div class="re-DetailDescription">
            Piso reformado cerca del puerto. Para visitas llamar 634567890.
            Tres habitaciones, dos banos, terraza con vistas al mar.
        </div>
        <span>Anuncio Particular</span>
        <img src="https://static.fotocasa.es/images/uuid-12345/photo.jpg" />
    </body>
    </html>
    '''


@pytest.fixture
def idealista_detail_html():
    """Mock HTML from Idealista detail page."""
    return '''
    <html>
    <head><title>Casa en venta en Tarragona</title></head>
    <body>
        <h1>Casa adosada en venta en Tarragona</h1>
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
    </body>
    </html>
    '''


@pytest.fixture
def milanuncios_detail_html():
    """Mock HTML from Milanuncios detail page."""
    return '''
    <html>
    <head>
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
        <h1>Piso en venta Reus centro</h1>
        <div class="ad-description">
            Vendo piso por traslado. 75m2, 2 habitaciones.
            Interesados contactar 666777888.
        </div>
    </body>
    </html>
    '''


# ============================================================
# Scraper Fixtures
# ============================================================

@pytest.fixture
def mock_postgres_config():
    """Mock PostgreSQL configuration."""
    return {
        'host': 'localhost',
        'port': 5432,
        'database': 'test_db',
        'user': 'test_user',
        'password': 'test_pass',
    }


@pytest.fixture
def botasaurus_base_scraper():
    """Create a BotasaurusBaseScraper without connections."""
    from scrapers.botasaurus_base import BotasaurusBaseScraper
    return BotasaurusBaseScraper(
        tenant_id=1,
        postgres_config=None,
        headless=True
    )


# ============================================================
# Django Test Client Fixtures
# ============================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = MagicMock()
    user.is_authenticated = True
    user.id = 1
    user.username = 'testuser'
    return user


@pytest.fixture
def mock_request(mock_user):
    """Mock Django request object."""
    request = MagicMock()
    request.user = mock_user
    request.session = {'tenant_id': 1}
    request.GET = {}
    return request


@pytest.fixture
def mock_db_cursor():
    """Mock database cursor for API tests."""
    cursor = MagicMock()
    cursor.description = [
        ('total_leads',), ('leads_nuevos',), ('leads_en_proceso',),
        ('leads_interesados',), ('leads_convertidos',), ('leads_descartados',),
        ('tasa_conversion',), ('valor_pipeline',), ('leads_ultima_semana',),
        ('leads_este_mes',), ('precio_medio',), ('portales_activos',)
    ]
    cursor.fetchone.return_value = (
        100, 50, 20, 15, 5, 10, 5.0, 1500000, 25, 80, 150000.0, 4
    )
    return cursor


# ============================================================
# Sample Data Fixtures
# ============================================================

@pytest.fixture
def sample_listing_data():
    """Sample listing data for tests."""
    return {
        'anuncio_id': '123456789',
        'titulo': 'Piso en venta en Salou',
        'precio': 145600.0,
        'metros': 83,
        'habitaciones': 2,
        'descripcion': 'Magnifico piso en el centro de Salou. Contactar al 612345678.',
        'telefono': '612345678',
        'telefono_norm': '612345678',
        'portal': 'habitaclia',
        'zona_geografica': 'Salou',
        'es_particular': True,
        'vendedor': 'Particular',
        'url_anuncio': 'https://www.habitaclia.com/comprar-piso-salou-i123456789.htm',
        'fotos': ['https://images.habimg.com/imgh/500-6030072/foto1_XXL.jpg'],
    }


@pytest.fixture
def sample_kpis_response():
    """Sample KPIs API response."""
    return {
        'data': {
            'total_leads': 100,
            'leads_nuevos': 50,
            'leads_en_proceso': 20,
            'leads_interesados': 15,
            'leads_convertidos': 5,
            'leads_descartados': 10,
            'tasa_conversion': 5.0,
            'valor_pipeline': 1500000,
            'leads_ultima_semana': 25,
            'leads_este_mes': 80,
            'precio_medio': 150000.0,
            'portales_activos': 4,
        }
    }


@pytest.fixture
def sample_leads_por_dia_response():
    """Sample leads-por-dia API response."""
    return {
        'data': [
            {'fecha': '2026-01-01', 'leads_captados': 10, 'leads_unicos': 8, 'precio_medio': 145000.0},
            {'fecha': '2026-01-02', 'leads_captados': 15, 'leads_unicos': 12, 'precio_medio': 152000.0},
            {'fecha': '2026-01-03', 'leads_captados': 8, 'leads_unicos': 7, 'precio_medio': 138000.0},
        ]
    }

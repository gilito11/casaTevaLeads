"""
Integration tests for Django Zones API.

Tests API endpoints for geographic zones management.
Uses SQLite in-memory database for isolation.
"""
import pytest
from unittest.mock import MagicMock, patch
from django.test import Client
from django.contrib.auth import get_user_model
from rest_framework import status


User = get_user_model()


@pytest.fixture
def api_client():
    """Create Django test client."""
    return Client()


@pytest.fixture
def authenticated_client(api_client, django_user):
    """Create authenticated test client."""
    api_client.force_login(django_user)
    return api_client


@pytest.fixture
def django_user(db):
    """Create test user."""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    return user


@pytest.fixture
def mock_tenant_user(django_user):
    """Mock TenantUser for authenticated requests."""
    with patch('apps.core.api_views.TenantUser') as mock_tu:
        mock_tenant = MagicMock()
        mock_tenant.tenant.tenant_id = 1
        mock_tu.objects.filter.return_value.first.return_value = mock_tenant
        yield mock_tu


@pytest.mark.django_db
class TestZonesAPIEndpoints:
    """Tests for /api/zonas/ endpoints."""

    def test_zones_list_requires_auth(self, api_client):
        """GET /api/zonas/ should require authentication."""
        response = api_client.get('/api/zonas/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]

    def test_zones_list_authenticated(self, authenticated_client, mock_tenant_user):
        """GET /api/zonas/ should return zones for authenticated user."""
        with patch('apps.core.api_views.ZonaGeografica') as mock_zona:
            mock_zona.objects.all.return_value.filter.return_value.select_related.return_value = []
            response = authenticated_client.get('/api/zonas/')
            assert response.status_code == status.HTTP_200_OK

    def test_zones_preestablecidas_endpoint(self, authenticated_client, mock_tenant_user):
        """GET /api/zonas/preestablecidas/ should return preset zones."""
        response = authenticated_client.get('/api/zonas/preestablecidas/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # Should have zones defined
        assert len(data) > 0


@pytest.mark.django_db
class TestZonesAPIFiltering:
    """Tests for zones API filtering capabilities."""

    def test_filter_by_activa(self, authenticated_client, mock_tenant_user):
        """Should filter zones by activa parameter."""
        with patch('apps.core.api_views.ZonaGeografica') as mock_zona:
            mock_zona.objects.all.return_value.filter.return_value.select_related.return_value = []
            response = authenticated_client.get('/api/zonas/?activa=true')
            assert response.status_code == status.HTTP_200_OK

    def test_filter_by_tipo(self, authenticated_client, mock_tenant_user):
        """Should filter zones by tipo parameter."""
        with patch('apps.core.api_views.ZonaGeografica') as mock_zona:
            mock_zona.objects.all.return_value.filter.return_value.select_related.return_value = []
            response = authenticated_client.get('/api/zonas/?tipo=ciudad')
            assert response.status_code == status.HTTP_200_OK

    def test_filter_by_portal_scraping(self, authenticated_client, mock_tenant_user):
        """Should filter zones by portal scraping flags."""
        with patch('apps.core.api_views.ZonaGeografica') as mock_zona:
            mock_zona.objects.all.return_value.filter.return_value.select_related.return_value = []
            response = authenticated_client.get('/api/zonas/?scrapear_habitaclia=true')
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestZonesAPICreation:
    """Tests for zone creation endpoints."""

    def test_crear_desde_preestablecida_requires_auth(self, api_client):
        """POST /api/zonas/crear_desde_preestablecida/ should require auth."""
        response = api_client.post(
            '/api/zonas/crear_desde_preestablecida/',
            data={'zona_key': 'salou'},
            content_type='application/json'
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]

    def test_crear_desde_preestablecida_invalid_key(self, authenticated_client, mock_tenant_user):
        """Should reject invalid zone key."""
        response = authenticated_client.post(
            '/api/zonas/crear_desde_preestablecida/',
            data={'zona_key': 'zona_inexistente'},
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestZonesAPITogglePortal:
    """Tests for toggle_portal action."""

    def test_toggle_portal_requires_auth(self, api_client):
        """POST /api/zonas/{id}/toggle_portal/ should require auth."""
        response = api_client.post(
            '/api/zonas/1/toggle_portal/',
            data={'portal': 'milanuncios', 'activo': True},
            content_type='application/json'
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]


class TestZonasPreestablecidas:
    """Tests for preset zones configuration."""

    def test_zonas_preestablecidas_has_required_zones(self):
        """Should have key zones defined."""
        from apps.core.models import ZONAS_PREESTABLECIDAS
        required_zones = ['salou', 'cambrils', 'tarragona', 'reus', 'lleida']
        for zone in required_zones:
            assert zone in ZONAS_PREESTABLECIDAS, f"Missing zone: {zone}"

    def test_zonas_preestablecidas_has_coordinates(self):
        """Each zone should have lat/lon coordinates."""
        from apps.core.models import ZONAS_PREESTABLECIDAS
        for key, data in ZONAS_PREESTABLECIDAS.items():
            assert 'lat' in data, f"Zone {key} missing lat"
            assert 'lon' in data, f"Zone {key} missing lon"
            # Validate coordinates are in Spain
            assert 36 <= data['lat'] <= 44, f"Zone {key} lat out of Spain range"
            assert -10 <= data['lon'] <= 5, f"Zone {key} lon out of Spain range"

    def test_zonas_preestablecidas_has_names(self):
        """Each zone should have a display name."""
        from apps.core.models import ZONAS_PREESTABLECIDAS
        for key, data in ZONAS_PREESTABLECIDAS.items():
            assert 'nombre' in data, f"Zone {key} missing nombre"
            assert len(data['nombre']) > 0, f"Zone {key} has empty nombre"


class TestZonaSerializers:
    """Tests for Zone serializers."""

    def test_zona_serializer_fields(self):
        """ZonaGeograficaSerializer should have required fields."""
        from apps.core.serializers import ZonaGeograficaSerializer
        fields = ZonaGeograficaSerializer.Meta.fields
        required_fields = ['id', 'nombre', 'slug', 'latitud', 'longitud', 'activa']
        for field in required_fields:
            assert field in fields

    def test_zona_serializer_has_portal_flags(self):
        """ZonaGeograficaSerializer should have portal scraping flags."""
        from apps.core.serializers import ZonaGeograficaSerializer
        fields = ZonaGeograficaSerializer.Meta.fields
        portal_flags = ['scrapear_milanuncios', 'scrapear_fotocasa', 'scrapear_habitaclia', 'scrapear_idealista']
        for flag in portal_flags:
            assert flag in fields

    def test_zona_create_serializer_validates_key(self):
        """ZonaGeograficaCreateSerializer should validate zona_key."""
        from apps.core.serializers import ZonaGeograficaCreateSerializer
        from apps.core.models import ZONAS_PREESTABLECIDAS

        serializer = ZonaGeograficaCreateSerializer(data={'zona_key': 'salou'})
        assert serializer.is_valid()

        serializer = ZonaGeograficaCreateSerializer(data={'zona_key': 'zona_invalida'})
        assert not serializer.is_valid()


@pytest.mark.django_db
class TestBlacklistAPI:
    """Tests for blacklist API endpoints."""

    def test_blacklist_list_requires_auth(self, api_client):
        """GET /api/blacklist/ should require authentication."""
        response = api_client.get('/api/blacklist/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]

    def test_blacklist_stats_endpoint(self, authenticated_client, mock_tenant_user):
        """GET /api/blacklist/stats/ should return statistics."""
        with patch('apps.core.api_views.UsuarioBlacklist') as mock_bl:
            mock_qs = MagicMock()
            mock_qs.filter.return_value.count.return_value = 10
            mock_qs.filter.return_value.values.return_value.annotate.return_value = []
            mock_bl.objects.all.return_value.filter.return_value.select_related.return_value = mock_qs

            response = authenticated_client.get('/api/blacklist/stats/')
            assert response.status_code == status.HTTP_200_OK

    def test_blacklist_verificar_requires_params(self, authenticated_client, mock_tenant_user):
        """POST /api/blacklist/verificar/ should require portal and usuario_id."""
        response = authenticated_client.post(
            '/api/blacklist/verificar/',
            data={},
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestBlacklistSerializers:
    """Tests for Blacklist serializers."""

    def test_blacklist_serializer_fields(self):
        """UsuarioBlacklistSerializer should have required fields."""
        from apps.core.serializers import UsuarioBlacklistSerializer
        fields = UsuarioBlacklistSerializer.Meta.fields
        required_fields = ['id', 'portal', 'usuario_id', 'nombre_usuario', 'motivo', 'activo']
        for field in required_fields:
            assert field in fields

    def test_blacklist_serializer_has_global_indicator(self):
        """UsuarioBlacklistSerializer should have es_global field."""
        from apps.core.serializers import UsuarioBlacklistSerializer
        fields = UsuarioBlacklistSerializer.Meta.fields
        assert 'es_global' in fields

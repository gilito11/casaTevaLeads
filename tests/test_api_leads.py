"""
Integration tests for Django Leads API.

Tests API endpoints using Django test client.
Uses SQLite in-memory database for isolation.
"""
import pytest
from unittest.mock import MagicMock, patch
from django.test import Client, override_settings
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
    with patch('apps.leads.api_views.TenantUser') as mock_tu:
        mock_tenant = MagicMock()
        mock_tenant.tenant.tenant_id = 1
        mock_tu.objects.filter.return_value.first.return_value = mock_tenant
        yield mock_tu


@pytest.mark.django_db
class TestLeadsAPIEndpoints:
    """Tests for /api/leads/ endpoints."""

    def test_leads_list_requires_auth(self, api_client):
        """GET /api/leads/ should require authentication."""
        response = api_client.get('/api/leads/')
        # Should redirect to login or return 401/403
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]

    def test_leads_list_authenticated(self, authenticated_client, mock_tenant_user):
        """GET /api/leads/ should return leads for authenticated user."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/')
            # Should return 200 (may be empty list)
            assert response.status_code == status.HTTP_200_OK

    def test_leads_stats_endpoint(self, authenticated_client, mock_tenant_user):
        """GET /api/leads/stats/ should return statistics."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            # Mock aggregation
            mock_qs = MagicMock()
            mock_qs.aggregate.return_value = {
                'total': 100,
                'nuevos': 50,
                'en_proceso': 20,
                'contactados': 10,
                'interesados': 8,
                'no_interesados': 5,
                'en_espera': 3,
                'clientes': 2,
                'ya_vendidos': 1,
                'no_contactar': 1,
            }
            mock_qs.values.return_value.annotate.return_value = []
            mock_lead.objects.all.return_value.filter.return_value = mock_qs

            response = authenticated_client.get('/api/leads/stats/')
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestLeadsAPIFiltering:
    """Tests for leads API filtering capabilities."""

    def test_filter_by_estado(self, authenticated_client, mock_tenant_user):
        """Should filter leads by estado parameter."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/?estado=NUEVO')
            assert response.status_code == status.HTTP_200_OK

    def test_filter_by_portal(self, authenticated_client, mock_tenant_user):
        """Should filter leads by portal parameter."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/?portal=habitaclia')
            assert response.status_code == status.HTTP_200_OK

    def test_filter_by_zona(self, authenticated_client, mock_tenant_user):
        """Should filter leads by zona_geografica parameter."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/?zona_geografica=Salou')
            assert response.status_code == status.HTTP_200_OK

    def test_search_by_telefono(self, authenticated_client, mock_tenant_user):
        """Should search leads by telefono_norm."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/?search=612345678')
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestLeadsAPIOrdering:
    """Tests for leads API ordering capabilities."""

    def test_order_by_fecha_scraping(self, authenticated_client, mock_tenant_user):
        """Should order leads by fecha_scraping."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/?ordering=-fecha_scraping')
            assert response.status_code == status.HTTP_200_OK

    def test_order_by_precio(self, authenticated_client, mock_tenant_user):
        """Should order leads by precio."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead.objects.all.return_value.filter.return_value = []
            response = authenticated_client.get('/api/leads/?ordering=precio')
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestLeadsAPICambiarEstado:
    """Tests for cambiar_estado action."""

    def test_cambiar_estado_requires_auth(self, api_client):
        """POST /api/leads/{id}/cambiar_estado/ should require auth."""
        response = api_client.post('/api/leads/1/cambiar_estado/', {'estado': 'EN_PROCESO'})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]

    def test_cambiar_estado_invalid_estado(self, authenticated_client, mock_tenant_user):
        """Should reject invalid estado values."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead_obj = MagicMock()
            mock_lead_obj.estado = 'NUEVO'
            mock_lead.objects.all.return_value.filter.return_value.get.return_value = mock_lead_obj
            mock_lead.ESTADO_CHOICES = [
                ('NUEVO', 'Nuevo'),
                ('EN_PROCESO', 'En proceso'),
            ]

            response = authenticated_client.post(
                '/api/leads/1/cambiar_estado/',
                data={'estado': 'ESTADO_INVALIDO'},
                content_type='application/json'
            )
            # Should return 400 or 404 (lead not found)
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


@pytest.mark.django_db
class TestLeadsAPINotas:
    """Tests for notas action on leads."""

    def test_notas_list_requires_auth(self, api_client):
        """GET /api/leads/{id}/notas/ should require auth."""
        response = api_client.get('/api/leads/1/notas/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, 302]

    def test_notas_create_requires_texto(self, authenticated_client, mock_tenant_user):
        """POST /api/leads/{id}/notas/ should require texto field."""
        with patch('apps.leads.api_views.Lead') as mock_lead:
            mock_lead_obj = MagicMock()
            mock_lead.objects.all.return_value.filter.return_value.get.return_value = mock_lead_obj

            response = authenticated_client.post(
                '/api/leads/1/notas/',
                data={'texto': ''},
                content_type='application/json'
            )
            # Should return 400 or 404
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


class TestLeadsSerializers:
    """Tests for Lead serializers."""

    def test_lead_list_serializer_fields(self):
        """LeadListSerializer should have required fields."""
        from apps.leads.serializers import LeadListSerializer
        fields = LeadListSerializer.Meta.fields
        required_fields = ['lead_id', 'telefono_norm', 'portal', 'estado', 'precio']
        for field in required_fields:
            assert field in fields

    def test_lead_detail_serializer_fields(self):
        """LeadDetailSerializer should have all detail fields."""
        from apps.leads.serializers import LeadDetailSerializer
        fields = LeadDetailSerializer.Meta.fields
        required_fields = ['lead_id', 'titulo', 'descripcion', 'url_anuncio', 'notas']
        for field in required_fields:
            assert field in fields

    def test_lead_update_serializer_limited_fields(self):
        """LeadUpdateSerializer should only allow updating specific fields."""
        from apps.leads.serializers import LeadUpdateSerializer
        fields = LeadUpdateSerializer.Meta.fields
        # Should not allow updating core data
        assert 'telefono_norm' not in fields
        assert 'portal' not in fields
        # Should allow updating CRM fields
        assert 'estado' in fields


class TestLeadsEstadoChoices:
    """Tests for Lead estado choices."""

    def test_estado_choices_defined(self):
        """Lead model should have ESTADO_CHOICES defined."""
        from apps.leads.models import Lead
        assert hasattr(Lead, 'ESTADO_CHOICES')
        choices = dict(Lead.ESTADO_CHOICES)
        assert 'NUEVO' in choices
        assert 'EN_PROCESO' in choices
        assert 'INTERESADO' in choices
        assert 'CLIENTE' in choices

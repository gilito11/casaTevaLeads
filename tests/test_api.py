"""
Unit tests for Analytics API endpoints.

Tests API responses with mocked database - NO real DB connections.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date


class TestConvertDecimals:
    """Tests for Decimal to float conversion utility."""

    def test_convert_single_decimal(self):
        """Should convert single Decimal to float."""
        from backend.apps.analytics.api_views import convert_decimals

        result = convert_decimals(Decimal('123.45'))
        assert result == 123.45
        assert isinstance(result, float)

    def test_convert_decimal_in_dict(self):
        """Should convert Decimals inside dict."""
        from backend.apps.analytics.api_views import convert_decimals

        data = {'precio': Decimal('150000.50'), 'metros': 85}
        result = convert_decimals(data)

        assert result['precio'] == 150000.50
        assert isinstance(result['precio'], float)
        assert result['metros'] == 85

    def test_convert_decimal_in_list(self):
        """Should convert Decimals inside list."""
        from backend.apps.analytics.api_views import convert_decimals

        data = [Decimal('100.0'), Decimal('200.0'), 300]
        result = convert_decimals(data)

        assert result == [100.0, 200.0, 300]

    def test_convert_nested_structure(self):
        """Should convert Decimals in nested structures."""
        from backend.apps.analytics.api_views import convert_decimals

        data = {
            'leads': [
                {'precio': Decimal('150000'), 'metros': Decimal('85.5')},
                {'precio': Decimal('200000'), 'metros': Decimal('95.0')},
            ],
            'totals': {'sum': Decimal('350000')}
        }
        result = convert_decimals(data)

        assert result['leads'][0]['precio'] == 150000
        assert result['leads'][1]['metros'] == 95.0
        assert result['totals']['sum'] == 350000


class TestBuildWhereClause:
    """Tests for WHERE clause builder."""

    def test_basic_where_clause(self, mock_request):
        """Should build basic WHERE with tenant_id."""
        from backend.apps.analytics.api_views import build_where_clause

        where, params = build_where_clause(mock_request)

        assert 'l.tenant_id = %s' in where
        assert 1 in params

    def test_where_with_portal_filter(self, mock_request):
        """Should add portal filter when specified."""
        from backend.apps.analytics.api_views import build_where_clause

        mock_request.GET = {'portal': 'habitaclia'}
        where, params = build_where_clause(mock_request)

        assert 'l.portal = %s' in where
        assert 'habitaclia' in params

    def test_where_with_zona_filter(self, mock_request):
        """Should add zona filter when specified."""
        from backend.apps.analytics.api_views import build_where_clause

        mock_request.GET = {'zona': 'Salou'}
        where, params = build_where_clause(mock_request)

        assert 'l.zona_geografica = %s' in where
        assert 'Salou' in params

    def test_where_with_date_range(self, mock_request):
        """Should add date filters when specified."""
        from backend.apps.analytics.api_views import build_where_clause

        mock_request.GET = {
            'fecha_inicio': '2026-01-01',
            'fecha_fin': '2026-01-31'
        }
        where, params = build_where_clause(mock_request)

        assert 'DATE(l.updated_at) >= %s' in where
        assert 'DATE(l.updated_at) <= %s' in where
        assert '2026-01-01' in params
        assert '2026-01-31' in params

    def test_where_ignores_todos_value(self, mock_request):
        """Should ignore 'todos' portal value."""
        from backend.apps.analytics.api_views import build_where_clause

        mock_request.GET = {'portal': 'todos'}
        where, params = build_where_clause(mock_request)

        assert 'l.portal = %s' not in where


class TestDictFetchAll:
    """Tests for cursor result to dict conversion."""

    def test_converts_rows_to_dicts(self):
        """Should convert cursor rows to list of dicts."""
        from backend.apps.analytics.api_views import dict_fetchall

        cursor = MagicMock()
        cursor.description = [('id',), ('nombre',), ('precio',)]
        cursor.fetchall.return_value = [
            (1, 'Lead 1', Decimal('150000')),
            (2, 'Lead 2', Decimal('200000')),
        ]

        result = dict_fetchall(cursor)

        assert len(result) == 2
        assert result[0] == {'id': 1, 'nombre': 'Lead 1', 'precio': 150000.0}
        assert result[1] == {'id': 2, 'nombre': 'Lead 2', 'precio': 200000.0}


class TestDictFetchOne:
    """Tests for single cursor result to dict conversion."""

    def test_converts_row_to_dict(self):
        """Should convert single cursor row to dict."""
        from backend.apps.analytics.api_views import dict_fetchone

        cursor = MagicMock()
        cursor.description = [('total',), ('precio_medio',)]
        cursor.fetchone.return_value = (100, Decimal('175000.50'))

        result = dict_fetchone(cursor)

        assert result == {'total': 100, 'precio_medio': 175000.50}

    def test_returns_empty_dict_for_no_row(self):
        """Should return empty dict when no row."""
        from backend.apps.analytics.api_views import dict_fetchone

        cursor = MagicMock()
        cursor.description = [('total',)]
        cursor.fetchone.return_value = None

        result = dict_fetchone(cursor)

        assert result == {}


class TestApiKpis:
    """Tests for /analytics/api/kpis/ endpoint."""

    @patch('backend.apps.analytics.api_views.connection')
    def test_returns_json_response(self, mock_connection, mock_request):
        """Should return JsonResponse with KPI data."""
        from backend.apps.analytics.api_views import api_kpis

        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('total_leads',), ('leads_nuevos',), ('leads_en_proceso',),
            ('leads_interesados',), ('leads_convertidos',), ('leads_descartados',),
            ('tasa_conversion',), ('valor_pipeline',), ('leads_ultima_semana',),
            ('leads_este_mes',), ('precio_medio',), ('portales_activos',)
        ]
        mock_cursor.fetchone.return_value = (
            100, 50, 20, 15, 5, 10, Decimal('5.0'), Decimal('1500000'),
            25, 80, Decimal('150000.0'), 4
        )
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_kpis(mock_request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data
        assert data['data']['total_leads'] == 100
        assert data['data']['tasa_conversion'] == 5.0

    @patch('backend.apps.analytics.api_views.connection')
    def test_respects_portal_filter(self, mock_connection, mock_request):
        """Should filter by portal when specified."""
        from backend.apps.analytics.api_views import api_kpis

        mock_request.GET = {'portal': 'fotocasa'}

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('total_leads',), ('leads_nuevos',), ('leads_en_proceso',),
            ('leads_interesados',), ('leads_convertidos',), ('leads_descartados',),
            ('tasa_conversion',), ('valor_pipeline',), ('leads_ultima_semana',),
            ('leads_este_mes',), ('precio_medio',), ('portales_activos',)
        ]
        mock_cursor.fetchone.return_value = (
            25, 15, 5, 3, 2, 0, Decimal('8.0'), Decimal('500000'),
            10, 20, Decimal('180000.0'), 1
        )
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_kpis(mock_request)

        assert response.status_code == 200
        # Verify SQL was executed with portal filter
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert 'fotocasa' in call_args[0][1]


class TestApiLeadsPorDia:
    """Tests for /analytics/api/leads-por-dia/ endpoint."""

    @patch('backend.apps.analytics.api_views.connection')
    def test_returns_daily_leads(self, mock_connection, mock_request):
        """Should return leads per day data."""
        from backend.apps.analytics.api_views import api_leads_por_dia

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('fecha',), ('leads_captados',), ('leads_unicos',), ('precio_medio',)
        ]
        mock_cursor.fetchall.return_value = [
            (date(2026, 1, 1), 10, 8, Decimal('145000.0')),
            (date(2026, 1, 2), 15, 12, Decimal('152000.0')),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_leads_por_dia(mock_request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data
        assert len(data['data']) == 2
        assert data['data'][0]['fecha'] == '2026-01-01'
        assert data['data'][0]['leads_captados'] == 10

    @patch('backend.apps.analytics.api_views.connection')
    def test_formats_dates_as_strings(self, mock_connection, mock_request):
        """Should format dates as YYYY-MM-DD strings."""
        from backend.apps.analytics.api_views import api_leads_por_dia

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('fecha',), ('leads_captados',), ('leads_unicos',), ('precio_medio',)
        ]
        mock_cursor.fetchall.return_value = [
            (date(2026, 1, 15), 20, 18, Decimal('160000.0')),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_leads_por_dia(mock_request)

        data = json.loads(response.content)
        assert data['data'][0]['fecha'] == '2026-01-15'


class TestApiFilterOptions:
    """Tests for /analytics/api/filter-options/ endpoint."""

    @patch('backend.apps.analytics.api_views.connection')
    def test_returns_filter_options(self, mock_connection, mock_request):
        """Should return available filter options."""
        from backend.apps.analytics.api_views import api_filter_options

        mock_cursor = MagicMock()
        # First call for portals
        mock_cursor.fetchall.side_effect = [
            [('habitaclia',), ('fotocasa',), ('milanuncios',)],  # portals
            [('Salou',), ('Cambrils',), ('Tarragona',)],  # zones
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_filter_options(mock_request)

        assert response.status_code == 200
        data = json.loads(response.content)

        assert 'portales' in data
        assert 'zonas' in data
        assert 'estados' in data

        assert 'habitaclia' in data['portales']
        assert 'Salou' in data['zonas']
        assert 'NUEVO' in data['estados']
        assert 'CLIENTE' in data['estados']


class TestApiComparativaPortales:
    """Tests for /analytics/api/comparativa-portales/ endpoint."""

    @patch('backend.apps.analytics.api_views.connection')
    def test_returns_portal_comparison(self, mock_connection, mock_request):
        """Should return comparison data by portal."""
        from backend.apps.analytics.api_views import api_comparativa_portales

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('portal',), ('total_leads',), ('leads_unicos',), ('convertidos',),
            ('tasa_conversion',), ('precio_medio',), ('precio_m2_medio',)
        ]
        mock_cursor.fetchall.return_value = [
            ('habitaclia', 45, 40, 3, Decimal('6.7'), Decimal('145000'), Decimal('1750')),
            ('fotocasa', 35, 30, 2, Decimal('5.7'), Decimal('165000'), Decimal('1900')),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_comparativa_portales(mock_request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data
        assert len(data['data']) == 2
        assert data['data'][0]['portal'] == 'habitaclia'
        assert data['data'][0]['total_leads'] == 45


class TestApiPreciosPorZona:
    """Tests for /analytics/api/precios-por-zona/ endpoint."""

    @patch('backend.apps.analytics.api_views.connection')
    def test_returns_zone_prices(self, mock_connection, mock_request):
        """Should return price statistics by zone."""
        from backend.apps.analytics.api_views import api_precios_por_zona

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('zona_geografica',), ('precio_medio',), ('precio_mediana',),
            ('precio_m2_medio',), ('total_inmuebles',), ('precio_min',), ('precio_max',)
        ]
        mock_cursor.fetchall.return_value = [
            ('Salou', Decimal('185000'), Decimal('175000'), Decimal('2100'),
             25, Decimal('95000'), Decimal('350000')),
            ('Cambrils', Decimal('210000'), Decimal('195000'), Decimal('2300'),
             18, Decimal('120000'), Decimal('400000')),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        response = api_precios_por_zona(mock_request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data
        assert len(data['data']) == 2
        assert data['data'][0]['zona_geografica'] == 'Salou'
        assert data['data'][0]['precio_medio'] == 185000


class TestApiResponseFormat:
    """Tests for consistent API response format."""

    def test_response_is_valid_json(self, sample_kpis_response):
        """KPIs response should be valid JSON structure."""
        assert 'data' in sample_kpis_response
        assert isinstance(sample_kpis_response['data'], dict)
        assert 'total_leads' in sample_kpis_response['data']

    def test_leads_por_dia_format(self, sample_leads_por_dia_response):
        """Leads por dia response should have correct format."""
        assert 'data' in sample_leads_por_dia_response
        assert isinstance(sample_leads_por_dia_response['data'], list)

        for item in sample_leads_por_dia_response['data']:
            assert 'fecha' in item
            assert 'leads_captados' in item
            assert 'leads_unicos' in item
            assert 'precio_medio' in item

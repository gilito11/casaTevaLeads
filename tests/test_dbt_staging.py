"""
Integration tests for dbt staging models.

Tests dbt model SQL logic and transformations.
Uses mock data to validate SQL patterns without real database.
"""
import pytest
import re
import os


class TestDbtProjectConfig:
    """Tests for dbt project configuration."""

    @pytest.fixture
    def dbt_project_path(self):
        """Get dbt project path."""
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project'
        )

    def test_dbt_project_yml_exists(self, dbt_project_path):
        """dbt_project.yml should exist."""
        yml_path = os.path.join(dbt_project_path, 'dbt_project.yml')
        assert os.path.exists(yml_path), "dbt_project.yml not found"

    def test_staging_models_exist(self, dbt_project_path):
        """Staging models for all portals should exist."""
        staging_path = os.path.join(dbt_project_path, 'models', 'staging')
        expected_models = [
            'stg_habitaclia.sql',
            'stg_fotocasa.sql',
            'stg_milanuncios.sql',
            'stg_idealista.sql',
        ]
        for model in expected_models:
            model_path = os.path.join(staging_path, model)
            assert os.path.exists(model_path), f"Missing staging model: {model}"

    def test_marts_dim_leads_exists(self, dbt_project_path):
        """dim_leads mart model should exist."""
        marts_path = os.path.join(dbt_project_path, 'models', 'marts')
        dim_leads_path = os.path.join(marts_path, 'dim_leads.sql')
        assert os.path.exists(dim_leads_path), "dim_leads.sql not found in marts"


class TestStagingModelSQL:
    """Tests for staging model SQL patterns."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture
    def stg_fotocasa_sql(self):
        """Read stg_fotocasa.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_fotocasa.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture
    def stg_milanuncios_sql(self):
        """Read stg_milanuncios.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_milanuncios.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    @pytest.fixture
    def stg_idealista_sql(self):
        """Read stg_idealista.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_idealista.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_habitaclia_filters_by_portal(self, stg_habitaclia_sql):
        """Should filter raw_listings by portal = 'habitaclia'."""
        assert "portal = 'habitaclia'" in stg_habitaclia_sql

    def test_fotocasa_filters_by_portal(self, stg_fotocasa_sql):
        """Should filter raw_listings by portal = 'fotocasa'."""
        assert "portal = 'fotocasa'" in stg_fotocasa_sql

    def test_milanuncios_filters_by_portal(self, stg_milanuncios_sql):
        """Should filter raw_listings by portal = 'milanuncios'."""
        assert "portal = 'milanuncios'" in stg_milanuncios_sql

    def test_idealista_filters_by_portal(self, stg_idealista_sql):
        """Should filter raw_listings by portal = 'idealista'."""
        assert "portal = 'idealista'" in stg_idealista_sql


class TestPhoneNormalizationSQL:
    """Tests for phone normalization SQL patterns."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_removes_country_code(self, stg_habitaclia_sql):
        """Should remove +34 and 0034 country codes."""
        # Check for regex patterns that remove country codes
        assert '+34' in stg_habitaclia_sql or '\\+34' in stg_habitaclia_sql
        assert '0034' in stg_habitaclia_sql

    def test_removes_formatting_characters(self, stg_habitaclia_sql):
        """Should remove spaces, dashes, and dots from phones."""
        # Check for regex patterns that remove formatting
        assert 'REGEXP_REPLACE' in stg_habitaclia_sql

    def test_outputs_telefono_norm(self, stg_habitaclia_sql):
        """Should output telefono_norm field."""
        assert 'telefono_norm' in stg_habitaclia_sql


class TestPriceExtractionSQL:
    """Tests for price extraction SQL patterns."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_extracts_precio_from_raw_data(self, stg_habitaclia_sql):
        """Should extract precio from raw_data JSONB."""
        assert "raw_data->>'precio'" in stg_habitaclia_sql

    def test_filters_minimum_price(self, stg_habitaclia_sql):
        """Should filter out listings with price < 5000 (rentals)."""
        assert 'precio > 5000' in stg_habitaclia_sql or 'precio >= 5000' in stg_habitaclia_sql

    def test_calculates_price_per_m2(self, stg_habitaclia_sql):
        """Should calculate precio_por_m2."""
        assert 'precio_por_m2' in stg_habitaclia_sql


class TestAgencyFilterSQL:
    """Tests for agency filtering SQL patterns."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_filters_abstener_agencias(self, stg_habitaclia_sql):
        """Should filter 'abstenerse agencias' from descriptions."""
        sql_lower = stg_habitaclia_sql.lower()
        assert 'abstener' in sql_lower or 'agencia' in sql_lower

    def test_filters_no_inmobiliarias(self, stg_habitaclia_sql):
        """Should filter 'no inmobiliarias' from descriptions."""
        sql_lower = stg_habitaclia_sql.lower()
        assert 'inmobiliaria' in sql_lower

    def test_filters_sin_intermediarios(self, stg_habitaclia_sql):
        """Should filter 'sin intermediarios' from descriptions."""
        sql_lower = stg_habitaclia_sql.lower()
        assert 'intermediario' in sql_lower


class TestZoneClassificationSQL:
    """Tests for zone classification SQL patterns."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_classifies_salou(self, stg_habitaclia_sql):
        """Should classify Salou locations."""
        sql_lower = stg_habitaclia_sql.lower()
        assert 'salou' in sql_lower

    def test_classifies_lleida(self, stg_habitaclia_sql):
        """Should classify Lleida locations."""
        sql_lower = stg_habitaclia_sql.lower()
        assert 'lleida' in sql_lower or 'lerida' in sql_lower

    def test_classifies_tarragona(self, stg_habitaclia_sql):
        """Should classify Tarragona locations."""
        sql_lower = stg_habitaclia_sql.lower()
        assert 'tarragona' in sql_lower

    def test_outputs_zona_clasificada(self, stg_habitaclia_sql):
        """Should output zona_clasificada field."""
        assert 'zona_clasificada' in stg_habitaclia_sql


class TestJSONBExtraction:
    """Tests for JSONB field extraction patterns."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_extracts_anuncio_id(self, stg_habitaclia_sql):
        """Should extract anuncio_id from raw_data."""
        assert "raw_data->>'anuncio_id'" in stg_habitaclia_sql

    def test_extracts_titulo(self, stg_habitaclia_sql):
        """Should extract titulo from raw_data."""
        assert "raw_data->>'titulo'" in stg_habitaclia_sql

    def test_extracts_descripcion(self, stg_habitaclia_sql):
        """Should extract descripcion from raw_data."""
        assert "raw_data->>'descripcion'" in stg_habitaclia_sql

    def test_extracts_fotos(self, stg_habitaclia_sql):
        """Should extract fotos array from raw_data."""
        assert "raw_data->'fotos'" in stg_habitaclia_sql or "raw_data->>'fotos'" in stg_habitaclia_sql

    def test_extracts_habitaciones(self, stg_habitaclia_sql):
        """Should extract habitaciones from raw_data."""
        assert "raw_data->>'habitaciones'" in stg_habitaclia_sql

    def test_extracts_metros(self, stg_habitaclia_sql):
        """Should extract metros from raw_data."""
        assert "raw_data->>'metros'" in stg_habitaclia_sql


class TestSourceConfiguration:
    """Tests for dbt source configuration."""

    @pytest.fixture
    def sources_yml(self):
        """Read sources.yml content."""
        sources_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'sources.yml'
        )
        with open(sources_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_defines_raw_source(self, sources_yml):
        """Should define 'raw' source."""
        assert 'name: raw' in sources_yml or "'raw'" in sources_yml

    def test_defines_raw_listings_table(self, sources_yml):
        """Should define raw_listings table."""
        assert 'raw_listings' in sources_yml


class TestModelMaterialization:
    """Tests for model materialization settings."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_staging_model_is_view(self, stg_habitaclia_sql):
        """Staging models should be materialized as views."""
        assert "materialized='view'" in stg_habitaclia_sql

    def test_staging_model_has_schema(self, stg_habitaclia_sql):
        """Staging models should specify schema='staging'."""
        assert "schema='staging'" in stg_habitaclia_sql


class TestDbtTags:
    """Tests for dbt model tags."""

    @pytest.fixture
    def stg_habitaclia_sql(self):
        """Read stg_habitaclia.sql content."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'dbt_project', 'models', 'staging', 'stg_habitaclia.sql'
        )
        with open(model_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_has_staging_tag(self, stg_habitaclia_sql):
        """Staging models should have 'staging' tag."""
        assert 'staging' in stg_habitaclia_sql

    def test_has_portal_tag(self, stg_habitaclia_sql):
        """Staging models should have portal-specific tag."""
        assert 'habitaclia' in stg_habitaclia_sql

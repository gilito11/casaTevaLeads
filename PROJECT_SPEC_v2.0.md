 Fija# Casa Teva - Sistema de Captación de Propietarios v2.0
## Especificación Técnica Completa - Modern Data Stack 2025

---

## 📋 ÍNDICE

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Contexto del Negocio](#contexto-del-negocio)
3. [Objetivos del Sistema](#objetivos-del-sistema)
4. [Stack Tecnológico 2025](#stack-tecnológico-2025)
5. [Arquitectura del Sistema](#arquitectura-del-sistema)
6. [Estructura de Carpetas](#estructura-de-carpetas)
7. [Base de Datos](#base-de-datos)
8. [Data Lake](#data-lake)
9. [Pipeline de Datos (Dagster + dbt)](#pipeline-de-datos)
10. [Backend (Django)](#backend-django)
11. [Frontend](#frontend)
12. [Multi-Tenancy](#multi-tenancy)
13. [Consideraciones Legales RGPD](#consideraciones-legales)
14. [Setup e Instalación](#setup-e-instalación)
15. [Roadmap de Implementación](#roadmap-de-implementación)
16. [Métricas y KPIs](#métricas-y-kpis)

---

## RESUMEN EJECUTIVO

**Proyecto**: Sistema automatizado de captación de propietarios vendedores con arquitectura Modern Data Stack

**Problema**: Casa Teva tiene demanda de compradores pero falta oferta (propietarios que quieren vender). Actualmente los comerciales pasan 3-4 horas diarias buscando manualmente propietarios en portales inmobiliarios.

**Solución v2.0**: Sistema escalable que:
1. **Scrapea** portales inmobiliarios con Scrapy + Playwright
2. **Almacena raw data** en Data Lake (MinIO) para auditabilidad
3. **Transforma** datos con dbt en Data Warehouse (PostgreSQL)
4. **Gestiona** leads en CRM Django con HTMX
5. **Orquesta** todo con Dagster (asset-centric approach)
6. **Escala** con multi-tenancy para múltiples inmobiliarias

**Innovación clave**: Arquitectura Data Lake + Data Warehouse con separación clara bronze/silver/gold layers, siguiendo patrones de Modern Data Stack empresarial.

**Valor**:
- **Operacional**: Ahorro de 15-20h/semana de trabajo manual
- **Escalabilidad**: 100-200 leads/día automatizados + arquitectura multi-tenant
- **Analytics**: Dashboards con KPIs de conversión por zona, portal, precio
- **Académico**: TFG completo con Modern Data Stack, Data Lake, orchestración asset-centric
- **Comercial**: Sistema convertible en SaaS para otras inmobiliarias

---

## CONTEXTO DEL NEGOCIO

### Casa Teva Inmobiliaria

**Ubicación**: Lleida, España  
**Modelo de negocio**: Intermediación inmobiliaria (compraventa de viviendas)  
**Problema actual**: Escasez de oferta (propietarios vendedores)  
**Potencial futuro**: Expansión a Andorra, otras inmobiliarias españolas

### Zonas Geográficas Objetivo

1. **Lleida Ciudad**: Código postal 25XXX
2. **Lleida Provincia**: Balaguer, Mollerussa, Tàrrega, Sudanell, Montoliu
3. **Tarragona Costa Dorada**: Salou, Cambrils, Miami Platja, L'Ametlla de Mar

### Portales a Scrapear

**PORTALES PRINCIPALES**:
- **Fotocasa Particulares**: Sección específica de particulares
- **Milanuncios**: Portal de clasificados, mayormente particulares
- **Wallapop Inmobiliaria**: Sección inmobiliaria de Wallapop

**PORTALES SECUNDARIOS** (si tiempo):
- **Idealista**: Solo si permiten filtrar por particulares
- **Habitaclia**: Popular en Cataluña, solo particulares

**⚠️ FILTRO CRÍTICO - SOLO PARTICULARES**:
El sistema DEBE filtrar y **NUNCA scrapear**:
- ❌ Anuncios de otras inmobiliarias
- ❌ Particulares que indiquen "NO inmobiliarias"
- ❌ Particulares que indiquen "solo compradores directos"
- ❌ Anuncios profesionales/agencias

---

## OBJETIVOS DEL SISTEMA

### Funcionales

1. **Scraping automatizado**: 
   - Ejecutar cada 6 horas con Dagster
   - Extraer solo anuncios de particulares (filtrado estricto)
   - Soportar múltiples portales de forma modular
   - Almacenar raw data en Data Lake para auditoría

2. **Deduplicación inteligente**:
   - Identificar duplicados por teléfono normalizado
   - No contactar 2 veces al mismo propietario
   - Mantener historial en Data Lake

3. **CRM operacional multi-tenant**:
   - Gestión de leads con estados
   - Sistema de notas por lead
   - Filtros por zona, precio, estado
   - Asignación a comerciales
   - Soporte para múltiples inmobiliarias (tenants)

4. **Analytics e Insights**:
   - KPIs diarios por tenant (leads nuevos, tasa de contacto, conversión)
   - Análisis por zona geográfica
   - Comparativa de portales
   - Tendencias de receptividad

5. **Data Governance**:
   - Auditoría completa (raw data guardada)
   - Re-procesamiento de datos históricos
   - Cumplimiento RGPD

### No Funcionales

1. **Legalidad**: Cumplimiento RGPD (interés legítimo)
2. **Rendimiento**: Procesar 200+ leads/día
3. **Escalabilidad**: Sistema multi-tenant para N inmobiliarias
4. **Mantenibilidad**: Código limpio, tests, documentación
5. **Usabilidad**: Interface simple para comerciales no técnicos
6. **Observabilidad**: Logs, métricas, alertas con Dagster

---

## STACK TECNOLÓGICO 2025

```yaml
Lenguaje Base: Python 3.11+

Ingesta de Datos:
  - Scrapy 2.11: Framework de scraping (crawling, pipelines)
  - Playwright 1.40+: Browser automation (JS rendering)
  - scrapy-playwright: Integración Scrapy + Playwright
  - Beautiful Soup: Parsing HTML fallback

Orquestación (NUEVO):
  - Dagster 1.5+: Asset-centric orchestration
  - Dagster Cloud: Opcional para CI/CD (gratis 1 dev)

Data Lake (NUEVO):
  - MinIO: S3-compatible object storage
  - boto3: Python SDK para S3

Base de Datos:
  - PostgreSQL 16: Base de datos principal (Data Warehouse)
  - Schemas: raw, staging, marts, analytics, public

Transformaciones:
  - dbt 1.7+: Transformaciones SQL (ELT approach)
  - SQLAlchemy: ORM para Python

Backend:
  - Django 5.1: Framework web + Admin panel
  - Django REST Framework: API REST

Frontend:
  - Django Templates: Server-side rendering
  - HTMX 1.9: Interactividad sin JS pesado
  - Alpine.js 3.x: JavaScript sprinkles (NUEVO)
  - Tailwind CSS 3.4: Utility-first CSS

Analytics:
  - Apache Superset: BI y visualizaciones (opcional)
  - Alternativa: Metabase

DevOps:
  - Docker + Docker Compose: Containerización
  - Git: Control de versiones
```

### 🆕 Mejoras v2.0 vs v1.0

| Aspecto | v1.0 | v2.0 |
|---------|------|------|
| **Orquestación** | Airflow (task-centric) | **Dagster** (asset-centric) |
| **Scraping** | Scrapy + Selenium | **Scrapy + Playwright** |
| **Almacenamiento** | Solo PostgreSQL | **MinIO (Data Lake) + PostgreSQL (Warehouse)** |
| **Arquitectura** | Single-tenant | **Multi-tenant** |
| **Frontend** | HTMX + Tailwind | **HTMX + Alpine.js + Tailwind** |
| **Escalabilidad** | Casa Teva only | **N inmobiliarias** |

---

## ARQUITECTURA DEL SISTEMA

### Arquitectura Modern Data Stack (Medallion Architecture)

```
┌────────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA v2.0 - MODERN DATA STACK              │
│                   Data Lake + Data Warehouse + Multi-Tenancy          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 0: CONFIGURACIÓN MULTI-TENANT                              │ │
│  │                                                                   │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │ │
│  │  │  Casa Teva   │  │ Inmobiliaria │  │ Inmobiliaria │          │ │
│  │  │   (Lleida)   │  │    Madrid    │  │   Barcelona  │          │ │
│  │  │              │  │              │  │              │          │ │
│  │  │ Portales:    │  │ Portales:    │  │ Portales:    │          │ │
│  │  │  Fotocasa    │  │  Idealista   │  │  Habitaclia  │          │ │
│  │  │  Milanuncios │  │  Fotocasa    │  │  Fotocasa    │          │ │
│  │  │  Wallapop    │  │              │  │              │          │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │ │
│  │         ↓                ↓                 ↓                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 1: INGESTA (Scrapy + Playwright)                          │ │
│  │                                                                   │ │
│  │  Dagster Asset: scrape_fotocasa(tenant_config)                  │ │
│  │  Dagster Asset: scrape_milanuncios(tenant_config)               │ │
│  │  Dagster Asset: scrape_wallapop(tenant_config)                  │ │
│  │                                                                   │ │
│  │  FOR EACH tenant:                                                │ │
│  │    FOR EACH portal in tenant.portales:                           │ │
│  │      scrapy-playwright → extrae datos → MinIO (bronze)          │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 2: DATA LAKE (Bronze Layer)                               │ │
│  │                                                                   │ │
│  │  MinIO (S3-compatible)                                           │ │
│  │  ├── bronze/                    ← RAW data sin procesar          │ │
│  │  │   ├── tenant_1/                                               │ │
│  │  │   │   ├── fotocasa/2024-11-24/listing_12345.json             │ │
│  │  │   │   ├── milanuncios/2024-11-24/listing_67890.json          │ │
│  │  │   │   └── wallapop/2024-11-24/listing_11111.json             │ │
│  │  │   ├── tenant_2/                                               │ │
│  │  │   └── tenant_3/                                               │ │
│  │  │                                                               │ │
│  │  ├── screenshots/              ← Evidencia visual                │ │
│  │  │   └── tenant_1/listing_12345.png                             │ │
│  │  │                                                               │ │
│  │  └── logs/                     ← Logs scraping                   │ │
│  │      └── 2024-11-24_scraping_tenant_1.log                       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 3: CARGA A WAREHOUSE (Dagster)                            │ │
│  │                                                                   │ │
│  │  Dagster Asset: load_bronze_to_postgres(bronze_data)            │ │
│  │    → Lee JSON de MinIO                                           │ │
│  │    → Carga a PostgreSQL schema 'raw'                            │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 4: TRANSFORMACIÓN (dbt + Dagster)                         │ │
│  │                                                                   │ │
│  │  Dagster Asset: dbt_staging_models                              │ │
│  │    dbt run --select staging.*   (limpieza por tenant)           │ │
│  │                                                                   │ │
│  │  Dagster Asset: dbt_marts_models                                │ │
│  │    dbt run --select marts.*     (modelo dimensional)            │ │
│  │                                                                   │ │
│  │  Dagster Asset: dbt_analytics_models                            │ │
│  │    dbt run --select analytics.* (KPIs por tenant)               │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 5: DATA WAREHOUSE (PostgreSQL) - Silver/Gold Layers       │ │
│  │                                                                   │ │
│  │  raw:        Datos crudos desde Data Lake                       │ │
│  │  staging:    Datos limpios (silver layer)                       │ │
│  │  marts:      Modelo dimensional (gold layer)                    │ │
│  │  analytics:  KPIs y agregaciones                                │ │
│  │  public:     Tablas Django (auth, sesiones, etc)                │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 6: APLICACIÓN (Django + HTMX + Alpine.js)                 │ │
│  │                                                                   │ │
│  │  ├─ Django Backend (multi-tenant con RLS)                       │ │
│  │  ├─ Django Admin (gestión super-admin)                          │ │
│  │  ├─ CRM Views (dashboard, lista leads, detalle)                 │ │
│  │  └─ Frontend: Templates + HTMX + Alpine.js + Tailwind           │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                              ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPA 7: ANALYTICS (Superset / Metabase)                        │ │
│  │                                                                   │ │
│  │  Dashboards por tenant con KPIs:                                │ │
│  │  - Performance captación                                         │ │
│  │  - Análisis temporal y geográfico                               │ │
│  │  - Rendimiento comerciales                                       │ │
│  │  - Comparativa portales                                          │ │
│  │                                                                   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos Detallado

```
1. SCRAPING (Scrapy-Playwright)
   ├─ Scrapy spider navega al portal
   ├─ Playwright renderiza JavaScript
   ├─ Extrae: teléfono, email, dirección, precio, fotos, descripción
   ├─ Aplica filtros: es_particular=True, permite_inmobiliarias=True
   └─ Guarda JSON en MinIO bronze/tenant_X/portal/YYYY-MM-DD/

2. CARGA A WAREHOUSE (Dagster)
   ├─ Dagster asset lee JSONs de MinIO
   ├─ Carga a PostgreSQL schema 'raw'
   └─ Tabla: raw_listings (con tenant_id)

3. TRANSFORMACIÓN (dbt)
   ├─ Staging: limpia, normaliza teléfonos, clasifica zonas
   ├─ Marts: crea dim_leads, dim_tenants, fact_scrapings
   └─ Analytics: calcula KPIs diarios por tenant

4. APLICACIÓN (Django)
   ├─ Lee desde marts.dim_leads (con Row Level Security)
   ├─ Comerciales gestionan leads en CRM
   ├─ Estados: NUEVO → EN_PROCESO → CONTACTADO → INTERESADO → CLIENTE
   └─ Dashboards con HTMX (actualizaciones parciales)

5. ANALYTICS (Superset)
   ├─ Lee desde schema 'analytics'
   ├─ Dashboards interactivos por tenant
   └─ Export de reportes
```

---

## ESTRUCTURA DE CARPETAS

```
casa-teva-lead-system/
│
├── README.md
├── PROJECT_SPEC_v2.0.md             # Este documento
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── dagster/                         # NUEVO: Dagster orchestration
│   ├── workspace.yaml
│   ├── dagster.yaml
│   ├── casa_teva_pipeline/
│   │   ├── __init__.py
│   │   ├── assets/
│   │   │   ├── __init__.py
│   │   │   ├── scraping_assets.py      # Assets de scraping
│   │   │   ├── data_lake_assets.py     # Assets de Data Lake
│   │   │   ├── dbt_assets.py           # Assets de dbt
│   │   │   └── warehouse_assets.py     # Assets de warehouse
│   │   ├── resources/
│   │   │   ├── __init__.py
│   │   │   ├── minio_resource.py
│   │   │   ├── postgres_resource.py
│   │   │   └── scrapy_resource.py
│   │   ├── sensors/
│   │   │   └── new_listings_sensor.py
│   │   └── schedules/
│   │       └── scraping_schedules.py
│
├── scrapers/                        # Scrapers con Playwright
│   ├── __init__.py
│   ├── base_scraper.py             # Base class
│   ├── fotocasa_scraper.py         # Scrapy + Playwright
│   ├── milanuncios_scraper.py
│   ├── wallapop_scraper.py
│   ├── settings.py                  # Scrapy settings
│   ├── middlewares.py
│   ├── pipelines.py                 # MinIO + PostgreSQL pipelines
│   └── utils/
│       ├── __init__.py
│       ├── particular_filter.py     # ⚠️ CRÍTICO: filtrado
│       ├── phone_normalizer.py
│       ├── geo_classifier.py
│       └── minio_uploader.py        # NUEVO: upload a Data Lake
│
├── dbt_project/                     # dbt transformations
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── schema.yml
│   │   │   ├── stg_fotocasa.sql
│   │   │   ├── stg_milanuncios.sql
│   │   │   └── stg_wallapop.sql
│   │   ├── marts/
│   │   │   ├── schema.yml
│   │   │   ├── dim_tenants.sql      # NUEVO: tabla tenants
│   │   │   ├── dim_leads.sql
│   │   │   ├── dim_zones.sql
│   │   │   ├── dim_portals.sql
│   │   │   ├── fact_scrapings.sql   # NUEVO: métricas scraping
│   │   │   └── fact_contacts.sql
│   │   └── analytics/
│   │       ├── schema.yml
│   │       ├── kpi_diarios_por_tenant.sql    # NUEVO: multi-tenant
│   │       ├── conversion_funnel.sql
│   │       ├── zona_performance.sql
│   │       ├── portal_comparison.sql
│   │       └── receptividad_trends.sql
│   ├── macros/
│   │   └── normalize_phone.sql
│   └── tests/
│       └── assert_no_duplicates.sql
│
├── backend/                         # Django backend
│   ├── manage.py
│   ├── casa_teva/                   # Django project
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── middleware.py            # NUEVO: TenantMiddleware
│   ├── apps/
│   │   ├── core/
│   │   │   ├── models.py            # NUEVO: Tenant, TenantUser
│   │   │   ├── admin.py
│   │   │   └── middleware.py        # Multi-tenant middleware
│   │   ├── leads/
│   │   │   ├── models.py            # Lead model
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   ├── filters.py
│   │   │   └── urls.py
│   │   └── analytics/
│   │       ├── views.py             # KPIs views
│   │       └── urls.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html           # HTMX + Alpine.js
│   │   ├── leads/
│   │   │   ├── list.html
│   │   │   ├── detail.html
│   │   │   └── partials/            # HTMX partials
│   │   └── components/
│   └── static/
│       ├── css/
│       │   └── tailwind.css
│       └── js/
│           └── alpine-components.js  # NUEVO: Alpine.js
│
├── data_lake/                       # NUEVO: Data Lake setup
│   └── minio_init.sh                # Script inicialización buckets
│
├── docs/                            # Documentación
│   ├── legal/
│   │   ├── LIA_evaluacion_interes_legitimo.md
│   │   ├── RAT_registro_actividades.md
│   │   ├── politica_privacidad.html
│   │   └── protocolo_contacto.md
│   ├── architecture/
│   │   └── architecture_diagrams.md
│   └── api/
│       └── api_documentation.md
│
├── scripts/                         # Utility scripts
│   ├── setup_db.sh
│   ├── setup_minio.sh              # NUEVO
│   └── seed_data.py
│
└── tests/                           # Tests
    ├── test_scrapers/
    │   ├── test_particular_filter.py  # ⚠️ CRÍTICO
    │   └── test_phone_normalizer.py
    ├── test_dbt/
    └── test_backend/
```

---

## BASE DE DATOS

### PostgreSQL Schemas y Tablas

#### Schema: `public` (Django)

```sql
-- Tabla de tenants (inmobiliarias)
CREATE TABLE tenants (
    tenant_id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    email_contacto VARCHAR(255),
    telefono VARCHAR(20),
    
    -- Configuración de scraping (JSON)
    config_scraping JSONB NOT NULL DEFAULT '{
        "portales": ["fotocasa", "milanuncios", "wallapop"],
        "zonas": {
            "lleida_ciudad": {
                "enabled": true,
                "codigos_postales": ["25001", "25002", "25003"]
            }
        },
        "filtros_precio": {"min": 50000, "max": 1000000},
        "schedule_scraping": "0 */6 * * *",
        "max_leads_por_dia": 50
    }'::jsonb,
    
    activo BOOLEAN DEFAULT TRUE,
    fecha_alta TIMESTAMP DEFAULT NOW(),
    max_leads_mes INTEGER DEFAULT 1000,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_activo ON tenants(activo);

-- Tabla de usuarios por tenant
CREATE TABLE tenant_users (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id),
    tenant_id INTEGER REFERENCES tenants(tenant_id),
    rol VARCHAR(50) CHECK (rol IN ('admin', 'comercial', 'viewer')),
    UNIQUE(user_id, tenant_id)
);
```

#### Schema: `raw` (Datos crudos desde Data Lake)

```sql
CREATE SCHEMA IF NOT EXISTS raw;

-- Datos raw desde Data Lake
CREATE TABLE raw.raw_listings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES public.tenants(tenant_id),
    portal VARCHAR(50) NOT NULL,
    
    -- Data Lake reference
    data_lake_path TEXT NOT NULL,  -- s3://bronze/tenant_1/fotocasa/...
    
    -- Datos extraídos (JSONB)
    raw_data JSONB NOT NULL,
    
    -- Metadata
    scraping_timestamp TIMESTAMP DEFAULT NOW(),
    scraper_version VARCHAR(20),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_raw_listings_tenant ON raw.raw_listings(tenant_id);
CREATE INDEX idx_raw_listings_portal ON raw.raw_listings(portal);
CREATE INDEX idx_raw_listings_timestamp ON raw.raw_listings(scraping_timestamp);

-- Tabla de runs de scraping
CREATE TABLE raw.scraping_runs (
    run_id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES public.tenants(tenant_id),
    portal VARCHAR(50),
    zona VARCHAR(100),
    
    fecha_inicio TIMESTAMP,
    fecha_fin TIMESTAMP,
    duracion_segundos INTEGER,
    
    anuncios_encontrados INTEGER DEFAULT 0,
    leads_validos INTEGER DEFAULT 0,
    leads_descartados INTEGER DEFAULT 0,
    leads_duplicados INTEGER DEFAULT 0,
    
    -- Razones descarte
    descartados_por_profesional INTEGER DEFAULT 0,
    descartados_por_rechazo_inmo INTEGER DEFAULT 0,
    
    -- Data Lake reference
    data_lake_path TEXT,
    
    errores JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Schema: `staging` (Datos limpios - dbt)

```sql
CREATE SCHEMA IF NOT EXISTS staging;

-- Gestionado por dbt
-- Ver: dbt_project/models/staging/*.sql
```

#### Schema: `marts` (Modelo dimensional - dbt)

```sql
CREATE SCHEMA IF NOT EXISTS marts;

-- Tabla dimensional: dim_tenants
CREATE TABLE marts.dim_tenants AS
SELECT
    tenant_id,
    nombre,
    slug,
    config_scraping,
    activo,
    fecha_alta
FROM public.tenants;

-- Tabla dimensional: dim_leads
CREATE TABLE marts.dim_leads (
    lead_id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES public.tenants(tenant_id),
    
    -- Identificación
    telefono_norm VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    nombre VARCHAR(255),
    
    -- Ubicación
    direccion TEXT,
    zona_geografica VARCHAR(100),
    codigo_postal VARCHAR(10),
    municipio VARCHAR(100),
    provincia VARCHAR(100),
    
    -- Inmueble
    tipo_inmueble VARCHAR(50),
    precio DECIMAL(12, 2),
    habitaciones INTEGER,
    metros DECIMAL(8, 2),
    descripcion TEXT,
    fotos JSONB,  -- array de URLs
    
    -- Origen
    portal VARCHAR(50),
    url_anuncio TEXT,
    data_lake_reference TEXT,  -- NUEVO: link a bronze data
    
    -- Filtros aplicados
    es_particular BOOLEAN DEFAULT TRUE,
    permite_inmobiliarias BOOLEAN DEFAULT TRUE,
    
    -- Gestión CRM
    estado VARCHAR(50) DEFAULT 'NUEVO',
    asignado_a INTEGER REFERENCES auth_user(id),
    numero_intentos INTEGER DEFAULT 0,
    
    -- Fechas
    fecha_scraping TIMESTAMP,
    fecha_primer_contacto TIMESTAMP,
    fecha_ultimo_contacto TIMESTAMP,
    fecha_cambio_estado TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_lead_per_tenant UNIQUE (tenant_id, telefono_norm)
);

-- Índices
CREATE INDEX idx_leads_tenant ON marts.dim_leads(tenant_id);
CREATE INDEX idx_leads_telefono ON marts.dim_leads(telefono_norm);
CREATE INDEX idx_leads_estado ON marts.dim_leads(estado);
CREATE INDEX idx_leads_zona ON marts.dim_leads(zona_geografica);
CREATE INDEX idx_leads_portal ON marts.dim_leads(portal);
CREATE INDEX idx_leads_asignado ON marts.dim_leads(asignado_a);

-- Row Level Security
ALTER TABLE marts.dim_leads ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON marts.dim_leads
    USING (tenant_id = current_setting('app.current_tenant', true)::INTEGER);

-- Tabla de hechos: fact_scrapings
CREATE TABLE marts.fact_scrapings (
    scraping_id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES public.tenants(tenant_id),
    portal VARCHAR(50) NOT NULL,
    zona_geografica VARCHAR(100),
    
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP,
    duracion_segundos INTEGER,
    
    anuncios_encontrados INTEGER DEFAULT 0,
    leads_validos INTEGER DEFAULT 0,
    leads_descartados INTEGER DEFAULT 0,
    leads_duplicados INTEGER DEFAULT 0,
    
    descartados_por_profesional INTEGER DEFAULT 0,
    descartados_por_rechazo_inmo INTEGER DEFAULT 0,
    
    data_lake_path TEXT,
    scraper_version VARCHAR(20),
    errores JSONB,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scrapings_tenant ON marts.fact_scrapings(tenant_id);
CREATE INDEX idx_scrapings_fecha ON marts.fact_scrapings(fecha_inicio);

-- Tabla de hechos: fact_contacts
CREATE TABLE marts.fact_contacts (
    contacto_id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES marts.dim_leads(lead_id),
    tenant_id INTEGER REFERENCES public.tenants(tenant_id),
    comercial_id INTEGER REFERENCES auth_user(id),
    
    fecha_contacto TIMESTAMP NOT NULL,
    tipo_contacto VARCHAR(50),  -- llamada, email, whatsapp
    resultado VARCHAR(50),       -- sin_respuesta, interes, no_interes, conversion
    notas TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_contacts_lead ON marts.fact_contacts(lead_id);
CREATE INDEX idx_contacts_tenant ON marts.fact_contacts(tenant_id);
CREATE INDEX idx_contacts_fecha ON marts.fact_contacts(fecha_contacto);
```

#### Schema: `analytics` (KPIs - dbt)

```sql
CREATE SCHEMA IF NOT EXISTS analytics;

-- Gestionado por dbt
-- Ver: dbt_project/models/analytics/*.sql
-- Tablas: kpi_diarios_por_tenant, conversion_funnel, zona_performance, etc.
```

---

## DATA LAKE

### Arquitectura Data Lake (MinIO)

**Propósito**: Almacenar datos crudos antes de procesarlos para:
1. Auditoría y compliance (RGPD)
2. Re-procesamiento si cambia lógica
3. Debugging (acceso al HTML/JSON original)
4. Backup de disaster recovery

### Estructura de Buckets

```
Bucket: casa-teva-data-lake

/bronze/                           ← Raw data sin procesar (Medallion Bronze)
  /tenant_1/                       ← Casa Teva
    /fotocasa/
      /2024-11-24/
        /run_20241124_080000/      ← Run específico
          listing_12345.json       ← Anuncio completo
          metadata.json            ← Metadata del run
        /run_20241124_140000/
      /2024-11-25/
    /milanuncios/
      /2024-11-24/
    /wallapop/
      /2024-11-24/
  /tenant_2/                       ← Otra inmobiliaria (futuro)
    /idealista/
      /2024-11-24/

/screenshots/                      ← Capturas de pantalla (evidencia)
  /tenant_1/
    /fotocasa/
      listing_12345.png
      listing_12346.png

/logs/                             ← Logs de scraping
  /2024-11-24/
    tenant_1_fotocasa_080000.log
    tenant_1_milanuncios_080000.log

/processed/                        ← Marca de procesados (opcional)
  /tenant_1/
    /2024-11-24/
      run_20241124_080000.processed
```

### Formato de Datos en Data Lake

**Ejemplo: `listing_12345.json`**

```json
{
  "scraping_metadata": {
    "tenant_id": 1,
    "portal": "fotocasa",
    "url": "https://www.fotocasa.es/es/comprar/vivienda/lleida-capital/...",
    "timestamp": "2024-11-24T08:15:23Z",
    "scraper_version": "1.0.0",
    "run_id": "run_20241124_080000"
  },
  "extracted_data": {
    "telefono": "666 123 456",
    "email": "propietario@example.com",
    "nombre": "Juan García",
    "direccion": "Calle Mayor 123, Lleida",
    "codigo_postal": "25001",
    "precio": "195000",
    "precio_formatted": "195.000 €",
    "titulo": "Piso 3 habitaciones centro Lleida",
    "descripcion": "Precioso piso en el centro de Lleida, 3 habitaciones...",
    "fotos": [
      "https://fotocasa.es/photo1.jpg",
      "https://fotocasa.es/photo2.jpg",
      "https://fotocasa.es/photo3.jpg"
    ],
    "habitaciones": 3,
    "metros": "90 m²",
    "tipo_inmueble": "Piso",
    "zona": "Lleida - Centre Històric"
  },
  "html_snapshot": "<html>...</html>",     // Opcional, solo si debugging
  "filters_applied": {
    "es_particular": true,
    "permite_inmobiliarias": true,
    "razon_descarte": null
  },
  "validation": {
    "has_phone": true,
    "has_address": true,
    "has_price": true,
    "has_photos": true,
    "is_valid": true
  }
}
```

### MinIO Configuration

**docker-compose.yml snippet**:

```yaml
minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000"      # S3 API
    - "9001:9001"      # Web UI
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  volumes:
    - minio_data:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 20s
    retries: 3
```

---

## PIPELINE DE DATOS

### Dagster: Asset-Centric Orchestration

**¿Por qué Dagster y no Airflow?**

1. **Asset-centric approach**: El proyecto trata de "leads" (assets), no "tareas"
2. **Integración nativa con dbt**: Dagster + dbt es matrimonio perfecto
3. **Data lineage out-of-the-box**: Visualización de dependencies automática
4. **Mejor developer experience**: Testing, local dev, debugging más fácil
5. **Moderno**: Es el estándar emergente del Modern Data Stack 2025

### Arquitectura de Assets

```python
# dagster/casa_teva_pipeline/assets/scraping_assets.py

from dagster import asset, AssetExecutionContext, Output
from typing import Dict, Any
import json

@asset(
    group_name="ingestion",
    compute_kind="scrapy",
    description="Scrapea Fotocasa Particulares para todos los tenants activos"
)
def bronze_fotocasa_listings(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Asset que scrapea Fotocasa y guarda en Data Lake (bronze)
    """
    from scrapers.fotocasa_scraper import FotocasaScraper
    from resources.minio_resource import MinIOResource
    from resources.postgres_resource import PostgresResource
    
    # Obtener tenants activos
    tenants = get_active_tenants()
    
    results = {}
    
    for tenant in tenants:
        tenant_id = tenant['tenant_id']
        config = tenant['config_scraping']
        
        # Solo scrapear si Fotocasa está en la config
        if 'fotocasa' not in config.get('portales', []):
            continue
        
        # Ejecutar scraper
        scraper = FotocasaScraper(
            tenant_id=tenant_id,
            zones=config['zonas'],
            filters=config.get('filtros_precio')
        )
        
        listings = scraper.scrape()
        
        # Guardar en MinIO (bronze)
        minio = MinIOResource()
        saved_paths = []
        
        for listing in listings:
            path = minio.save_listing(
                tenant_id=tenant_id,
                portal='fotocasa',
                listing_data=listing
            )
            saved_paths.append(path)
        
        results[tenant_id] = {
            'listings_scraped': len(listings),
            'data_lake_paths': saved_paths
        }
        
        context.log.info(
            f"Tenant {tenant_id}: Scrapeados {len(listings)} listings de Fotocasa"
        )
    
    return results


@asset(
    group_name="ingestion",
    compute_kind="scrapy",
    deps=[bronze_fotocasa_listings]  # Depende del asset anterior
)
def bronze_milanuncios_listings(context: AssetExecutionContext) -> Dict[str, Any]:
    """Asset para Milanuncios"""
    # Similar a Fotocasa
    pass


@asset(
    group_name="ingestion",
    compute_kind="scrapy"
)
def bronze_wallapop_listings(context: AssetExecutionContext) -> Dict[str, Any]:
    """Asset para Wallapop"""
    # Similar a Fotocasa
    pass


@asset(
    group_name="loading",
    compute_kind="python",
    deps=[
        bronze_fotocasa_listings,
        bronze_milanuncios_listings,
        bronze_wallapop_listings
    ]
)
def raw_postgres_listings(context: AssetExecutionContext) -> int:
    """
    Carga datos desde Data Lake (bronze) a PostgreSQL (raw schema)
    """
    from resources.minio_resource import MinIOResource
    from resources.postgres_resource import PostgresResource
    
    minio = MinIOResource()
    postgres = PostgresResource()
    
    # Obtener todos los JSONs de hoy
    today = datetime.now().date()
    listings_to_load = minio.list_bronze_listings(date=today)
    
    loaded_count = 0
    
    for listing_path in listings_to_load:
        # Leer JSON de MinIO
        listing_data = minio.read_json(listing_path)
        
        # Insertar en PostgreSQL raw.raw_listings
        postgres.insert_raw_listing(
            tenant_id=listing_data['scraping_metadata']['tenant_id'],
            portal=listing_data['scraping_metadata']['portal'],
            data_lake_path=listing_path,
            raw_data=listing_data
        )
        
        loaded_count += 1
    
    context.log.info(f"Cargados {loaded_count} listings a PostgreSQL raw schema")
    
    return loaded_count


@asset(
    group_name="transformation",
    compute_kind="dbt",
    deps=[raw_postgres_listings]
)
def dbt_staging_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Ejecuta modelos dbt staging (limpieza)
    """
    dbt_run_results = dbt.cli(["run", "--select", "staging.*"], context=context).wait()
    
    return Output(
        value=dbt_run_results,
        metadata={
            "models_run": len(dbt_run_results.result.results),
            "success": dbt_run_results.success
        }
    )


@asset(
    group_name="transformation",
    compute_kind="dbt",
    deps=[dbt_staging_models]
)
def dbt_marts_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Ejecuta modelos dbt marts (modelo dimensional)
    """
    dbt_run_results = dbt.cli(["run", "--select", "marts.*"], context=context).wait()
    
    return Output(
        value=dbt_run_results,
        metadata={
            "models_run": len(dbt_run_results.result.results),
            "dim_leads_count": get_dim_leads_count()
        }
    )


@asset(
    group_name="transformation",
    compute_kind="dbt",
    deps=[dbt_marts_models]
)
def dbt_analytics_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Ejecuta modelos dbt analytics (KPIs)
    """
    dbt_run_results = dbt.cli(["run", "--select", "analytics.*"], context=context).wait()
    
    return Output(
        value=dbt_run_results,
        metadata={
            "kpis_generated": True,
            "tenants_processed": get_active_tenants_count()
        }
    )
```

### Dagster Schedules

```python
# dagster/casa_teva_pipeline/schedules/scraping_schedules.py

from dagster import ScheduleDefinition, DefaultScheduleStatus

# Schedule principal: cada 6 horas
scraping_schedule = ScheduleDefinition(
    name="scraping_pipeline_schedule",
    cron_schedule="0 */6 * * *",  # Cada 6 horas
    job_name="scraping_to_analytics_job",
    execution_timezone="Europe/Madrid",
    default_status=DefaultScheduleStatus.RUNNING
)

# Schedule para dbt incremental: cada 1 hora
dbt_incremental_schedule = ScheduleDefinition(
    name="dbt_incremental_schedule",
    cron_schedule="0 * * * *",  # Cada hora
    job_name="dbt_incremental_job",
    execution_timezone="Europe/Madrid"
)
```

### Dagster Jobs

```python
# dagster/casa_teva_pipeline/jobs.py

from dagster import define_asset_job, AssetSelection

# Job completo: scraping -> Data Lake -> Warehouse -> dbt
scraping_to_analytics_job = define_asset_job(
    name="scraping_to_analytics_job",
    selection=AssetSelection.all(),
    description="Pipeline completo: scraping, carga, transformación y analytics"
)

# Job solo dbt (para re-transformaciones)
dbt_only_job = define_asset_job(
    name="dbt_only_job",
    selection=AssetSelection.groups("transformation"),
    description="Solo ejecuta transformaciones dbt"
)

# Job solo scraping (para testing)
scraping_only_job = define_asset_job(
    name="scraping_only_job",
    selection=AssetSelection.groups("ingestion"),
    description="Solo ejecuta scrapers y guarda en Data Lake"
)
```

### dbt Models

#### Staging: `stg_fotocasa.sql`

```sql
-- dbt_project/models/staging/stg_fotocasa.sql

{{ config(
    materialized='view',
    schema='staging'
) }}

WITH raw_data AS (
    SELECT
        id,
        tenant_id,
        portal,
        data_lake_path,
        raw_data,
        scraping_timestamp,
        created_at
    FROM {{ source('raw', 'raw_listings') }}
    WHERE portal = 'fotocasa'
    AND scraping_timestamp >= CURRENT_DATE - INTERVAL '7 days'
),

extracted AS (
    SELECT
        id,
        tenant_id,
        portal,
        data_lake_path,
        
        -- Extraer campos del JSONB
        raw_data->'extracted_data'->>'telefono' AS telefono_raw,
        raw_data->'extracted_data'->>'email' AS email,
        raw_data->'extracted_data'->>'nombre' AS nombre,
        raw_data->'extracted_data'->>'direccion' AS direccion,
        raw_data->'extracted_data'->>'codigo_postal' AS codigo_postal,
        (raw_data->'extracted_data'->>'precio')::NUMERIC AS precio,
        raw_data->'extracted_data'->>'titulo' AS titulo,
        raw_data->'extracted_data'->>'descripcion' AS descripcion,
        raw_data->'extracted_data'->'fotos' AS fotos,
        (raw_data->'extracted_data'->>'habitaciones')::INTEGER AS habitaciones,
        (raw_data->'extracted_data'->>'metros')::NUMERIC AS metros,
        raw_data->'extracted_data'->>'tipo_inmueble' AS tipo_inmueble,
        raw_data->'extracted_data'->>'zona' AS zona,
        raw_data->'scraping_metadata'->>'url' AS url_anuncio,
        
        -- Filtros aplicados
        (raw_data->'filters_applied'->>'es_particular')::BOOLEAN AS es_particular,
        (raw_data->'filters_applied'->>'permite_inmobiliarias')::BOOLEAN AS permite_inmobiliarias,
        
        scraping_timestamp,
        created_at
    FROM raw_data
)

SELECT
    id,
    tenant_id,
    portal,
    data_lake_path,
    
    -- Normalizar teléfono
    {{ normalize_phone('telefono_raw') }} AS telefono_norm,
    email,
    nombre,
    direccion,
    codigo_postal,
    precio,
    titulo,
    descripcion,
    fotos,
    habitaciones,
    metros,
    tipo_inmueble,
    
    -- Clasificar zona geográfica
    CASE
        WHEN codigo_postal LIKE '25%' THEN 'Lleida Ciudad'
        WHEN codigo_postal LIKE '43%' THEN 'Tarragona Costa'
        ELSE 'Lleida Provincia'
    END AS zona_geografica,
    
    zona AS zona_detalle,
    url_anuncio,
    es_particular,
    permite_inmobiliarias,
    scraping_timestamp AS fecha_scraping,
    created_at

FROM extracted

-- ⚠️ FILTRO CRÍTICO: Solo particulares que permiten inmobiliarias
WHERE es_particular = TRUE
  AND permite_inmobiliarias = TRUE
  AND telefono_raw IS NOT NULL
  AND direccion IS NOT NULL
  AND precio IS NOT NULL
```

#### Marts: `dim_leads.sql`

```sql
-- dbt_project/models/marts/dim_leads.sql

{{ config(
    materialized='incremental',
    unique_key='lead_id',
    schema='marts'
) }}

WITH all_listings AS (
    SELECT * FROM {{ ref('stg_fotocasa') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_milanuncios') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_wallapop') }}
),

deduplicated AS (
    SELECT
        tenant_id,
        telefono_norm,
        email,
        nombre,
        direccion,
        codigo_postal,
        zona_geografica,
        zona_detalle,
        tipo_inmueble,
        precio,
        habitaciones,
        metros,
        descripcion,
        fotos,
        portal,
        url_anuncio,
        data_lake_path,
        es_particular,
        permite_inmobiliarias,
        fecha_scraping,
        created_at,
        
        -- Mantener el registro más reciente por tenant + teléfono
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, telefono_norm 
            ORDER BY fecha_scraping DESC
        ) AS rn
    FROM all_listings
    
    {% if is_incremental() %}
    WHERE fecha_scraping > (SELECT MAX(fecha_scraping) FROM {{ this }})
    {% endif %}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['tenant_id', 'telefono_norm']) }} AS lead_id,
    tenant_id,
    telefono_norm,
    email,
    nombre,
    direccion,
    codigo_postal,
    zona_geografica,
    zona_detalle,
    tipo_inmueble,
    precio,
    habitaciones,
    metros,
    descripcion,
    fotos,
    portal,
    url_anuncio,
    data_lake_path,
    es_particular,
    permite_inmobiliarias,
    
    -- Estado CRM (inicial)
    'NUEVO' AS estado,
    NULL::INTEGER AS asignado_a,
    0 AS numero_intentos,
    
    fecha_scraping,
    NULL::TIMESTAMP AS fecha_primer_contacto,
    NULL::TIMESTAMP AS fecha_ultimo_contacto,
    NULL::TIMESTAMP AS fecha_cambio_estado,
    
    NOW() AS created_at,
    NOW() AS updated_at

FROM deduplicated
WHERE rn = 1
```

#### Analytics: `kpi_diarios_por_tenant.sql`

```sql
-- dbt_project/models/analytics/kpi_diarios_por_tenant.sql

{{ config(
    materialized='table',
    schema='analytics'
) }}

WITH scrapings_diarios AS (
    SELECT
        tenant_id,
        DATE(fecha_inicio) AS fecha,
        portal,
        SUM(anuncios_encontrados) AS total_anuncios,
        SUM(leads_validos) AS total_leads_validos,
        SUM(leads_descartados) AS total_descartados,
        AVG(duracion_segundos) AS duracion_promedio
    FROM {{ ref('fact_scrapings') }}
    GROUP BY 1, 2, 3
),

contactos_diarios AS (
    SELECT
        tenant_id,
        DATE(fecha_contacto) AS fecha,
        COUNT(*) AS total_contactos,
        COUNT(CASE WHEN resultado = 'interes' THEN 1 END) AS contactos_interesados,
        COUNT(CASE WHEN resultado = 'conversion' THEN 1 END) AS conversiones
    FROM {{ ref('fact_contacts') }}
    GROUP BY 1, 2
),

tenants AS (
    SELECT tenant_id, nombre
    FROM {{ ref('dim_tenants') }}
)

SELECT
    t.tenant_id,
    t.nombre AS tenant_nombre,
    s.fecha,
    s.portal,
    s.total_anuncios,
    s.total_leads_validos,
    s.total_descartados,
    s.duracion_promedio,
    
    COALESCE(c.total_contactos, 0) AS contactos_realizados,
    COALESCE(c.contactos_interesados, 0) AS contactos_interesados,
    COALESCE(c.conversiones, 0) AS conversiones,
    
    -- KPIs calculados
    ROUND(
        s.total_leads_validos::NUMERIC / 
        NULLIF(s.total_anuncios, 0) * 100, 
        2
    ) AS tasa_validacion_pct,
    
    ROUND(
        COALESCE(c.contactos_interesados, 0)::NUMERIC / 
        NULLIF(c.total_contactos, 0) * 100,
        2
    ) AS tasa_interes_pct,
    
    ROUND(
        COALESCE(c.conversiones, 0)::NUMERIC / 
        NULLIF(c.contactos_interesados, 0) * 100,
        2
    ) AS tasa_conversion_pct

FROM scrapings_diarios s
JOIN tenants t ON s.tenant_id = t.tenant_id
LEFT JOIN contactos_diarios c 
    ON s.tenant_id = c.tenant_id 
    AND s.fecha = c.fecha
ORDER BY t.tenant_id, s.fecha DESC
```

---

## BACKEND DJANGO

### Multi-Tenancy con Row Level Security

#### Models

```python
# backend/apps/core/models.py

from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    """Inmobiliaria/Cliente del sistema"""
    tenant_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    email_contacto = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    
    config_scraping = models.JSONField(default=dict)
    
    activo = models.BooleanField(default=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)
    max_leads_mes = models.IntegerField(default=1000)
    
    class Meta:
        db_table = 'tenants'
        verbose_name = 'Tenant (Inmobiliaria)'
        verbose_name_plural = 'Tenants'
    
    def __str__(self):
        return self.nombre


class TenantUser(models.Model):
    """Relación Usuario - Tenant"""
    
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('comercial', 'Comercial'),
        ('viewer', 'Solo Lectura'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    rol = models.CharField(max_length=50, choices=ROL_CHOICES)
    
    class Meta:
        db_table = 'tenant_users'
        unique_together = ['user', 'tenant']
    
    def __str__(self):
        return f"{self.user.username} - {self.tenant.nombre} ({self.rol})"
```

```python
# backend/apps/leads/models.py

from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Tenant

class Lead(models.Model):
    """Lead con soporte multi-tenant"""
    
    ESTADO_CHOICES = [
        ('NUEVO', 'Nuevo'),
        ('EN_PROCESO', 'En Proceso'),
        ('CONTACTADO_SIN_RESPUESTA', 'Contactado Sin Respuesta'),
        ('INTERESADO', 'Interesado'),
        ('NO_INTERESADO', 'No Interesado'),
        ('NO_CONTACTAR', 'No Contactar'),
        ('CLIENTE', 'Cliente'),
        ('YA_VENDIDO', 'Ya Vendido'),
    ]
    
    lead_id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='leads')
    
    # Identificación
    telefono_norm = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    nombre = models.CharField(max_length=255, blank=True)
    
    # Ubicación
    direccion = models.TextField()
    zona_geografica = models.CharField(max_length=100)
    codigo_postal = models.CharField(max_length=10, blank=True)
    
    # Inmueble
    tipo_inmueble = models.CharField(max_length=50, blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    habitaciones = models.IntegerField(null=True, blank=True)
    metros = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(blank=True)
    fotos = models.JSONField(default=list)
    
    # Origen
    portal = models.CharField(max_length=50)
    url_anuncio = models.TextField()
    data_lake_reference = models.TextField(blank=True)
    
    # Gestión CRM
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='NUEVO')
    asignado_a = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='leads_asignados'
    )
    numero_intentos = models.IntegerField(default=0)
    
    # Fechas
    fecha_scraping = models.DateTimeField()
    fecha_primer_contacto = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_contacto = models.DateTimeField(null=True, blank=True)
    fecha_cambio_estado = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'marts"."dim_leads'
        managed = False  # Tabla gestionada por dbt
        unique_together = ['tenant', 'telefono_norm']
        indexes = [
            models.Index(fields=['tenant', 'estado']),
            models.Index(fields=['tenant', 'zona_geografica']),
        ]
    
    def __str__(self):
        return f"{self.telefono_norm} - {self.direccion}"


class Nota(models.Model):
    """Notas sobre leads"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notas')
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    texto = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
```

#### Middleware Multi-Tenant

```python
# backend/apps/core/middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from .models import TenantUser

class TenantMiddleware(MiddlewareMixin):
    """
    Set current tenant in PostgreSQL session variable para RLS
    """
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                tenant_user = TenantUser.objects.select_related('tenant').get(
                    user=request.user
                )
                request.tenant = tenant_user.tenant
                
                # Set PostgreSQL session variable para Row Level Security
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET app.current_tenant = %s",
                        [tenant_user.tenant.tenant_id]
                    )
                    
            except TenantUser.DoesNotExist:
                request.tenant = None
        else:
            request.tenant = None
        
        return None
```

#### Views

```python
# backend/apps/leads/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .models import Lead, Nota
from apps.core.models import Tenant

@login_required
def lead_list(request):
    """Lista de leads con filtros - Multi-tenant"""
    
    if not request.tenant:
        return HttpResponseForbidden("No tienes acceso a ningún tenant")
    
    # Filtrar automáticamente por tenant (gracias a RLS)
    leads = Lead.objects.filter(tenant=request.tenant)
    
    # Aplicar filtros adicionales
    estado = request.GET.get('estado')
    if estado:
        leads = leads.filter(estado=estado)
    
    zona = request.GET.get('zona')
    if zona:
        leads = leads.filter(zona_geografica=zona)
    
    precio_min = request.GET.get('precio_min')
    if precio_min:
        leads = leads.filter(precio__gte=precio_min)
    
    precio_max = request.GET.get('precio_max')
    if precio_max:
        leads = leads.filter(precio__lte=precio_max)
    
    # Ordenar
    leads = leads.order_by('-fecha_scraping')
    
    context = {
        'leads': leads,
        'tenant': request.tenant,
        'estados': Lead.ESTADO_CHOICES,
    }
    
    return render(request, 'leads/list.html', context)


@login_required
def lead_detail(request, lead_id):
    """Detalle de un lead - Multi-tenant"""
    
    if not request.tenant:
        return HttpResponseForbidden("No tienes acceso a ningún tenant")
    
    # RLS asegura que solo vea leads de su tenant
    lead = get_object_or_404(Lead, lead_id=lead_id, tenant=request.tenant)
    
    # Obtener notas
    notas = lead.notas.all()
    
    # Si es POST, añadir nota
    if request.method == 'POST':
        texto_nota = request.POST.get('nota')
        if texto_nota:
            Nota.objects.create(
                lead=lead,
                autor=request.user,
                texto=texto_nota
            )
    
    context = {
        'lead': lead,
        'notas': notas,
        'tenant': request.tenant,
    }
    
    return render(request, 'leads/detail.html', context)


@login_required
def dashboard(request):
    """Dashboard principal con KPIs"""
    
    if not request.tenant:
        return HttpResponseForbidden("No tienes acceso a ningún tenant")
    
    # KPIs básicos
    leads_nuevos = Lead.objects.filter(
        tenant=request.tenant, 
        estado='NUEVO'
    ).count()
    
    leads_en_proceso = Lead.objects.filter(
        tenant=request.tenant,
        estado='EN_PROCESO'
    ).count()
    
    leads_interesados = Lead.objects.filter(
        tenant=request.tenant,
        estado='INTERESADO'
    ).count()
    
    clientes = Lead.objects.filter(
        tenant=request.tenant,
        estado='CLIENTE'
    ).count()
    
    # Leads por zona
    leads_por_zona = Lead.objects.filter(
        tenant=request.tenant
    ).values('zona_geografica').annotate(
        count=models.Count('lead_id')
    ).order_by('-count')
    
    context = {
        'leads_nuevos': leads_nuevos,
        'leads_en_proceso': leads_en_proceso,
        'leads_interesados': leads_interesados,
        'clientes': clientes,
        'leads_por_zona': leads_por_zona,
        'tenant': request.tenant,
    }
    
    return render(request, 'dashboard.html', context)
```

---

## FRONTEND

### Django Templates + HTMX + Alpine.js

#### Base Template

```html
<!-- backend/templates/base.html -->

<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Casa Teva - CRM{% endblock %}</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    
    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    
    {% block extra_head %}{% endblock %}
</head>
<body class="bg-gray-50">
    
    <!-- Navbar -->
    <nav class="bg-white shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <h1 class="text-xl font-bold text-gray-900">
                        Casa Teva CRM
                    </h1>
                    {% if tenant %}
                    <span class="ml-4 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                        {{ tenant.nombre }}
                    </span>
                    {% endif %}
                </div>
                
                <div class="flex items-center space-x-4">
                    <a href="{% url 'dashboard' %}" 
                       class="text-gray-700 hover:text-gray-900">
                        Dashboard
                    </a>
                    <a href="{% url 'lead_list' %}" 
                       class="text-gray-700 hover:text-gray-900">
                        Leads
                    </a>
                    <span class="text-gray-700">
                        {{ user.username }}
                    </span>
                    <a href="{% url 'logout' %}" 
                       class="text-red-600 hover:text-red-800">
                        Salir
                    </a>
                </div>
            </div>
        </div>
    </nav>
    
    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {% block content %}{% endblock %}
    </main>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

#### Dashboard con HTMX + Alpine.js

```html
<!-- backend/templates/dashboard.html -->

{% extends 'base.html' %}

{% block content %}
<div x-data="dashboard()" x-init="init()">
    
    <!-- KPIs Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        
        <!-- Leads Nuevos -->
        <div class="bg-white rounded-lg shadow p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-sm text-gray-600">Leads Nuevos</p>
                    <p class="text-3xl font-bold text-gray-900">
                        {{ leads_nuevos }}
                    </p>
                </div>
                <div class="bg-blue-100 rounded-full p-3">
                    <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                    </svg>
                </div>
            </div>
        </div>
        
        <!-- En Proceso -->
        <div class="bg-white rounded-lg shadow p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-sm text-gray-600">En Proceso</p>
                    <p class="text-3xl font-bold text-gray-900">
                        {{ leads_en_proceso }}
                    </p>
                </div>
                <div class="bg-yellow-100 rounded-full p-3">
                    <svg class="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
            </div>
        </div>
        
        <!-- Interesados -->
        <div class="bg-white rounded-lg shadow p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-sm text-gray-600">Interesados</p>
                    <p class="text-3xl font-bold text-gray-900">
                        {{ leads_interesados }}
                    </p>
                </div>
                <div class="bg-green-100 rounded-full p-3">
                    <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
            </div>
        </div>
        
        <!-- Clientes -->
        <div class="bg-white rounded-lg shadow p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-sm text-gray-600">Clientes</p>
                    <p class="text-3xl font-bold text-gray-900">
                        {{ clientes }}
                    </p>
                </div>
                <div class="bg-purple-100 rounded-full p-3">
                    <svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
            </div>
        </div>
        
    </div>
    
    <!-- Filtros con Alpine.js -->
    <div class="bg-white rounded-lg shadow p-6 mb-8">
        <h3 class="text-lg font-semibold mb-4">Filtros</h3>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            
            <!-- Filtro Zona -->
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Zona
                </label>
                <select x-model="filters.zona" 
                        @change="applyFilters()"
                        class="w-full border border-gray-300 rounded-md p-2">
                    <option value="">Todas las zonas</option>
                    <option value="Lleida Ciudad">Lleida Ciudad</option>
                    <option value="Lleida Provincia">Lleida Provincia</option>
                    <option value="Tarragona Costa">Tarragona Costa</option>
                </select>
            </div>
            
            <!-- Filtro Precio Min -->
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Precio Mínimo
                </label>
                <input type="number" 
                       x-model="filters.precio_min"
                       @input="applyFilters()"
                       placeholder="50000"
                       class="w-full border border-gray-300 rounded-md p-2">
            </div>
            
            <!-- Filtro Precio Max -->
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Precio Máximo
                </label>
                <input type="number" 
                       x-model="filters.precio_max"
                       @input="applyFilters()"
                       placeholder="500000"
                       class="w-full border border-gray-300 rounded-md p-2">
            </div>
            
        </div>
        
        <!-- Botón Reset -->
        <div class="mt-4">
            <button @click="resetFilters()" 
                    class="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300">
                Limpiar Filtros
            </button>
        </div>
    </div>
    
    <!-- Lista de Leads con HTMX -->
    <div class="bg-white rounded-lg shadow">
        <div class="p-6 border-b border-gray-200">
            <h3 class="text-lg font-semibold">Últimos Leads</h3>
        </div>
        
        <div id="leads-container"
             hx-get="{% url 'lead_list_partial' %}"
             hx-trigger="load, filter-changed from:body"
             hx-vals='{"zona": "", "precio_min": "", "precio_max": ""}'
             class="p-6">
            <!-- Leads se cargan aquí vía HTMX -->
            <p class="text-gray-500">Cargando leads...</p>
        </div>
    </div>
    
</div>

<script>
function dashboard() {
    return {
        filters: {
            zona: '',
            precio_min: '',
            precio_max: ''
        },
        
        init() {
            console.log('Dashboard initialized');
        },
        
        applyFilters() {
            // Trigger HTMX reload con filtros
            const container = document.getElementById('leads-container');
            htmx.trigger(container, 'filter-changed', {
                detail: this.filters
            });
        },
        
        resetFilters() {
            this.filters = {
                zona: '',
                precio_min: '',
                precio_max: ''
            };
            this.applyFilters();
        }
    }
}
</script>
{% endblock %}
```

#### Lista de Leads (HTMX Partial)

```html
<!-- backend/templates/leads/partials/list_partial.html -->

{% if leads %}
<table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50">
        <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Dirección
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Zona
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Precio
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Portal
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Estado
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Acciones
            </th>
        </tr>
    </thead>
    <tbody class="bg-white divide-y divide-gray-200">
        {% for lead in leads %}
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ lead.direccion|truncatewords:5 }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                {{ lead.zona_geografica }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-semibold">
                {{ lead.precio|floatformat:0 }}€
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                {{ lead.portal|title }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 text-xs rounded-full
                    {% if lead.estado == 'NUEVO' %}bg-blue-100 text-blue-800
                    {% elif lead.estado == 'INTERESADO' %}bg-green-100 text-green-800
                    {% elif lead.estado == 'CLIENTE' %}bg-purple-100 text-purple-800
                    {% else %}bg-gray-100 text-gray-800{% endif %}">
                    {{ lead.get_estado_display }}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <a href="{% url 'lead_detail' lead.lead_id %}" 
                   class="text-blue-600 hover:text-blue-900">
                    Ver Detalle
                </a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<p class="text-gray-500 text-center py-8">
    No se encontraron leads con estos filtros.
</p>
{% endif %}
```

---

## MULTI-TENANCY

### Configuración de Tenants

```python
# backend/management/commands/create_tenant.py

from django.core.management.base import BaseCommand
from apps.core.models import Tenant

class Command(BaseCommand):
    help = 'Crea un nuevo tenant'
    
    def add_arguments(self, parser):
        parser.add_argument('nombre', type=str)
        parser.add_argument('slug', type=str)
        parser.add_argument('--email', type=str)
    
    def handle(self, *args, **options):
        tenant = Tenant.objects.create(
            nombre=options['nombre'],
            slug=options['slug'],
            email_contacto=options.get('email', ''),
            config_scraping={
                "portales": ["fotocasa", "milanuncios", "wallapop"],
                "zonas": {
                    "lleida_ciudad": {
                        "enabled": True,
                        "codigos_postales": ["25001", "25002", "25003"]
                    }
                },
                "filtros_precio": {
                    "min": 50000,
                    "max": 1000000
                },
                "schedule_scraping": "0 */6 * * *",
                "max_leads_por_dia": 50
            }
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Tenant "{tenant.nombre}" creado con ID {tenant.tenant_id}')
        )
```

**Uso**:
```bash
python manage.py create_tenant "Casa Teva Inmobiliaria" "casa-teva" --email="info@casateva.es"
```

### Seed Data de Ejemplo

```bash
# Crear tenant Casa Teva
python manage.py create_tenant "Casa Teva Inmobiliaria" "casa-teva" --email="info@casateva.es"

# Crear usuario y asignarlo al tenant
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from apps.core.models import Tenant, TenantUser
>>> user = User.objects.create_user('raul', 'raul@casateva.es', 'password123')
>>> tenant = Tenant.objects.get(slug='casa-teva')
>>> TenantUser.objects.create(user=user, tenant=tenant, rol='admin')
```

---

## CONSIDERACIONES LEGALES

### Documentos RGPD Completos

Ver documento completo en: `docs/legal/`

**Archivos incluidos**:
1. `LIA_evaluacion_interes_legitimo.md` - Justificación legal completa
2. `RAT_registro_actividades.md` - Obligatorio Art. 30 RGPD
3. `politica_privacidad.html` - Para web Casa Teva
4. `protocolo_contacto.md` - Manual comerciales

**Email obligatorio**: `privacidad@casateva.es`

**Salvaguardas implementadas**:
- Máximo 1 llamada por lead
- Horario: 9:00-21:00 laborables
- Derecho de oposición inmediato
- Eliminación tras 90 días sin interés
- No cesión a terceros

---

## SETUP E INSTALACIÓN

### Requisitos

```bash
- Python 3.11+
- PostgreSQL 16
- Docker + Docker Compose
- Git
```

### Instalación Rápida

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-repo/casa-teva-lead-system.git
cd casa-teva-lead-system

# 2. Copiar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 3. Levantar servicios con Docker Compose
docker-compose up -d

# 4. Esperar que servicios estén ready
docker-compose logs -f

# 5. Inicializar MinIO (crear buckets)
docker-compose exec minio sh /data_lake/minio_init.sh

# 6. Inicializar PostgreSQL
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser

# 7. Crear tenant Casa Teva
docker-compose exec backend python manage.py create_tenant "Casa Teva" "casa-teva" --email="info@casateva.es"

# 8. Inicializar dbt
docker-compose exec dbt dbt deps
docker-compose exec dbt dbt run

# 9. Acceder a servicios
# - Django CRM: http://localhost:8000
# - Dagster UI: http://localhost:3000
# - MinIO Console: http://localhost:9001
# - Superset: http://localhost:8088
```

### docker-compose.yml Completo

```yaml
version: '3.8'

services:
  # PostgreSQL
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: casa_teva
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: casa_teva_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U casa_teva"]
      interval: 10s
      timeout: 5s
      retries: 5

  # MinIO (Data Lake)
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
      - ./data_lake:/data_lake
    ports:
      - "9000:9000"  # S3 API
      - "9001:9001"  # Web Console
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  # Dagster (Orchestration)
  dagster:
    build:
      context: ./dagster
      dockerfile: Dockerfile
    environment:
      DAGSTER_POSTGRES_USER: casa_teva
      DAGSTER_POSTGRES_PASSWORD: ${DB_PASSWORD}
      DAGSTER_POSTGRES_DB: casa_teva_db
      DAGSTER_POSTGRES_HOST: postgres
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ./dagster:/opt/dagster/app
      - ./scrapers:/opt/dagster/scrapers
      - ./dbt_project:/opt/dagster/dbt
    ports:
      - "3000:3000"  # Dagster UI
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: dagster dev -h 0.0.0.0 -p 3000

  # Django Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://casa_teva:${DB_PASSWORD}@postgres/casa_teva_db
    depends_on:
      postgres:
        condition: service_healthy

  # dbt
  dbt:
    build:
      context: ./dbt_project
      dockerfile: Dockerfile
    volumes:
      - ./dbt_project:/dbt
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DBT_PROFILES_DIR: /dbt
      DBT_TARGET: dev
    command: ["dbt", "run"]

  # Superset (Analytics)
  superset:
    image: apache/superset:latest
    ports:
      - "8088:8088"
    environment:
      SUPERSET_SECRET_KEY: ${SUPERSET_SECRET_KEY}
      DATABASE_URL: postgresql://casa_teva:${DB_PASSWORD}@postgres/casa_teva_db
    depends_on:
      postgres:
        condition: service_healthy
    command: >
      sh -c "superset db upgrade &&
             superset fab create-admin --username admin --firstname Admin --lastname User --email admin@casateva.es --password admin &&
             superset init &&
             superset run -h 0.0.0.0 -p 8088"

volumes:
  postgres_data:
  minio_data:
```

---

## ROADMAP DE IMPLEMENTACIÓN

### Fase 1: Setup Inicial (Semana 1)

- [ ] Crear estructura de carpetas completa
- [ ] Setup Docker Compose con todos los servicios
- [ ] PostgreSQL: crear schemas (raw, staging, marts, analytics, public)
- [ ] MinIO: inicializar buckets
- [ ] Setup Django con modelos Tenant, TenantUser
- [ ] Crear documentos legales (LIA, RAT, Política)
- [ ] Setup Dagster básico

### Fase 2: Scrapers con Playwright (Semana 2)

- [ ] ⚠️ **CRÍTICO**: Implementar `particular_filter.py` con tests
- [ ] Instalar scrapy-playwright
- [ ] Implementar base_scraper.py con MinIO integration
- [ ] Scraper Fotocasa Particulares (Scrapy + Playwright)
- [ ] Scraper Milanuncios (Scrapy + Playwright)
- [ ] Scraper Wallapop (Scrapy + Playwright)
- [ ] Tests completos de filtrado (pytest)
- [ ] Utils: phone_normalizer, geo_classifier, minio_uploader
- [ ] ⚠️ Validación manual: 50 leads scrapeados
  - Confirmar TODOS son particulares
  - Confirmar NINGUNO rechaza inmobiliarias

### Fase 3: Data Lake + Dagster (Semana 3)

- [ ] Configurar Dagster assets para scraping
- [ ] Asset: bronze_fotocasa_listings → MinIO
- [ ] Asset: bronze_milanuncios_listings → MinIO
- [ ] Asset: bronze_wallapop_listings → MinIO
- [ ] Asset: raw_postgres_listings (carga desde MinIO)
- [ ] Dagster schedules (cada 6h)
- [ ] Testing: pipeline end-to-end scraping → Data Lake → PostgreSQL

### Fase 4: dbt Transformations (Semana 4)

- [ ] Setup dbt project
- [ ] Modelos staging (stg_fotocasa, stg_milanuncios, stg_wallapop)
- [ ] Modelos marts (dim_tenants, dim_leads, fact_scrapings, fact_contacts)
- [ ] Modelos analytics (kpi_diarios_por_tenant, etc.)
- [ ] Dagster assets para dbt
- [ ] dbt tests (data quality)
- [ ] Testing: pipeline completo scraping → dbt → marts

### Fase 5: CRM Django Multi-Tenant (Semana 5)

- [ ] Models: Lead, Nota (con soporte tenant)
- [ ] Middleware: TenantMiddleware + RLS
- [ ] Views: dashboard, lead_list, lead_detail
- [ ] Templates con HTMX + Alpine.js + Tailwind
- [ ] Sistema de notas
- [ ] Filtros avanzados
- [ ] Sistema de asignación
- [ ] Testing: crear tenant, crear usuario, gestionar leads

### Fase 6: Analytics (Semana 6)

- [ ] Completar modelos dbt analytics
- [ ] Setup Superset
- [ ] Dashboard: Performance captación
- [ ] Dashboard: Análisis temporal
- [ ] Dashboard: Análisis geográfico
- [ ] Dashboard: Rendimiento comerciales
- [ ] Dashboard: Comparativa portales
- [ ] Export de reportes

### Fase 7: Testing y Refinamiento (Semana 7)

- [ ] Tests integración end-to-end
- [ ] Tests unitarios (filtros, normalizadores, etc.)
- [ ] Optimización queries PostgreSQL
- [ ] Optimización assets Dagster
- [ ] Documentación usuario
- [ ] Manual comerciales (protocolo contacto)
- [ ] Revisión RGPD compliance

### Fase 8: Producción (Semana 8)

- [ ] Deploy en servidor (DigitalOcean / AWS / Azure)
- [ ] SSL certificates
- [ ] Backups automáticos PostgreSQL + MinIO
- [ ] Monitorización (Dagster sensors + alertas)
- [ ] Formación Casa Teva
- [ ] Documentación deployment
- [ ] Plan de mantenimiento

---

## MÉTRICAS Y KPIS

### Dashboards Implementados

#### 1. Dashboard: Performance Captación
- Leads scrapeados por día/semana/mes (por tenant)
- Tasa de validación (leads_validos / anuncios_encontrados)
- Tasa de contacto (contactados / nuevos)
- Tasa de interés (interesados / contactados)
- Tasa de conversión (clientes / interesados)
- Tiempo promedio: lead → cliente

#### 2. Dashboard: Análisis Temporal
- Inmuebles por día (gráfico línea temporal)
- Mejor hora/día para llamar
- Estacionalidad de oferta
- Tendencias de receptividad
- Comparativa mes actual vs mes anterior

#### 3. Dashboard: Análisis Geográfico
- Performance por zona (Lleida ciudad, provincia, Tarragona, Andorra)
- Mapa de calor por código postal
- Precio medio por zona
- Tiempo de conversión por zona

#### 4. Dashboard: Rendimiento Comerciales
- Leads asignados por comercial
- Leads contactados por comercial
- Tasa de conversión individual
- Tiempo promedio de gestión
- Ranking de comerciales

#### 5. Dashboard: Análisis de Precio
- Segmentación (<100k, 100-200k, 200-300k, 300-500k, >500k)
- Conversión por rango de precio
- Precio medio por zona
- Distribución de precios

#### 6. Dashboard: Comparativa Portales
- Leads por portal (Fotocasa, Milanuncios, Wallapop)
- Tasa de conversión por portal
- Calidad de leads por portal
- Tiempo scraping por portal

#### 7. Dashboard: Receptividad
- % que contestan vs no contestan
- % que muestran interés inicial
- Motivos de rechazo (categorización)
- Tendencia temporal de receptividad

---

## ⚠️ NOTAS CRÍTICAS FINALES

### 1. Filtrado de Particulares - LA PRIORIDAD #1

**El éxito del proyecto depende de esto**:
- Si scrapeamos inmobiliarias → Casa Teva pierde tiempo y credibilidad
- Si scrapeamos particulares que dicen "NO inmobiliarias" → problemas legales
- Si scrapeamos bien → sistema funciona perfecto

**Validación obligatoria antes de producción**:
1. Scrapear 100 leads de prueba
2. Revisar MANUALMENTE los 100
3. Confirmar que TODOS son particulares válidos
4. Si alguno es inmobiliaria → arreglar filtro

### 2. Data Lake es tu Backup

Si algo sale mal en las transformaciones:
1. Tienes el JSON original en MinIO
2. Puedes re-procesar sin re-scrapear
3. Auditoría completa para RGPD

### 3. Dagster vs Airflow: Elegimos Dagster

**Razones finales**:
- Asset-centric = mejor para tu proyecto (leads son assets)
- Integración nativa con dbt
- Data lineage automático
- Más moderno = mejor para CV
- Mejor developer experience

### 4. Multi-Tenancy desde Día 1

Aunque Casa Teva es el único cliente ahora:
- Arquitectura lista para escalar
- Fácil añadir nuevas inmobiliarias
- Modelo de negocio SaaS potencial
- Mejor para nota TFG (más completo)

### 5. Stack Final 2025

```
Scrapy-Playwright
+ MinIO (Data Lake)
+ PostgreSQL (Data Warehouse)
+ Dagster (Orchestration)
+ dbt (Transformations)
+ Django (Backend)
+ HTMX + Alpine.js + Tailwind (Frontend)
+ Superset (Analytics)
```

Este stack es:
- ✅ Moderno (2025-ready)
- ✅ Escalable (multi-tenant, Data Lake)
- ✅ Completo (desde scraping hasta BI)
- ✅ Profesional (empresas reales lo usan)
- ✅ Educativo (aprenderás mucho)

---

## 📚 RECURSOS Y REFERENCIAS

### Documentación Oficial

- **Dagster**: https://docs.dagster.io/
- **Playwright**: https://playwright.dev/python/
- **dbt**: https://docs.getdbt.com/
- **Django**: https://docs.djangoproject.com/
- **HTMX**: https://htmx.org/docs/
- **Alpine.js**: https://alpinejs.dev/
- **MinIO**: https://min.io/docs/

### Tutoriales Recomendados

- Dagster University: https://dagster.io/university (gratis)
- dbt Fundamentals: https://learn.getdbt.com/
- Playwright Web Scraping: https://scrapfly.io/blog/playwright-python-tutorial/
- Django + HTMX: https://www.youtube.com/watch?v=3GObi93tjZI


## 📞 CONTACTO Y SOPORTE

**Proyecto**: Casa Teva - Sistema de Captación de Propietarios  
**Autor**: Eric Gil  
**Colaboración**: Claude (Assistant AI)  
**Fecha**: Noviembre 2024 - Febrero 2025  

---

**Versión**: 2.0  
**Fecha creación**: 24 noviembre 2024  
**Última actualización**: 24 noviembre 2024  
**Cambios v2.0**:
- Migrado de Airflow a Dagster (asset-centric orchestration)
- Añadido Data Lake con MinIO (arquitectura medallion)
- Implementado multi-tenancy desde día 1
- Cambiado Selenium por Playwright
- Añadido Alpine.js junto a HTMX
- Arquitectura completa Modern Data Stack 2025
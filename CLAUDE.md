# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 2 January 2026

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de 5 portales.

## Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Azure PostgreSQL en prod)
- **Scrapers**: Botasaurus (habitaclia, fotocasa), ScrapingBee (milanuncios, idealista)
- **Orquestacion**: Dagster
- **ETL**: dbt (raw -> public_staging -> public_marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

## Scrapers - Estado actual

| Portal | Tecnologia | Azure | Local | Coste | Datos extraidos |
|--------|------------|-------|-------|-------|-----------------|
| habitaclia | Botasaurus | ✅ | ✅ | Gratis | titulo, precio, metros, fotos (sin telefono) |
| fotocasa | Botasaurus | ✅ | ✅ | Gratis | titulo, precio, telefono, metros, fotos |
| milanuncios | ScrapingBee | ✅ | ✅ | 75 credits/req | titulo, precio, telefono, metros, fotos |
| idealista | ScrapingBee | ✅ | ✅ | 75 credits/req | titulo, precio, telefono, metros, fotos |

### Limitaciones conocidas
- **Habitaclia**: Telefono oculto tras AJAX (requiere login), no extraible
- **Fotocasa/Idealista**: Mayoria de anuncios son agencias (filtrados automaticamente)
- **Pisos.com**: Deshabilitado temporalmente

### ScrapingBee
- API Key: configurada en Azure Container Apps y GitHub Secrets
- Plan: 50€/mes = 250,000 credits = ~3,333 requests
- Stealth proxy bypass: GeeTest (Milanuncios), DataDome (Idealista)
- Coste estimado por scrape: ~€0.20 (Milanuncios) + ~€0.20 (Idealista)

## Comandos

```bash
# === LOCAL ===
python run_pisos_scraper.py --zones salou --postgres
python run_habitaclia_scraper.py --zones salou --postgres
python run_fotocasa_scraper.py --zones salou --postgres
python run_scrapingbee_milanuncios_scraper.py --zones salou reus --postgres
python run_scrapingbee_idealista_scraper.py --zones salou cambrils --postgres

# === AZURE LOGS ===
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100

# === WSL (desde iPhone via Termius) ===
# Aliases disponibles: dagster-logs, dagster-status, gh-runs, leads-count, cc
```

## Entornos

| Servicio | Local | Azure |
|----------|-------|-------|
| Web | localhost:8000 | inmoleads-crm.azurewebsites.net |
| Dagster | localhost:3000 | dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | localhost:5432 | inmoleads-db.postgres.database.azure.com |

## Credenciales

- **Local**: casa_teva / casateva2024 / casa_teva_db
- **Azure**: inmoleadsadmin / ataulfo1! / inmoleadsdb (sslmode=require)

## Portal names para BD
`pisos`, `habitaclia`, `fotocasa`, `milanuncios`, `idealista`, `wallapop`

## Estados de Lead (Django ESTADO_CHOICES)
`NUEVO`, `EN_PROCESO`, `CONTACTADO_SIN_RESPUESTA`, `INTERESADO`, `NO_INTERESADO`, `EN_ESPERA`, `NO_CONTACTAR`, `CLIENTE`, `YA_VENDIDO`

## dbt Pipeline
```
raw.raw_listings (JSONB) -> public_staging.stg_* -> public_marts.dim_leads
```

### Modelos dbt
- **public_staging/**: `stg_habitaclia`, `stg_fotocasa`, `stg_milanuncios`, `stg_idealista` (views)
- **public_marts/**: `dim_leads` (incremental, unique_key=[tenant_id, telefono_norm])

### Django Lead model
El modelo Lead apunta a `public_marts.dim_leads` (vista de solo lectura de dbt).
Los estados CRM se guardan en `leads_lead_estado` (tabla gestionada por Django).

### Ejecutar dbt
```bash
cd dbt_project
dbt run --select staging.*
dbt run --select dim_leads
dbt run --select analytics.*
dbt test
```

## Analytics API Endpoints
```
GET /analytics/api/kpis/              # KPIs globales
GET /analytics/api/embudo/            # Embudo de conversion
GET /analytics/api/leads-por-dia/     # Tendencia diaria
GET /analytics/api/evolucion-precios/ # Evolucion de precios
GET /analytics/api/comparativa-portales/ # Comparativa entre portales
GET /analytics/api/precios-por-zona/  # Precios por zona
GET /analytics/api/tipologia/         # Distribucion por tipo
GET /analytics/api/filter-options/    # Opciones para filtros
GET /analytics/api/export/            # Exportar CSV

# Query params: fecha_inicio, fecha_fin, portal, zona, estado
```

## CI/CD
Push a master -> GitHub Actions -> ACR -> Azure Container Apps

## Claude Code Preferences
- Ejecutar comandos largos en background
- Tomar decisiones sin preguntar
- Ser conciso

# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 3 January 2026

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de 4 portales.

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
| habitaclia | Botasaurus | OK | OK | Gratis | titulo, precio, metros, fotos, telefono (de descripcion) |
| fotocasa | Botasaurus | OK | OK | Gratis | titulo, precio, metros, fotos, telefono (de descripcion) |
| milanuncios | ScrapingBee | OK | OK | 75 credits/req | titulo, precio, metros, fotos, telefono |
| idealista | ScrapingBee | OK | OK | 75 credits/req | titulo, precio, metros, fotos, telefono |

### Extraccion de telefonos
- **Milanuncios/Idealista**: Click en boton "Ver telefono" via js_scenario de ScrapingBee
- **Habitaclia/Fotocasa**: Busqueda de patrones en descripcion del anuncio (regex)

### Portales eliminados (Enero 2026)
- **Pisos.com**: Eliminado - pocos leads de calidad
- **Wallapop**: Eliminado - no relevante para inmobiliaria

### ScrapingBee
- API Key: configurada en Azure Container Apps y GitHub Secrets
- Plan: 50eur/mes = 250,000 credits = ~3,333 requests
- Stealth proxy: GeeTest (Milanuncios), DataDome (Idealista)

## Comandos

```bash
# === LOCAL ===
python run_all_scrapers.py --portals habitaclia fotocasa --zones salou
python run_all_scrapers.py --portals milanuncios idealista --zones salou --postgres

# === AZURE LOGS ===
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100
```

## Entornos

| Servicio | Local | Azure |
|----------|-------|-------|
| Web | localhost:8000 | inmoleads-crm.azurewebsites.net |
| Dagster | localhost:3000 | dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | localhost:5432 | inmoleads-db.postgres.database.azure.com |

## Credenciales

- **Local**: casa_teva / [REDACTED] / casa_teva_db
- **Azure**: inmoleadsadmin / [REDACTED] / inmoleadsdb (sslmode=require)

## Portal names para BD
`habitaclia`, `fotocasa`, `milanuncios`, `idealista`

## Estados de Lead (Django ESTADO_CHOICES)
`NUEVO`, `EN_PROCESO`, `CONTACTADO_SIN_RESPUESTA`, `INTERESADO`, `NO_INTERESADO`, `EN_ESPERA`, `NO_CONTACTAR`, `CLIENTE`, `YA_VENDIDO`

## dbt Pipeline
```
raw.raw_listings (JSONB) -> public_staging.stg_* -> public_marts.dim_leads
```

### Modelos dbt
- **public_staging/**: `stg_habitaclia`, `stg_fotocasa`, `stg_milanuncios`, `stg_idealista` (views)
- **public_marts/**: `dim_leads` (incremental, unique_key=[tenant_id, telefono_norm])

### Campos importantes
- `fotos`: Array de URLs de imagenes (JSONB)
- `telefono_norm`: Telefono normalizado (sin espacios ni prefijo)
- `source_portal`: Portal de origen

### Django Lead model
El modelo Lead apunta a `public_marts.dim_leads` (vista de solo lectura de dbt).
Los estados CRM se guardan en `leads_lead_estado` (tabla gestionada por Django).

### Ejecutar dbt
```bash
cd dbt_project
dbt run --select staging.*
dbt run --select dim_leads
dbt test
```

## Analytics API Endpoints
```
GET /analytics/api/kpis/              # KPIs globales
GET /analytics/api/embudo/            # Embudo de conversion
GET /analytics/api/leads-por-dia/     # Tendencia diaria
GET /analytics/api/comparativa-portales/ # Comparativa entre portales
GET /analytics/api/precios-por-zona/  # Precios por zona
GET /analytics/api/filter-options/    # Opciones para filtros
GET /analytics/api/export/            # Exportar CSV
```

## CI/CD
Push a master -> GitHub Actions -> ACR -> Azure Container Apps

## Claude Code Preferences
- Ejecutar comandos largos en background
- Tomar decisiones sin preguntar
- Ser conciso

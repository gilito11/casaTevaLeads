# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: December 2025 (almost 2026!)

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de portales inmobiliarios con CRM para gestion de contactos.

## Stack Tecnologico
- **Backend**: Django 5.x + Django REST Framework
- **Base de datos**: PostgreSQL 16 (Azure PostgreSQL en produccion)
- **Scrapers** (todos GRATUITOS):
  - **Camoufox**: Milanuncios, Idealista (anti-detect browser, bypasses GeeTest/DataDome)
  - **Botasaurus**: Pisos.com, Habitaclia, Fotocasa
- **Orquestacion**: Dagster (pipelines)
- **ETL**: dbt (raw -> staging -> marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS
- **Contenedores**: Docker Compose (local) / Azure Container Apps (produccion)

## Arquitectura de Datos

```
Scrapers (Camoufox/Botasaurus)
    |
raw.raw_listings (JSONB)
    | dbt
staging.stg_* (vista por portal)
    | dbt
marts.dim_leads (tabla unificada)
    |
Django Lead model
```

- `raw.raw_listings`: Datos crudos de todos los portales (JSONB)
- `staging.stg_*`: Vistas normalizadas por portal (stg_milanuncios, stg_idealista, etc.)
- `marts.dim_leads`: Tabla principal con leads deduplicados
- `Lead` model: `managed=False`, apunta a marts.dim_leads
- `LeadEstado`: Tabla separada para estados CRM

## Entornos

### Local (Docker)
| Servicio | Puerto | Contenedor |
|----------|--------|------------|
| Django Web | 8000 | casa-teva-web |
| PostgreSQL | 5432 | casa-teva-postgres |
| Dagster | 3000 | casa-teva-dagster |

### Azure (Produccion)
| Servicio | URL |
|----------|-----|
| CRM Web | https://inmoleads-crm.azurewebsites.net |
| Dagster | https://dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | inmoleads-db.postgres.database.azure.com |

## Comandos Frecuentes

```bash
# === LOCAL ===
# Iniciar todo
docker-compose up -d

# Ver logs
docker-compose logs web --tail 50
docker-compose logs web -f  # seguir en tiempo real

# Ejecutar scraper manualmente
python run_camoufox_milanuncios.py salou cambrils
python run_camoufox_idealista.py salou cambrils
python run_pisos_scraper.py --zones salou --postgres

# Consultar base de datos
docker exec casa-teva-postgres psql -U casa_teva -d casa_teva_db -c "SELECT COUNT(*) FROM marts.dim_leads;"

# === AZURE ===
# Ver logs de Dagster
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 50

# Actualizar container con nueva imagen
az containerapp update -n dagster-scrapers -g inmoleads-crm --image inmoleadsacr.azurecr.io/casa-teva-dagster:latest

# Consultar BD Azure
PGPASSWORD='ataulfo1!' psql -h inmoleads-db.postgres.database.azure.com -U inmoleadsadmin -d inmoleadsdb -c "SELECT COUNT(*) FROM marts.dim_leads;"
```

## URLs Locales

- CRM Web: http://localhost:8000
- Admin Django: http://localhost:8000/admin
- Dagster UI: http://localhost:3000

## Estructura del Proyecto

```
casa-teva-lead-system/
├── backend/
│   ├── apps/
│   │   ├── core/          # Tenant, usuarios, zonas geograficas
│   │   └── leads/         # Modelo Lead, notas, estados, blacklist
│   ├── templates/
│   └── casa_teva/         # Settings Django
├── scrapers/
│   ├── camoufox_milanuncios.py  # Milanuncios (anti-detect, FREE)
│   ├── camoufox_idealista.py    # Idealista (anti-detect, FREE)
│   ├── botasaurus_pisos.py      # Pisos.com
│   ├── botasaurus_habitaclia.py # Habitaclia
│   └── botasaurus_fotocasa.py   # Fotocasa
├── dagster/                    # Pipelines de orquestacion
│   └── casa_teva_pipeline/
│       ├── assets/             # scraping_assets.py
│       ├── resources/          # postgres_resource.py
│       └── schedules/          # scraping_schedule.py
├── dbt_project/                # ETL transformations
├── .github/workflows/          # CI/CD
│   └── build-dagster.yml       # Build y push a ACR
├── run_camoufox_*.py           # Runner scripts (Camoufox)
├── run_*_scraper.py            # Runner scripts (Botasaurus)
├── Dockerfile                  # Imagen para Dagster
└── docker-compose.yml          # Desarrollo local
```

## Scrapers - Tecnologias

### Camoufox (Milanuncios + Idealista)
Camoufox es un browser anti-detect basado en Firefox con inyeccion de fingerprints a nivel C++.
**Coste: GRATIS** (open source)

Bypasses:
- **GeeTest** (Milanuncios): Captcha de deslizar
- **DataDome** (Idealista): Anti-bot avanzado

```bash
# Ejecucion manual
python run_camoufox_milanuncios.py salou cambrils --max-pages 2
python run_camoufox_idealista.py salou cambrils --max-pages 2

# Ver zonas disponibles
python run_camoufox_idealista.py --list-zones
```

### Botasaurus (Pisos.com, Habitaclia, Fotocasa)
Framework de scraping con Chrome, para portales sin anti-bot agresivo.
**Coste: GRATIS** (open source)

```bash
python run_pisos_scraper.py --zones salou --postgres
python run_habitaclia_scraper.py --zones salou --postgres
python run_fotocasa_scraper.py --zones salou --postgres
```

## Decisiones de Diseno Importantes

1. **Lead ID es INTEGER**: Hash truncado del anuncio, generado con `int(md5_hash, 16) % 2147483647`
2. **PostgreSQL host en Docker**: Usar `postgres` (no `localhost`)
3. **Lead tabla (managed=False)**: Django no gestiona migraciones de marts.dim_leads
4. **Estados en LeadEstado**: Tabla separada para estados CRM (permite actualizar sin tocar lead)
5. **Playwright en /opt/playwright**: Navegadores instalados en el contenedor
6. **Camoufox necesita Xvfb**: Para headless mode en contenedores Linux
7. **Todos los scrapers son GRATUITOS**: Ya no usamos ScrapingBee (era de pago)

## Credenciales

### Desarrollo (Local)
```
PostgreSQL:
  - Host: postgres (Docker) / localhost
  - DB: casa_teva_db
  - User: casa_teva
  - Password: casateva2024
```

### Produccion (Azure)
```
PostgreSQL:
  - Host: inmoleads-db.postgres.database.azure.com
  - DB: inmoleadsdb
  - User: inmoleadsadmin
  - Password: ataulfo1!
  - SSL: require

ACR (Container Registry):
  - Server: inmoleadsacr.azurecr.io
  - User: inmoleadsacr
```

## Zonas de Scraping Disponibles

### Milanuncios / Idealista (Camoufox)
- **Lleida**: lleida_ciudad, balaguer, mollerussa, tarrega
- **Tarragona**: tarragona_ciudad
- **Costa Daurada**: salou, cambrils, reus, vendrell, altafulla, torredembarra, calafell, valls
- **Terres de l'Ebre**: tortosa, amposta

### Pisos.com / Habitaclia / Fotocasa (Botasaurus)
- **Lleida**: lleida_capital, lleida_provincia
- **Tarragona**: tarragona_capital, tarragona_provincia
- **Ciudades**: salou, cambrils, reus, vendrell, calafell, torredembarra, altafulla, valls, tortosa, amposta

## Problemas Conocidos

- La tabla `marts.dim_leads` debe existir para que Django funcione
- Camoufox necesita Xvfb y GTK3 en Linux (ya instalados en Dockerfile)
- Wallapop scraper desactivado (API privada, no scrapeable)

## GitHub y CI/CD

- **Repo**: gilito11/casaTevaLeads
- **Issues**: `gh issue list --repo gilito11/casaTevaLeads`
- **CI/CD**: GitHub Actions -> Azure Container Registry -> Azure Container Apps

### Workflow de Despliegue
1. Push a master
2. GitHub Actions construye imagen Docker
3. Push a Azure Container Registry (inmoleadsacr.azurecr.io)
4. `az containerapp update` para actualizar el contenedor

## Claude Code Preferences

- Run long commands (builds, deploys, tests) in background mode
- Make decisions without asking when possible - just do it
- Use parallel agents for codebase exploration
- Be concise, skip unnecessary confirmations

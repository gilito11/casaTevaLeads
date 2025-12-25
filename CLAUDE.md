# Casa Teva Lead System - CRM Inmobiliario

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de portales (Milanuncios, Pisos.com) con CRM para gestion de contactos.

## Stack Tecnologico
- **Backend**: Django 5.x + Django REST Framework
- **Base de datos**: PostgreSQL 16 (Azure PostgreSQL en produccion)
- **Scrapers**: Scrapy + Playwright (headless Chromium)
- **Orquestacion**: Dagster (pipelines)
- **Frontend**: Django Templates + HTMX + TailwindCSS
- **Contenedores**: Docker Compose (local) / Azure Container Apps (produccion)

## Arquitectura de Datos

```
Scrapers → marts.dim_leads (tabla) → Django Lead model
```

- `marts.dim_leads`: Tabla principal donde se guardan los leads
- `Lead` model: `managed=False`, apunta a la tabla
- `lead_id`: INTEGER (hash truncado del anuncio_id)
- `LeadEstado`: Tabla separada para gestionar estados CRM

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
docker exec casa-teva-web python run_milanuncios_scraper.py --zones cambrils --postgres
docker exec casa-teva-web python run_pisos_scraper.py --zones salou --postgres

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
│   ├── milanuncios_scraper.py  # Scraper principal
│   ├── pisos_scraper.py        # Scraper Pisos.com
│   └── base_scraper.py         # Clase base con PostgreSQL
├── dagster/                    # Pipelines de orquestacion
│   └── casa_teva_pipeline/
│       ├── assets/             # scraping_assets.py
│       ├── resources/          # postgres_resource.py
│       └── schedules/          # scraping_schedule.py
├── .github/workflows/          # CI/CD
│   └── build-dagster.yml       # Build y push a ACR
├── run_*_scraper.py            # Scripts de ejecucion
├── Dockerfile                  # Imagen para Dagster
└── docker-compose.yml          # Desarrollo local
```

## Decisiones de Diseno Importantes

1. **Lead ID es INTEGER**: Hash truncado del anuncio, generado con `int(md5_hash, 16) % 2147483647`
2. **PostgreSQL host en Docker**: Usar `postgres` (no `localhost`)
3. **Lead tabla (managed=False)**: Django no gestiona migraciones de marts.dim_leads
4. **Estados en LeadEstado**: Tabla separada para estados CRM (permite actualizar sin tocar lead)
5. **Playwright en /opt/playwright**: Navegadores instalados en el contenedor
6. **Scrapers activos**: Solo Milanuncios y Pisos.com funcionan actualmente

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

### Milanuncios (todas las zonas)
- **Lleida**: lleida_ciudad, lleida_20km, lleida_30km, lleida_40km, lleida_50km, la_bordeta, balaguer, mollerussa, tremp, tarrega
- **Tarragona**: tarragona_ciudad, tarragona_20km, tarragona_30km, tarragona_40km, tarragona_50km
- **Costa Daurada**: salou, cambrils, reus, vendrell, altafulla, torredembarra, miami_platja, hospitalet_infant, calafell, coma_ruga, valls, montblanc, vila_seca
- **Terres de l'Ebre**: tortosa, amposta, deltebre, ametlla_mar, sant_carles_rapita

### Pisos.com
- **Lleida**: lleida_capital, lleida_provincia
- **Tarragona**: tarragona_capital, tarragona_provincia
- **Ciudades**: salou, cambrils, reus, vendrell, calafell, torredembarra, altafulla, valls, tortosa, amposta

## Problemas Conocidos

- Milanuncios puede bloquear sin cookies (anti-bot) - ejecutar `python scrapers/capture_cookies.py`
- Wallapop y Fotocasa scrapers estan desactivados (no funcionan actualmente)
- La tabla `marts.dim_leads` debe existir para que Django funcione

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

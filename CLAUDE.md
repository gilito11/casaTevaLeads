# Casa Teva Lead System - CRM Inmobiliario

## Resumen
Sistema de captación de leads inmobiliarios mediante scraping de portales (Milanuncios, Fotocasa, Wallapop) con CRM para gestión de contactos.

## Stack Tecnológico
- **Backend**: Django 5.x + Django REST Framework
- **Base de datos**: PostgreSQL 16
- **Scrapers**: Scrapy + Playwright (headless Chromium)
- **Orquestación**: Dagster (pipelines)
- **Frontend**: Django Templates + HTMX + TailwindCSS
- **Contenedores**: Docker Compose

## Arquitectura de Datos

```
Scrapers → raw.raw_listings (JSONB) → marts.dim_leads (VIEW) → Django Lead model
```

- `raw.raw_listings`: Tabla real donde se guardan los datos scrapeados
- `marts.dim_leads`: Vista SQL que transforma los datos para Django
- `Lead` model: `managed=False`, apunta a la vista
- `lead_id`: Hash MD5 (texto), NO es integer

## Docker Services

| Servicio | Puerto | Contenedor |
|----------|--------|------------|
| Django Web | 8000 | casa-teva-web |
| PostgreSQL | 5432 | casa-teva-postgres |
| Dagster | 3000 | casa-teva-dagster |

## Comandos Frecuentes

```bash
# Iniciar todo
docker-compose up -d

# Ver logs
docker-compose logs web --tail 50
docker-compose logs web -f  # seguir en tiempo real

# Reconstruir después de cambios en Dockerfile
docker-compose build web dagster && docker-compose up -d

# Ejecutar scraper manualmente
docker exec casa-teva-web bash -c "cd /app && python run_milanuncios_scraper.py --zones cambrils --postgres"

# Consultar base de datos
docker exec casa-teva-postgres psql -U casa_teva -d casa_teva_db -c "SELECT COUNT(*) FROM raw.raw_listings;"

# Ver leads en la vista
docker exec casa-teva-postgres psql -U casa_teva -d casa_teva_db -c "SELECT * FROM marts.dim_leads LIMIT 5;"
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
│   │   ├── core/          # Tenant, usuarios, vistas principales
│   │   ├── leads/         # Modelo Lead, notas, estados
│   │   └── analytics/     # (futuro)
│   ├── templates/
│   └── casa_teva/         # Settings Django
├── scrapers/
│   ├── milanuncios_scraper.py
│   ├── fotocasa_scraper.py
│   ├── wallapop_scraper.py
│   └── base_scraper.py    # Clase base con PostgreSQL
├── dagster/               # Pipelines de orquestación
├── run_*_scraper.py       # Scripts de ejecución
└── docker-compose.yml
```

## Decisiones de Diseño Importantes

1. **Lead ID es hash MD5**: No usar `<int:lead_id>` en URLs, usar `<str:lead_id>`
2. **PostgreSQL host en Docker**: Usar `postgres` (no `localhost`)
3. **Lead es vista (managed=False)**: No se puede hacer `lead.save()` directamente
4. **Estados se guardan en LeadEstado**: Tabla separada para estados CRM
5. **Playwright necesita navegadores**: Instalados en `/opt/playwright`

## Credenciales Desarrollo

```
PostgreSQL:
  - Host: postgres (Docker) / localhost (local)
  - DB: casa_teva_db
  - User: casa_teva
  - Password: casateva2024

Django Admin:
  - User: admin
  - Password: (crear con createsuperuser)
```

## Zonas de Scraping Disponibles

**Milanuncios**: la_bordeta, lleida_ciudad, tarragona_ciudad, salou, cambrils, costa_dorada, reus
**Wallapop**: barcelona, lleida, tarragona, salou, cambrils, reus
**Fotocasa**: tarragona_ciudad, tarragona_provincia, lleida_ciudad, lleida_provincia, barcelona_ciudad

## Problemas Conocidos

- Milanuncios puede bloquear sin cookies (anti-bot)
- Ejecutar `python scrapers/capture_cookies.py` si hay bloqueos
- La vista `marts.dim_leads` debe existir para que Django funcione

## GitHub

- Repo: gilito11/casaTevaLeads
- Issues: `gh issue list --repo gilito11/casaTevaLeads`

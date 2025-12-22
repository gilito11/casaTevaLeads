# Casa Teva Lead System

Sistema de captación de leads inmobiliarios mediante web scraping de portales españoles, con CRM integrado para gestión de contactos.

## Características

- **Scraping automatizado** de portales inmobiliarios (Milanuncios, Pisos.com)
- **CRM web** para gestión de leads con estados, notas y asignaciones
- **Orquestación con Dagster** para ejecución programada
- **Filtrado inteligente** de particulares vs inmobiliarias
- **Detección de duplicados** mediante anuncio_id único
- **Blacklist** para evitar re-scrapear anuncios descartados
- **Operaciones bulk** para cambio masivo de estados

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Backend | Django 5.x + Django REST Framework |
| Base de datos | PostgreSQL 16 |
| Scrapers | Scrapy + Playwright (headless Chromium) |
| Orquestación | Dagster |
| Frontend | Django Templates + HTMX + TailwindCSS |
| Contenedores | Docker Compose |
| Cloud | Azure Container Apps + Azure PostgreSQL |

## Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Milanuncios   │     │    Pisos.com    │     │   (Futuro)      │
│    Scraper      │     │    Scraper      │     │   Scrapers      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      Dagster           │
                    │   (Orquestación)       │
                    │   Puerto: 3000         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     PostgreSQL          │
                    │   marts.dim_leads       │
                    │   Puerto: 5432          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      Django CRM         │
                    │   Puerto: 8000          │
                    └─────────────────────────┘
```

## Inicio Rápido (Local)

```bash
# Clonar repositorio
git clone https://github.com/gilito11/casaTevaLeads.git
cd casaTevaLeads

# Iniciar servicios con Docker
docker-compose up -d

# Acceder a las interfaces
# CRM Web: http://localhost:8000
# Dagster: http://localhost:3000
```

## Despliegue en Azure

El proyecto está desplegado en Azure con:
- **Azure Container Apps**: Dagster + Scrapers
- **Azure App Service**: Django CRM
- **Azure PostgreSQL**: Base de datos

### URLs de Producción
- CRM: https://inmoleads-crm.azurewebsites.net
- Dagster: https://dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io

## Ejecución de Scrapers

### Manual (local)
```bash
# Ejecutar scraper de Milanuncios
docker exec casa-teva-web python run_milanuncios_scraper.py --zones lleida_ciudad,salou --postgres

# Ejecutar scraper de Pisos.com
docker exec casa-teva-web python run_pisos_scraper.py --zones lleida_capital,tarragona_capital --postgres
```

### Automatizado (Dagster)
Los scrapers se ejecutan automáticamente a las horas configuradas (horario español):
- 9:00, 11:00, 13:00, 15:00, 17:00, 19:00

Para ejecución manual, acceder a Dagster UI y hacer clic en "Materialize all".

## Zonas Disponibles

### Milanuncios
- **Lleida**: lleida_ciudad, lleida_20km, lleida_30km, lleida_40km, lleida_50km, la_bordeta, balaguer, mollerussa, tremp, tarrega
- **Tarragona**: tarragona_ciudad, tarragona_20km, tarragona_30km, tarragona_40km, tarragona_50km
- **Costa Daurada**: salou, cambrils, reus, vendrell, altafulla, torredembarra, miami_platja, hospitalet_infant, calafell, coma_ruga, valls, montblanc, vila_seca
- **Terres de l'Ebre**: tortosa, amposta, deltebre, ametlla_mar, sant_carles_rapita

### Pisos.com
- **Lleida**: lleida_capital, lleida_provincia
- **Tarragona**: tarragona_capital, tarragona_provincia, salou, cambrils, reus, vendrell, calafell, torredembarra, valls, tortosa, amposta

## Estructura del Proyecto

```
casa-teva-lead-system/
├── backend/                 # Django application
│   ├── apps/
│   │   ├── core/           # Tenants, usuarios
│   │   └── leads/          # Modelo Lead, notas, estados
│   └── templates/          # HTML templates
├── scrapers/               # Web scrapers
│   ├── milanuncios_scraper.py
│   ├── pisos_scraper.py
│   └── base_scraper.py
├── dagster/                # Pipeline orchestration
│   └── casa_teva_pipeline/
├── docker-compose.yml      # Local development
├── Dockerfile              # Container image
└── .github/workflows/      # CI/CD
```

## Contribuir

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Add nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abrir Pull Request

## Licencia

Proyecto privado - Casa Teva Inmobiliaria

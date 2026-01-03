# Casa Teva Lead System

Sistema de captacion de leads inmobiliarios mediante web scraping de portales espanoles, con CRM integrado.

## Caracteristicas

- **Scraping automatizado** de 4 portales inmobiliarios (Habitaclia, Fotocasa, Milanuncios, Idealista)
- **CRM web** para gestion de leads con estados, notas y asignaciones
- **Dashboard de analytics** con metricas de leads por portal, zona y estado
- **Extraccion de fotos** de las propiedades
- **Extraccion de telefonos** de descripciones y botones
- **Orquestacion con Dagster** para ejecucion programada
- **Filtrado inteligente** de particulares vs inmobiliarias
- **Deteccion de duplicados** mediante listing_id unico

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Django 5.x + Django REST Framework |
| Base de datos | PostgreSQL 16 |
| Scrapers (gratis) | Botasaurus (Habitaclia, Fotocasa) |
| Scrapers (anti-bot) | ScrapingBee (Milanuncios, Idealista) |
| ETL | dbt (raw -> staging -> marts) |
| Orquestacion | Dagster |
| Frontend | Django Templates + HTMX + TailwindCSS |
| Contenedores | Docker Compose (local) / Azure Container Apps (prod) |

## Arquitectura

```
┌─────────────────┐  ┌─────────────────┐
│   Habitaclia    │  │    Fotocasa     │
│  (Botasaurus)   │  │  (Botasaurus)   │
│     GRATIS      │  │     GRATIS      │
└────────┬────────┘  └────────┬────────┘
         │                    │
         │  ┌─────────────────┴─────────────────┐
         │  │                                   │
         │  │  ┌─────────────┐  ┌─────────────┐ │
         │  │  │ Milanuncios │  │  Idealista  │ │
         │  │  │(ScrapingBee)│  │(ScrapingBee)│ │
         │  │  │ 75 cred/req │  │ 75 cred/req │ │
         │  │  └──────┬──────┘  └──────┬──────┘ │
         │  │         │                │        │
         └──┴─────────┴────────────────┴────────┘
                              │
                 ┌────────────▼────────────┐
                 │      Dagster            │
                 │   (Orquestacion)        │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │     PostgreSQL          │
                 │   raw -> dbt -> marts   │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │      Django CRM         │
                 │   + Analytics Dashboard │
                 └─────────────────────────┘
```

## Inicio Rapido (Local)

```bash
# Clonar repositorio
git clone https://github.com/gilito11/casaTevaLeads.git
cd casaTevaLeads

# Iniciar servicios con Docker
docker-compose up -d

# CRM Web: http://localhost:8000
# Dagster: http://localhost:3000
```

## Despliegue en Azure

- **Azure Container Apps**: Dagster + Scrapers
- **Azure App Service**: Django CRM
- **Azure PostgreSQL**: Base de datos

### URLs de Produccion
- CRM: https://inmoleads-crm.azurewebsites.net
- Dagster: https://dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io

## Estado de Scrapers (Enero 2026)

| Portal | Tecnologia | Coste | Datos |
|--------|-----------|-------|-------|
| Habitaclia | Botasaurus | Gratis | titulo, precio, metros, fotos, telefono* |
| Fotocasa | Botasaurus | Gratis | titulo, precio, metros, fotos, telefono* |
| Milanuncios | ScrapingBee | 75 cred | titulo, precio, metros, fotos, telefono |
| Idealista | ScrapingBee | 75 cred | titulo, precio, metros, fotos, telefono |

*Telefono extraido de la descripcion del anuncio

## Ejecucion de Scrapers

```bash
# Todos los scrapers
python run_all_scrapers.py --zones salou cambrils --postgres

# Scrapers especificos
python run_all_scrapers.py --portals habitaclia fotocasa --zones salou
python run_all_scrapers.py --portals milanuncios idealista --zones reus
```

## Estructura del Proyecto

```
casa-teva-lead-system/
├── backend/                 # Django application
│   ├── apps/
│   │   ├── core/           # Lead model, zonas
│   │   ├── leads/          # Estados, analytics
│   │   └── analytics/      # Dashboard
│   └── templates/          # HTML templates
├── scrapers/               # Web scrapers
│   ├── botasaurus_habitaclia.py
│   ├── botasaurus_fotocasa.py
│   ├── scrapingbee_milanuncios.py
│   └── scrapingbee_idealista.py
├── dagster/                # Pipeline orchestration
├── dbt_project/            # ETL transformations
├── docker-compose.yml
└── .github/workflows/      # CI/CD
```

## CI/CD

Push a master -> GitHub Actions -> Azure Container Registry -> Azure Container Apps

## Licencia

Proyecto privado - Casa Teva Inmobiliaria

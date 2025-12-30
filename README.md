# Casa Teva Lead System

Sistema de captacion de leads inmobiliarios mediante web scraping de portales espanoles, con CRM integrado para gestion de contactos.

## Caracteristicas

- **Scraping automatizado** de 5 portales inmobiliarios (Milanuncios, Idealista, Habitaclia, Fotocasa, Pisos.com)
- **100% GRATUITO** - Sin APIs de pago, usando Camoufox y Botasaurus
- **CRM web** para gestion de leads con estados, notas y asignaciones
- **Dashboard de analytics** con metricas de leads por portal, zona y estado
- **Extraccion de fotos** de las propiedades desde los portales
- **Orquestacion con Dagster** para ejecucion programada
- **Filtrado inteligente** de particulares vs inmobiliarias
- **Deteccion de duplicados** mediante anuncio_id unico
- **Blacklist** para evitar re-scrapear anuncios descartados
- **Operaciones bulk** para cambio masivo de estados

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Django 5.x + Django REST Framework |
| Base de datos | PostgreSQL 16 |
| Scrapers (anti-bot) | Camoufox (Milanuncios, Idealista) |
| Scrapers (browser) | Botasaurus (Habitaclia, Fotocasa) |
| Scrapers (HTTP) | requests+BeautifulSoup (Pisos.com) |
| ETL | dbt (raw -> staging -> marts) |
| Orquestacion | Dagster |
| Frontend | Django Templates + HTMX + TailwindCSS |
| Contenedores | Docker Compose (local) / Azure Container Apps (prod) |

## Arquitectura

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Milanuncios   │  │    Idealista    │  │    Pisos.com    │
│   (Camoufox)    │  │   (Camoufox)    │  │  (Botasaurus)   │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
┌────────┴────────┐  ┌────────┴────────┐          │
│   Habitaclia    │  │    Fotocasa     │          │
│  (Botasaurus)   │  │  (Botasaurus)   │          │
└────────┬────────┘  └────────┬────────┘          │
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                 ┌────────────▼────────────┐
                 │      Dagster            │
                 │   (Orquestacion)        │
                 │   Puerto: 3000          │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │     PostgreSQL          │
                 │   raw -> dbt -> marts   │
                 │   Puerto: 5432          │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │      Django CRM         │
                 │   + Analytics Dashboard │
                 │   Puerto: 8000          │
                 └─────────────────────────┘
```

## Inicio Rapido (Local)

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

El proyecto esta desplegado en Azure con:
- **Azure Container Apps**: Dagster + Scrapers
- **Azure App Service**: Django CRM
- **Azure PostgreSQL**: Base de datos

### URLs de Produccion
- CRM: https://inmoleads-crm.azurewebsites.net
- Dagster: https://dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io

## Ejecucion de Scrapers

### Camoufox (Milanuncios, Idealista)
Anti-detect browser que bypasea GeeTest y DataDome. **GRATIS**.

```bash
# Milanuncios
python run_camoufox_milanuncios.py salou cambrils --max-pages 2

# Idealista
python run_camoufox_idealista.py salou cambrils --max-pages 2

# Ver zonas disponibles
python run_camoufox_idealista.py --list-zones
```

### Pisos.com (HTTP puro - sin browser)
Scraping con requests+BeautifulSoup. **10x mas rapido**. Pisos.com no tiene anti-bot.

```bash
python run_pisos_scraper.py --zones salou --postgres --max-pages 2
```

### Botasaurus (Habitaclia, Fotocasa)
Framework de scraping con Chrome. **GRATIS**.

```bash
python run_habitaclia_scraper.py --zones salou --postgres
python run_fotocasa_scraper.py --zones salou --postgres
```

### Automatizado (Dagster)
Los scrapers se ejecutan automaticamente segun el schedule configurado en Dagster.
Para ejecucion manual, acceder a Dagster UI y hacer clic en "Materialize all".

## Zonas Disponibles

### Milanuncios / Idealista (Camoufox)
- **Lleida**: lleida_ciudad, balaguer, mollerussa, tarrega
- **Tarragona**: tarragona_ciudad
- **Costa Daurada**: salou, cambrils, reus, vendrell, altafulla, torredembarra, calafell, valls
- **Terres de l'Ebre**: tortosa, amposta

### Pisos.com / Habitaclia / Fotocasa (Botasaurus)
- **Lleida**: lleida_capital, lleida_provincia
- **Tarragona**: tarragona_capital, tarragona_provincia
- **Ciudades**: salou, cambrils, reus, vendrell, calafell, torredembarra, altafulla, valls, tortosa, amposta

## Estructura del Proyecto

```
casa-teva-lead-system/
├── backend/                 # Django application
│   ├── apps/
│   │   ├── core/           # Tenants, usuarios
│   │   └── leads/          # Modelo Lead, notas, estados, analytics
│   └── templates/          # HTML templates
├── scrapers/               # Web scrapers
│   ├── http_pisos.py             # Pisos.com (HTTP - rapido)
│   ├── camoufox_milanuncios.py   # Milanuncios (Camoufox)
│   ├── camoufox_idealista.py     # Idealista (Camoufox)
│   ├── botasaurus_habitaclia.py  # Habitaclia (Botasaurus)
│   └── botasaurus_fotocasa.py    # Fotocasa (Botasaurus)
├── dagster/                # Pipeline orchestration
│   └── casa_teva_pipeline/
├── dbt_project/            # ETL transformations
├── docker-compose.yml      # Local development
├── Dockerfile              # Container image
└── .github/workflows/      # CI/CD
```

## CI/CD

- **Repo**: gilito11/casaTevaLeads
- **CI/CD**: GitHub Actions -> Azure Container Registry -> Azure Container Apps

### Workflow de Despliegue
1. Push a master
2. GitHub Actions construye imagen Docker
3. Push a Azure Container Registry (inmoleadsacr.azurecr.io)
4. Despliegue automatico a Azure Container Apps

## Licencia

Proyecto privado - Casa Teva Inmobiliaria

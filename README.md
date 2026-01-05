<p align="center">
  <img src="https://img.shields.io/badge/🏠-Casa%20Teva%20Lead%20System-blue?style=for-the-badge&labelColor=1a1a2e" alt="Casa Teva" />
</p>

<h1 align="center">
  🏡 Casa Teva Lead System
</h1>

<p align="center">
  <strong>Sistema inteligente de captación de leads inmobiliarios</strong><br>
  Scraping automatizado de portales españoles + CRM integrado + Analytics Dashboard
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Django-5.x-092e20?style=flat-square&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169e1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/dbt-Core-ff694b?style=flat-square&logo=dbt&logoColor=white" alt="dbt" />
  <img src="https://img.shields.io/badge/Dagster-latest-5c4ee5?style=flat-square&logo=dagster&logoColor=white" alt="Dagster" />
  <img src="https://img.shields.io/badge/Azure-Deployed-0078d4?style=flat-square&logo=microsoft-azure&logoColor=white" alt="Azure" />
  <img src="https://img.shields.io/badge/License-Private-red?style=flat-square" alt="License" />
</p>

<p align="center">
  <a href="#-características">Características</a> •
  <a href="#-arquitectura">Arquitectura</a> •
  <a href="#-inicio-rápido">Inicio Rápido</a> •
  <a href="#-portales-soportados">Portales</a> •
  <a href="#-documentación">Docs</a>
</p>

---

## ✨ Características

| Feature | Descripción |
|---------|-------------|
| 🕷️ **Multi-portal Scraping** | Extrae leads de 4 portales inmobiliarios españoles simultáneamente |
| 🎯 **Filtrado Inteligente** | Detecta y filtra automáticamente anuncios de agencias (solo particulares) |
| 📱 **Extracción de Contactos** | Captura teléfonos de descripciones y botones de contacto |
| 📸 **Galería de Fotos** | Descarga y almacena todas las imágenes de cada propiedad |
| 🔄 **Deduplicación** | Identifica duplicados por listing_id único entre ejecuciones |
| 📊 **Analytics Dashboard** | Métricas en tiempo real, embudo de conversión, comparativas |
| 🏷️ **CRM Completo** | Gestión de estados, notas, asignaciones y seguimiento |
| ⏰ **Schedule Optimizado** | Ejecución programada a las 12:00 y 18:00 (horarios óptimos) |
| 🚀 **CI/CD Automático** | Deploy automático a Azure con GitHub Actions |

---

## 🏗️ Arquitectura

```
                              ┌─────────────────────────────────────────┐
                              │           🌐 PORTALES WEB               │
                              └─────────────────────────────────────────┘
                                    │            │            │
          ┌─────────────────────────┼────────────┼────────────┼─────────────────────────┐
          │                         │            │            │                         │
          ▼                         ▼            ▼            ▼                         │
   ┌──────────────┐          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
   │ 🏠 Habitaclia│          │ 📸 Fotocasa  │  │ 📋 Milanuncios│  │ 🏢 Idealista │      │
   │  Botasaurus  │          │  Botasaurus  │  │  ScrapingBee │  │  ScrapingBee │      │
   │    GRATIS    │          │    GRATIS    │  │   75 cred    │  │   75 cred    │      │
   └──────┬───────┘          └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
          │                         │                 │                 │              │
          └─────────────────────────┴────────┬────────┴─────────────────┘              │
                                             │                                          │
                                             ▼                                          │
                              ┌──────────────────────────────┐                         │
                              │     ⚙️ DAGSTER ORCHESTRATOR   │                         │
                              │   Schedule: 12:00 / 18:00    │                         │
                              └──────────────┬───────────────┘                         │
                                             │                                          │
                                             ▼                                          │
                              ┌──────────────────────────────┐                         │
                              │    🗄️ POSTGRESQL DATABASE     │                         │
                              │                              │                         │
                              │  raw_listings ──► dbt ──►   │                         │
                              │    (JSONB)    staging  marts │                         │
                              └──────────────┬───────────────┘                         │
                                             │                                          │
                                             ▼                                          │
                              ┌──────────────────────────────┐                         │
                              │      🖥️ DJANGO CRM + WEB      │                         │
                              │   HTMX + TailwindCSS + DRF   │                         │
                              └──────────────────────────────┘                         │
                                                                                        │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16 (o usar Docker)

### Instalación Local

```bash
# 1. Clonar repositorio
git clone https://github.com/gilito11/casaTevaLeads.git
cd casaTevaLeads

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar servicios con Docker
docker-compose up -d

# 5. Aplicar migraciones
cd backend && python manage.py migrate

# 6. Crear usuario admin
python manage.py createsuperuser
```

### URLs Locales

| Servicio | URL |
|----------|-----|
| 🖥️ CRM Web | http://localhost:8000 |
| ⚙️ Dagster UI | http://localhost:3000 |
| 🐘 PostgreSQL | localhost:5432 |

---

## 🌐 Portales Soportados

| Portal | Tecnología | Coste | Datos Extraídos |
|--------|------------|-------|-----------------|
| ![Habitaclia](https://img.shields.io/badge/-Habitaclia-ff6b35?style=flat-square) | Botasaurus | ✅ Gratis | título, precio, m², fotos, teléfono* |
| ![Fotocasa](https://img.shields.io/badge/-Fotocasa-1a73e8?style=flat-square) | Botasaurus | ✅ Gratis | título, precio, m², fotos, teléfono* |
| ![Milanuncios](https://img.shields.io/badge/-Milanuncios-ffc107?style=flat-square) | ScrapingBee | 75 credits | título, precio, m², fotos, teléfono |
| ![Idealista](https://img.shields.io/badge/-Idealista-5cb85c?style=flat-square) | ScrapingBee | 75 credits | título, precio, m², fotos, teléfono |

> *Teléfono extraído de la descripción del anuncio mediante regex

---

## 📁 Estructura del Proyecto

```
casa-teva-lead-system/
│
├── 🖥️ backend/                    # Django Application
│   ├── apps/
│   │   ├── core/                 # Modelos base, zonas, tenants
│   │   ├── leads/                # Estados CRM, vistas de leads
│   │   └── analytics/            # Dashboard y API de métricas
│   ├── templates/                # HTML (HTMX + Tailwind)
│   └── casa_teva/                # Settings Django
│
├── 🕷️ scrapers/                   # Web Scrapers
│   ├── botasaurus_habitaclia.py  # Scraper Habitaclia
│   ├── botasaurus_fotocasa.py    # Scraper Fotocasa
│   ├── scrapingbee_milanuncios.py # Scraper Milanuncios
│   └── scrapingbee_idealista.py  # Scraper Idealista
│
├── ⚙️ dagster/                    # Pipeline Orchestration
│   ├── assets/                   # Dagster assets
│   └── schedules/                # Programación de jobs
│
├── 📊 dbt_project/                # ETL Transformations
│   ├── models/
│   │   ├── staging/              # stg_* views
│   │   └── marts/                # dim_leads (incremental)
│   └── tests/                    # dbt tests
│
├── 🐳 docker-compose.yml         # Local development
├── 📋 requirements.txt           # Python dependencies
└── ⚡ .github/workflows/         # CI/CD pipelines
```

---

## 💻 Uso

### Ejecutar Scrapers

```bash
# Todos los portales, todas las zonas
python run_all_scrapers.py --postgres

# Portales específicos
python run_all_scrapers.py --portals habitaclia fotocasa --zones salou

# Solo ScrapingBee (consume créditos)
python run_all_scrapers.py --portals milanuncios idealista --zones reus
```

### Pipeline dbt

```bash
cd dbt_project

# Ejecutar staging models
dbt run --select staging.*

# Ejecutar marts
dbt run --select dim_leads

# Tests
dbt test
```

---

## ☁️ Despliegue en Azure

El sistema está desplegado en Azure con la siguiente arquitectura:

| Servicio | Plataforma Azure |
|----------|-----------------|
| Django CRM | Azure App Service |
| Dagster + Scrapers | Azure Container Apps |
| Base de datos | Azure PostgreSQL Flexible Server |
| Registry | Azure Container Registry |

### URLs de Producción

- 🖥️ **CRM**: https://inmoleads-crm.azurewebsites.net
- ⚙️ **Dagster**: https://dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io

---

## 🔧 Stack Tecnológico

<table>
  <tr>
    <td align="center"><strong>Backend</strong></td>
    <td align="center"><strong>Frontend</strong></td>
    <td align="center"><strong>Data</strong></td>
    <td align="center"><strong>Infra</strong></td>
  </tr>
  <tr>
    <td>
      <img src="https://img.shields.io/badge/Django-092e20?style=flat-square&logo=django" /><br>
      <img src="https://img.shields.io/badge/DRF-ff1709?style=flat-square" /><br>
      <img src="https://img.shields.io/badge/Python-3776ab?style=flat-square&logo=python&logoColor=white" />
    </td>
    <td>
      <img src="https://img.shields.io/badge/HTMX-3d72d7?style=flat-square" /><br>
      <img src="https://img.shields.io/badge/Tailwind-38bdf8?style=flat-square&logo=tailwindcss&logoColor=white" /><br>
      <img src="https://img.shields.io/badge/AlpineJS-8bc0d0?style=flat-square&logo=alpine.js&logoColor=white" />
    </td>
    <td>
      <img src="https://img.shields.io/badge/PostgreSQL-4169e1?style=flat-square&logo=postgresql&logoColor=white" /><br>
      <img src="https://img.shields.io/badge/dbt-ff694b?style=flat-square&logo=dbt&logoColor=white" /><br>
      <img src="https://img.shields.io/badge/Dagster-5c4ee5?style=flat-square&logo=dagster&logoColor=white" />
    </td>
    <td>
      <img src="https://img.shields.io/badge/Docker-2496ed?style=flat-square&logo=docker&logoColor=white" /><br>
      <img src="https://img.shields.io/badge/Azure-0078d4?style=flat-square&logo=microsoft-azure&logoColor=white" /><br>
      <img src="https://img.shields.io/badge/GitHub_Actions-2088ff?style=flat-square&logo=github-actions&logoColor=white" />
    </td>
  </tr>
</table>

---

## 📈 Analytics API

```
GET /analytics/api/kpis/                  # KPIs globales
GET /analytics/api/embudo/                # Embudo de conversión
GET /analytics/api/leads-por-dia/         # Tendencia diaria
GET /analytics/api/comparativa-portales/  # Comparativa entre portales
GET /analytics/api/precios-por-zona/      # Precios por zona
GET /analytics/api/export/                # Exportar a CSV
```

---

## 🔄 CI/CD

```
Push a master → GitHub Actions → Build → Azure Container Registry → Deploy Azure
```

El pipeline incluye:
- ✅ Build de imagen Docker
- ✅ Push a Azure Container Registry
- ✅ Deploy a Azure Container Apps (Dagster)
- ✅ Deploy a Azure App Service (Django)

---

## 🤝 Contribuir

¿Encontraste un bug o tienes una idea? Revisa nuestra [guía de contribución](CONTRIBUTING.md).

---

## 📄 Licencia

Proyecto privado - **Casa Teva Inmobiliaria** © 2026

---

<p align="center">
  <sub>Hecho con ❤️ para la captación inteligente de leads inmobiliarios</sub>
</p>

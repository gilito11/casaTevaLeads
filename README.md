<p align="center">
  <img src="https://img.shields.io/badge/🏠-FincaRadar-blue?style=for-the-badge&labelColor=1a1a2e" alt="FincaRadar" />
</p>

<h1 align="center">FincaRadar</h1>

<p align="center">
  <strong>CRM inmobiliario con captación automática de leads</strong><br>
  Scraping de 4 portales españoles · Contacto automatizado · Valoraciones ACM · Analytics
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Django-5.x-092e20?style=flat-square&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169e1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/dbt-Core-ff694b?style=flat-square&logo=dbt&logoColor=white" alt="dbt" />
  <img src="https://img.shields.io/badge/Cloudflare-Tunnel-f38020?style=flat-square&logo=cloudflare&logoColor=white" alt="Cloudflare" />
  <img src="https://img.shields.io/badge/Coste-~€4/mes-00c853?style=flat-square" alt="Coste" />
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-arquitectura">Arquitectura</a> •
  <a href="#-portales">Portales</a> •
  <a href="#-inicio-rápido">Inicio Rápido</a> •
  <a href="#-api">API</a>
</p>

---

## ✨ Features

### Captación
- **Scraping multi-portal** — Habitaclia, Fotocasa, Milanuncios, Idealista
- **Anti-bot bypass** — Botasaurus (Chrome), Camoufox (Firefox anti-detect) con proxy residencial
- **Deduplicación cross-portal** — Por teléfono + ubicación + precio + metros
- **Detección de bajadas de precio** — Histórico de precios con alertas (>5%)

### CRM
- **Lead scoring** — 0-90 pts: días en mercado, teléfono, fotos, precio relativo
- **Gestión de estados** — NUEVO → EN_PROCESO → CONTACTADO → INTERESADO → CLIENTE
- **Agenda de tareas** — Seguimiento por comercial con calendario
- **Contacto automatizado** — Envío de mensajes a 4 portales con rate limiting

### Valoraciones
- **ACM (Análisis Comparativo de Mercado)** — Búsqueda de comparables, índice de confianza
- **PDF de valoración** — Generación automática con datos del mercado
- **Widget embebible** — JS snippet para webs de terceros (`/api/widget/valorar/`)

### Plataforma
- **API REST v1** — Autenticación X-API-Key, filtros, paginación, webhooks
- **PWA** — Service Worker, Push Notifications, instalable en móvil
- **Alertas Telegram** — Resumen diario, bajadas de precio, errores de scraping
- **Analytics** — Dashboard con KPIs, embudo de conversión, métricas por portal/zona

---

## 🏗️ Arquitectura

```
         Contabo VPS (Windows Server)              GitHub Actions
         ─────────────────────────                  ──────────────
         │ Camoufox + IPRoyal proxy │               │ Botasaurus  │
         │ habitaclia, milanuncios  │               │ fotocasa    │
         │ L-X-V 13:00 CET         │               │ Camoufox    │
         │                          │               │ idealista   │
         │ Django CRM (waitress)    │               │ L-X-V 12:00 │
         │ Cloudflare Tunnel        │               └──────┬──────┘
         └────────────┬─────────────┘                      │
                      │                                    │
                      ▼                                    ▼
              ┌───────────────────────────────────────────────┐
              │          Neon PostgreSQL (Serverless)          │
              │                                               │
              │  raw.raw_listings → stg_* → dim_leads (dbt)  │
              └───────────────────────────────────────────────┘
                                    │
                                    ▼
                      https://fincaradar.com
                      Cloudflare CDN + SSL
```

### Costes

| Servicio | Coste |
|----------|-------|
| Contabo VPS (8GB, 2 vCPU) | €4.99/mes |
| Neon PostgreSQL | Gratis |
| GitHub Actions | Gratis |
| Cloudflare (DNS + Tunnel) | Gratis |
| 2Captcha (Habitaclia reCAPTCHA) | ~€3/mes |
| IPRoyal proxy (Idealista DataDome) | ~€1/mes* |
| **Total** | **~€9/mes** |

<sub>*IPRoyal: compra única de $7/GB, tráfico no expira. Estimado ~100-200MB/mes.</sub>

---

## 🌐 Portales

| Portal | Scraper | Anti-bot | Infraestructura |
|--------|---------|----------|-----------------|
| **Habitaclia** | Camoufox | Imperva → proxy residencial | VPS + GitHub Actions |
| **Fotocasa** | Botasaurus | Imperva (bloquea datacenter) | GitHub Actions |
| **Milanuncios** | Camoufox | GeeTest (bypass nativo) | VPS + GitHub Actions |
| **Idealista** | Camoufox | DataDome → proxy residencial | GitHub Actions |

**Datos extraídos**: listing_id, URL, título, precio, descripción, ubicación, teléfono, tipo de propiedad, habitaciones, baños, m², fotos, tipo de vendedor (particular/agencia).

**Contacto automático**: Login en portal → formulario/chat → mensaje personalizado. Rate limit: 5/día, delay 2-5min.

---

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.11+
- PostgreSQL 16 (o [Neon](https://neon.tech) gratuito)
- Google Chrome (para Botasaurus)

### Instalación

```bash
git clone https://github.com/gilito11/casaTevaLeads.git
cd casaTevaLeads

python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt

# Configurar .env en raíz del proyecto
cp .env.example .env  # Editar con tus credenciales

# Django
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Scraping manual

```bash
# Habitaclia (Botasaurus)
python run_habitaclia_scraper.py --zones salou cambrils --postgres

# Milanuncios (Camoufox)
python run_camoufox_milanuncios_scraper.py --zones tarragona --max-pages 2 --postgres

# Idealista (Camoufox + proxy)
python run_camoufox_idealista_scraper.py --zones igualada --max-pages 2 --postgres

# dbt transformaciones
cd dbt_project && dbt run --select staging marts
```

---

## 📡 API

### REST API v1

```
GET  /api/v1/leads/              # Listar leads (filtros, paginación)
GET  /api/v1/leads/{id}/         # Detalle de lead
POST /api/v1/leads/{id}/estado/  # Cambiar estado CRM
```

Autenticación: header `X-API-Key: ctv_xxxxx...`

### Analytics

```
GET /analytics/api/kpis/                  # KPIs globales
GET /analytics/api/embudo/                # Embudo de conversión
GET /analytics/api/leads-por-dia/         # Tendencia diaria
GET /analytics/api/comparativa-portales/  # Comparativa por portal
GET /analytics/api/precios-por-zona/      # Precios por zona
GET /analytics/api/export/                # Exportar CSV
```

### Widget valorador

```html
<script src="https://fincaradar.com/static/widget/valorador.js"></script>
<div id="valorador-widget" data-api-key="ctv_xxx"></div>
```

### Webhooks

Eventos: `new_lead`, `status_change`, `price_drop`. Firma HMAC-SHA256 en `X-Webhook-Signature`.

---

## 📁 Estructura

```
casa-teva-lead-system/
├── backend/                  # Django 5.x
│   ├── apps/
│   │   ├── leads/            # Lead model, CRM views, scoring, PDF
│   │   ├── acm/              # Análisis Comparativo de Mercado
│   │   ├── api_v1/           # REST API + API Keys
│   │   ├── widget/           # Widget valorador embebible
│   │   ├── analytics/        # Dashboard, métricas, export
│   │   ├── notifications/    # Telegram + Push notifications
│   │   └── core/             # Tenants, health, utilidades
│   └── templates/            # HTMX + TailwindCSS
├── scrapers/                 # Web scrapers
│   ├── botasaurus_*.py       # Chrome headless (hab, foto)
│   ├── camoufox_*.py         # Anti-detect Firefox (mil, ide, hab)
│   └── contact_automation/   # Auto-contacto (4 portales)
├── dbt_project/              # raw → staging → marts
├── ai_agents/                # Ollama vision scoring (PoC)
├── scripts/                  # VPS setup, cron, tunnel
└── .github/workflows/        # Scraping + contacto (GH Actions)
```

---

## 🔄 Scheduling

| Tarea | Schedule | Infraestructura |
|-------|----------|-----------------|
| Scraping habitaclia + milanuncios | L-X-V 13:00 CET | VPS (schtasks) |
| Scraping fotocasa + idealista | L-X-V 12:00 UTC | GitHub Actions (cron) |
| Contacto automático | L-V 18:00 CET | VPS (schtasks) |
| Alertas Telegram | Diario + eventos | Automático |

---

## 📄 Licencia

Proyecto privado — © 2026

<p align="center">
  <sub>Hecho con Django, dbt, y mucho scraping</sub>
</p>

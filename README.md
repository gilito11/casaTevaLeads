<p align="center">
  <img src="https://img.shields.io/badge/🏠-FincaRadar-blue?style=for-the-badge&labelColor=1a1a2e" alt="FincaRadar" />
</p>

<h1 align="center">FincaRadar</h1>

<p align="center">
  <strong>CRM inmobiliario con captación automática de leads</strong><br>
  Scraping de 5 portales españoles · Contacto automatizado · Valoraciones ACM · Analytics
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Django-5.x-092e20?style=flat-square&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169e1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/dbt-Core-ff694b?style=flat-square&logo=dbt&logoColor=white" alt="dbt" />
  <img src="https://img.shields.io/badge/Scrapling-0.4.7-6c47ff?style=flat-square" alt="Scrapling" />
  <img src="https://img.shields.io/badge/Coste-~€10/mes-00c853?style=flat-square" alt="Coste" />
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
- **Scraping multi-portal** — Habitaclia, Fotocasa, Milanuncios, Idealista y Wallapop
- **Anti-bot bypass** — Scrapling + Patchright (DataDome, Imperva, GeeTest sin proxy) y Bright Data Web Unlocker para los portales geo-bloqueados
- **Detección particular vs agencia** — Señales por portal (URLs, JSON del vendedor, watermarks, guarda global por nombre de anunciante)
- **Filtro de zonas activas** — Solo el área de trabajo (Lleida ≤20km + costa de Tarragona) con nombres de municipio canónicos; el resto queda descartado pero recuperable
- **Detección de bajadas de precio** — Histórico de precios con alertas (>5%)

### CRM
- **Lead scoring** — 0-100 pts: días en mercado, teléfono, fotos, precio
- **Duplicados cross-portal** — Mismo inmueble en varios portales detectado (zona + precio exacto + m²), badge "En N portales" y desplegable para abrir cada anuncio
- **Gestión de estados** — NUEVO → EN_PROCESO → CONTACTADO → INTERESADO → CLIENTE, con registro de auditoría interno
- **Agenda de tareas** — Seguimiento por comercial con calendario
- **Contacto automatizado** — Cola post-scrape con plantillas A/B; nunca contacta dos veces al mismo vendedor aunque esté en varios portales

### Valoraciones
- **ACM (Análisis Comparativo de Mercado)** — Búsqueda de comparables, índice de confianza
- **PDF de valoración** — Generación automática con datos del mercado
- **Widget embebible** — JS snippet para webs de terceros (`/api/widget/valorar/`)

### Plataforma
- **API REST v1** — Autenticación X-API-Key, filtros, paginación, webhooks
- **PWA** — Service Worker, Push Notifications, instalable en móvil
- **Alertas Telegram** — Resumen diario, bajadas de precio, control de calidad del scraping
- **Analytics** — Dashboard con KPIs, embudo de conversión, métricas por portal/zona, mapa de leads

---

## 🏗️ Arquitectura

```
              GitHub Actions (cron DIARIO 12:00 UTC)
              ───────────────────────────────────────
              │ Scrapling: habitaclia, wallapop      │
              │ Bright Data: fotocasa, milanuncios   │
              │ (idealista: solo dispatch manual)    │
              │   → dbt (staging → marts)            │
              │   → cola de contacto automático      │
              │   → validación calidad + Telegram    │
              └──────────────────┬───────────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────────────┐
              │      Neon PostgreSQL (Serverless)     │
              │ raw.raw_listings → stg_* → dim_leads  │
              └──────────────────┬────────────────────┘
                                 │
         Contabo VPS (Windows Server)
         ────────────────────────────
         │ Django CRM (waitress)     │ ──► https://fincaradar.com
         │ Cloudflare Tunnel         │     Cloudflare CDN + SSL
         │ milanuncios L-X-V (resid.)│
         └───────────────────────────┘
```

### Costes

| Servicio | Coste |
|----------|-------|
| Contabo VPS (8GB, 2 vCPU) | €4.99/mes |
| Neon PostgreSQL | Gratis |
| GitHub Actions | Gratis |
| Cloudflare (DNS + Tunnel) | Gratis |
| Bright Data Web Unlocker (fotocasa, milanuncios, idealista) | ~€1/mes |
| 2Captcha (Cloudflare Turnstile) | ~€3/mes |
| IPRoyal proxy (wallapop desde GH Actions) | ~€1/mes* |
| **Total** | **~€10/mes** |

<sub>*IPRoyal: compra única de $7/GB, tráfico no expira.</sub>

---

## 🌐 Portales

| Portal | Scraper | Anti-bot / vía | Infraestructura |
|--------|---------|----------------|-----------------|
| **Habitaclia** | Scrapling | Imperva (bypass nativo) | GitHub Actions diario |
| **Fotocasa** | Bright Data + API interna `propertysearch` | Imperva / geo-block | GitHub Actions diario |
| **Milanuncios** | Bright Data (URLs provinciales `?vendedor=part`) | GeeTest / geo-block | GitHub Actions diario |
| **Wallapop** | Scrapling (`__NEXT_DATA__`) | Proxy ES (IPRoyal) | GitHub Actions diario |
| **Idealista** | Bright Data Web Unlocker | DataDome | Dispatch manual (~0.6% particulares) |

Los scrapers antiguos (Botasaurus/Camoufox) se conservan como fallback; Camoufox sigue en uso para el **contacto automático** (login + formulario/chat en 4 portales, rate limit 5/día con delay 2-5 min).

**Datos extraídos**: listing_id, URL, título, precio, descripción, ubicación, teléfono, tipo de propiedad, habitaciones, baños, m², fotos, tipo de vendedor (particular/agencia).

---

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.11+
- PostgreSQL 16 (o [Neon](https://neon.tech) gratuito)

### Instalación

```bash
git clone https://github.com/gilito11/casaTevaLeads.git
cd casaTevaLeads

python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
scrapling install   # navegador Patchright para los scrapers

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
# Scrapling (sin proxy desde IP española)
python -m scrapers.scrapling_habitaclia --zones salou cambrils --postgres
python -m scrapers.scrapling_wallapop --zones lleida --max-pages 2 --postgres

# Bright Data (requiere BRIGHTDATA_API_KEY)
python -m scrapers.scrapling_fotocasa_bd --zones salou --max-pages 2 --postgres
python -m scrapers.scrapling_milanuncios_bd --max-pages 3 --postgres
python -m scrapers.scrapling_idealista_bd --zones lleida --max-pages 1 --postgres

# dbt transformaciones
cd dbt_project && dbt run --select staging marts

# Trigger del workflow completo en GitHub Actions
gh workflow run scrape-neon.yml -f portals="habitaclia,wallapop" -f zones="salou,cambrils"
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
│   │   ├── leads/            # Lead model, CRM views, scoring, PDF, audit log
│   │   ├── acm/              # Análisis Comparativo de Mercado
│   │   ├── api_v1/           # REST API + API Keys
│   │   ├── widget/           # Widget valorador embebible
│   │   ├── analytics/        # Dashboard, métricas, mapa, export
│   │   ├── notifications/    # Telegram + Push notifications
│   │   └── core/             # Tenants, health, utilidades
│   └── templates/            # HTMX + TailwindCSS
├── scrapers/                 # Web scrapers
│   ├── scrapling_base.py     # StealthySession multi-tenant
│   ├── scrapling_*.py        # Scrapers por portal (+ *_bd.py via Bright Data)
│   ├── zones/                # ZONAS_GEOGRAFICAS por portal
│   ├── camoufox_*.py         # Legacy / fallback
│   └── contact_automation/   # Auto-contacto (4 portales)
├── dbt_project/              # raw → staging → marts (dim_leads, duplicados)
├── ai_agents/                # Ollama vision scoring (PoC)
├── scripts/                  # Cola de contacto, health checks, reports
└── .github/workflows/        # scrape-neon, contact-queue, dbt-refresh
```

---

## 🔄 Scheduling

| Tarea | Schedule | Infraestructura |
|-------|----------|-----------------|
| Scraping (wallapop, habitaclia, fotocasa, milanuncios) + dbt + cola contacto | **Diario** 12:00 UTC | GitHub Actions (`scrape-neon.yml`) |
| Scraping idealista | Manual (`gh workflow run`) | GitHub Actions |
| Scraping milanuncios (residual) | L-X-V 13:00 CET | VPS (schtasks) |
| Procesado cola de contacto | L-V 18:00 CET | GitHub Actions (`contact-queue.yml`) |
| Alertas y control de calidad Telegram | Tras cada scrape | Automático |

---

## 📄 Licencia

Proyecto privado — © 2026

<p align="center">
  <sub>Hecho con Django, dbt, y mucho scraping</sub>
</p>

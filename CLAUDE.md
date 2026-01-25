# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 25 Enero 2026

## Quick Reference

### Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Neon - serverless)
- **Scrapers**: Botasaurus (habitaclia, fotocasa), Camoufox (milanuncios, idealista)
- **Contacto**: Camoufox + IPRoyal proxy (4 portales)
- **Orquestacion**: GitHub Actions (L-X-V 12:00 UTC)
- **ETL**: dbt (raw → staging → marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

### Entornos
| Servicio | Local | Produccion |
|----------|-------|------------|
| Web | localhost:8000 | casatevaleads.fly.dev |
| BD | localhost:5432 | Neon (ep-ancient-darkness-*.neon.tech) |
| Scrapers | manual | GitHub Actions |

### Comandos Frecuentes
```bash
# Local scraping (Botasaurus)
python run_habitaclia_scraper.py --zones salou --postgres

# Local scraping Idealista (Camoufox + proxy)
DATADOME_PROXY="user:pass_country-es@geo.iproyal.com:12321" python run_camoufox_idealista_scraper.py --zones igualada --postgres

# Trigger GitHub Actions scraping
gh workflow run scrape-neon.yml -f portals="habitaclia,fotocasa,idealista" -f zones="salou"

# dbt (local con Neon)
cd dbt_project && dbt run --profiles-dir /tmp/dbt_profiles --select staging marts
```

### Portal Names (BD constraint)
`habitaclia`, `fotocasa`, `milanuncios`, `idealista`

### Estados de Lead
`NUEVO`, `EN_PROCESO`, `CONTACTADO_SIN_RESPUESTA`, `INTERESADO`, `NO_INTERESADO`, `EN_ESPERA`, `NO_CONTACTAR`, `CLIENTE`, `YA_VENDIDO`

---

## Arquitectura (Enero 2026)

```
GitHub Actions (scraping)     Fly.io (Django)
         ↓                         ↓
  Botasaurus + Camoufox       casatevaleads.fly.dev
   + IPRoyal proxy                  ↓
         ↓                          ↓
    ┌─────────────────────────────────┐
    │   Neon PostgreSQL (serverless)  │
    │   ep-ancient-darkness-*.neon.tech│
    └─────────────────────────────────┘
         ↓
    dbt (staging → marts)
```

### Costes Mensuales
| Servicio | Coste |
|----------|-------|
| Fly.io (hosting) | GRATIS |
| Neon PostgreSQL | GRATIS |
| GitHub Actions | GRATIS |
| 2Captcha (Habitaclia reCAPTCHA) | ~$3/mes |
| IPRoyal proxy (Idealista DataDome) | ~$1/mes* |
| **Total** | **~$4/mes** |

*IPRoyal: Compra única de $7/GB, tráfico no expira. Estimado ~100-200MB/mes.

---

## Features Implementadas

### Core
- [x] Lead scoring (0-90 pts): días mercado, teléfono, fotos, precio
- [x] Histórico precios + alertas bajadas (>5%)
- [x] Duplicados cross-portal (teléfono + ubicación+precio+metros)
- [x] Alertas Telegram (resumen diario, bajadas, errores)
- [x] Contacto automatizado (4 portales)

### CRM
- [x] **Widget Valorador** - `/api/widget/valorar/`, JS embebible
- [x] **API REST v1** - `/api/v1/leads/`, autenticación X-API-Key
- [x] **PWA** - Service Worker, Push Notifications, manifest.json
- [x] **PDF Valoración** - `/leads/<id>/valuation-pdf/`
- [x] **ACM** - `/acm/api/generate/<id>/`, comparables + confianza
- [x] **Task Agenda** - `/leads/agenda/`, tareas por comercial

### Pendiente
- [ ] UI para contacto desde app (cola → GitHub Actions)
- [ ] WhatsApp Business API (Issue #32)
- [ ] Integrar Ollama image scoring en producción

---

## Scrapers

| Portal | Tecnología | Coste | Anti-bot |
|--------|------------|-------|----------|
| habitaclia | Botasaurus | Gratis | Ninguno |
| fotocasa | Botasaurus | Gratis | Ninguno |
| milanuncios | Camoufox | Gratis | GeeTest (bypass) |
| idealista | Camoufox + IPRoyal | ~$1/mes | DataDome (bypass) |

### Schedule
- **Workflow**: `.github/workflows/scrape-neon.yml`
- **Cron**: `0 12 * * 1,3,5` (12:00 UTC, L-X-V)
- **Manual**: `gh workflow run scrape-neon.yml`

---

## Contacto Automático

| Portal | Estado | Método |
|--------|--------|--------|
| Fotocasa | ✅ OK | Auto-login + formulario |
| Habitaclia | ✅ OK | 2Captcha reCAPTCHA |
| Milanuncios | ✅ OK | Camoufox + chat interno |
| Idealista | ✅ OK | Camoufox + IPRoyal proxy + geoip |

**Modelos**: `ContactQueue`, `PortalSession`, `PortalCredential`
**Límite**: 5 contactos/día, delay 2-5min entre contactos
**Código**: `scrapers/contact_automation/`
**Idealista**: `camoufox_idealista.py` (requiere `DATADOME_PROXY`)

---

## Ollama (PoC)

Análisis de imágenes de inmuebles con Llama 3.2 Vision.

**Archivo**: `ai_agents/vision_analyzer.py`

**Uso**:
```bash
ollama pull llama3.2-vision
ollama serve
python ai_agents/vision_analyzer.py --test
```

**Output**: Score 0-30 pts para sumar a lead_score
**Estado**: PoC local, no integrado en producción

---

## Arquitectura de Datos

```
raw.raw_listings (JSONB)
        ↓
public_staging.stg_* (views por portal)
        ↓
public_marts.dim_leads (incremental)
public_marts.dim_lead_duplicates
```

### Mapping Django → dbt
| Django | dbt | Uso |
|--------|-----|-----|
| `updated_at` | `ultima_actualizacion` | Última actualización |
| `portal` | `source_portal` | Portal origen |
| `metros` | `superficie_m2` | Superficie |
| `zona_geografica` | `zona_clasificada` | Zona |

---

## GitHub Secrets

**Scraping**:
- `NEON_DATABASE_URL` - Connection string Neon ✅
- `NEON_DB_PASSWORD` - Password para dbt ✅

**Contacto**:
- `FOTOCASA_EMAIL/PASSWORD` ✅
- `CAPTCHA_API_KEY` (2Captcha) ✅
- `DATADOME_PROXY` (IPRoyal) ✅ - Formato: `user:pass_country-es@geo.iproyal.com:12321`
- `IDEALISTA_EMAIL/PASSWORD` ✅
- `CONTACT_NAME/EMAIL/PHONE` ✅

**Alertas**:
- `TELEGRAM_BOT_TOKEN/CHAT_ID` ✅ (bot: @casateva_alerts_bot)

---

## CI/CD

### Scraping
Push a master → GitHub Actions build
Manual: `gh workflow run scrape-neon.yml`

### Web (Fly.io)
```bash
fly deploy
fly logs
fly ssh console
```

---

## Debugging

Si un bug no se resuelve al primer intento → crear endpoint de debug temporal:

```python
def debug_view(request):
    results = {}
    try:
        cursor.execute("SELECT COUNT(*) FROM tabla")
        results['count'] = cursor.fetchone()[0]
    except Exception as e:
        results['error'] = str(e)
    return JsonResponse(results)
```

Desplegar → analizar output → arreglar → eliminar endpoint.

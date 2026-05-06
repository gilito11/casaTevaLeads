# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 4 Mayo 2026

## Quick Reference

### Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Neon - serverless)
- **Scrapers**: Scrapling 0.4.7 + Patchright (4 portales, sin proxy desde 4 May 2026)
- **Contacto**: Camoufox + IPRoyal proxy (4 portales — pendiente migrar a Scrapling)
- **Orquestacion**: GitHub Actions (L-X-V 12:00 UTC) + VPS Contabo Windows
- **ETL**: dbt (raw → staging → marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

### Entornos
| Servicio | Local | Produccion |
|----------|-------|------------|
| Web | localhost:8000 | fincaradar.com (Contabo VPS) + casatevaleads.fly.dev |
| BD | localhost:5432 | Neon (ep-ancient-darkness-*.neon.tech) |
| Scrapers | manual | GitHub Actions + VPS scheduled |

### Comandos Frecuentes
```bash
# Local scraping (Scrapling, sin proxy)
python -m scrapers.scrapling_idealista --zones salou --max-pages 2 --postgres
python -m scrapers.scrapling_fotocasa --zones salou cambrils --postgres
python -m scrapers.scrapling_habitaclia --zones salou --postgres
python -m scrapers.scrapling_milanuncios --zones tarragona --max-pages 2 --postgres

# Trigger GitHub Actions scraping
gh workflow run scrape-neon.yml -f portals="habitaclia,fotocasa,idealista,milanuncios" -f zones="salou,cambrils,reus"

# dbt (local con Neon — usa /tmp/dbt_profiles sin search_path por compatibilidad pooler)
DBT_HOST=ep-...neon.tech DBT_USER=neondb_owner DBT_PASSWORD=... DBT_DBNAME=neondb \
  dbt run --select staging marts --project-dir dbt_project --profiles-dir /tmp/dbt_profiles
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
- [x] **"Es agencia" botón** - `/leads/<id>/mark-agency/`, blacklist + delete (botón naranja en list)

### Pendiente
- [ ] UI para contacto desde app (cola → GitHub Actions)
- [ ] WhatsApp Business API (Issue #32)
- [ ] Integrar Ollama image scoring en producción

---

## Scrapers (Mayo 2026 - Migrado a Scrapling)

| Portal | Tecnología | Coste | Anti-bot | Detección Particular |
|--------|------------|-------|----------|----------------------|
| habitaclia | Scrapling 0.4.7 | Gratis | Imperva (bypass nativo) | URL `/viviendas-particulares-` |
| fotocasa | Scrapling 0.4.7 | Gratis | Imperva (bypass nativo) | URL `/particulares/` + filtro `tu agente` |
| milanuncios | Scrapling 0.4.7 | Gratis | GeeTest (bypass nativo) | JSON `sellerType=private` + 6 signals |
| idealista | Scrapling 0.4.7 | Gratis | DataDome (bypass nativo) | Card `item_contains_branding` + detail `/pro/<slug>/` |

### Archivos
- Base class: `scrapers/scrapling_base.py` (StealthySession, multi-tenant, raw.raw_listings)
- Por portal: `scrapers/scrapling_<portal>.py`
- ZONAS_GEOGRAFICAS: `scrapers/zones/<portal>.py` (módulo neutro, sin deps)
- Camoufox antiguos: `scrapers/camoufox_*.py` (preservados como fallback)

### Schedule
- **Workflow**: `.github/workflows/scrape-neon.yml`
- **Cron**: `0 12 * * 1,3,5` (12:00 UTC, L-X-V)
- **Manual**: `gh workflow run scrape-neon.yml`
- **VPS scheduled**: `scripts/scheduled_scrape.py` corre los 4 portales L-X-V (antes solo 2)

### Migración Scrapling (4 May 2026)
- IPRoyal proxy ya NO necesario (DataDome/Imperva bypass sin proxy desde IP española)
- 2Captcha solo para Cloudflare Turnstile (auto via `solve_cloudflare=True`)
- StealthySession crucial: `StealthyFetcher.fetch` aislado → 403 en idealista detail; con sesión → OK

### Geo-block matrix (validado 6 May 2026)
| Origen | habitaclia | fotocasa | idealista | milanuncios |
|--------|:----------:|:--------:|:---------:|:-----------:|
| Local sandbox (España) | ✅ | ✅* | ✅ | ✅ |
| GH Actions (Azure US) | ✅ | ❌ | ❌ | ❌ |
| VPS Contabo (Alemania) | ❌ | ❌ | ❌ | ✅ |

*Fotocasa: Salou primera petición OK; siguientes mismas IP rate-limited.

**Implicación**: GH Actions cron sirve para habitaclia (mejor productor) sin proxy.
Idealista/fotocasa requieren IP española o proxy ES (Decodo $0.70/GB recomendado).

### Idealista — extracción específica
- m² + habitaciones del search card: concat de TODAS las `.item-detail` spans (single span loses 2/3)
- Detección Profesional: `<div class="professional-name">`, `<a href="/pro/<slug>/">`, `<input name="professional">` (cualquiera dispara `es_particular=False`)
- Phone reveal `page_action`: clica `button.see-phones-btn` / `.hidden-contact-phones_link` / `a:has-text("Ver teléfono")` antes de capturar HTML

### Fotocasa — JS DOM extraction
- Lazy-loads cards (~2 cards iniciales, ~30 skeletons que hidratan en scroll)
- `search_page_action()` hace 8x scroll, luego `page.evaluate()` extrae listings + stash JSON en `<script id="__SCRAPLING_LISTINGS__">`
- `parse_search_page` lee ese JSON en lugar del HTML serializado (que está incompleto)
- `_wants_detail()` returns False — detail page reliably 405. Card-level data es suficiente.

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

## Workflow Rules

### Planning
- Plan mode for non-trivial tasks (3+ steps or architectural decisions)
- Write plan to `tasks/todo.md` with checkable items before implementing
- If something goes sideways, STOP and re-plan — don't keep pushing
- Mark items complete as you go, add results summary when done

### Execution
- Offload research, exploration, and parallel analysis to subagents (one task per subagent)
- For bugs: just fix them. Read logs, trace errors, resolve. Zero hand-holding from user
- Fix failing CI tests autonomously without being told how

### Verification
- Never mark a task complete without proving it works (tests, logs, demo)
- Diff behavior between main and changes when relevant
- Ask: "Would a staff engineer approve this?"

### Quality
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky, implement the clean solution instead
- Skip elegance checks for simple, obvious fixes — don't over-engineer
- Find root causes. No temporary fixes

### Learning
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules that prevent the same mistake from recurring
- Review lessons at session start

---

## Impact Analysis (OBLIGATORIO antes de implementar)

Antes de tocar código en cambios no triviales: mapear dependencias → implementar en orden → validar en cada paso.

### Cadenas de Dependencia

```
SCRAPER FIELD CHANGE:
  scraper raw_data keys
    → dbt staging (stg_*.sql)
      → dbt marts (dim_leads.sql)
        → Django Lead model (models.py, managed=False)
          → views.py / api_views.py / serializers.py
            → templates HTML

DB SCHEMA CHANGE:
  models.py (add/remove field)
    → migrations/
      → raw SQL en views.py, analytics/views.py, listing_checker.py
        → API serializers

SHARED UTILITY CHANGE:
  camoufox_idealista.py (parse_proxy, check_proxy_health)
    → camoufox_habitaclia.py, camoufox_fotocasa.py, camoufox_milanuncios.py
      → contact_automation/milanuncios_contact.py
  error_handling.py (validate_scraping_results, log_scraper_run)
    → los 4 camoufox scrapers
  utils/particular_filter.py (debe_scrapear)
    → base_scraper.py, botasaurus_base.py, camoufox_habitaclia.py
  utils/telegram_alerts.py
    → error_handling.py, check_portal_health.py, check_proxy.py

WORKFLOW CHANGE:
  scrape-neon.yml
    → run_*_scraper.py (runners)
      → scrapers/camoufox_*.py (classes)
        → utils/ (shared modules)
  contact-queue.yml
    → scripts/process_contact_queue.py
      → scrapers/contact_automation/*.py
```

### Nodo Crítico: dim_leads

`dim_leads` es el hub central — si cambias una columna aquí, verificar:
1. Los 4 `stg_*.sql` (inputs)
2. Los 7 `analytics_*.sql` (dependientes)
3. `dim_lead_duplicates.sql`
4. Django `Lead` model (db_column mappings)
5. `LeadListSerializer` / `LeadDetailSerializer`
6. Raw SQL en `analytics/views.py` y `analytics/api_views.py`
7. `listing_checker.py`, `post_scrape_auto_queue.py`

### Zona Imports (ZONAS_GEOGRAFICAS)

Cada scraper tiene su propio dict, pero camoufox hereda del botasaurus:
- `camoufox_habitaclia.py` → importa de `botasaurus_habitaclia.py`
- `camoufox_fotocasa.py` → importa de `botasaurus_fotocasa.py`
- `camoufox_milanuncios.py` → dict propio
- `camoufox_idealista.py` → dict propio

### Checklist Pre-Implementación

Antes de cualquier cambio no trivial, responder:
- [ ] ¿Qué archivos importan del archivo que voy a modificar?
- [ ] ¿Hay raw SQL en views/scripts que referencia columnas afectadas?
- [ ] ¿Hay workflows de GitHub Actions que ejecutan este script?
- [ ] ¿El cambio afecta a dim_leads? → verificar los 7 puntos de arriba
- [ ] ¿El cambio afecta a un shared utility? → verificar todos los importadores

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

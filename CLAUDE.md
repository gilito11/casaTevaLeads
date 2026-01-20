# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 20 Enero 2026

## Quick Reference

### Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Azure Flexible Server)
- **Scrapers**: Botasaurus (habitaclia, fotocasa), ScrapingBee (milanuncios, idealista)
- **Orquestacion**: Dagster
- **ETL**: dbt (raw → staging → marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

### Entornos
| Servicio | Local | Azure |
|----------|-------|-------|
| Web | localhost:8000 | inmoleads-crm.azurewebsites.net |
| Dagster | localhost:3000 | dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | localhost:5432 | inmoleads-db.postgres.database.azure.com |

### Comandos Frecuentes
```bash
# Local scraping
python run_all_scrapers.py --portals habitaclia fotocasa --zones salou

# Azure logs
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100

# dbt
cd dbt_project && dbt run --select staging.* && dbt run --select dim_leads
```

### Portal Names (BD constraint)
`habitaclia`, `fotocasa`, `milanuncios`, `idealista`

### Estados de Lead
`NUEVO`, `EN_PROCESO`, `CONTACTADO_SIN_RESPUESTA`, `INTERESADO`, `NO_INTERESADO`, `EN_ESPERA`, `NO_CONTACTAR`, `CLIENTE`, `YA_VENDIDO`

---

## Features Implementadas (Enero 2026)

### Core
- [x] Lead scoring (0-90 pts): días mercado, teléfono, fotos, precio
- [x] Histórico precios + alertas bajadas (>5%)
- [x] Duplicados cross-portal (teléfono + ubicación+precio+metros)
- [x] Alertas Telegram (resumen diario, bajadas, errores)
- [x] Contacto automatizado (4 portales)

### Nuevas (20 Enero 2026)
- [x] **Widget Valorador** - `/api/widget/valorar/`, JS embebible
- [x] **API REST v1** - `/api/v1/leads/`, autenticación X-API-Key
- [x] **PWA** - Service Worker, Push Notifications, manifest.json
- [x] **PDF Valoración** - `/leads/<id>/valuation-pdf/`
- [x] **ACM** - `/acm/api/generate/<id>/`, comparables + confianza
- [x] **Task Agenda** - `/leads/agenda/`, tareas por comercial

### Pendiente
- [ ] WhatsApp Business API (Issue #32) - requiere cuenta Meta verificada

---

## API Endpoints

### REST API v1 (`/api/v1/`)
```
GET  /api/v1/leads/              # Listar leads (paginado)
GET  /api/v1/leads/{id}/         # Detalle lead
GET  /api/v1/zones/              # Zonas activas
POST /api/v1/webhooks/           # Crear webhook
GET  /api/v1/docs/               # Swagger UI
```
**Auth**: Header `X-API-Key: <key>` (crear en admin)

### Widget
```
GET  /widget/valorador.js        # JS para embed
POST /api/widget/valorar/        # Calcular valoración
POST /api/widget/lead/           # Crear lead desde widget
```

### ACM
```
POST /acm/api/generate/{lead_id}/  # Generar informe ACM
GET  /acm/api/report/{lead_id}/    # Obtener último ACM
```

### Analytics
```
GET /analytics/api/kpis/
GET /analytics/api/leads-por-dia/
GET /analytics/api/export/
```

---

## Scrapers

| Portal | Tecnología | Coste | Anti-bot |
|--------|------------|-------|----------|
| habitaclia | Botasaurus | Gratis | Ninguno |
| fotocasa | Botasaurus | Gratis | Ninguno |
| milanuncios | ScrapingBee | 75 cr/req | GeeTest |
| idealista | ScrapingBee | 75 cr/req | DataDome |

### Schedule Actual (TEMPORAL)
- **Cron**: `0 12 * * 1,3,5` (12:00, solo L-X-V)
- **Normal**: `0 12,18 * * *` (12:00 y 18:00 diario)

### Zonas sin Idealista
Idealista desactivado para zonas pequeñas (95%+ agencias):
`amposta, deltebre, ametlla_mar, hospitalet_infant, montroig_camp, sant_carles_rapita`

---

## Contacto Automático

| Portal | Estado | Método |
|--------|--------|--------|
| Fotocasa | ✅ OK | Auto-login + formulario |
| Habitaclia | ✅ OK | 2Captcha reCAPTCHA |
| Milanuncios | ✅ OK | Camoufox + chat interno |
| Idealista | ⚠️ Parcial | DataDome bloquea login |

**Modelos**: `ContactQueue`, `PortalSession`, `PortalCredential`
**Límite**: 5 contactos/día, delay 2-5min entre contactos

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

## Variables de Entorno (Azure)

**Scraping**:
- `SCRAPINGBEE_API_KEY`

**Contacto**:
- `FOTOCASA_EMAIL/PASSWORD`
- `MILANUNCIOS_EMAIL/PASSWORD`
- `IDEALISTA_EMAIL/PASSWORD`
- `CAPTCHA_API_KEY` (2Captcha)
- `CONTACT_NAME/EMAIL/PHONE`

**Alertas**:
- `TELEGRAM_BOT_TOKEN/CHAT_ID`
- `ALERT_WEBHOOK_URL` (Discord)

**PWA**:
- `VAPID_PUBLIC_KEY/PRIVATE_KEY`
- `VAPID_CLAIMS_EMAIL`

---

## Costes Mensuales

| Servicio | Coste |
|----------|-------|
| Azure (DB + Web + Container) | ~$50 |
| ScrapingBee | 50€ |
| **Total** | **~100€/mes** |

---

## Debugging

Si un bug no se resuelve al primer intento → crear endpoint de debug temporal:

```python
# views.py
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

---

## Onboarding Inmobiliaria

1. Crear Tenant en `/admin/core/tenant/`
2. Crear User + TenantUser (rol: admin)
3. Configurar zonas en `/admin/core/zonageografica/`
4. (Opcional) Credenciales portales en `/admin/leads/portalcredential/`
5. Verificar login y scraping

---

## CI/CD

Push a master → GitHub Actions → ACR → Azure (Web App + Container Apps)

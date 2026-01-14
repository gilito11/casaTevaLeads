# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 14 January 2026 (Idealista desactivado para zonas pequeñas Terres de l'Ebre)

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de 4 portales.

## Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Azure PostgreSQL en prod)
- **Scrapers**: Botasaurus (habitaclia, fotocasa), ScrapingBee (milanuncios, idealista)
- **Orquestacion**: Dagster (PostgreSQL storage para persistencia)
- **ETL**: dbt (raw -> public_staging -> public_marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

## Scrapers - Estado actual

| Portal | Tecnologia | Azure | Local | Coste | Datos extraidos |
|--------|------------|-------|-------|-------|-----------------|
| habitaclia | Botasaurus | OK | OK | Gratis | titulo, precio, metros, fotos, telefono (de descripcion) |
| fotocasa | Botasaurus | OK | OK | Gratis | titulo, precio, metros, fotos, telefono (de descripcion) |
| milanuncios | ScrapingBee | OK | OK | 75 credits/req | titulo, precio, metros, fotos, telefono |
| idealista | ScrapingBee | OK | OK | 75 credits/req | titulo, precio, metros, fotos, telefono |

### Extraction Patterns (Fixed Jan 2026)
Los scrapers extraen datos de elementos HTML especificos para evitar valores incorrectos:

| Portal | Precio | Metros | Habitaciones |
|--------|--------|--------|--------------|
| habitaclia | `feature-container` class | `<li>Superficie X m2</li>` | `<li>X habitaciones</li>` |
| fotocasa | `re-DetailHeader-price` class | `<span><span>N</span> m²` | `<span><span>N</span> hab` |
| idealista | `info-data-price` class | `info-features` section | `info-features` section |
| milanuncios | JSON-LD / data attributes | Generic (detail page only) | Generic (detail page only) |

### Idealista Particulares (Fixed 14 Jan 2026)
**IMPORTANTE**: Idealista NO tiene filtro URL publico para particulares (solo herramientas de pago).
El scraper filtra agencias via deteccion HTML en dos niveles:

**Nivel 1 - Pagina de busqueda** (pre-filtro, ahorra creditos):
- `professional-name`, `logo-profesional`, `item-link-professional`
- Logos de inmobiliarias en resultados

**Nivel 2 - Pagina de detalle** (filtro mas especifico):
- `data-seller-type="professional"` - Atributo vendedor (exacto)
- `advertiser-name` con texto "inmobiliaria/agencia/fincas"
- `professional-info` con contenido de agencia
- JSON-LD: seller con nombre de inmobiliaria
- Texto "contactar con la inmobiliaria"

**Bug arreglado 14 Jan 2026**: Patrones anteriores eran demasiado amplios (detectaban
logos de Idealista como agencias). Ahora solo patrones especificos con contenido real.

**Selectores de extraccion**:
- Titulo: `<span class="main-info__title-main">`
- Descripcion: `<div class="adCommentsLanguage">`

### Encoding Fix (11 Jan 2026)
`fix_encoding()` solo corrige texto doblemente codificado (marcadores como `Ã¡`).
Preserva UTF-8 correcto (ej: `Tàrrega` no se corrompe a `Trrega`).

### Extraccion de telefonos
- **Milanuncios/Idealista**: Busqueda en descripcion (regex)
- **Habitaclia/Fotocasa**: Busqueda de patrones en descripcion del anuncio (regex)

### Portales eliminados (Enero 2026)
- **Pisos.com**: Eliminado - pocos leads de calidad
- **Wallapop**: Eliminado - no relevante para inmobiliaria

### Filtro de agencias (dbt staging)
Los modelos dbt filtran automaticamente anuncios con frases como:
- "abstenerse agencias/inmobiliarias"
- "no agencias/no inmobiliarias"
- "sin intermediarios"

### Zonas disponibles
20+ zonas preconfiguradas en `backend/apps/core/models.py`:
- **Lleida**: Lleida, Balaguer, Mollerussa, Tàrrega, Alcoletge, Alpicat, Torrefarrera...
- **Costa Daurada**: Salou, Cambrils, Miami Platja, La Pineda, Vilafortuny, Mont-roig...
- **Tarragona**: Tarragona, Reus, Valls, Montblanc
- **Terres de l'Ebre**: Tortosa, Amposta, Deltebre, L'Ametlla de Mar

**Portales por defecto**: Al agregar una zona, los 4 portales (MA+FC+HA+ID) se habilitan automaticamente.

### ScrapingBee
- API Key: configurada en Azure Container Apps y GitHub Secrets
- Plan: 50eur/mes = 250,000 credits = ~3,333 requests
- Stealth proxy: GeeTest (Milanuncios), DataDome (Idealista)
- **Timeout**: 120s por request (aumentado de 60s para stealth proxy)
- **Idealista detail pages**: 3 por pagina busqueda (reducido de 10 para evitar timeout 45min)

### Idealista - Zonas pequeñas (14 Enero 2026)
**DECISION**: Idealista desactivado para zonas pequeñas de Terres de l'Ebre.

En zonas pequeñas (< 20K habitantes), el 95%+ de anuncios en Idealista son de agencias
inmobiliarias. El filtro `only_particulares=True` devuelve 0 resultados consistentemente,
gastando credits de ScrapingBee sin beneficio.

**Zonas excluidas** (definidas en `IDEALISTA_SKIP_ZONES` en `scraping_assets.py`):
- amposta, deltebre, ametlla_mar, hospitalet_infant, montroig_camp, sant_carles_rapita

**NO reactivar Idealista para estas zonas** - simplemente no hay particulares vendiendo.

### Milanuncios - Filtro de watermarks (14 Enero 2026)
**DECISION**: Filtrar anuncios con marca de agua en la primera imagen.

Las agencias inmobiliarias añaden watermarks (logo/texto) en la parte inferior de las fotos.
El scraper ahora descarga la primera imagen y analiza si tiene watermark usando detección de bordes.

**Implementación** (en `scrapers/watermark_detector.py`):
- Descarga primera imagen del anuncio
- Analiza el 15% inferior (donde se colocan watermarks)
- Detecta alta densidad de bordes (indicador de texto/logos)
- Si detecta watermark → descarta el anuncio

**Parámetro**: `filter_watermarks=True` (por defecto activo en `ScrapingBeeMilanuncios`)

### Schedule Optimizado (Enero 2026)
Basado en analisis de 220 anuncios de Milanuncios:
- **Pico manana**: 9:00-11:00 (26 anuncios a las 9:00)
- **Pico tarde**: 16:00 (19 anuncios)
- **Lunes mas activo** (23%), sabado casi nulo (3%)

**Horario Dagster**: `0 12,18 * * *` (12:00 y 18:00 Espana)
- 12:00: Captura pico de manana
- 18:00: Captura pico de tarde
- **Ahorro**: 67% creditos (de 6 a 2 scrapes/dia)
- **Status**: Funcionando en produccion

### KEDA Scale-to-Zero (ELIMINADO Enero 2026)
~~Container Apps con KEDA cron scaler~~ - **Eliminado** porque Container Apps ya tiene
scale-to-zero nativo sin necesidad de KEDA.

**Configuracion actual**:
- minReplicas: 1, maxReplicas: 1
- Scale rules: ninguna (siempre 1 replica activa)
- Container Apps cobra por uso, no por tiempo activo

### Costes Azure (Enero 2026)
Suscripción: **Azure for Students** ($100 crédito/12 meses)

| Servicio | SKU | Coste/mes |
|----------|-----|-----------|
| PostgreSQL Flexible | B1ms (1vCPU, 2GB, 32GB) | ~$17 |
| Web App | B1 Linux | ~$13 |
| Container Apps | Consumption | ~$10-15 |
| ACR | Basic | ~$5 |
| Log Analytics | Mínimo | ~$2 |
| **Total Azure** | | **~$47-52/mes** |
| ScrapingBee | 250K credits | 50€/mes |
| **TOTAL** | | **~$95-100/mes** |

### Alertas Discord (Enero 2026)
Sistema de alertas via webhook para detectar problemas de scraping:
- **Variable de entorno**: `ALERT_WEBHOOK_URL`
- **Deteccion de bloqueos**: Alerta si 0 resultados Y algun scraper fallo (evita falsos positivos por duplicados)
- **Deteccion de cambios HTML**: Alerta si >50% de anuncios sin titulo/precio (estructura HTML cambiada)
- **Reintentos automaticos**: 3 intentos con backoff exponencial antes de alertar
- **Duracion job**: ~25 min (4 scrapers + dbt)

### Fiabilidad Produccion (Enero 2026)
- **Backup PostgreSQL**: 35 dias retencion (Azure)
- **Health Check**: `/health/` verifica conexion BD (retorna 503 si falla)
- **Logs Centralizados**: Azure Log Analytics (`casateva-logs`)
- **Validacion Datos**: Precio (1K-10M), telefono (9 digitos), URL, metros
- **Logging**: JSON estructurado en produccion
- **Rate Limiting**: ScrapingBee 1s/req, Botasaurus 2s/page
- **API Docs**: Swagger UI en `/api/docs/`
- **Runbooks**: `docs/RUNBOOKS.md` con procedimientos de incidentes
- **Key Vault**: `casateva-kv` para secrets (pendiente migracion)

## Comandos

```bash
# === LOCAL ===
python run_all_scrapers.py --portals habitaclia fotocasa --zones salou
python run_all_scrapers.py --portals milanuncios idealista --zones salou --postgres

# === AZURE LOGS ===
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100

# === KEDA / SCALING ===
az containerapp show -g inmoleads-crm -n dagster-scrapers --query "properties.template.scale" -o json
az containerapp replica list -g inmoleads-crm -n dagster-scrapers -o table
```

## Entornos

| Servicio | Local | Azure |
|----------|-------|-------|
| Web | localhost:8000 | inmoleads-crm.azurewebsites.net |
| Dagster | localhost:3000 | dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | localhost:5432 | inmoleads-db.postgres.database.azure.com |

## Credenciales

- **Local**: casa_teva / [REDACTED] / casa_teva_db
- **Azure**: inmoleadsadmin / [REDACTED] / inmoleadsdb (sslmode=require)

## Portal names para BD
`habitaclia`, `fotocasa`, `milanuncios`, `idealista`

## Estados de Lead (Django ESTADO_CHOICES)
`NUEVO`, `EN_PROCESO`, `CONTACTADO_SIN_RESPUESTA`, `INTERESADO`, `NO_INTERESADO`, `EN_ESPERA`, `NO_CONTACTAR`, `CLIENTE`, `YA_VENDIDO`

## dbt Pipeline
```
raw.raw_listings (JSONB) -> public_staging.stg_* -> public_marts.dim_leads
```

### Modelos dbt
- **public_staging/**: `stg_habitaclia`, `stg_fotocasa`, `stg_milanuncios`, `stg_idealista` (views)
- **public_marts/**: `dim_leads` (incremental, unique_key=[tenant_id, telefono_norm])

### Campos importantes
- `fotos`: Array de URLs de imagenes (JSONB)
- `telefono_norm`: Telefono normalizado (sin espacios ni prefijo)
- `source_portal`: Portal de origen

### Django Lead model
El modelo Lead apunta a `public_marts.dim_leads` (vista de solo lectura de dbt).
Los estados CRM se guardan en `leads_lead_estado` (tabla gestionada por Django).

### Column Name Mapping (Django → dbt)
**IMPORTANTE**: En raw SQL queries usar nombres de columna dbt, no Django:

| Django Field | dbt Column | Uso |
|--------------|------------|-----|
| `updated_at` | `ultima_actualizacion` | Fecha última actualización |
| `fecha_scraping` | `fecha_primera_captura` | Fecha primer scrape |
| `portal` | `source_portal` | Portal de origen |
| `url_anuncio` | `listing_url` | URL del anuncio |
| `metros` | `superficie_m2` | Superficie en m² |
| `nombre` | `nombre_contacto` | Nombre del contacto |
| `direccion` | `ubicacion` | Ubicación/dirección |
| `zona_geografica` | `zona_clasificada` | Zona geográfica |
| `tipo_inmueble` | `tipo_propiedad` | Tipo de propiedad |
| `anuncio_id` | `source_listing_id` | ID original del anuncio |

### Ejecutar dbt
```bash
cd dbt_project
dbt run --select staging.*
dbt run --select dim_leads
dbt test
```

## Analytics API Endpoints
```
GET /analytics/api/kpis/              # KPIs globales
GET /analytics/api/embudo/            # Embudo de conversion
GET /analytics/api/leads-por-dia/     # Tendencia diaria
GET /analytics/api/comparativa-portales/ # Comparativa entre portales
GET /analytics/api/precios-por-zona/  # Precios por zona
GET /analytics/api/filter-options/    # Opciones para filtros
GET /analytics/api/export/            # Exportar CSV
```

## CI/CD
Push a master -> GitHub Actions -> ACR -> Azure Container Apps

## Claude Code Preferences
- Ejecutar comandos largos en background
- Tomar decisiones sin preguntar
- Ser conciso

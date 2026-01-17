# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 17 January 2026 (Automated contact system with queue + 2Captcha)

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
Los modelos dbt filtran automaticamente anuncios:

**Por descripcion** (frases que indican agencias):
- "abstenerse agencias/inmobiliarias"
- "no agencias/no inmobiliarias"
- "sin intermediarios"
- "sin comisiones de agencia" (agencias disfrazadas de particulares)
- "0% comision" / "cero comision"

**Por nombre de vendedor** (Milanuncios - añadido 17 Jan 2026):
- Nombres con: inmobiliaria, inmuebles, fincas, agencia, grupo
- Sufijos empresariales: S.L., SL, S.A.
- Otros: real estate, properties, servicios inmobiliarios

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

### Sistema de Contacto Automatico (17 Enero 2026)
Sistema para contactar leads automaticamente via los portales inmobiliarios.

**Arquitectura**:
```
CRM (encolar leads) -> PostgreSQL (contact_queue)
                            ↓
Dagster (job diario) -> Playwright (headless)
                            ↓
              Fotocasa: login automatico con credenciales
              Habitaclia: 2Captcha para reCAPTCHA
```

**UI CRM**:
- Sidebar: "Cola Contactos" - ver items pendientes/completados
- Detalle lead (Fotocasa/Habitaclia): Boton "Contactar automaticamente"
- Filtros por estado: PENDIENTE, EN_PROCESO, COMPLETADO, FALLIDO, CANCELADO

**Modelos Django** (`leads/models.py`):
- `ContactQueue`: Cola de leads pendientes (portal, mensaje, estado, prioridad)
- `PortalSession`: Cookies de sesion por portal (tenant, portal, cookies JSON)

**Dagster** (`dagster/casa_teva_pipeline/assets/contact_assets.py`):
- Asset: `process_contact_queue` (max 5 contactos/dia)
- Job: `contact_job`
- Schedule: `contact_schedule` (L-V 10:00 AM, desactivado por defecto)

**Endpoints CRM**:
- `POST /leads/<lead_id>/enqueue/` - Encolar un lead
- `POST /leads/bulk-enqueue/` - Encolar multiples leads
- `GET /leads/contact-queue/` - Ver cola de contactos
- `POST /leads/contact-queue/<id>/cancel/` - Cancelar contacto

**Variables de entorno** (configuradas en Azure Container Apps):
```
CAPTCHA_API_KEY=<2captcha_api_key>    # ~$3/1500 CAPTCHAs (Habitaclia)
CONTACT_NAME=<nombre_formularios>
CONTACT_EMAIL=<email_contacto>
CONTACT_PHONE=<telefono_contacto>
FOTOCASA_EMAIL=<cuenta_fotocasa>      # Login automatico
FOTOCASA_PASSWORD=<password>          # Login automatico
```

**Limitaciones**:
- Max 5 contactos/dia (conservador para evitar bloqueos)
- Delay 2-5 min entre contactos (simular humano)
- Solo soporta Fotocasa y Habitaclia (tienen formulario web)
- Milanuncios e Idealista pendientes de implementar

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

### Bugs Arreglados (17 Enero 2026)

**1. Habitaclia no extraia fotos**
- **Problema**: Scraper de Habitaclia devuelvia 0 fotos por anuncio
- **Causa**: Filtro `id_for_match` comparaba IDs incompatibles (anuncio vs directorio imagen)
- **Fix**: Eliminar filtro erroneo, mantener deduplicacion por directory/filename
- **Archivo**: `scrapers/botasaurus_habitaclia.py`

**2. Dashboard 500 error - Wrong URL pattern**
- **Problema**: Dashboard devuelvia 500 en `/analytics/dashboard/`
- **Causa**: Template usaba `{% url 'leads:contact_detail' lead.lead_id %}` pero `contact_detail` espera integer ID, no MD5 hash
- **Fix**: Cambiar a `{% url 'leads:detail' lead.lead_id %}` (acepta string)
- **Archivo**: `backend/templates/analytics/dashboard.html`

### Bugs Arreglados (15 Enero 2026)

**1. DATABASE_URL parsing en runners Botasaurus**
- **Problema**: Habitaclia/Fotocasa guardaban 0 leads en Azure (20-50 encontrados, 0 saved)
- **Causa**: `if 'azure' in db_url` no detectaba hostname `inmoleads-db.postgres.database.azure.com`
- **Fix**: Cambio a `if parsed.hostname and 'azure' in parsed.hostname.lower()`
- **Archivos**: `run_habitaclia_scraper.py`, `run_fotocasa_scraper.py`

**2. scraping_stats columna inexistente**
- **Problema**: Error `column "created_at" does not exist` en asset scraping_stats
- **Causa**: dbt usa `fecha_primera_captura`, no `created_at`
- **Fix**: Cambiar query a usar `fecha_primera_captura`
- **Archivo**: `dagster/casa_teva_pipeline/assets/scraping_assets.py`

**3. dbt dim_leads falla por tabla inexistente**
- **Problema**: dbt fallaba con error de tabla `public.lead_image_scores` no existe
- **Causa**: La tabla se crea en asset `image_analysis` que corre DESPUES de dbt
- **Fix**: Nuevo modelo `stg_lead_image_scores.sql` con pre_hook que crea la tabla
- **Archivo**: `dbt_project/models/staging/stg_lead_image_scores.sql`

### Dashboard Analytics (17 Enero 2026)
Mejoras en `/analytics/`:

**Filtros interactivos**:
- Portal (habitaclia, fotocasa, milanuncios, idealista)
- Zona geografica
- Periodo (7, 30, 90 dias)

**KPIs arreglados**:
- `score_medio`: Ahora calcula AVG(lead_score) real
- `dias_medio_primer_contacto`: Calcula dias desde captura hasta primer contacto

**Nueva seccion "Ultimos Leads"**:
- Tabla con 10 leads mas recientes
- Muestra: titulo, portal, zona, precio, score, estado, fecha
- Links directos a detalle del lead

### Idealista - Estado actual (15 Enero 2026)
**⚠️ Idealista sigue con bloqueos intermitentes de DataDome** en algunas zonas.
- Zona `vendrell`: Bloqueado consistentemente (3 requests, 0 pages scraped)
- Otras zonas pequeñas: Skip automatico via `IDEALISTA_SKIP_ZONES`
- **No es bug del codigo** - es proteccion anti-bot de Idealista
- ScrapingBee stealth proxy funciona ~70% del tiempo

### Verificador de ofertas eliminadas (15 Enero 2026)
Script para detectar anuncios que ya no existen en los portales.

**Archivo**: `scrapers/listing_checker.py`

**Deteccion**:
- HTTP 404/410
- Redireccion a homepage
- Texto "anuncio no disponible/eliminado" en HTML

**Uso**:
```bash
# Django management command
python manage.py check_removed_listings --limit 50 --dry-run
python manage.py check_removed_listings --portal habitaclia

# Script directo
python scrapers/listing_checker.py --limit 100
```

**Accion**: Marca leads eliminados como `YA_VENDIDO` automaticamente.

### CRM - Asignatarios (15 Enero 2026)
Los usuarios admin (`is_superuser=True` o `is_staff=True`) ya no aparecen
en el dropdown de asignatarios. Solo usuarios normales del tenant.

## Debugging - Regla Importante

**REGLA**: Si un bug/error NO se resuelve en el PRIMER intento, crear inmediatamente un endpoint de debug temporal.

**Patron recomendado**:
1. Primer intento: Analizar codigo y probar fix obvio
2. Si falla: Crear `/analytics/debug/` o similar que:
   - Ejecute queries sospechosas individualmente
   - Muestre tipos de datos (pg_typeof, type())
   - Pruebe imports de modelos
   - Devuelva JSON con errores detallados
3. Desplegar y analizar output del debug endpoint
4. Arreglar el problema real
5. Eliminar endpoint de debug

**Ejemplo de debug endpoint**:
```python
def debug_view(request):
    errors = []
    results = {}
    try:
        # Test queries individuales
        cursor.execute("SELECT COUNT(*) FROM tabla")
        results['count'] = cursor.fetchone()[0]
    except Exception as e:
        errors.append(f"query: {e}")
    return JsonResponse({'errors': errors, 'results': results})
```

**Ventaja**: Evita ciclos largos de deploy->error->analizar->deploy. Un debug endpoint bien hecho identifica el problema en 1 deploy.

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

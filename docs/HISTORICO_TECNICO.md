# Histórico Técnico - Casa Teva

> Información técnica de referencia extraída de CLAUDE.md (20 Enero 2026)

## Selectores HTML por Portal

### Habitaclia
| Campo | Selector |
|-------|----------|
| Precio | `feature-container` class |
| Metros | `<li>Superficie X m2</li>` |
| Habitaciones | `<li>X habitaciones</li>` |

### Fotocasa
| Campo | Selector |
|-------|----------|
| Precio | `re-DetailHeader-price` class |
| Metros | `<span><span>N</span> m²` |
| Habitaciones | `<span><span>N</span> hab` |

### Idealista
| Campo | Selector |
|-------|----------|
| Precio | `info-data-price` class |
| Metros | `info-features` section |
| Habitaciones | `info-features` section |
| Título | `<span class="main-info__title-main">` |
| Descripción | `<div class="adCommentsLanguage">` |

### Milanuncios
| Campo | Selector |
|-------|----------|
| Precio | JSON-LD / data attributes |
| Metros | Generic (detail page only) |
| Habitaciones | Generic (detail page only) |

## Filtro de Agencias Idealista

Idealista NO tiene filtro URL público para particulares. El scraper filtra en dos niveles:

**Nivel 1 - Página búsqueda** (ahorra créditos):
- `professional-name`, `logo-profesional`, `item-link-professional`

**Nivel 2 - Página detalle**:
- `data-seller-type="professional"`
- `advertiser-name` con texto "inmobiliaria/agencia/fincas"
- `professional-info`
- JSON-LD: seller con nombre de inmobiliaria
- Texto "contactar con la inmobiliaria"

## Filtro Agencias dbt

**Por descripción**:
- "abstenerse agencias/inmobiliarias"
- "no agencias/no inmobiliarias"
- "sin intermediarios"
- "sin comisiones de agencia"
- "0% comision" / "cero comision"

**Por nombre vendedor (Milanuncios)**:
- Palabras: inmobiliaria, inmuebles, fincas, agencia, grupo
- Sufijos: S.L., SL, S.A.
- Otros: real estate, properties, servicios inmobiliarios

## Sistema Contacto Automático

### Estado por Portal (Enero 2026)

| Portal | Estado | Anti-bot | Notas |
|--------|--------|----------|-------|
| Fotocasa | ✅ OK | Ninguno | Email confirmación recibido |
| Habitaclia | ✅ Listo | 2Captcha reCAPTCHA | Configurado |
| Milanuncios | ✅ OK | Camoufox (GeeTest) | Login con Enter, no clic |
| Idealista | ⚠️ Parcial | DataDome | Páginas OK, login bloqueado |

### Hallazgos Técnicos

**Milanuncios**:
- GeeTest bloquea Playwright (Firefox y Chromium)
- Camoufox bypassa GeeTest
- Login funciona con `press('Enter')` no clic en botón

**Idealista**:
- DataDome bloquea login pero NO páginas de anuncios
- Con cookies guardadas, anuncios cargan OK
- `base.py` línea 103: Usar Chromium (no Firefox)
- Login necesita proxy residencial (~$15/mes)

## Bugs Históricos Resueltos

### Enero 2026

1. **Habitaclia no extraía fotos**: Filtro `id_for_match` comparaba IDs incompatibles
2. **Dashboard 500 error**: Template usaba `contact_detail` (int) vs `detail` (string)
3. **DATABASE_URL parsing**: `if 'azure' in db_url` no detectaba hostname Azure
4. **scraping_stats columna**: Usar `fecha_primera_captura` no `created_at`
5. **dbt dim_leads falla**: Crear tabla `lead_image_scores` en pre_hook

### Fix Encoding (11 Enero 2026)
`fix_encoding()` solo corrige texto doblemente codificado (marcadores como `Ã¡`).
Preserva UTF-8 correcto (ej: `Tàrrega` no se corrompe).

## Zonas Skip Idealista

Zonas pequeñas donde 95%+ son agencias (0 particulares):
- amposta, deltebre, ametlla_mar, hospitalet_infant, montroig_camp, sant_carles_rapita

Definidas en `IDEALISTA_SKIP_ZONES` en `scraping_assets.py`.

## Watermark Detection (Milanuncios)

Filtro para detectar agencias disfrazadas:
- Descarga primera imagen
- Analiza 15% inferior (zona watermarks)
- Detecta alta densidad de bordes (texto/logos)
- Si detecta → descarta anuncio

Módulo: `scrapers/watermark_detector.py`

## Competencia (Precios Enero 2026)

| Producto | Precio | Qué ofrece |
|----------|--------|------------|
| Idealista Tools | ~50€/provincia/mes | Captación, CRM |
| Fotocasa Pro | Variable | Publicación 3 portales |
| Betipo | 19.99€+9.99€/100 val | Widget valorador |
| Inmovilla | 79€/mes | CRM completo |
| Witei | 40€/mes | CRM simple |

## WhatsApp Business API (Pendiente)

Requisitos:
1. Cuenta Business verificada por Meta (~2 semanas)
2. Servidor webhook HTTPS
3. Templates aprobados por Meta

Coste: ~$0.05/mensaje (Twilio: ~$0.005/msg)

67% interacciones inmobiliarias empiezan en WhatsApp.
30% leads abandonan si no respuesta en 24h.

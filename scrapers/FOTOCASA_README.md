# Fotocasa Scraper

Scraper de Fotocasa usando Scrapy + Playwright para extraer anuncios de particulares que venden viviendas.

## 🎯 Características

- ✅ **Scrapy + Playwright**: Renderiza JavaScript para obtener contenido dinámico
- ✅ **Filtrado inteligente**: Rechaza inmobiliarias y particulares que no permiten contacto
- ✅ **Rate limiting**: 3 segundos entre requests, 1 request concurrente
- ✅ **Persistencia dual**: Guarda en MinIO (data lake) y PostgreSQL (raw layer)
- ✅ **Normalización**: Teléfonos normalizados, zonas clasificadas
- ✅ **Paginación**: Navega automáticamente por todas las páginas
- ✅ **Estadísticas**: Trackea listings procesados, filtrados, guardados y errores

## 📋 Requisitos

### Instalar dependencias:

```bash
# Instalar dependencias de Python
pip install -r requirements.txt

# Instalar navegadores de Playwright
playwright install chromium
```

### Servicios necesarios (opcional):

- **MinIO**: Para guardar datos en data lake
- **PostgreSQL**: Para guardar datos en raw layer

## 🚀 Uso

### Modo básico (solo logs, sin guardar):

```bash
python run_fotocasa_scraper.py
```

### Con MinIO y PostgreSQL:

```bash
python run_fotocasa_scraper.py --minio --postgres
```

### Para un tenant específico:

```bash
python run_fotocasa_scraper.py --tenant-id=2 --minio --postgres
```

### Usando Scrapy directamente:

```bash
scrapy crawl fotocasa
```

## 🔧 Configuración

### Editar `run_fotocasa_scraper.py`:

```python
# Zonas a scrapear
zones = {
    "lleida_ciudad": {
        "enabled": True,
        "codigos_postales": ["25001", "25002", ...]
    }
}

# Filtros de búsqueda
filters = {
    "filtros_precio": {
        "min": 50000,
        "max": 1000000
    }
}

# Configuración MinIO
minio_config = {
    'endpoint': 'localhost:9000',
    'access_key': 'minioadmin',
    'secret_key': 'minioadmin',
    'secure': False
}

# Configuración PostgreSQL
postgres_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'casa_teva_db',
    'user': 'casa_teva',
    'password': 'casateva2024'
}
```

## 📊 Datos Extraídos

Para cada listing, el scraper extrae:

- **Título**: Título del anuncio
- **Precio**: Precio en €
- **Dirección**: Ubicación completa
- **Código Postal**: Extraído de la dirección
- **Habitaciones**: Número de habitaciones
- **Metros**: Superficie en m²
- **Descripción**: Texto descriptivo del anuncio
- **Fotos**: URLs de las imágenes
- **URL Anuncio**: Link al anuncio original
- **Teléfono**: Número de contacto (si disponible)
- **Zona Geográfica**: Clasificada automáticamente

## 🎯 Sistema de Filtrado

El scraper **NUNCA** guarda:

❌ Anuncios de inmobiliarias/agencias
❌ Particulares que digan "NO INMOBILIARIAS"
❌ Profesionales con muchos anuncios
❌ Usuarios con badges profesionales

Solo guarda:

✅ Particulares que permiten contacto de inmobiliarias
✅ Usuarios con pocos anuncios activos
✅ Sin badges profesionales

## 📁 Estructura de Datos

### Data Lake (MinIO):

```
bronze/tenant_1/fotocasa/2025-12-07/listing_abc123.json
```

### PostgreSQL (raw.raw_listings):

```sql
INSERT INTO raw.raw_listings (
    tenant_id,
    portal,
    data_lake_path,
    raw_data,       -- JSONB con todos los datos
    scraping_timestamp
)
```

## ⚠️ IMPORTANTE: Selectores CSS

Los selectores CSS en `fotocasa_scraper.py` son **aproximados** y deben ajustarse según la estructura real actual de Fotocasa:

```python
# Ajustar estos selectores inspeccionando fotocasa.es:
listing_cards = response.css('.re-Card')           # Card principal
titulo = card.css('.re-Card-title::text').get()   # Título
precio = card.css('.re-Card-price::text').get()   # Precio
direccion = card.css('.re-Card-location::text').get()  # Dirección
# ... etc
```

**Pasos para ajustar selectores:**

1. Ir a https://www.fotocasa.es
2. Abrir DevTools (F12)
3. Inspeccionar elementos de un anuncio
4. Copiar selectores CSS correctos
5. Actualizar en `_extract_listing_data()`

## 📈 Estadísticas

El scraper muestra estadísticas al finalizar:

```
Spider cerrado. Razón: finished
Estadísticas finales:
  - Total listings procesados: 120
  - Filtrados (rechazados): 45
  - Guardados exitosamente: 75
  - Errores: 0
  - Tasa de filtrado: 37.5%
```

## 🐛 Debugging

### Ver logs detallados:

Editar `scrapers/settings.py`:

```python
LOG_LEVEL = 'DEBUG'  # Cambiar de INFO a DEBUG
```

### Ejecutar en modo headful (ver navegador):

Editar `fotocasa_scraper.py`:

```python
'PLAYWRIGHT_LAUNCH_OPTIONS': {
    'headless': False,  # Cambiar a False
    'timeout': 60000,
}
```

### Capturar screenshots:

```python
# Añadir en parse():
await page.screenshot(path='screenshot.png')
```

## 🔄 Integración con Dagster

El scraper puede ser integrado en Dagster como un asset:

```python
@asset
def fotocasa_scraping_job():
    subprocess.run([
        'python', 'run_fotocasa_scraper.py',
        '--minio', '--postgres'
    ])
```

## 📝 Próximos Pasos

1. **Ajustar selectores CSS** según estructura real de Fotocasa
2. **Probar extracción de teléfonos** con Playwright
3. **Implementar paginación** completa
4. **Añadir manejo de CAPTCHAs** si es necesario
5. **Implementar proxies** si hay bloqueos
6. **Añadir tests unitarios** para el scraper

## ⚖️ Legal

Este scraper es para uso educativo y de desarrollo. Asegúrate de:

- Respetar los términos de servicio de Fotocasa
- No sobrecargar sus servidores (rate limiting habilitado)
- Usar los datos de forma ética y legal
- Considerar el uso de su API oficial si está disponible

# Dagster Pipeline - Casa Teva

Orquestación de scrapers y ETL para el sistema de captación de leads inmobiliarios.

## 📁 Estructura

```
dagster/
├── workspace.yaml                           # Configuración del workspace
└── casa_teva_pipeline/
    ├── __init__.py                         # Definitions principal
    ├── assets/
    │   └── scraping_assets.py              # Assets de scraping
    ├── resources/
    │   ├── minio_resource.py               # Resource MinIO
    │   └── postgres_resource.py            # Resource PostgreSQL
    └── schedules/
        └── scraping_schedules.py           # Schedules automatizados
```

## 🚀 Inicio Rápido

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Iniciar Dagster UI

```bash
cd dagster
dagster dev
```

La UI estará disponible en: http://localhost:3000

### 3. Ver assets y jobs

- Navega a la pestaña "Assets"
- Verás todos los assets definidos con sus dependencias

### 4. Ejecutar manualmente

Desde la UI:
1. Ir a "Assets" → Seleccionar assets
2. Click en "Materialize selected"

Desde CLI:
```bash
dagster asset materialize -m casa_teva_pipeline
```

## 📊 Assets Definidos

### **bronze_fotocasa_listings**
- Ejecuta scraper de Fotocasa
- Guarda JSONs en MinIO: `bronze/tenant_1/fotocasa/{fecha}/`
- **Output**: Metadata con número de listings y paths

### **raw_postgres_listings**
- Depende de: `bronze_fotocasa_listings`
- Lee JSONs de MinIO
- Inserta en PostgreSQL: `raw.raw_listings`
- **Output**: Número de registros cargados

### **scraping_stats**
- Depende de: `raw_postgres_listings`
- Genera estadísticas consolidadas
- **Output**: Dict con métricas de scraping

### **bronze_milanuncios_listings** (Placeholder)
- Por implementar cuando scraper esté listo

### **bronze_wallapop_listings** (Placeholder)
- Por implementar cuando scraper esté listo

## 🔧 Resources

### **MinIOResource**
Interacción con Data Lake (MinIO):
- `save_json()`: Guarda diccionarios como JSON
- `read_json()`: Lee archivos JSON
- `list_files()`: Lista archivos por prefijo
- `delete_file()`: Elimina archivos

**Configuración:**
```python
MinIOResource(
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    bucket_name="casa-teva-data-lake",
    secure=False
)
```

### **PostgresResource**
Interacción con PostgreSQL:
- `execute_query()`: Ejecuta queries SQL
- `insert_data()`: Inserta registros
- `insert_raw_listing()`: Inserta en raw.raw_listings
- `bulk_insert_raw_listings()`: Inserta múltiples registros
- `get_latest_scraping_timestamp()`: Obtiene último scraping

**Configuración:**
```python
PostgresResource(
    host="localhost",
    port=5432,
    database="casa_teva_db",
    user="casa_teva",
    password="casateva2024"
)
```

## ⏰ Schedules

### **scraping_schedule** (Activo)
- **Cron**: `0 */6 * * *` (cada 6 horas)
- **Timezone**: Europe/Madrid
- **Horarios**: 00:00, 06:00, 12:00, 18:00
- **Estado**: RUNNING

### **scraping_schedule_hourly** (Inactivo)
- **Cron**: `0 * * * *` (cada hora)
- **Estado**: STOPPED (para testing)

### **scraping_schedule_daily** (Inactivo)
- **Cron**: `0 2 * * *` (2 AM diario)
- **Estado**: STOPPED

### **scraping_schedule_custom** (Inactivo)
- **Lógica custom**: Solo días laborables
- **Estado**: STOPPED

## 🎯 Jobs

### **scraping_job**
- Ejecuta todos los assets de scraping
- Tags: team=data-engineering, priority=high

### **fotocasa_job**
- Solo ejecuta assets de Fotocasa
- Tags: portal=fotocasa

## 📈 Lineage de Datos

```
bronze_fotocasa_listings (MinIO)
    ↓
raw_postgres_listings (PostgreSQL)
    ↓
scraping_stats (Métricas)
```

## 🔄 Flujo de Ejecución

1. **Scraping** (`bronze_fotocasa_listings`)
   - Ejecuta `run_fotocasa_scraper.py --minio`
   - Scrapy + Playwright extrae listings
   - Guarda JSONs en MinIO bronze layer

2. **Carga** (`raw_postgres_listings`)
   - Lee todos los JSONs del día
   - Bulk insert en PostgreSQL
   - Tabla: `raw.raw_listings`

3. **Reporting** (`scraping_stats`)
   - Consolida estadísticas
   - Metadata en Dagster UI

## 🛠️ Comandos Útiles

### Verificar configuración
```bash
dagster dev --check
```

### Materializar asset específico
```bash
dagster asset materialize -m casa_teva_pipeline -s bronze_fotocasa_listings
```

### Materializar todos los assets
```bash
dagster asset materialize -m casa_teva_pipeline
```

### Ver logs
```bash
# Los logs aparecen en la UI y en consola
dagster dev -v
```

### Activar/desactivar schedule desde CLI
```bash
dagster schedule start scraping_schedule
dagster schedule stop scraping_schedule
```

## 📝 Configuración Personalizada

### Cambiar configuración de MinIO

Editar `casa_teva_pipeline/__init__.py`:

```python
resources = {
    "minio": MinIOResource(
        endpoint="minio.tudominio.com:9000",  # ← Cambiar
        access_key="tu_access_key",           # ← Cambiar
        secret_key="tu_secret_key",           # ← Cambiar
        bucket_name="mi-bucket",              # ← Cambiar
        secure=True,                          # ← Cambiar si usas HTTPS
    ),
    # ...
}
```

### Cambiar horarios de schedule

Editar `schedules/scraping_schedules.py`:

```python
scraping_schedule = ScheduleDefinition(
    name="scraping_schedule",
    cron_schedule="0 */4 * * *",  # ← Cambiar a cada 4 horas
    # ...
)
```

## 🐛 Debugging

### Ver detalles de ejecución
1. Ir a "Runs" en la UI
2. Click en el run específico
3. Ver logs, duración, metadata

### Ejecutar en modo debug
```bash
dagster dev --log-level debug
```

### Verificar assets sin ejecutar
```bash
dagster asset check -m casa_teva_pipeline
```

## 🔐 Seguridad

**IMPORTANTE**: Las credenciales en `__init__.py` son para desarrollo.

Para producción:
1. Usar variables de entorno
2. Usar secrets manager (AWS Secrets Manager, etc.)
3. Configurar con ConfigurableResource

Ejemplo con env vars:
```python
import os

resources = {
    "postgres": PostgresResource(
        password=os.getenv("POSTGRES_PASSWORD"),
        # ...
    ),
}
```

## 📊 Metadata y Observabilidad

Dagster trackea automáticamente:
- ✅ Tiempo de ejecución de cada asset
- ✅ Metadata custom (num_listings, paths, etc.)
- ✅ Lineage de datos
- ✅ Versiones de assets
- ✅ Historial de runs

## 🚧 Próximos Pasos

1. Implementar assets para Milanuncios y Wallapop
2. Añadir sensors para ejecutar cuando aparezcan nuevos archivos
3. Implementar alertas (Slack, email)
4. Añadir tests para assets
5. Configurar Dagster Cloud para producción

## 📚 Documentación

- [Dagster Docs](https://docs.dagster.io/)
- [Asset Best Practices](https://docs.dagster.io/concepts/assets/software-defined-assets)
- [Schedule Guide](https://docs.dagster.io/concepts/partitions-schedules-sensors/schedules)

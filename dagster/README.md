# Dagster Pipeline - Casa Teva

Orquestación de scrapers y ETL para el sistema de captación de leads inmobiliarios.

## Decisión de Diseño: Sin MinIO

> MinIO fue eliminado del proyecto. Los datos se guardan directamente en PostgreSQL
> como JSONB en la tabla `raw.raw_listings`. Ver `INSTRUCCIONES_SETUP.md` para más detalles.

## Estructura

```
dagster/
├── workspace.yaml                           # Configuración del workspace
└── casa_teva_pipeline/
    ├── __init__.py                         # Definitions principal
    ├── assets/
    │   └── scraping_assets.py              # Assets de scraping
    ├── resources/
    │   └── postgres_resource.py            # Resource PostgreSQL
    └── schedules/
        └── scraping_schedules.py           # Schedules automatizados
```

## Inicio Rápido

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

## Assets Definidos

### **raw_postgres_listings**
- Inserta datos en PostgreSQL: `raw.raw_listings`
- **Output**: Número de registros cargados

### **scraping_stats**
- Depende de: `raw_postgres_listings`
- Genera estadísticas consolidadas
- **Output**: Dict con métricas de scraping

## Resources

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

## Schedules

### **scraping_schedule**
- **Cron**: `0 */6 * * *` (cada 6 horas)
- **Timezone**: Europe/Madrid
- **Horarios**: 00:00, 06:00, 12:00, 18:00
- **Estado**: STOPPED (activar manualmente)

### **scraping_schedule_daily**
- **Cron**: `0 2 * * *` (2 AM diario)
- **Estado**: STOPPED

## Jobs

### **scraping_job**
- Ejecuta todos los assets de scraping
- Tags: team=data-engineering, priority=high

### **fotocasa_job**
- Solo ejecuta assets de Fotocasa
- Tags: portal=fotocasa

## Lineage de Datos

```
Scrapers (Playwright)
    ↓
raw.raw_listings (PostgreSQL JSONB)
    ↓
dbt (staging → marts)
    ↓
Django (Web CRM)
```

## Comandos Útiles

### Verificar configuración
```bash
dagster dev --check
```

### Materializar asset específico
```bash
dagster asset materialize -m casa_teva_pipeline -s raw_postgres_listings
```

### Ver logs
```bash
dagster dev -v
```

### Activar/desactivar schedule desde CLI
```bash
dagster schedule start scraping_schedule
dagster schedule stop scraping_schedule
```

## Configuración Personalizada

### Cambiar configuración de PostgreSQL

Editar `casa_teva_pipeline/__init__.py`:

```python
import os

resources = {
    "postgres": PostgresResource(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=5432,
        database=os.getenv("POSTGRES_DB", "casa_teva_db"),
        user=os.getenv("POSTGRES_USER", "casa_teva"),
        password=os.getenv("POSTGRES_PASSWORD", "casateva2024"),
    ),
}
```

### Cambiar horarios de schedule

Editar `schedules/scraping_schedules.py`:

```python
scraping_schedule = ScheduleDefinition(
    name="scraping_schedule",
    cron_schedule="0 */4 * * *",  # Cambiar a cada 4 horas
    # ...
)
```

## Debugging

### Ver detalles de ejecución
1. Ir a "Runs" en la UI
2. Click en el run específico
3. Ver logs, duración, metadata

### Ejecutar en modo debug
```bash
dagster dev --log-level debug
```

## Seguridad

**IMPORTANTE**: Las credenciales en `__init__.py` son para desarrollo.

Para producción:
1. Usar variables de entorno
2. Usar Azure Key Vault u otro secrets manager
3. Configurar con ConfigurableResource

## Próximos Pasos

1. Configurar Azure Functions para scrapers automáticos
2. Implementar alertas (Slack, email)
3. Añadir tests para assets
4. Configurar para producción en Azure

## Documentación

- [Dagster Docs](https://docs.dagster.io/)
- [Asset Best Practices](https://docs.dagster.io/concepts/assets/software-defined-assets)
- [Schedule Guide](https://docs.dagster.io/concepts/partitions-schedules-sensors/schedules)

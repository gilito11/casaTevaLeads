# Scripts de Setup - Casa Teva Lead System

Scripts de utilidad para configurar la infraestructura del sistema.

## Quick Start

```bash
# Setup PostgreSQL (schemas + tablas)
python scripts/setup_postgres.py
```

---

## Scripts Disponibles

### `setup_postgres.py` - PostgreSQL Setup

Configura PostgreSQL con schemas y tablas necesarias.

**Lo que hace:**
1. Verifica conexión a PostgreSQL
2. Crea schemas: `raw`, `staging`, `marts`, `analytics`
3. Crea tabla `raw.raw_listings` con estructura JSONB
4. Crea índices para optimizar queries
5. Configura permisos

**Uso básico:**
```bash
python scripts/setup_postgres.py
```

**Opciones:**
```bash
# Recrear schemas desde cero (elimina datos)
python scripts/setup_postgres.py --drop-all
```

**Configuración:**

El script usa estas variables de entorno (o defaults):
- `DB_HOST`: localhost
- `DB_PORT`: 5432
- `DB_NAME`: casa_teva_db
- `DB_USER`: casa_teva
- `DB_PASSWORD`: casateva2024

---

## Nota: MinIO Eliminado

> El script `setup_minio.py` ha sido eliminado del proyecto.
>
> **Razón:** Se decidió simplificar la arquitectura guardando todos los datos
> directamente en PostgreSQL como JSONB, eliminando la necesidad de un Data Lake
> separado. Ver `INSTRUCCIONES_SETUP.md` para más detalles sobre esta decisión.

---

## Workflow Completo

### Primera Vez

```bash
# 1. Iniciar Docker
docker-compose up -d

# 2. Setup PostgreSQL
python scripts/setup_postgres.py

# 3. Migrar Django
cd backend
python manage.py migrate
python manage.py createsuperuser

# 4. Ejecutar dbt
cd ../dbt_project
dbt deps
dbt run

# 5. Test scraper
cd ..
python run_all_scrapers.py --zones salou --postgres

# 6. Iniciar servicios
docker-compose up -d
```

---

## Requisitos

```bash
pip install psycopg2-binary
```

---

## Debugging

### Ver estado de PostgreSQL

```bash
# Conectar a PostgreSQL
docker exec -it casa-teva-postgres psql -U casa_teva -d casa_teva_db

# Ver schemas
\dn

# Ver tablas en schema raw
\dt raw.*

# Describir tabla
\d raw.raw_listings

# Contar registros
SELECT COUNT(*) FROM raw.raw_listings;

# Ver últimos leads
SELECT
    raw_data->>'titulo' as titulo,
    raw_data->>'precio' as precio,
    created_at
FROM raw.raw_listings
ORDER BY created_at DESC
LIMIT 5;
```

---

## Notas

- Los scripts son **idempotentes**: puedes ejecutarlos múltiples veces sin problemas
- Usan `IF NOT EXISTS` para evitar errores si ya están creados
- Verifican la configuración al final

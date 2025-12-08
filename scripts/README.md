# Scripts de Setup - Casa Teva Lead System

Scripts de utilidad para configurar la infraestructura del sistema.

## 🚀 Quick Start

### Setup Completo (Recomendado)

```bash
# Setup todo (PostgreSQL + MinIO)
python scripts/setup_all.py
```

### Setup Individual

```bash
# Solo PostgreSQL
python scripts/setup_postgres.py

# Solo MinIO
python scripts/setup_minio.py
```

---

## 📋 Scripts Disponibles

### 1. `setup_all.py` - Setup Maestro

Ejecuta todos los setups en orden correcto.

**Uso básico:**
```bash
python scripts/setup_all.py
```

**Opciones:**
```bash
# Recrear TODO desde cero (⚠️ PELIGROSO - elimina datos)
python scripts/setup_all.py --reset

# Saltar PostgreSQL
python scripts/setup_all.py --skip-postgres

# Saltar MinIO
python scripts/setup_all.py --skip-minio
```

---

### 2. `setup_postgres.py` - PostgreSQL Setup

Configura PostgreSQL con schemas y tablas necesarias.

**Lo que hace:**
1. ✅ Verifica conexión a PostgreSQL
2. ✅ Crea schemas: `raw`, `staging`, `marts`, `analytics`
3. ✅ Crea tabla `raw.raw_listings` con estructura correcta
4. ✅ Crea índices para optimizar queries
5. ✅ Configura permisos
6. ✅ Verifica todo está OK

**Uso básico:**
```bash
python scripts/setup_postgres.py
```

**Opciones:**
```bash
# Recrear schemas desde cero (⚠️ elimina datos)
python scripts/setup_postgres.py --drop-all
```

**Configuración:**

El script usa estas variables de entorno (o defaults):
- `DB_HOST`: localhost
- `DB_PORT`: 5432
- `DB_NAME`: casa_teva_db
- `DB_USER`: casa_teva
- `DB_PASSWORD`: casateva2024 (desde .env)

**Troubleshooting:**

Si falla la conexión:
```bash
# 1. Verificar PostgreSQL está corriendo
pg_ctl status

# 2. Crear base de datos si no existe
createdb -U postgres casa_teva_db

# 3. Crear usuario si no existe
psql -U postgres -c "CREATE USER casa_teva WITH PASSWORD 'casateva2024';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE casa_teva_db TO casa_teva;"
```

---

### 3. `setup_minio.py` - MinIO Setup

Configura MinIO (Data Lake) con buckets y estructura.

**Lo que hace:**
1. ✅ Verifica conexión a MinIO
2. ✅ Crea bucket `casa-teva-data-lake`
3. ✅ Crea estructura de carpetas:
   - `bronze/tenant_X/portal/` - Datos raw
   - `screenshots/tenant_X/` - Capturas
   - `logs/` - Logs de scraping
4. ✅ Crea archivo de prueba
5. ✅ Verifica todo está OK

**Uso básico:**
```bash
python scripts/setup_minio.py
```

**Opciones:**
```bash
# Recrear bucket desde cero (⚠️ elimina datos)
python scripts/setup_minio.py --recreate
```

**Configuración:**

El script usa estas variables de entorno (o defaults):
- `MINIO_ENDPOINT`: localhost:9000
- `MINIO_ACCESS_KEY`: minioadmin
- `MINIO_SECRET_KEY`: minioadmin
- `MINIO_SECURE`: False

**Troubleshooting:**

Si MinIO no está corriendo:
```bash
# Iniciar MinIO con Docker
docker run -d \
  -p 9000:9000 -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  --name minio \
  minio/minio server /data --console-address ":9001"

# Verificar está corriendo
docker ps | grep minio

# Acceder a consola
open http://localhost:9001
# Usuario: minioadmin
# Password: minioadmin
```

---

## 🔄 Workflow Completo

### Primera Vez

```bash
# 1. Setup infraestructura
python scripts/setup_all.py

# 2. Migrar Django
cd backend
python manage.py migrate

# 3. Crear superuser
python manage.py createsuperuser

# 4. Ejecutar dbt
cd ../dbt_project
dbt deps
dbt run

# 5. Test scraper
cd ..
python run_fotocasa_scraper.py --tenant-id=1 --minio

# 6. Iniciar Dagster
dagster dev -f dagster/workspace.yaml
```

### Reset Completo

```bash
# ⚠️ CUIDADO: Esto elimina TODOS los datos
python scripts/setup_all.py --reset
```

---

## 📦 Requisitos

```bash
pip install psycopg2-binary minio
```

O desde requirements.txt:
```bash
pip install -r requirements.txt
```

---

## 🐛 Debugging

### Ver logs de PostgreSQL

```bash
# Conectar a PostgreSQL
psql -U casa_teva -d casa_teva_db

# Ver schemas
\dn

# Ver tablas en schema raw
\dt raw.*

# Describir tabla
\d raw.raw_listings

# Contar registros
SELECT COUNT(*) FROM raw.raw_listings;
```

### Ver logs de MinIO

```bash
# Ver buckets
mc alias set minio http://localhost:9000 minioadmin minioadmin
mc ls minio/

# Ver contenido del bucket
mc ls minio/casa-teva-data-lake/

# Listar archivos recursivamente
mc ls --recursive minio/casa-teva-data-lake/bronze/
```

---

## 📝 Notas

- Los scripts son **idempotentes**: puedes ejecutarlos múltiples veces sin problemas
- Usan `IF NOT EXISTS` para evitar errores si ya están creados
- Verifican la configuración al final
- Todos los scripts soportan `--help` para ver opciones

---

## 🆘 Ayuda

Si tienes problemas:

1. **Lee los mensajes de error** - Los scripts dan sugerencias específicas
2. **Verifica la configuración** - Revisa `.env` y credenciales
3. **Comprueba los servicios** - PostgreSQL y MinIO deben estar corriendo
4. **Mira los logs** - PostgreSQL y MinIO tienen logs detallados

Para soporte, revisa:
- `PROJECT_SPEC_v2.0.md` - Especificación completa
- `VERIFICACION_PROYECTO.md` - Checklist de verificación

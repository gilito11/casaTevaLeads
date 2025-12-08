# 🚀 Instrucciones de Setup - Casa Teva Lead System

## ✅ ESTADO ACTUAL

### Lo que YA está implementado:
- ✅ **Scripts de setup** creados y funcionales:
  - `scripts/setup_postgres.py` - Configura PostgreSQL
  - `scripts/setup_minio.py` - Configura MinIO
  - `scripts/setup_all.py` - Setup completo
  - `scripts/README.md` - Documentación
- ✅ **Dagster** configurado (assets, resources, schedules)
- ✅ **dbt** configurado (staging, marts, macros)
- ✅ **Django** implementado (models, multi-tenancy)
- ✅ **Scrapers** implementados (Fotocasa con filtros)

### Lo que FALTA configurar:
- ❌ **PostgreSQL**: No está corriendo (o no en localhost:5432)
- ❌ **MinIO**: No verificado aún

---

## 📋 PASOS PARA COMPLETAR EL SETUP

### OPCIÓN A: Tienes PostgreSQL instalado localmente

#### 1. Iniciar PostgreSQL

**Windows:**
```cmd
# Si instalaste con Installer oficial
net start postgresql-x64-16

# O buscar en Servicios de Windows
services.msc
→ Buscar "postgresql"
→ Click derecho → Iniciar
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo systemctl start postgresql

# Mac con Homebrew
brew services start postgresql@16
```

#### 2. Crear base de datos y usuario

```bash
# Conectar como postgres
psql -U postgres

# O en Windows:
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```

```sql
-- Crear base de datos
CREATE DATABASE casa_teva_db;

-- Crear usuario
CREATE USER casa_teva WITH PASSWORD 'casateva2024';

-- Dar permisos
GRANT ALL PRIVILEGES ON DATABASE casa_teva_db TO casa_teva;
ALTER DATABASE casa_teva_db OWNER TO casa_teva;

-- Salir
\q
```

#### 3. Ejecutar setup

```bash
python scripts/setup_postgres.py
```

---

### OPCIÓN B: Usar Docker (Recomendado para desarrollo)

#### 1. Crear archivo docker-compose.yml

Ya te lo preparo aquí abajo ⬇️

#### 2. Iniciar servicios

```bash
docker-compose up -d
```

#### 3. Ejecutar setups

```bash
# Esperar 10 segundos a que PostgreSQL inicie
sleep 10

# Setup PostgreSQL
python scripts/setup_postgres.py

# Setup MinIO
python scripts/setup_minio.py
```

---

## 🐳 Docker Compose (Solución Más Fácil)

### Paso 1: Crear archivo `docker-compose.yml` en la raíz del proyecto

```yaml
version: '3.8'

services:
  # PostgreSQL - Data Warehouse
  postgres:
    image: postgres:16-alpine
    container_name: casa-teva-postgres
    environment:
      POSTGRES_DB: casa_teva_db
      POSTGRES_USER: casa_teva
      POSTGRES_PASSWORD: casateva2024
      POSTGRES_INITDB_ARGS: "-E UTF8"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U casa_teva -d casa_teva_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # MinIO - Data Lake
  minio:
    image: minio/minio:latest
    container_name: casa-teva-minio
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Console
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
  minio_data:
    driver: local
```

### Paso 2: Iniciar servicios

```bash
docker-compose up -d
```

### Paso 3: Verificar que están corriendo

```bash
docker-compose ps

# Deberías ver:
# casa-teva-postgres   running   0.0.0.0:5432->5432/tcp
# casa-teva-minio      running   0.0.0.0:9000-9001->9000-9001/tcp
```

### Paso 4: Ejecutar scripts de setup

```bash
# Setup PostgreSQL (schemas + tablas)
python scripts/setup_postgres.py

# Setup MinIO (bucket + estructura)
python scripts/setup_minio.py
```

---

## ✅ Verificación Post-Setup

### PostgreSQL

```bash
# Conectar
psql -U casa_teva -d casa_teva_db

# O con Docker
docker exec -it casa-teva-postgres psql -U casa_teva -d casa_teva_db
```

```sql
-- Verificar schemas
\dn

-- Debería mostrar:
--   raw
--   staging
--   marts
--   analytics

-- Verificar tabla
\dt raw.*

-- Debería mostrar:
--   raw.raw_listings

-- Salir
\q
```

### MinIO

1. **Abrir consola**: http://localhost:9001
2. **Login**:
   - Usuario: `minioadmin`
   - Password: `minioadmin`
3. **Verificar bucket**: `casa-teva-data-lake`
4. **Verificar estructura**:
   - `bronze/tenant_1/fotocasa/`
   - `screenshots/tenant_1/`
   - `logs/`

---

## 🎯 Próximos Pasos (después del setup)

### 1. Migraciones Django

```bash
cd backend
python manage.py migrate
python manage.py createsuperuser
```

### 2. Ejecutar dbt

```bash
cd dbt_project
dbt run
dbt test
```

### 3. Test Scraper

```bash
python run_fotocasa_scraper.py --tenant-id=1 --minio
```

### 4. Iniciar Dagster

```bash
dagster dev -f dagster/workspace.yaml
# Acceder a: http://localhost:3000
```

### 5. Iniciar Django

```bash
cd backend
python manage.py runserver
# Acceder a: http://localhost:8000/admin
```

---

## 🆘 Troubleshooting

### Error: "connection refused" en PostgreSQL

```bash
# Verificar que PostgreSQL está corriendo
docker ps | grep postgres

# O en Windows (sin Docker)
services.msc → buscar "postgresql"

# Ver logs
docker logs casa-teva-postgres
```

### Error: MinIO no accesible

```bash
# Verificar que MinIO está corriendo
docker ps | grep minio

# Ver logs
docker logs casa-teva-minio

# Reiniciar
docker-compose restart minio
```

### Puertos ya en uso

```bash
# Ver qué proceso usa el puerto 5432
netstat -ano | findstr :5432

# O puerto 9000
netstat -ano | findstr :9000

# Matar proceso (Windows)
taskkill /PID <PID> /F

# O cambiar puertos en docker-compose.yml
ports:
  - "15432:5432"  # PostgreSQL en puerto 15432
  - "19000:9000"  # MinIO en puerto 19000
```

---

## 📊 URLs Útiles

Después del setup completo:

- **MinIO Console**: http://localhost:9001
- **Dagster UI**: http://localhost:3000
- **Django Admin**: http://localhost:8000/admin
- **Django API**: http://localhost:8000/api/

---

## 🎉 Resumen

**Scripts creados:**
```
scripts/
├── setup_postgres.py    ✅ Configura PostgreSQL
├── setup_minio.py       ✅ Configura MinIO
├── setup_all.py         ✅ Setup completo
└── README.md            ✅ Documentación
```

**Para empezar:**

1. **Opción rápida (Docker)**:
   ```bash
   docker-compose up -d
   python scripts/setup_all.py
   ```

2. **Opción manual**:
   - Instalar PostgreSQL + MinIO
   - Ejecutar `python scripts/setup_all.py`

**Estado**: El código está listo, solo faltan los servicios corriendo! 🚀

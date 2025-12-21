# Instrucciones de Setup - Casa Teva Lead System

## Estado Actual

### Lo que YA está implementado:
- **PostgreSQL**: Base de datos principal (Docker)
- **Django**: Backend web con multi-tenancy
- **Scrapers**: Milanuncios, Fotocasa, Wallapop
- **Dagster**: Orquestación de pipelines

### Decisión de Diseño: Sin MinIO

> **¿Por qué no usamos MinIO/Data Lake?**
>
> Inicialmente el proyecto incluía MinIO como Data Lake para almacenar JSONs crudos.
> Se decidió eliminarlo por las siguientes razones:
>
> 1. **Redundancia**: PostgreSQL ya almacena los datos como JSONB en `raw.raw_listings`
> 2. **Simplicidad**: Menos servicios = menos mantenimiento
> 3. **Azure**: Para producción, usaríamos Azure Blob Storage (no MinIO)
> 4. **Coste**: Ahorra recursos (RAM, disco) en desarrollo local
>
> Los datos se guardan directamente en PostgreSQL, que ofrece:
> - Indexación de campos JSONB
> - Queries SQL sobre datos JSON
> - Backups integrados
> - Una sola fuente de verdad

---

## Pasos para Setup

### Opción A: Docker (Recomendado)

#### 1. Iniciar servicios

```bash
docker-compose up -d
```

#### 2. Verificar que están corriendo

```bash
docker-compose ps

# Deberías ver:
# casa-teva-postgres   running   0.0.0.0:5432->5432/tcp
# casa-teva-web        running   0.0.0.0:8000->8000/tcp
# casa-teva-dagster    running   0.0.0.0:3000->3000/tcp
```

#### 3. Ejecutar setup de PostgreSQL

```bash
python scripts/setup_postgres.py
```

---

### Opción B: PostgreSQL Local (sin Docker)

#### 1. Iniciar PostgreSQL

**Windows:**
```cmd
net start postgresql-x64-16
```

**Linux/Mac:**
```bash
sudo systemctl start postgresql
```

#### 2. Crear base de datos y usuario

```sql
-- Conectar como postgres
psql -U postgres

-- Crear base de datos
CREATE DATABASE casa_teva_db;

-- Crear usuario
CREATE USER casa_teva WITH PASSWORD 'casateva2024';

-- Dar permisos
GRANT ALL PRIVILEGES ON DATABASE casa_teva_db TO casa_teva;
ALTER DATABASE casa_teva_db OWNER TO casa_teva;

\q
```

#### 3. Ejecutar setup

```bash
python scripts/setup_postgres.py
```

---

## Verificación Post-Setup

### PostgreSQL

```bash
# Conectar (Docker)
docker exec -it casa-teva-postgres psql -U casa_teva -d casa_teva_db

# Verificar schemas
\dn

# Debería mostrar:
#   raw
#   staging
#   marts
#   analytics

# Verificar tabla
\dt raw.*

# Debería mostrar:
#   raw.raw_listings
```

---

## Próximos Pasos

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
python run_all_scrapers.py --zones salou --postgres
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
# Acceder a: http://localhost:8000
```

---

## URLs Útiles

| Servicio | URL | Notas |
|----------|-----|-------|
| Django Web | http://localhost:8000 | CRM de leads |
| Django Admin | http://localhost:8000/admin | Administración |
| Dagster UI | http://localhost:3000 | Pipelines |

---

## Troubleshooting

### Error: "connection refused" en PostgreSQL

```bash
# Verificar que PostgreSQL está corriendo
docker ps | grep postgres

# Ver logs
docker logs casa-teva-postgres
```

### Puertos ya en uso

```bash
# Ver qué proceso usa el puerto 5432
netstat -ano | findstr :5432

# Cambiar puertos en docker-compose.yml si es necesario
ports:
  - "15432:5432"  # PostgreSQL en puerto 15432
```

---

## Arquitectura Simplificada

```
┌─────────────────┐     ┌─────────────────┐
│    Scrapers     │────>│   PostgreSQL    │
│  (Playwright)   │     │  raw.raw_listings│
└─────────────────┘     │     (JSONB)     │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │       dbt       │
                        │  staging/marts  │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │     Django      │
                        │   (Web CRM)     │
                        └─────────────────┘
```

**Flujo de datos:**
1. Scrapers extraen anuncios → PostgreSQL (JSONB)
2. dbt transforma datos → staging → marts
3. Django muestra leads en interfaz web

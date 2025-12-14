# Despliegue en Azure - Casa Teva CRM

## Requisitos previos
- Cuenta Azure for Students activa
- Azure CLI instalado (o usar Azure Portal)

---

## Paso 1: Crear grupo de recursos

```bash
# Login en Azure
az login

# Crear grupo de recursos
az group create --name casa-teva-rg --location westeurope
```

---

## Paso 2: Crear Azure Database for PostgreSQL

### Opción A: Desde Azure Portal (más fácil)
1. Ve a portal.azure.com
2. Busca "Azure Database for PostgreSQL"
3. Selecciona "Flexible Server"
4. Configuración:
   - **Nombre**: casa-teva-db
   - **Región**: West Europe
   - **Workload type**: Development (más barato)
   - **Compute + storage**: Burstable B1ms (~€12/mes, gratis con créditos)
   - **Usuario admin**: casatevaadmin
   - **Password**: [tu-password-seguro]
5. En Networking: "Allow public access" y añade tu IP

### Opción B: Desde CLI
```bash
az postgres flexible-server create \
  --resource-group casa-teva-rg \
  --name casa-teva-db \
  --location westeurope \
  --admin-user casatevaadmin \
  --admin-password "TuPasswordSeguro123!" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --public-access 0.0.0.0
```

### Crear la base de datos
```bash
az postgres flexible-server db create \
  --resource-group casa-teva-rg \
  --server-name casa-teva-db \
  --database-name casatevacrm
```

---

## Paso 3: Crear Azure App Service

### Opción A: Desde Azure Portal
1. Busca "App Services"
2. Click "Create"
3. Configuración:
   - **Nombre**: casa-teva-crm (será casa-teva-crm.azurewebsites.net)
   - **Publish**: Code
   - **Runtime stack**: Python 3.11
   - **Region**: West Europe
   - **Pricing plan**: Basic B1 (~€12/mes, gratis con créditos)

### Opción B: Desde CLI
```bash
# Crear App Service Plan
az appservice plan create \
  --name casa-teva-plan \
  --resource-group casa-teva-rg \
  --sku B1 \
  --is-linux

# Crear Web App
az webapp create \
  --resource-group casa-teva-rg \
  --plan casa-teva-plan \
  --name casa-teva-crm \
  --runtime "PYTHON:3.11"
```

---

## Paso 4: Configurar variables de entorno

En Azure Portal > App Service > Configuration > Application settings:

```
DJANGO_SECRET_KEY=genera-una-clave-secreta-larga-y-aleatoria
DEBUG=False
ALLOWED_HOSTS=casa-teva-crm.azurewebsites.net
CSRF_TRUSTED_ORIGINS=https://casa-teva-crm.azurewebsites.net
DATABASE_URL=postgresql://casatevaadmin:TuPassword@casa-teva-db.postgres.database.azure.com:5432/casatevacrm?sslmode=require
SECURE_SSL_REDIRECT=True
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

También configurar:
- **Startup Command**: `cd backend && gunicorn casa_teva.wsgi:application --bind 0.0.0.0:8000`

---

## Paso 5: Desplegar el código

### Opción A: Desde GitHub (recomendado)
1. Sube tu código a GitHub
2. En Azure Portal > App Service > Deployment Center
3. Selecciona GitHub
4. Conecta tu repositorio
5. Azure desplegará automáticamente en cada push

### Opción B: Desde local con Azure CLI
```bash
# En la raíz del proyecto
az webapp up \
  --resource-group casa-teva-rg \
  --name casa-teva-crm \
  --runtime "PYTHON:3.11" \
  --sku B1
```

### Opción C: Con ZIP deploy
```bash
# Crear ZIP del proyecto
cd casa-teva-lead-system
zip -r deploy.zip backend/ -x "*.pyc" -x "__pycache__/*" -x "*.git*"

# Desplegar
az webapp deployment source config-zip \
  --resource-group casa-teva-rg \
  --name casa-teva-crm \
  --src deploy.zip
```

---

## Paso 6: Crear usuario admin y datos iniciales

Conectar al shell de la app:
```bash
az webapp ssh --resource-group casa-teva-rg --name casa-teva-crm
```

O desde Azure Portal > App Service > SSH

```bash
cd /home/site/wwwroot/backend
python manage.py migrate
python manage.py createsuperuser
python manage.py shell
```

En el shell de Python:
```python
from core.models import Tenant, TenantUser
from django.contrib.auth.models import User

# Crear tenant
tenant = Tenant.objects.create(
    nombre="Casa Teva Inmobiliaria",
    email_contacto="info@casateva.es",
    telefono="+34612345678"
)

# Asignar admin al tenant
admin = User.objects.get(username='admin')
TenantUser.objects.create(user=admin, tenant=tenant, rol='admin')

# Crear esquema marts para leads
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("CREATE SCHEMA IF NOT EXISTS marts;")
```

---

## Paso 7: Verificar despliegue

1. Visita: https://casa-teva-crm.azurewebsites.net
2. Deberías ver la página de login
3. Entra con el usuario admin

---

## Costes estimados (con créditos de estudiante)

| Recurso | Coste/mes | Con créditos |
|---------|-----------|--------------|
| App Service B1 | ~€12 | €0 |
| PostgreSQL B1ms | ~€12 | €0 |
| **Total** | ~€24 | **€0** |

Con $100 de créditos tienes para ~4 meses sin preocuparte.

---

## Troubleshooting

### Ver logs
```bash
az webapp log tail --resource-group casa-teva-rg --name casa-teva-crm
```

### Reiniciar app
```bash
az webapp restart --resource-group casa-teva-rg --name casa-teva-crm
```

### Conectar a PostgreSQL desde local
```bash
psql "host=casa-teva-db.postgres.database.azure.com port=5432 dbname=casatevacrm user=casatevaadmin sslmode=require"
```

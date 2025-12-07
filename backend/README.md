# Casa Teva - Backend Django

Sistema de captación y gestión de leads inmobiliarios.

## Stack Tecnológico

- **Framework**: Django 5.1
- **Base de Datos**: PostgreSQL
- **API**: Django REST Framework
- **Python**: 3.13+

## Estructura del Proyecto

```
backend/
├── casa_teva/              # Proyecto Django principal
│   ├── settings.py         # Configuración del proyecto
│   ├── urls.py            # URLs principales
│   └── wsgi.py            # WSGI application
├── apps/                  # Aplicaciones Django
│   ├── core/              # App core (Tenants, Usuarios)
│   │   ├── models.py      # Tenant, TenantUser
│   │   ├── admin.py       # Configuración del admin
│   │   └── urls.py        # URLs de la app
│   ├── leads/             # App leads (Leads, Notas)
│   │   ├── models.py      # Lead, Nota
│   │   ├── admin.py       # Configuración del admin
│   │   └── urls.py        # URLs de la app
│   └── analytics/         # App analytics
│       └── urls.py        # URLs de la app
├── manage.py              # Django CLI
└── requirements.txt       # Dependencias Python

```

## Configuración Inicial

### 1. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Crea un archivo `.env` basado en `.env.example`:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales de PostgreSQL.

### 3. Ejecutar migraciones

```bash
python manage.py migrate
```

### 4. Crear superusuario

```bash
python manage.py createsuperuser
```

### 5. Ejecutar servidor de desarrollo

```bash
python manage.py runserver
```

El servidor estará disponible en `http://localhost:8000`

El panel de administración en `http://localhost:8000/admin`

## Modelos de Datos

### App: core

- **Tenant**: Inquilinos/clientes del sistema
- **TenantUser**: Relación usuarios-tenants con roles

### App: leads

- **Lead**: Leads inmobiliarios (vista desde `marts.dim_leads` - gestionada por dbt)
- **Nota**: Notas asociadas a leads

## Comandos Útiles

```bash
# Verificar configuración
python manage.py check

# Crear nuevas migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Shell interactivo de Django
python manage.py shell

# Recopilar archivos estáticos
python manage.py collectstatic
```

## Notas Importantes

- El modelo `Lead` tiene `managed = False` porque apunta a una tabla gestionada por dbt en el schema `marts`
- Las apps están organizadas en el directorio `apps/` para mejor estructura
- El proyecto usa `psycopg3` para conectar con PostgreSQL
- La configuración está preparada para leer `DATABASE_URL` de variables de entorno

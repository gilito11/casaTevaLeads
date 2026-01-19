# Casa Teva - Protocolo de Trabajo Concurrente Multi-Terminal

> Documento para coordinar trabajo entre múltiples sesiones de Claude Code

## Estado Actual del Proyecto (19 Enero 2026)

### Commits recientes
```
7fbbc36 feat: Add lead scoring, price history, duplicates detection, Telegram alerts
a3b2e52 docs: Add session context for next session
353d325 chore: Update admin for comercial fields + onboarding checklist
8eec326 feat: Add comercial contact fields to TenantUser
99bba94 feat: Add retry button for failed contacts in queue
```

### Migración pendiente (EJECUTAR EN AZURE)
```sql
-- Conectar a Azure PostgreSQL y ejecutar:
-- Host: inmoleads-db.postgres.database.azure.com
-- User: inmoleadsadmin
-- DB: inmoleadsdb

\i migrations/001_create_price_history.sql

-- O ejecutar el contenido directamente
```

### dbt pendiente de refresh
```bash
cd dbt_project
dbt run --select dim_leads dim_lead_duplicates --full-refresh
```

## Áreas de Trabajo (para asignar a terminales)

### TERMINAL A: Backend/Django
- Archivo clave: `backend/`
- Temas: vistas, templates, admin, API
- NO TOCAR: `dagster/`, `scrapers/`, `dbt_project/`

### TERMINAL B: Scrapers/Dagster
- Archivos clave: `scrapers/`, `dagster/`
- Temas: scraping, orquestación, alertas
- NO TOCAR: `backend/`

### TERMINAL C: dbt/SQL
- Archivos clave: `dbt_project/`, `migrations/`
- Temas: transformaciones, modelos, migraciones
- NO TOCAR: código Python

## Protocolo de Coordinación

### Antes de empezar
```bash
git pull origin master
```

### Durante el trabajo
- NO modificar archivos fuera de tu área asignada
- Si necesitas modificar un archivo compartido (CLAUDE.md, requirements.txt):
  1. Comunicar a las otras terminales
  2. Hacer pull antes de editar
  3. Commit inmediato después de editar

### Al terminar
```bash
git add -A
git commit -m "feat/fix/chore: descripcion corta"
git push origin master
```

## Issues Activas

| # | Título | Prioridad | Asignado |
|---|--------|-----------|----------|
| 28 | Mejoras producción (rate limit, Key Vault) | Media | Libre |
| 31 | PDF valoración automático | Baja | Libre |

## Features Implementadas (NO DUPLICAR)

- ✅ Lead scoring (0-90 pts) → `dim_leads.sql`
- ✅ Histórico de precios → `listing_price_history` + scrapers
- ✅ Duplicados cross-portal → `dim_lead_duplicates.sql`
- ✅ Alertas Telegram → `telegram_alerts.py`
- ✅ Contacto automático 4 portales → `contact_assets.py`
- ✅ Credenciales por tenant → `PortalCredential`
- ✅ Email por comercial → `TenantUser.comercial_*`

## Env Vars Pendientes (Azure Container Apps)

```
TELEGRAM_BOT_TOKEN=<crear con @BotFather>
TELEGRAM_CHAT_ID=<ID del grupo>
```

## Prompt de Inicio para Nueva Terminal

```
Soy una terminal de trabajo para Casa Teva Lead System.

MI ÁREA ASIGNADA: [A: Backend | B: Scrapers | C: dbt]

ANTES DE EMPEZAR:
1. git pull origin master
2. Revisar .claude/CONCURRENT_WORK.md

REGLAS:
- Solo modifico archivos de mi área
- Commit frecuente y pequeño
- Push después de cada feature/fix
- Si toco archivo compartido, aviso

CONTEXTO:
- Sistema CRM de captación de leads inmobiliarios
- 4 portales: habitaclia, fotocasa, milanuncios, idealista
- Stack: Django + Dagster + dbt + PostgreSQL

¿Qué tarea debo hacer?
```

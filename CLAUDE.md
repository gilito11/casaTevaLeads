# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 30 December 2025

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de 5 portales. **100% gratuito** - sin APIs de pago.

## Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Azure PostgreSQL en prod)
- **Scrapers**:
  - **HTTP puro**: pisos.com (requests+BeautifulSoup, 10x mas rapido)
  - **Camoufox**: milanuncios, idealista (anti-detect Firefox, bypasses GeeTest/DataDome)
  - **Botasaurus**: habitaclia, fotocasa (Chrome headless)
- **Orquestacion**: Dagster
- **ETL**: dbt (raw -> staging -> marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

## Flujo de Datos
```
Scrapers -> raw.raw_listings (JSONB) -> dbt -> marts.dim_leads -> Django Lead model
```

## Entornos

| Servicio | Local | Azure |
|----------|-------|-------|
| Web | http://localhost:8000 | https://inmoleads-crm.azurewebsites.net |
| Dagster | http://localhost:3000 | https://dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | localhost:5432 | inmoleads-db.postgres.database.azure.com |

## Comandos

```bash
# === LOCAL ===
docker-compose up -d
python run_pisos_scraper.py --zones salou --postgres          # HTTP (rapido)
python run_camoufox_milanuncios.py salou cambrils             # Camoufox
python run_habitaclia_scraper.py --zones salou --postgres     # Botasaurus
docker exec casa-teva-postgres psql -U casa_teva -d casa_teva_db -c "SELECT portal, COUNT(*) FROM marts.dim_leads GROUP BY portal;"

# === AZURE ===
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100
az containerapp revision list -n dagster-scrapers -g inmoleads-crm -o table
```

## Scrapers

| Portal | Tecnologia | Anti-bot | Velocidad |
|--------|------------|----------|-----------|
| pisos.com | HTTP puro | Ninguno | ~15s/zona |
| habitaclia | Botasaurus (Chrome) | Minimo | ~2min/zona |
| fotocasa | Botasaurus (Chrome) | Minimo | ~2min/zona |
| milanuncios | Camoufox (Firefox) | GeeTest captcha | ~3min/zona |
| idealista | Camoufox (Firefox) | DataDome | ~3min/zona |

### Portal names para BD
Usar estos nombres exactos en `raw.raw_listings.portal`:
- `pisos` (no "pisos.com")
- `habitaclia`
- `fotocasa`
- `milanuncios`
- `idealista`

## Azure Container Apps

El contenedor Dagster necesita:
- **EmptyDir volume en /dev/shm** - Para Chrome shared memory
- **Xvfb** - Para Camoufox headless
- **2GB RAM minimo** - Chrome consume mucha memoria

Config en `azure-containerapp-update.yaml`:
```yaml
volumeMounts:
  - volumeName: shm
    mountPath: /dev/shm
volumes:
  - name: shm
    storageType: EmptyDir
```

## Credenciales

**Local**: postgres / casa_teva / casateva2024 / casa_teva_db
**Azure**: inmoleads-db.postgres.database.azure.com / inmoleadsadmin / ataulfo1! / inmoleadsdb (sslmode=require)

## Troubleshooting

### "No hay zonas activas"
La tabla `core_zonageografica` debe tener zonas con `activo=true`. Ejecutar migraciones Django en Azure si no existen.

### Chrome crash en Azure
Verificar EmptyDir volume montado en /dev/shm. Flags necesarios: `--no-sandbox`, `--disable-dev-shm-usage`.

### Constraint "valid_portal"
Portales validos: `pisos`, `habitaclia`, `fotocasa`, `milanuncios`, `idealista`, `wallapop`

## CI/CD

Push a master -> GitHub Actions -> ACR (inmoleadsacr.azurecr.io) -> Azure Container Apps

## Claude Code Preferences

- Ejecutar comandos largos en background
- Tomar decisiones sin preguntar cuando sea posible
- Usar agents paralelos para explorar codebase
- Ser conciso

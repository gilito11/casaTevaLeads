# Casa Teva Lead System - CRM Inmobiliario

> **Last Updated**: 31 December 2025

## Resumen
Sistema de captacion de leads inmobiliarios mediante scraping de 5 portales. **100% gratuito** - sin APIs de pago.

## Stack
- **Backend**: Django 5.x + DRF
- **BD**: PostgreSQL 16 (Azure PostgreSQL en prod)
- **Scrapers**: HTTP (pisos, milanuncios), Botasaurus (habitaclia, fotocasa), Camoufox (idealista)
- **Orquestacion**: Dagster
- **ETL**: dbt (raw -> staging -> marts)
- **Frontend**: Django Templates + HTMX + TailwindCSS

## Scrapers - Estado actual

| Portal | Tecnologia | Azure | Local | Notas |
|--------|------------|-------|-------|-------|
| pisos.com | HTTP (requests) | ✅ | ✅ | Filtra agencias automáticamente |
| habitaclia | Botasaurus | ✅ | ✅ | Chrome headless |
| fotocasa | Botasaurus | ✅ | ✅ | Chrome headless |
| milanuncios | HTTP (curl_cffi) | ❌ 403 | ✅ | **Solo funciona desde IP residencial** |
| idealista | Camoufox | ❌ | ❌ | DataDome muy agresivo |

### Limitación Milanuncios
Milanuncios bloquea IPs de datacenter (Azure):
- curl_cffi → 403 Forbidden
- Camoufox → GeeTest captcha

**Solución**: Ejecutar localmente desde IP residencial:
```bash
python run_http_milanuncios_scraper.py --zones salou reus lleida_ciudad --postgres
```

## Comandos

```bash
# === LOCAL ===
python run_pisos_scraper.py --zones salou --postgres
python run_http_milanuncios_scraper.py --zones salou reus --postgres  # Solo local!
python run_habitaclia_scraper.py --zones salou --postgres

# === AZURE LOGS ===
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100

# === WSL (desde iPhone via Termius) ===
# Aliases disponibles: dagster-logs, dagster-status, gh-runs, leads-count, cc
```

## Entornos

| Servicio | Local | Azure |
|----------|-------|-------|
| Web | localhost:8000 | inmoleads-crm.azurewebsites.net |
| Dagster | localhost:3000 | dagster-scrapers.happysky-957a1351.spaincentral.azurecontainerapps.io |
| PostgreSQL | localhost:5432 | inmoleads-db.postgres.database.azure.com |

## Credenciales

- **Local**: casa_teva / casateva2024 / casa_teva_db
- **Azure**: inmoleadsadmin / ataulfo1! / inmoleadsdb (sslmode=require)

## Portal names para BD
`pisos`, `habitaclia`, `fotocasa`, `milanuncios`, `idealista`

## CI/CD
Push a master -> GitHub Actions -> ACR -> Azure Container Apps

## Claude Code Preferences
- Ejecutar comandos largos en background
- Tomar decisiones sin preguntar
- Ser conciso

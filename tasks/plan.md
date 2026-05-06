# Roadmap post-migración Scrapling — 6 May 2026

> Status: Scrapling 0.4.7 en producción, 5 commits subidos hoy. Big scrape en curso.
> El detalle de cada commit/test está en MEMORY.md y en los commits de git.

## Estado actual

### Lo que funciona ✅
- **Scrapling base + 4 portales** (`scrapers/scrapling_*.py`)
- **CRM "Es agencia" botón** — blacklist + delete + remove from dim_leads
- **dbt pipeline** raw → staging → marts compatible con scraper_type='scrapling'
- **Multi-tenant** (Casa Teva tenant 1, Find&Look tenant 2)
- **Workflows GH Actions** actualizados (scrape-neon.yml, scrape-madrid.yml)
- **VPS scheduled_scrape.py** actualizado para los 4 portales
- **Auto-load .env** en `scrapling_base.py` (backend/.env precedence sobre root .env)

### Lo que NO funciona ❌
- **VPS Contabo no puede scrapear idealista, fotocasa, habitaclia** — 403 por geo-block (IP alemana). Solo `milanuncios` funciona desde VPS.
- **Detección Particular/Profesional en idealista** sigue ~99% Profesional en zonas turísticas (Salou). Esto es realidad del mercado, no bug — pero el ratio es bajísimo.
- **Phone extraction** sin click "Ver teléfono" no captura números (Idealista oculta).
- **`metros` y `ubicacion`** a veces vacíos en idealista cards.

### Gaps conocidos en datos extraídos
| Portal | Campo | Estado | Nota |
|--------|-------|--------|------|
| idealista | telefono | Vacío | Click "Ver teléfono" no implementado en Scrapling (necesita `page_action`) |
| idealista | metros | A veces vacío | `.item-detail` regex `m²` falla cuando texto vacío |
| idealista | ubicacion | A veces vacío | `.item-location` no en todas las cards |
| fotocasa | (similar) | (similar) | Detail page extrae descripción/precio/fotos OK |
| habitaclia | telefono | Mejor (en descripción) | regex sobre desc |
| milanuncios | seller_type | OK (JSON) | Confiable |

## Prioridades inmediatas (próximas 1-2 semanas)

### P0 — Activar producción
1. **Trigger primer GH Actions con Scrapling** desde local: `gh workflow run scrape-neon.yml -f portals=idealista,fotocasa,habitaclia,milanuncios -f zones=salou,cambrils,reus,tarragona`
   - Verificar que GH Actions runner (US/Europe) NO está geo-blocked. Si lo está, idealista/fotocasa quedan locked-in al cron L-X-V con proxy rentado.
2. **Verificar VPS scheduled_scrape.py corre solo milanuncios** (los otros 3 fallarán por geo-block desde VPS Contabo).
   - Action: editar `scripts/scheduled_scrape.py` para skip idealista/fotocasa/habitaclia en VPS, dejar solo milanuncios. O documentar que el cron tolera fallos.
3. **Backup workflow** Camoufox + IPRoyal para emergencias. Mantener `run_camoufox_*.py` como fallback hasta 1 mes estable.

### P1 — Mejoras de calidad de datos
4. **Phone reveal (idealista)**: implementar `page_action` que clique el botón "Ver teléfono" y lea `tel:` del DOM. Eleva el valor de cada lead idealista (~30 leads/scrape × 1 phone = 30 contactables/run).
5. **Ratio Particular/Profesional**: actualmente 1-3% en idealista. Probar URL filters por orden de fecha + filtros de precio para encontrar particulares más recientes (suelen ser más particulares al principio de listar).
6. **`mark_as_agency` button audit**: añadir vista admin que muestre todos los blacklist entries, motivo, quién, cuándo. Ya está en DB pero sin UI.

### P2 — Mantenimiento
7. **Limpiar Camoufox**: tras 2 semanas estables, eliminar `scrapers/camoufox_*.py`, `run_camoufox_*.py`, `playwright-stealth`, `camoufox` de requirements. Issue separado.
8. **Eliminar 2Captcha** si fotocasa GeeTest no aparece tras 1 semana de scrapes.
9. **Eliminar IPRoyal credentials** de GH Secrets cuando se valide que no hace falta.

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Idealista revoca el bypass de Patchright | Media | Alto (sin idealista) | Mantener Camoufox+IPRoyal como fallback. Monitorizar daily success rate. |
| GH Actions IPs también geo-bloqueados | Media | Alto | Si pasa, configurar proxy rentado solo para esos workflows |
| Mi sandbox local (la única IP española) no puede ser dependencia de producción | Alta | Media | Usar GH Actions como CI principal, mi sandbox solo para dev |
| Patchright Chromium consume mucha RAM en VPS (8GB) | Baja | Media | Solo milanuncios en VPS — escalado mínimo |
| dbt incremental no recoge updates si raw_data cambia | Media | Bajo | `--full-refresh` mensual (ya soportado en workflow input) |

## Rollback plan

Si Scrapling falla en producción:
```bash
# 1. Revertir migración
git revert fa2591d  # The migration commit
git push

# 2. Restore IPRoyal proxy (necesita recharge $7)
# - Actualizar GH Secret DATADOME_PROXY si fue removido

# 3. VPS rollback
ssh vps "cd C:\casa-teva; git pull; nssm restart CasaTevaWeb"

# 4. Forzar quick-scan con Camoufox
gh workflow run quick-scan-v2.yml -f portals=idealista
```

Camoufox files preservados: `scrapers/camoufox_*.py` (4 archivos) — no eliminar hasta confirmar estabilidad Scrapling.

## Métricas para evaluar éxito (próximas 2 semanas)

- **Success rate por portal** (raw rows insertadas/run): target >80% por portal
- **% es_particular en idealista**: target >5% (actualmente <1%)
- **Time-to-first-lead** desde scrape inicio: target <10min/zona
- **Costos**: target $0/mes (sin IPRoyal, sin 2Captcha excepto fallback)
- **Telegram alerts**: 0 errors críticos en 7 días consecutivos

## Comandos de operación

```bash
# Big scrape local (España IP — funciona todos los portales)
python -u -m scrapers.scrapling_idealista --zones salou cambrils reus tarragona --max-pages 2 --postgres
python -u -m scrapers.scrapling_fotocasa --zones salou cambrils reus tarragona --max-pages 2 --postgres
python -u -m scrapers.scrapling_habitaclia --zones salou cambrils reus tarragona --max-pages 2 --postgres
python -u -m scrapers.scrapling_milanuncios --zones tarragona --max-pages 2 --postgres

# Audit calidad
python scripts/audit_scrapling_quality.py --since "2 hours"

# dbt local refresh
DBT_HOST=ep-...neon.tech DBT_USER=neondb_owner DBT_PASSWORD=... DBT_DBNAME=neondb \
  dbt run --select staging marts --project-dir dbt_project --profiles-dir /tmp/dbt_profiles

# Trigger GH Actions
gh workflow run scrape-neon.yml -f portals=idealista,fotocasa,habitaclia,milanuncios -f zones=salou,cambrils

# Verify production /leads/
curl -s https://fincaradar.com/leads/ -I | head
```

## Notas históricas

- **Migración Scrapling**: 4-6 May 2026 — 5 commits (`fa2591d`, `d707097`, `e26b20c`, `4f1f57d`, `f941dc9`, `44674c5`)
- **IPRoyal exhausted**: 1 Apr 2026 — driver de la migración
- **VPS deploy completed**: 5 May 2026 23:08 (Patchright Chromium 1208 instalado)

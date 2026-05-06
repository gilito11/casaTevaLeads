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
| idealista | telefono | 0% | Click "Ver teléfono" no implementado en Scrapling (necesita `page_action`) |
| idealista | metros | 100% (post-fix `c0ef59b`) | Concat de TODAS las `.item-detail` spans |
| idealista | habitaciones | 93% | Misma fix |
| idealista | ubicacion | A veces vacío | `.item-location` no en todas las cards |
| fotocasa | volumen | Bajo | parse_search_page solo URL+id; detail bloqueado a veces → row vacío. Data-quality gate `dac6cef` ahora skipea esos, pero perdemos volumen. **TODO**: rewrite parse_search_page para extraer titulo/precio del card directamente |
| fotocasa | URL filter | Roto | `/particulares/` URL devuelve SPA shell sin listings. Ahora usamos URL genérica `c0ef59b` (deteccion particulares se hace por divider HTML) |
| habitaclia | telefono | 0% | Buscar en descripción es insuficiente; añadir regex robusto sobre detail HTML |
| milanuncios | madrid URLs | 403 | URL pattern `/venta-de-pisos-en-X-madrid-madrid/` no existe — buscar pattern correcto |
| milanuncios | seller_type | OK (JSON) | Confiable, todos los signals funcionando |

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

## Big scrape 6 May 2026 — Resultados

### Volumen scrape (4 portales × Tenant 1+2 × 2 pages)

| Portal | T1 raw saved | T2 raw saved | Particulares | Profesionales | Tiempo |
|--------|-------------:|-------------:|-------------:|--------------:|-------:|
| idealista | 90 | 60 | 0 | 150 | ~25min |
| habitaclia | 45 | 12 | **57** | 0 | ~13min |
| fotocasa | 1 (post-cleanup) | 0 | 1 | 0 | ~5min |
| milanuncios | 0 | 0 | 0 | 0 (Tarragona/Madrid agencias) | ~1min |
| **Total** | **136** | **72** | **58** | **150** | |

### Tras dbt run staging+marts

- dim_leads antes: 386
- dim_leads después: **393** (+7 visibles tras dedup; 40 rows con `fecha_primera_captura` reciente)
- 5 leads ejemplo nuevos: precios €170K-€2M, descripciones 700-1845 chars, 10 fotos c/u

### Auditoría calidad (post-fix)
- ✅ habitaclia: 100% titulo/precio/desc/fotos/m2, hab 91%
- ✅ idealista: 100% titulo/precio, desc 80-91%, **m2 100% post-fix `c0ef59b`**, hab 93% post-fix
- ❌ idealista telefono: 0% (pendiente page_action)
- ⚠️ fotocasa: 1 row con datos completos; el resto data-quality-gated (URL bug fixed pero parse_search_page necesita rewrite)
- ✅ 0 duplicados en dim_leads

## Notas históricas

- **Migración Scrapling**: 4-6 May 2026 — 9 commits (`fa2591d`, `d707097`, `e26b20c`, `4f1f57d`, `f941dc9`, `44674c5`, `bdad082`, `dac6cef`, `c0ef59b`)
- **IPRoyal exhausted**: 1 Apr 2026 — driver de la migración
- **VPS deploy completed**: 5 May 2026 23:08 (Patchright Chromium 1208 instalado)
- **Geo-block VPS confirmado**: 6 May 2026 — Contabo IP alemana → 403 en idealista/fotocasa/habitaclia. Solo milanuncios funciona desde VPS. Local sandbox (España) y GH Actions (a verificar) son las únicas opciones para los 3 portales protegidos.
- **Big scrape**: 6 May 2026 ~15:00-15:25 — 4 portales × 8 zonas (T1 4 + T2 2) × 2 pages = 208 raw rows, 58 particulares, 25 min

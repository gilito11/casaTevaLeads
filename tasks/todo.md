# Zonas descartadas: visibilidad + activacion manual del pipeline

> Objetivo: el equipo ve en el dashboard las zonas que el scraping captura pero
> la keep-list descarta, y puede activarlas con un boton. Activar una zona =
> entra en dim_leads (dbt) + entra en el scraping diario de todos los portales.

## Diseño
- Fuente de verdad de zonas activas: tabla existente `zonas_geograficas`
  (modelo core.ZonaGeografica, tenant 1 hoy vacio). Se siembra con la keep-list
  actual de dim_leads.sql (47 municipios canonicos + mollerussa_rural).
- `dim_leads.sql` deja de tener el dict Jinja hardcodeado: filtro y nombre
  canonico salen de un JOIN contra `public.zonas_geograficas` (activa=true).
  Se mantiene un CASE pequeño de alias ortograficos (vilaseca->vila seca...).
- Cron de scrape-neon.yml: la lista de zonas se lee de la BD por portal
  (`scripts/get_active_zones.py --portal X`, respeta flags scrapear_<portal>),
  con fallback a la lista actual si la BD falla. Costa: activa=true (ingesta)
  pero scrapear_*=false salvo milanuncios (cubre provincia), preservando el
  comportamiento actual del cron.
- Dashboard: seccion "Zonas descartadas (30 dias)" con conteo, precios,
  portales y boton "Activar zona" -> crea fila ZonaGeografica (todos los
  portales on) + bump de scraping_timestamp en raw para ingesta en el
  proximo run de dbt.

## Tareas
- [x] Impact analysis (dim_leads deps, workflow, zones dicts, ZonaGeografica usos)
- [x] 1. Data migration: seed tenant 1 en zonas_geograficas (54 filas)
- [x] 2. Aplicar migracion (Neon): OK
- [x] 3. scripts/get_active_zones.py: reproduce la lista del cron exacta
- [x] 4. scrape-neon.yml: zonas desde BD por portal (fallback hardcoded)
- [x] 5. scheduled_scrape.py (VPS): usa env SCRAPE_ZONES, se deja igual
      (canal casi muerto por geo-block; milanuncios cubre provincia)
- [x] 6. dim_leads.sql: JOIN a zonas_geograficas + alias CASE; equivalencia
      del filtro viejo vs nuevo = 0 diferencias sobre staging; dbt run marts OK
- [x] 7. Dashboard: seccion "Zonas descartadas (30 dias)" + POST /zonas/activar/
- [x] 8. Verificacion: manage.py check OK; GET / renderiza seccion (15 zonas,
      Alcanar/La Rapita arriba); POST activar crea fila con 5 portales on
      (probado con zona dummy y borrada); dim_leads INSERT 0 0 (sin cambios)
- [x] 9. Commit local (sin push hasta que Eric lo pida)

## Resultado
Pipeline de activacion completo: dashboard muestra zonas descartadas con
particulares/precios/portales; "Activar zona" crea la fila en
zonas_geograficas; el cron diario lee zonas de esa tabla por portal y dbt
ingiere la zona en el siguiente ciclo (max 24h, solo anuncios vivos).
Pendiente de deploy: push a GitHub (workflow) + pull en VPS (dashboard).

## Riesgos vigilados
- dim_leads es el hub: no se toca ninguna columna de salida, solo el origen
  del filtro/canonico -> serializers, analytics y raw SQL intactos.
- Si tenant 1 quedara sin filas activas, el filtro descartaria todo: la
  migracion siembra ANTES de que el dbt nuevo corra (mismo repo, dbt corre en
  workflow tras checkout; migracion se aplica en local contra Neon ya).
- JOIN no debe duplicar filas: agregacion por (tenant, norm) en CTE.

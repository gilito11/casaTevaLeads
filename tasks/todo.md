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
## 4. Templates ✅
- [x] detail.html: botón "Crear contacto" + sección dirección exacta editable.
- [x] contact_detail.html: tarjeta "Propiedades asignadas" (tipo/precio/fecha + quitar).
- [x] map.html: markercluster, color por estado, icono exacto, toggle "Ver vendidos".

## 5. Verificación ✅
- [x] check OK; /analytics/mapa 200, /leads/<id>/ 200, contacto 200; save_address 302
      (guarda + geocode); add_propiedad 302 (vendida/precio/fecha guardados).
- [x] Commit + push (8a31c74) + deploy VPS OK (tablas ya en Neon; collectstatic + restart).
      Producción /analytics/mapa y / responden 302 (login). Live en fincaradar.com.

# Plan: Auditoría silenciosa de cambios de estado (Jul 2026)

- [x] Modelo `AuditLog` (`leads_audit_log`), migración 0011 aplicada en Neon.
- [x] Signals en LeadEstado (creado/cambiado/borrado) + middleware thread-local para usuario.
- [x] log explícito en delete_lead, bulk_delete y mark_as_agency (borran vía SQL crudo).
- [x] Admin solo superuser, solo lectura. Sin UI para comerciales.
- [x] Verificado end-to-end en shell: 4/4 registros correctos, save sin cambio no registra.
- [ ] Deploy VPS pendiente (tabla ya existe en Neon; falta git pull + restart).

# Plan: Fotocasa via Bright Data + cron con sabado (6 Jul 2026)

- [x] Diagnostico: cron solo wallapop+habitaclia (fotocasa/milanuncios manual-only);
      sabado sin scrape; VPS geo-bloqueado (solo milanuncios); habitaclia intermitente.
- [x] `scrapling_fotocasa_bd.py`: subclass BD Web Unlocker (por request), reusa
      parser JSON embebido clientTypeId — sin navegador.
- [x] Workflow: cron diario `0 12 * * *` + fotocasa en SCHEDULE_PORTALS via BD.
- [x] Commit bafd5b3 + push.
- [x] Descubrimiento (workflow bd-debug, 8 iteraciones): /pl da 502 via BD;
      API interna web.gw.fotocasa.es/v2/propertysearch/search responde JSON sin key,
      paginacion real + sortOrderDesc; advertiser.typeId 1=particular.
- [x] Scraper reescrito contra el API (commit 6fe952d). Test 3 zonas:
      180 anuncios -> 15 particulares guardados, 0 errores, 77s (~$0.01/run).
- [x] Verificado en dim_leads: 8 Lleida + 4 Alpicat + 3 Mollerussa con precio/vendedor.
- [x] bd-debug.yml eliminado. Deploy VPS del codigo de auditoria hecho.
- Resultado: cron diario (sabado incl.) wallapop+habitaclia+fotocasa(BD).

# Plan: Milanuncios via Bright Data (6 Jul 2026, tarde)

## Diagnostico
- [x] VPS scrapeaba zonas equivocadas (default salou/cambrils/tarragona/reus — nunca Lleida).
- [x] Slug viejo `pisos-en-X` mezcla ALQUILER; el bueno es `venta-de-pisos-en-X`.
- [x] Faltaba categoria CASAS (el stock real de los pueblos).
- [x] Probes BD (3 iteraciones): GeeTest no aparece; INITIAL_PROPS extraible;
      `?vendedor=part` filtra particulares server-side; `lleida-lleida` = provincia.
      Inventario actual: 32 pisos + 40 casas part. en Lleida prov, 9+7 Tarragona.

## Implementacion
- [x] `scrapling_milanuncios_bd.py`: BD + vendedor=part + zona por city del anuncio
      + detalle solo anuncios nuevos + filtro demanda (Compro/Busco). Commit 23b7571.
- [x] Workflow: milanuncios al cron diario via BD (SCHEDULE_PORTALS).
- [x] Test 1 (run 28803813019): 185 raw guardados pero timeout 20min — slugs de
      pueblo caian al fallback provincial (duplicaban todo) + URLs con `|` rechazadas.
- [x] Fix (1ff7ec9): 2 provincias x 2 categorias, percent-encode, dedupe intra-run.
- [x] Test 2 (run 28805933529): DONE en 234s, found=201 saved=185 details=7.
- [x] Verificado dim_leads: milanuncios 12 -> 177 leads (169 nuevos hoy),
      zonas por municipio real (Lleida 13, Tarragona 9, Reus 7, Salou 6...).
- [x] bd-debug.yml borrado. Memoria actualizada.
- Nota: 7 errors en detalles (transitorios); esos anuncios quedan sin tel/fotos.
- Nota: VPS scheduled_scrape sigue con milanuncios viejo (zonas Tarragona) — redundante
      pero inofensivo (upsert); candidato a limpiar otro dia.

# Fix: fotos rotas habitaclia + milanuncios (6 Jul 2026, noche)

- [x] Diagnostico: fotos SI se guardan (88-100%) pero habitaclia (sufijo XL_XXL
      concatenado -> 404) y milanuncios (sin ?rule= -> 404; images-re -> 403) no cargan.
- [x] Scrapers corregidos (URL base habitaclia; rule+dominio milanuncios).
- [x] Datos reparados: 405 raw + 342 dim_leads. Muestra 8/8 URLs -> HTTP 200.
- Wallapop 40% sin fotos: decision previa (no se guardan) — no tocado.

## Extra (petición usuario)
- [x] Wallapop: dejar de almacenar fotos (`_extract_photos` -> []). No gastaba anti-bot
      igualmente; el coste es la visita al detalle (por el teléfono).

## Notas
- VPS deploy NO corre migrate por defecto → añadirlo esta vez.
- Lead es vista dbt (solo lectura): todo lo editable va en tablas writable nuevas.

# Fix: pipeline de captación a cero por token Bright Data caducado (15 Sep 2026)

## Diagnóstico
- [x] GH Actions en "success" a diario, pero fotocasa-bd found=0 errors=32, milanuncios-bd 0/4,
      wallapop-bd 51 saved con 13 errores: `BD HTTP 401 Token expired` en cada zona.
- [x] Bisect de runs: último run bueno 26 Ago; primer 401 el 27 Ago 22:35 UTC. Secret
      BRIGHTDATA_API_KEY creado el 26 May → caducidad de 3 meses.
- [x] Neon: fotocasa last_seen 26 Ago, milanuncios 9 Sep (VPS viejo), 0 nuevos fotocasa en 7d.
- [x] Sin copia válida de la clave ni en .env local ni en el VPS.
- [x] Alerta diaria "0 results from: fotocasa, idealista, milanuncios" ignorada porque idealista
      (manual-only) salía siempre → ruido crónico.

## Implementación
- [x] `scrapers/brightdata.py`: get_api_key + build_session + verify_token (GET /status, gratis; 401 → BrightDataAuthError).
- [x] Los 4 `scrapling_*_bd.py` + `obra_nueva_watch.py` verifican al construir → abortan al instante.
- [x] `scripts/check_brightdata.py`: preflight con alerta Telegram; scrape-neon.yml y obra-nueva-watch.yml
      lo ejecutan y saltan los scrapers BD si `steps.bd.outcome != success`.
- [x] `validate_scrape_quality.py`: portales esperados desde env PORTALS (los que corren de verdad) + wallapop.
- [x] Probado local: sin clave → exit 1; clave inválida → 401 → exit 1; constructor scraper → BrightDataAuthError.
- [x] Clave nueva (Unlimited) creada por Eric, validada (status 200 + unlock real) y `gh secret set`.
- [x] Run 34954852660: fotocasa found=867 saved=88, milanuncios 186/172, wallapop 437/69, errors 0/7/0. dbt OK.
- [x] Neon: 13 leads nuevos hoy en dim_leads tenant 1 (7 fotocasa, 1 milanuncios, 5 wallapop).
- [x] Push a master (autorizado por Eric: "no me pidas permiso para subir nada").
- [x] Landing: endpoint demo-request commiteado y desplegado en VPS (400 en validación = ruta viva).
- [x] `publish_scrape_status.py` + rama `ops-status`; validado con run 34957021078 (ok=true).
- [x] Rutina cloud "FincaRadar scrape watch" (trig_01XAi9VYuiHYneEuVCKwp7VW, 14:00 UTC): primer run manual → "SCRAPE OK" en 5s, 2 turnos.

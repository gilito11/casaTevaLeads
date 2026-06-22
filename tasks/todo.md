# Macro Ataque: Wallapop + Refuerzo Idealista (Obra Nueva Lleida)

> Iniciado 22 Jun 2026. Contexto: Casa Teva paga 500€/lead cerrado.
> Objetivo: maximizar volumen de PARTICULARES + ser primeros en obra nueva.

## Contexto del cliente (Casa Teva)
- **Wallapop**: buen filón, buscan a mano y les funciona. Hay inmobiliarias camufladas
  como particulares (ej. **yaencontre** = portal inmobiliario disfrazado). CRÍTICO detectarlas.
- **Idealista**: ellos buscan por el MAPA de la provincia. Esencial para obra nueva en
  **Lleida** (Copa d'Or, Bordeta, Cappont) — quieren ser los primeros en llamar cuando
  salgan los pisos de nueva obra (probablemente en Idealista o Fotocasa).

## Decisiones de arquitectura
- Wallapop = 5º portal. Sigue el patrón Scrapling existente (base class + per-portal + zones).
- Wallapop es geo-based (lat/long + radio). Zones por COORDENADAS, no por URL de zona.
- Extracción: StealthySession (browser) carga el SPA `/inmobiliaria/<ciudad>`, scroll lazy-load,
  e INTERCEPTA el XHR a `api.wallapop.com/.../search` (evita reversear X-Signature).
- Detección agencia: nombre vendedor (yaencontre, *.com, s.l., inmo*, fincas, etc.)
  + flag `user.professional`/`is_professional` del JSON + heurísticas descripción.

## Plan (capas — orden de dependencia)

### Fase 0 — Mapeo (en curso, 3 agentes)
- [ ] Scraper architecture (base class, milanuncios, fotocasa, zones)
- [ ] dbt + portal CHECK constraint
- [ ] Django/UI integration points (todos los sitios)

### Fase 1 — Constraint BD (desbloquea todo)
- [ ] Añadir 'wallapop' al CHECK constraint de portal (migración + raw.raw_listings)

### Fase 2 — Scraper
- [ ] `scrapers/zones/wallapop.py` (ZONAS por lat/long + radio, incl. Lleida/Tarragona)
- [ ] `scrapers/scrapling_wallapop.py` (search SPA + XHR intercept + parse + agency detect)
- [ ] CLI `python -m scrapers.scrapling_wallapop --zones ... --postgres`
- [ ] Runner si aplica + integración scheduled_scrape.py + scrape-neon.yml

### Fase 3 — dbt
- [ ] `dbt_project/models/staging/stg_wallapop.sql` (filtros agencia incl. yaencontre)
- [ ] Integrar en `dim_leads.sql` (UNION)
- [ ] sources.yml / schema.yml si aplica

### Fase 4 — Django + UI (TODOS los sitios)
- [ ] models.py portal choices
- [ ] views/api: filtros portal, colores, badges
- [ ] templates: <select> filtros, selector de categorías, badges, leyendas charts, dashboard
- [ ] JS: portal color map, arrays
- [ ] check_portal_health, post_scrape_auto_queue, listing_checker

### Fase 5 — Idealista obra nueva Lleida (refuerzo)
- [ ] Añadir zonas Lleida (Copa d'Or, Bordeta, Cappont) a zones/idealista.py
- [ ] Filtro/flag obra nueva (`obraNueva` / "promoción" / "nueva construcción")
- [ ] Detección temprana: alerta Telegram inmediata para nuevos pisos obra nueva en esas zonas
- [ ] Evaluar búsqueda por mapa provincial (bounding box) en idealista

### Fase 6 — Verificación
- [ ] Scrape real wallapop 1 zona → leads particulares en dim_leads
- [ ] yaencontre correctamente excluido
- [ ] UI muestra wallapop en filtros/badges/charts

## Resultados (22 Jun 2026)

### Wallapop — COMPLETO y VALIDADO en real ✅
- Descubierto: Wallapop es **Next.js SSR**; anuncios en `__NEXT_DATA__`
  (`props.pageProps.seoLandingData.items`, ~80/zona). categoryId 200 = inmobiliaria.
  → Scraper parsea `__NEXT_DATA__` (no API/XHR), como milanuncios.
- Capas tocadas: scraper + zones (30 zonas geo) + dbt (stg_wallapop, dim_leads,
  sources/schema accepted_values) + Django (modelo scrapear_wallapop + 2 migraciones
  + ScrapingJob/admin/serializers/api_views) + UI (filtro lista, badges teal/cyan en
  detail/realtime/scrape_history/contact_queue/scrapers + toggle por zona) +
  orquestación (scheduled_scrape VPS T1+T2, scrape-neon.yml + proxy ES, check_portal_health).
- **Detección agencia/yaencontre**: seller.userName regex + flags + texto Ref:/frases,
  doble barrera en dbt. Test: "Yaencontre"→pro, "Juan Garcia"→particular.
- **Run real** (salou+reus+tarragona): 237 items → 7 particulares venta >10k, 0 agencias coladas.
  Ej. particular: Piso en venta Reus 90m² 200000€ (Xavi v.).

### Pendiente / decisión usuario
- [ ] Deploy VPS (commit+push+migrate+restart)
- [ ] **Obra nueva Lleida (Idealista/Fotocasa)**: requiere camino PARALELO que NO
      aplique filtro es_particular (obra nueva = promotor profesional). Decisión de
      producto pendiente de confirmar con el usuario.
- [ ] Contacto automático Wallapop (no implementado; supported_portals sin tocar a propósito).
- [ ] Tune categoría/pagina si en producción aparecen <80/zona o falsos pros.

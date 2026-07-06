# Plan: Mapa útil + Dirección exacta + Contactos desde lead

## Decisiones (confirmadas con usuario)
- Leads sin dirección exacta → agrupados en el centro del pueblo (cluster); al escribir
  dirección exacta "ascienden" a su punto real.
- Contactos → tabla nueva para asignar propiedades (tipo en_venta/vendida + precio + fecha).
- Crear contacto: botón en la ficha del lead, auto-rellena teléfono/nombre/email del lead.

## 1. Modelos + migración (leads/models.py, migration 0010) ✅
- [x] `LeadDireccion` + `ContactPropiedad` creados; migración 0010 aplicada en Neon.

## 2. Geocoding (leads/geocoding.py) ✅
- [x] `geocode_address` vía Nominatim. Verificado: Tarragona/Lleida resuelven coords.

## 3. Vistas (leads/views.py + analytics/views.py + urls.py) ✅
- [x] `contact_from_lead_view` mejorado (sin teléfono + auto-asocia propiedad + completa datos).
- [x] `save_lead_address_view`, `add_contact_propiedad_view`, `delete_contact_propiedad_view`.
- [x] `map_view` reescrito: puntos por inmueble + estado + exact + vendido.

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

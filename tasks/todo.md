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

## Extra (petición usuario)
- [x] Wallapop: dejar de almacenar fotos (`_extract_photos` -> []). No gastaba anti-bot
      igualmente; el coste es la visita al detalle (por el teléfono).

## Notas
- VPS deploy NO corre migrate por defecto → añadirlo esta vez.
- Lead es vista dbt (solo lectura): todo lo editable va en tablas writable nuevas.

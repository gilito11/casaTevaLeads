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
- [ ] Commit + push + deploy VPS (git pull + migrate + collectstatic + restart).

## Extra (petición usuario)
- [x] Wallapop: dejar de almacenar fotos (`_extract_photos` -> []). No gastaba anti-bot
      igualmente; el coste es la visita al detalle (por el teléfono).

## Notas
- VPS deploy NO corre migrate por defecto → añadirlo esta vez.
- Lead es vista dbt (solo lectura): todo lo editable va en tablas writable nuevas.

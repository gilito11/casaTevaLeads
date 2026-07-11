# Lessons

## 2026-07-11 — fecha_primera_captura no era "primera": verificar semántica antes de reportar
**Corrección del usuario**: reporté "203 leads nuevos en 48h" usando `fecha_primera_captura`; el usuario detectó la contradicción (un lead "de hoy" ya estaba EN_PROCESO). Eran 4 nuevos reales — el resto re-scrapes.

**Patrón**: antes de reportar métricas desde un mart, verificar que la columna significa lo que su nombre dice. Aquí fallaban DOS capas: el scraper upserta raw machacando `scraping_timestamp` (solo `created_at` sobrevive como primera captura), y `dim_leads` incremental sobreescribía la fila entera en cada re-scrape. Cross-check barato: si una métrica "nuevos" contradice otra tabla escribible (LeadEstado, audit), tirar del hilo antes de reportar. Y al diseñar modelos incrementales: los campos "first_*" deben protegerse explícitamente del merge (LEAST con el valor previo de `{{ this }}`).

## 2026-07-07 — Unificar nombres al tocar datos de zona/municipio
**Corrección del usuario**: tras montar el filtro de zonas, quedaron duplicados visibles ("Bellvis"/"Bellvís", "Mont Roig del Camp"/"Mont-roig del Camp") — el filtro los agrupaba internamente pero el nombre mostrado no.

**Patrón**: cuando un campo de texto libre (zona, municipio, tipo...) se usa como dimensión visible (dropdowns, agrupaciones, KPIs), no basta con que el matching sea tolerante a variantes: hay que **canonicalizar el valor almacenado/mostrado**. Un solo mapa `{variante normalizada -> nombre canónico}` debe servir para filtrar Y para renombrar. Después de cualquier cambio así, comprobar `SELECT DISTINCT` en busca de duplicados por acento/guion/apóstrofe antes de dar por terminado.

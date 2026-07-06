"""
Milanuncios scraper vía Bright Data Web Unlocker.

Descubierto 6 Jul 2026 (workflow bd-debug):
- BD atraviesa GeeTest/milanuncios sin navegador: HTML 200 con
  window.__INITIAL_PROPS__ (JSON.parse escapado) y 41 ads/página.
- El filtro `?vendedor=part` funciona server-side: devuelve SOLO particulares
  (Lleida provincia: 32 pisos + 40 casas en 1 página cada uno).
- `lleida-lleida` cubre la PROVINCIA entera (Alcarràs, Borges, Cervera...),
  así que 2 URLs cubren todos los pueblos del Segrià.
- El slug correcto es `venta-de-pisos-en-*` / `venta-de-casas-en-*`
  (el viejo `pisos-en-*` mezcla alquileres; `casas-en-venta-en-*` y
  `venta-de-terrenos-en-*` NO existen y devuelven España entera / 404).
- Cada ad trae `city.name` -> zona_clasificada por anuncio (regla dbt:
  zona_busqueda capitalizada manda).

Reusa de ScraplingMilanuncios: _extract_initial_props, _parse_json_listings
(señales sellerType/isPrivate/shop/Ref:) y parse_detail_page (badge
Profesional, teléfono, fotos, descripción).

Coste: ~25 páginas/día + detalles solo de anuncios NUEVOS (~$1-2/mes).

Env vars requeridas:
- BRIGHTDATA_API_KEY
- BRIGHTDATA_ZONE (default: web_unlocker1)
"""
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import requests
from scrapling.parser import Adaptor

from scrapers.scrapling_milanuncios import ScraplingMilanuncios

logger = logging.getLogger(__name__)

# Anuncios de demanda (compradores), no de venta
_DEMAND_TITLE_RE = re.compile(r"^\s*(compro|busco|se busca|cambio|permut)", re.IGNORECASE)


class ScraplingMilanunciosBD(ScraplingMilanuncios):
    BD_API_URL = "https://api.brightdata.com/request"
    BD_COUNTRY = "es"
    SERVICE_LABEL = "brightdata"

    BD_CATEGORIES = ("venta-de-pisos", "venta-de-casas")
    # slug de localizacion por zona. lleida_provincia cubre todos los pueblos.
    BD_ZONES = {
        "lleida_provincia": "lleida-lleida",
        "tarragona": "tarragona-tarragona",
        "salou": "salou-tarragona",
        "cambrils": "cambrils-tarragona",
        "reus": "reus-tarragona",
        "vila_seca": "vila-seca-tarragona",
        "la_pineda": "la-pineda-tarragona",
        "miami_platja": "miami-platja-tarragona",
        "torredembarra": "torredembarra-tarragona",
        "altafulla": "altafulla-tarragona",
        "la_canonja": "la-canonja-tarragona",
    }

    def __init__(self, *args, brightdata_api_key: Optional[str] = None,
                 brightdata_zone: str = "web_unlocker1", **kwargs):
        super().__init__(*args, **kwargs)
        self.bd_api_key = brightdata_api_key or os.environ.get("BRIGHTDATA_API_KEY")
        self.bd_zone = brightdata_zone or os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1")
        if not self.bd_api_key:
            raise RuntimeError("BRIGHTDATA_API_KEY env var or --brightdata-api-key arg required")
        self.bd_session = requests.Session()
        self.bd_session.headers.update({
            "Authorization": f"Bearer {self.bd_api_key}",
            "Content-Type": "application/json",
        })
        self._known_ids: Set[str] = set()

    # ------------------------------------------------------------------
    # Bright Data fetch
    # ------------------------------------------------------------------
    def _bd_request(self, url: str) -> Optional[str]:
        payload = {"zone": self.bd_zone, "url": url, "format": "raw", "country": self.BD_COUNTRY}
        try:
            r = self.bd_session.post(self.BD_API_URL, json=payload, timeout=150)
        except requests.RequestException as e:
            logger.warning(f"  BD fetch failed for {url}: {e}")
            self.stats["errors"] += 1
            return None
        if r.status_code != 200:
            logger.warning(f"  BD HTTP {r.status_code} for {url}: {r.text[:200]}")
            self.stats["errors"] += 1
            return None
        r.encoding = "utf-8"
        return r.text

    # ------------------------------------------------------------------
    # Dedupe: solo fetchear detalle de anuncios que no tenemos ya
    # ------------------------------------------------------------------
    def _load_known_ids(self):
        if not self.postgres_conn:
            return
        try:
            self._ensure_db()
            cur = self.postgres_conn.cursor()
            cur.execute(
                "SELECT DISTINCT raw_data->>'anuncio_id' FROM raw.raw_listings "
                "WHERE portal='milanuncios' AND tenant_id=%s",
                [self.tenant_id],
            )
            self._known_ids = {row[0] for row in cur.fetchall() if row[0]}
            logger.info(f"[milanuncios-bd] {len(self._known_ids)} anuncios ya conocidos (skip detail)")
        except Exception as e:
            logger.warning(f"[milanuncios-bd] known_ids load failed: {e}")
            self._known_ids = set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        zone_keys = [z for z in (self.zones or self.BD_ZONES.keys()) if z in self.BD_ZONES]
        unknown = [z for z in (self.zones or []) if z not in self.BD_ZONES]
        for z in unknown:
            logger.warning(f"[milanuncios-bd] Zone not found: {z}")
            self.stats["zones_failed"] += 1

        logger.info(
            f"[milanuncios-bd] Starting scrape | tenant={self.tenant_id} "
            f"zones={zone_keys} max_pages={self.max_pages} zone={self.bd_zone}"
        )
        start = datetime.now()
        self._load_known_ids()

        for zona_key in zone_keys:
            before = dict(self.stats)
            t0 = time.time()
            try:
                self._scrape_zone_bd(zona_key)
                self.stats["zones_completed"] += 1
            except Exception as e:
                logger.exception(f"[milanuncios-bd] zone={zona_key} failed: {e}")
                self.stats["zones_failed"] += 1
                self.stats["errors"] += 1
            finally:
                self.record_zone_metrics(zona_key, before, time.time() - t0)

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[milanuncios-bd] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"details={self.stats['details_fetched']} errors={self.stats['errors']}"
        )
        return self.stats

    def _scrape_zone_bd(self, zona_key: str):
        loc_slug = self.BD_ZONES[zona_key]
        for cat in self.BD_CATEGORIES:
            for page_num in range(1, self.max_pages + 1):
                url = f"{self.BASE_URL}/{cat}-en-{loc_slug}/?vendedor=part"
                if page_num > 1:
                    url += f"&pagina={page_num}"
                logger.info(f"[milanuncios-bd] {zona_key} {cat} p{page_num}")
                html = self._bd_request(url)
                if html is None:
                    break

                props = self._extract_initial_props(html)
                if not props:
                    logger.warning(f"  INITIAL_PROPS no extraible ({len(html)} bytes)")
                    self.stats["errors"] += 1
                    break

                listings, json_had_ads = self._parse_json_listings(props, zona_key)
                if not listings:
                    break  # pagina vacia = fin de paginacion

                self.stats["listings_found"] += len(listings)
                for listing in listings:
                    listing = self._postprocess(listing, cat)
                    if listing is None or self.should_skip(listing):
                        self.stats["listings_skipped"] += 1
                        continue

                    # Detalle solo para anuncios nuevos (verifica vendedor,
                    # saca telefono/fotos/descripcion). Los conocidos se
                    # re-guardan igualmente para refrescar precio.
                    if listing["anuncio_id"] not in self._known_ids:
                        time.sleep(1)
                        dhtml = self._bd_request(listing["url_anuncio"])
                        if dhtml:
                            self.stats["details_fetched"] += 1
                            try:
                                dpage = Adaptor(content=dhtml, url=listing["url_anuncio"])
                                listing = self.parse_detail_page(dpage, listing) or listing
                            except Exception as e:
                                logger.debug(f"  detail parse failed: {e}")
                        if self.should_skip(listing):
                            # el detalle lo degrado a profesional
                            self.stats["listings_skipped"] += 1
                            continue

                    self.save_listing(listing)

    def _postprocess(self, listing: Dict[str, Any], cat: str) -> Optional[Dict[str, Any]]:
        # Anuncios de demanda ("Compro casa...") no son leads de venta
        titulo = listing.get("titulo") or ""
        if _DEMAND_TITLE_RE.match(titulo):
            return None
        # Zona por municipio real del anuncio ('Lleida / Lerida' -> 'Lleida').
        # zona_busqueda capitalizada manda en stg_milanuncios (regla 1).
        city = (listing.get("ubicacion") or "").split("/")[0].strip()
        if city:
            listing["zona_busqueda"] = city
            listing["zona_geografica"] = city
        listing["tipo_inmueble"] = "casa" if "casas" in cat else "piso"
        return listing


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=[],
                    help="Zonas BD (default: todas). Ver ScraplingMilanunciosBD.BD_ZONES")
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true")
    ap.add_argument("--brightdata-zone", default=os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1"))
    args = ap.parse_args()

    scraper = ScraplingMilanunciosBD(
        tenant_id=args.tenant_id,
        zones=args.zones,
        max_pages=args.max_pages,
        save_to_postgres=args.postgres,
        brightdata_zone=args.brightdata_zone,
    )
    stats = scraper.run()
    print("STATS:", stats)
    try:
        from scrapers.error_handling import log_scraper_run
        log_scraper_run("milanuncios", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

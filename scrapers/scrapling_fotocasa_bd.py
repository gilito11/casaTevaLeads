"""
Fotocasa scraper vía Bright Data Web Unlocker + API interna propertysearch.

Motivación: fotocasa geo-bloquea GH Actions (Azure US) y el VPS (Alemania);
IPRoyal cobra por GB de navegador. BD Web Unlocker cobra por request
(~$0.0015) y atraviesa Imperva sin navegador.

Descubierto 6 Jul 2026 (workflow bd-debug):
- La URL /particulares/.../pl devuelve 502 vía BD (solo funciona con browser real).
- La búsqueda genérica /l funciona vía BD y su HTML trae combinedLocationIds.
- El API interno `web.gw.fotocasa.es/v2/propertysearch/search` responde 200
  vía BD SIN API key, con paginación real (pageNumber), orden por fecha
  (sortType=publicationDate&sortOrderDesc=true) y pageSize capado a 30.
- `advertiser.typeId`: 1 = particular, 3 = agencia. En Lleida capital p1
  ordenada por fecha: 6/30 particulares.

Flujo por zona: 1 fetch del /l HTML para extraer combinedLocationIds
(cacheado en memoria) + max_pages fetches del API. ~4 req/zona/run.

Env vars requeridas:
- BRIGHTDATA_API_KEY
- BRIGHTDATA_ZONE (default: web_unlocker1)
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from scrapers.scrapling_fotocasa import ScraplingFotocasa

logger = logging.getLogger(__name__)


class ScraplingFotocasaBD(ScraplingFotocasa):
    BD_API_URL = "https://api.brightdata.com/request"
    BD_COUNTRY = "es"
    SERVICE_LABEL = "brightdata"
    FC_SEARCH_API = "https://web.gw.fotocasa.es/v2/propertysearch/search"

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
        self._location_ids: Dict[str, str] = {}  # zona_key -> combinedLocationIds

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
    # combinedLocationIds discovery (1 request por zona, cacheado)
    # ------------------------------------------------------------------
    def _get_location_ids(self, zona_key: str) -> Optional[str]:
        if zona_key in self._location_ids:
            return self._location_ids[zona_key]
        zona = self.ZONAS.get(zona_key, {})
        url_path = zona.get("url_path", f"{zona_key}/todas-las-zonas")
        url = f"{self.BASE_URL}/es/comprar/viviendas/{url_path}/l"
        html = self._bd_request(url)
        if not html:
            return None
        m = re.search(r'combinedLocationIds=([0-9,]+)', html)
        if not m:
            m = re.search(r'"combinedLocationIds":"([0-9,]+)"', html)
        if not m:
            logger.warning(f"[fotocasa-bd] {zona_key}: combinedLocationIds no encontrado (html={len(html)} bytes)")
            return None
        self._location_ids[zona_key] = m.group(1)
        logger.info(f"[fotocasa-bd] {zona_key}: combinedLocationIds={m.group(1)}")
        return m.group(1)

    # ------------------------------------------------------------------
    # API item -> listing dict
    # ------------------------------------------------------------------
    @staticmethod
    def _api_features(features) -> Dict[str, int]:
        out: Dict[str, int] = {}
        if isinstance(features, list):
            for f in features:
                if isinstance(f, dict) and f.get("key"):
                    val = f.get("value")
                    if isinstance(val, list) and val:
                        val = val[0]
                    try:
                        out[f["key"]] = int(val)
                    except (TypeError, ValueError):
                        pass
        return out

    def _listing_from_api_item(self, d: dict, zona_key: str, zona_info: dict) -> Optional[Dict[str, Any]]:
        anuncio_id = str(d.get("id") or "")
        if not anuncio_id:
            return None
        # Promociones de obra nueva nunca son particulares
        if d.get("promotionId") or d.get("promotionTypeId"):
            return None

        adv = d.get("advertiser") or {}
        es_particular = adv.get("typeId") == 1
        vendedor = (adv.get("clientAlias") or "").strip() or ("Particular" if es_particular else "Agencia")

        precio = None
        for t in (d.get("transactions") or []):
            vals = t.get("value") or []
            if vals and isinstance(vals, list):
                try:
                    v = float(vals[0])
                    if v > 0:
                        precio = v
                        break
                except (TypeError, ValueError):
                    pass

        feats = self._api_features(d.get("features"))

        detail = d.get("detail") or {}
        href = (detail.get("es") or "").split("?", 1)[0]
        url_anuncio = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        addr = d.get("address") or {}
        loc = addr.get("location") or {}
        municipio = (loc.get("level5") or loc.get("level4") or "").strip()
        coords = addr.get("coordinates") or {}

        phone = adv.get("phone") or ""
        phone_digits = re.sub(r"\D", "", phone)[-9:] if phone else ""

        photos = []
        for mm in (d.get("multimedias") or []):
            if isinstance(mm, dict):
                u = mm.get("url") or mm.get("src") or ""
                if "/images/ads/" in u:
                    photos.append(u)

        descripcion = d.get("description") or ""

        return {
            "anuncio_id": anuncio_id,
            "titulo": descripcion[:200] if descripcion else f"Vivienda en {municipio or zona_info.get('nombre', zona_key)}",
            "precio": precio,
            "habitaciones": feats.get("rooms") or None,
            "metros": feats.get("surface") or None,
            "banos": feats.get("bathrooms") or None,
            "descripcion": descripcion,
            "telefono": phone_digits or None,
            "telefono_norm": self.normalize_phone(phone_digits) if phone_digits else None,
            "fotos": photos[:10] or None,
            "url_anuncio": url_anuncio,
            "direccion": (addr.get("ubication") or municipio or None),
            "municipio": municipio or None,
            "latitud": coords.get("latitude"),
            "longitud": coords.get("longitude"),
            "zona_geografica": municipio or zona_info.get("nombre", zona_key),
            "zona_busqueda": zona_key,
            "es_particular": es_particular,
            "vendedor": vendedor,
            "tipo_inmueble": "piso",
        }

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        if not self.zones:
            self.zones = list(self.ZONAS.keys())

        # Expand composite zones (mismo comportamiento que ScraplingFotocasa.run)
        expanded: List[str] = []
        for z in self.zones:
            info = self.ZONAS.get(z, {})
            if "composite" in info:
                expanded.extend(c for c in info["composite"] if c in self.ZONAS)
            elif z in self.ZONAS:
                expanded.append(z)
            else:
                logger.warning(f"[fotocasa-bd] Zone not found: {z}")
                self.stats["zones_failed"] += 1
        self.zones = expanded

        logger.info(
            f"[fotocasa-bd] Starting scrape | tenant={self.tenant_id} "
            f"zones={self.zones} max_pages={self.max_pages} zone={self.bd_zone}"
        )
        start = datetime.now()

        for zona_key in self.zones:
            before = dict(self.stats)
            t0 = time.time()
            try:
                self._scrape_zone_bd(zona_key)
                self.stats["zones_completed"] += 1
            except Exception as e:
                logger.exception(f"[fotocasa-bd] zone={zona_key} failed: {e}")
                self.stats["zones_failed"] += 1
                self.stats["errors"] += 1
            finally:
                self.record_zone_metrics(zona_key, before, time.time() - t0)

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[fotocasa-bd] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"errors={self.stats['errors']}"
        )
        return self.stats

    def _scrape_zone_bd(self, zona_key: str):
        loc_ids = self._get_location_ids(zona_key)
        if not loc_ids:
            self.stats["zones_failed"] += 1
            return
        zona_info = self.ZONAS.get(zona_key, {})

        for page_num in range(1, self.max_pages + 1):
            api_url = (
                f"{self.FC_SEARCH_API}?combinedLocationIds={loc_ids}"
                f"&transactionTypeId=1&pageNumber={page_num}"
                f"&sortType=publicationDate&sortOrderDesc=true&pageSize=30"
            )
            logger.info(f"[fotocasa-bd] {zona_key} p{page_num} (API)")
            body = self._bd_request(api_url)
            if body is None:
                break
            try:
                data = json.loads(body)
            except ValueError:
                logger.warning(f"  respuesta API no-JSON ({len(body)} bytes): {body[:150]!r}")
                self.stats["errors"] += 1
                break

            items = data.get("realEstates") or []
            listings = []
            for item in items:
                try:
                    listing = self._listing_from_api_item(item, zona_key, zona_info)
                except Exception as e:
                    logger.debug(f"  item parse error: {e}")
                    continue
                if listing:
                    listings.append(listing)

            n_part = sum(1 for x in listings if x["es_particular"])
            self.stats["listings_found"] += len(listings)
            logger.info(
                f"  {len(listings)} listings ({n_part} particulares, "
                f"{len(listings) - n_part} agencias) | total zona: {data.get('count')}"
            )
            if not listings:
                break  # página vacía = fin de paginación

            for listing in listings:
                if self.should_skip(listing):
                    self.stats["listings_skipped"] += 1
                    continue
                self.save_listing(listing)


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="+", required=True)
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true")
    ap.add_argument("--brightdata-zone", default=os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1"))
    args = ap.parse_args()

    scraper = ScraplingFotocasaBD(
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
        log_scraper_run("fotocasa", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

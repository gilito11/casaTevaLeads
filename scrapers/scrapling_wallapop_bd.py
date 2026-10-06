"""
Wallapop scraper: feed del API geolocalizado + detalle vía Bright Data.

Búsqueda (gratis): api.wallapop.com/api/v3/search es público y sin anti-bot,
se pide directo desde el runner con headers de app. Para cada zona:
lat/lng + distance_in_km + operation=buy + order_by=newest, paginando con
meta.next_page hasta que la página entera sea más antigua que --max-age-days
o se llegue a --max-pages. BD solo como fallback de la 1a página si el GET
directo falla.

La vertical SEO /inmobiliaria/<slug> ya NO se usa aquí: solo devolvía ~80
items por relevancia sin paginar (Lleida: 77/80 agencias) y se perdía a los
particulares nuevos.

Detalle (BD, geo-bloqueado en runners US): solo anuncios NUEVOS que pasan el
filtro de card. Re-verifica al vendedor (itemSeller.sellerType=Business =
agencia, p.ej. yaencontre). Los descartados por detalle se guardan en raw con
es_particular=false (stg_wallapop los filtra) para no volver a pagar su
detalle cada día.

Identidad: ver ScraplingWallapop.save_listing (id numérico del slug, reusa el
anuncio_id existente en raw, sea numérico o hash).

Env vars requeridas:
- BRIGHTDATA_API_KEY (opcional con --dry-run)
- BRIGHTDATA_ZONE (default: web_unlocker1)
"""
import logging
import os
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from scrapers.brightdata import build_session, get_api_key, verify_token
from scrapers.scrapling_wallapop import ScraplingWallapop

logger = logging.getLogger(__name__)


class _Page:
    """Shim mínimo: los parsers de ScraplingWallapop solo leen page.html_content."""

    def __init__(self, html: str):
        self.html_content = html


class ScraplingWallapopBD(ScraplingWallapop):
    BD_API_URL = "https://api.brightdata.com/request"
    BD_COUNTRY = "es"
    SERVICE_LABEL = "brightdata"
    API_PAGE_DELAY = 0.5

    def __init__(self, *args, brightdata_api_key: Optional[str] = None,
                 brightdata_zone: str = "web_unlocker1", max_age_days: int = 60,
                 dry_run: bool = False, **kwargs):
        if dry_run:
            kwargs["save_to_postgres"] = False
        kwargs.setdefault("max_pages", 10)
        super().__init__(*args, **kwargs)
        self.max_age_days = max_age_days
        self.dry_run = dry_run
        self.bd_zone = brightdata_zone or os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1")
        self.bd_session = None
        key = brightdata_api_key or os.environ.get("BRIGHTDATA_API_KEY")
        if not dry_run or key:
            self.bd_session = build_session(get_api_key(key))
            verify_token(self.bd_session)  # token caducado -> abortar ya, no 40 warnings 401
        if dry_run:
            # Solo lectura: known ids para medir lo que sería nuevo. Nunca escribe.
            try:
                self._init_postgres()
                self.postgres_conn.set_session(readonly=True)
            except Exception as e:
                logger.warning(f"[wallapop-bd] dry-run sin BD: {e}")
                self.postgres_conn = None
        self.stats["listings_new"] = 0
        self.stats["rejected_cached"] = 0
        self.stats["api_pages"] = 0
        self._seen: set = set()
        self._run_zones: List[str] = []
        self._city_zone: Dict[str, str] = {}
        self.dry_candidates: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    def _bd_request(self, url: str) -> Optional[str]:
        if self.bd_session is None:
            return None
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

    API_HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
        "X-DeviceOS": "0",
        "Accept": "application/json",
        "Accept-Language": "es-ES,es;q=0.9",
    }

    def _fetch_api(self, zona_key: str, url: str, allow_bd: bool) -> Optional[str]:
        try:
            r = requests.get(url, headers=self.API_HEADERS, timeout=30)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.text
            logger.info(f"[wallapop-bd] {zona_key}: API directa HTTP {r.status_code}")
        except requests.RequestException as e:
            logger.info(f"[wallapop-bd] {zona_key}: API directa falló ({e})")
        if not allow_bd:
            return None
        logger.info(f"[wallapop-bd] {zona_key}: fallback BD")
        return self._bd_request(url)

    # ------------------------------------------------------------------
    # Zona asignada (zonas solapadas: Lleida 12km cubre Alpicat, Alcarràs...)
    # ------------------------------------------------------------------
    def _assign_zone(self, item: Dict[str, Any], query_zone: str) -> str:
        """Municipio del anuncio si es una zona del run; si no, la zona del run
        más cercana en proporción a su radio (por defecto la de la búsqueda)."""
        loc = item.get("location") or {}
        by_city = self._city_zone.get(self._norm_place(loc.get("city")))
        if by_city:
            return by_city
        best, best_ratio = query_zone, None
        for z in self._run_zones:
            cfg = self.ZONAS[z]
            d = self._distance_km(loc, cfg)
            if d is None:
                return query_zone
            ratio = d / float(cfg.get("radius_km") or 4)
            if ratio <= 1.6 and (best_ratio is None or ratio < best_ratio):
                best, best_ratio = z, ratio
        return best

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        if not self.zones:
            self.zones = list(self.ZONAS.keys())
        zone_keys = [z for z in self.zones if z in self.ZONAS]
        for z in self.zones:
            if z not in self.ZONAS:
                logger.warning(f"[wallapop-bd] Zone not found: {z}")
                self.stats["zones_failed"] += 1
        self._run_zones = zone_keys
        self._city_zone = {}
        for z in zone_keys:
            for name in (z.replace("_", " "), self.ZONAS[z].get("nombre", "")):
                self._city_zone.setdefault(self._norm_place(name), z)

        logger.info(
            f"[wallapop-bd] Starting scrape | tenant={self.tenant_id} zones={zone_keys} "
            f"max_pages={self.max_pages} max_age_days={self.max_age_days} dry_run={self.dry_run}"
        )
        start = datetime.now()
        self._load_known()

        for zona_key in zone_keys:
            before = dict(self.stats)
            t0 = time.time()
            try:
                self._scrape_zone_feed(zona_key)
                self.stats["zones_completed"] += 1
            except Exception as e:
                logger.exception(f"[wallapop-bd] zone={zona_key} failed: {e}")
                self.stats["zones_failed"] += 1
                self.stats["errors"] += 1
            finally:
                if not self.dry_run:
                    self.record_zone_metrics(zona_key, before, time.time() - t0)

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[wallapop-bd] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"new={self.stats['listings_new']} details={self.stats['details_fetched']} "
            f"rejected={self.stats['rejected_cached']} pages={self.stats['api_pages']} "
            f"errors={self.stats['errors']}"
        )
        return self.stats

    def _scrape_zone_feed(self, zona_key: str):
        zona_cfg = self.ZONAS[zona_key]
        cutoff_ms = (time.time() - self.max_age_days * 86400) * 1000
        url = self.build_api_url(zona_key)
        logger.info(f"[wallapop-bd] {zona_key}: {url}")

        pages = n_items = en_radio = dup = cand = nuevos = 0
        while url and pages < self.max_pages:
            body = self._fetch_api(zona_key, url, allow_bd=(pages == 0))
            if body is None:
                if pages == 0:
                    self.stats["errors"] += 1
                break
            pages += 1
            self.stats["api_pages"] += 1
            items, next_page = self._api_payload(body)
            n_items += len(items)

            for item in items:
                try:
                    listing = self._api_item_to_listing(item, zona_key, zona_cfg)
                except Exception as e:
                    logger.debug(f"[wallapop-bd] api item parse error: {e}")
                    continue
                if listing is None or not self._within_radius(item.get("location") or {}, zona_cfg):
                    continue
                en_radio += 1
                if listing["anuncio_id"] in self._seen:
                    dup += 1
                    continue
                self._seen.add(listing["anuncio_id"])
                self.stats["listings_found"] += 1

                zona = self._assign_zone(item, zona_key)
                listing["zona_busqueda"] = zona
                listing["zona_geografica"] = self.ZONAS[zona].get("nombre", zona)

                if self.should_skip(listing):
                    self.stats["listings_skipped"] += 1
                    continue
                cand += 1
                if self._process(listing, cutoff_ms):
                    nuevos += 1

            created = [i.get("created_at") for i in items if isinstance(i.get("created_at"), (int, float))]
            if not items or not next_page or (created and min(created) < cutoff_ms):
                break
            url = f"{self.API_SEARCH_URL}?{urllib.parse.urlencode({'next_page': next_page})}"
            time.sleep(self.API_PAGE_DELAY)

        logger.info(
            f"[wallapop-bd] {zona_key}: pages={pages} items={n_items} en_radio={en_radio} "
            f"dup={dup} candidatos={cand} nuevos={nuevos}"
        )

    def _process(self, listing: Dict[str, Any], cutoff_ms: float) -> bool:
        """Guarda un candidato que pasó el filtro de card. True si es un anuncio
        nuevo (no estaba en raw) guardado como particular."""
        prev = self.known_entry(listing)
        if prev:
            if not prev["es_particular"]:
                self.stats["listings_skipped"] += 1  # descartado por detalle en otro run
                return False
            # Conocido: re-guardar para refrescar precio/timestamp, sin detalle.
            if not self.dry_run:
                self.save_listing(listing)
            return False

        # Las zonas pequeñas traen en la 1a página anuncios de hace años: solo
        # entran como lead los creados dentro de la ventana.
        created = listing.get("_created_at")
        if isinstance(created, (int, float)) and created < cutoff_ms:
            self.stats["listings_skipped"] += 1
            return False

        user_id = listing.get("_user_id")
        if user_id and user_id in self._agency_users:
            # Vendedor ya verificado como profesional (p.ej. un servicer con
            # cientos de anuncios): sin detalle.
            self.stats["listings_skipped"] += 1
            return False

        if self.dry_run:
            self.dry_candidates.append(listing)
            return True

        # Nuevo: detalle (teléfono en descripción, nombre real, re-verificación
        # del vendedor). Único gasto de BD del run.
        time.sleep(1)
        dhtml = self._bd_request(listing["url_anuncio"])
        if dhtml:
            self.stats["details_fetched"] += 1
            try:
                listing = self.parse_detail_page(_Page(dhtml), listing) or listing
            except Exception as e:
                logger.debug(f"  detail parse failed: {e}")
        if self.should_skip(listing):
            if listing.get("verified") and listing.get("es_particular") is False:
                # Cache del descarte: stg_wallapop exige es_particular=TRUE.
                if self.save_listing(listing):
                    self.stats["listings_saved"] -= 1
                    self.stats["rejected_cached"] += 1
                    if user_id and listing.get("_seller_pro"):
                        self._agency_users.add(user_id)
                        self._tag_user(listing["anuncio_id"], user_id)
            else:
                self.stats["listings_skipped"] += 1
            return False
        if self.save_listing(listing):
            self.stats["listings_new"] += 1
            return True
        return False

    def _tag_user(self, anuncio_id: str, user_id: str):
        """Persiste el user_id en la fila descartada (save_listing no lo guarda)
        para que _load_known recupere el vendedor profesional en el próximo run.
        Esas filas no se re-guardan nunca, así que el tag no se pierde."""
        try:
            cur = self.postgres_conn.cursor()
            cur.execute(
                """
                UPDATE raw.raw_listings
                SET raw_data = raw_data || jsonb_build_object('user_id', %s::text)
                WHERE tenant_id = %s AND portal = %s AND raw_data->>'anuncio_id' = %s
                """,
                (user_id, self.tenant_id, self.PORTAL_NAME, anuncio_id),
            )
            self.postgres_conn.commit()
            cur.close()
        except Exception as e:
            logger.debug(f"[wallapop-bd] user tag skipped: {e}")
            try:
                self.postgres_conn.rollback()
            except Exception:
                pass


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=[],
                    help="Zonas (default: todas las de scrapers.zones.wallapop)")
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true")
    ap.add_argument("--max-pages", type=int, default=10, help="Páginas de 40 por zona (tope)")
    ap.add_argument("--max-age-days", type=int, default=60,
                    help="Deja de paginar cuando una página es más antigua que esto")
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo lectura: sin detalle BD ni escrituras; lista candidatos nuevos")
    ap.add_argument("--brightdata-zone", default=os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1"))
    args = ap.parse_args()

    scraper = ScraplingWallapopBD(
        tenant_id=args.tenant_id,
        zones=args.zones,
        save_to_postgres=args.postgres,
        max_pages=args.max_pages,
        max_age_days=args.max_age_days,
        dry_run=args.dry_run,
        brightdata_zone=args.brightdata_zone,
    )
    stats = scraper.run()
    print("STATS:", stats)
    if args.dry_run:
        for l in scraper.dry_candidates:
            print(f"NEW\t{l['zona_busqueda']}\t{l['anuncio_id']}\t{l.get('precio')}\t{l['url_anuncio']}\t{l.get('_user_id')}")
        return
    try:
        from scrapers.error_handling import log_scraper_run
        log_scraper_run("wallapop", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

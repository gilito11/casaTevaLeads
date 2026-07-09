"""
Wallapop scraper vía Bright Data Web Unlocker.

Wallapop renderiza la vertical /inmobiliaria/<slug> server-side (Next.js):
el HTML crudo ya trae __NEXT_DATA__ con ~80 items por zona, sin navegador.
BD Web Unlocker con country=es resuelve el geo-block que mataba a IPRoyal
(ERR_TUNNEL_CONNECTION_FAILED en runners US, 8 Jul 2026).

Reusa de ScraplingWallapop: _extract_next_data, _items_from_next_data,
_item_to_listing (filtro agencias), parse_search_page y parse_detail_page
(teléfono en descripción, re-verificación del vendedor).

Coste: 1 request por zona + detalle solo de anuncios NUEVOS (~$0.5-1/mes).

Env vars requeridas:
- BRIGHTDATA_API_KEY
- BRIGHTDATA_ZONE (default: web_unlocker1)
"""
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional, Set

import requests

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
                "WHERE portal='wallapop' AND tenant_id=%s",
                [self.tenant_id],
            )
            self._known_ids = {row[0] for row in cur.fetchall() if row[0]}
            logger.info(f"[wallapop-bd] {len(self._known_ids)} anuncios ya conocidos (skip detail)")
        except Exception as e:
            logger.warning(f"[wallapop-bd] known_ids load failed: {e}")
            self._known_ids = set()

    # ------------------------------------------------------------------
    # Main loop (sin navegador: 1 GET por zona, SSR trae ~80 items)
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        if not self.zones:
            self.zones = list(self.ZONAS.keys())
        zone_keys = [z for z in self.zones if z in self.ZONAS]
        for z in self.zones:
            if z not in self.ZONAS:
                logger.warning(f"[wallapop-bd] Zone not found: {z}")
                self.stats["zones_failed"] += 1

        logger.info(
            f"[wallapop-bd] Starting scrape | tenant={self.tenant_id} "
            f"zones={zone_keys} zone={self.bd_zone}"
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
                logger.exception(f"[wallapop-bd] zone={zona_key} failed: {e}")
                self.stats["zones_failed"] += 1
                self.stats["errors"] += 1
            finally:
                self.record_zone_metrics(zona_key, before, time.time() - t0)

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[wallapop-bd] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"details={self.stats['details_fetched']} errors={self.stats['errors']}"
        )
        return self.stats

    def _scrape_zone_bd(self, zona_key: str):
        url = self.build_search_url(zona_key)
        logger.info(f"[wallapop-bd] {zona_key}: {url}")
        html = self._bd_request(url)
        if html is None:
            return

        listings = self.parse_search_page(_Page(html), zona_key)
        self.stats["listings_found"] += len(listings)

        for listing in listings:
            if self.should_skip(listing):
                self.stats["listings_skipped"] += 1
                continue

            # Detalle solo para anuncios nuevos (teléfono en descripción,
            # descripción completa, re-verificación del vendedor). Los
            # conocidos se re-guardan igualmente para refrescar precio.
            if listing["anuncio_id"] not in self._known_ids:
                time.sleep(1)
                dhtml = self._bd_request(listing["url_anuncio"])
                if dhtml:
                    self.stats["details_fetched"] += 1
                    try:
                        listing = self.parse_detail_page(_Page(dhtml), listing) or listing
                    except Exception as e:
                        logger.debug(f"  detail parse failed: {e}")
                if self.should_skip(listing):
                    # el detalle lo degradó a profesional
                    self._known_ids.add(listing["anuncio_id"])
                    self.stats["listings_skipped"] += 1
                    continue

            self.save_listing(listing)
            self._known_ids.add(listing["anuncio_id"])


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=[],
                    help="Zonas (default: todas las de scrapers.zones.wallapop)")
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true")
    ap.add_argument("--brightdata-zone", default=os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1"))
    args = ap.parse_args()

    scraper = ScraplingWallapopBD(
        tenant_id=args.tenant_id,
        zones=args.zones,
        save_to_postgres=args.postgres,
        brightdata_zone=args.brightdata_zone,
    )
    stats = scraper.run()
    print("STATS:", stats)
    try:
        from scrapers.error_handling import log_scraper_run
        log_scraper_run("wallapop", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

"""
Fotocasa scraper que fetchea vía Bright Data Web Unlocker API.

Motivación: fotocasa geo-bloquea los runners de GH Actions (Azure US) y el
VPS (Alemania); la alternativa IPRoyal cobra por GB de navegador (~$20-60/mes
en cron diario). BD Web Unlocker cobra por request (~$0.0015) -> ~78 req/día
con las zonas de Lleida = ~$3.5/mes.

Reusa el parser de ScraplingFotocasa: `_parse_embedded_listings` ancla en el
JSON embebido (`clientTypeId`) del HTML crudo, así que NO necesita ejecutar
JS ni el scroll de hidratación (eso era solo para serializar el DOM con
Scrapling). El fallback JS-stash no aplica aquí (no hay navegador).

Env vars requeridas:
- BRIGHTDATA_API_KEY
- BRIGHTDATA_ZONE (default: web_unlocker1)
- BRIGHTDATA_RENDER=true (opcional: fuerza render JS si el JSON no viene en el HTML)
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from scrapling.parser import Adaptor

from scrapers.scrapling_fotocasa import ScraplingFotocasa

logger = logging.getLogger(__name__)


class ScraplingFotocasaBD(ScraplingFotocasa):
    BD_API_URL = "https://api.brightdata.com/request"
    BD_COUNTRY = "es"
    SERVICE_LABEL = "brightdata"

    def __init__(self, *args, brightdata_api_key: Optional[str] = None,
                 brightdata_zone: str = "web_unlocker1", **kwargs):
        super().__init__(*args, **kwargs)
        self.bd_api_key = brightdata_api_key or os.environ.get("BRIGHTDATA_API_KEY")
        self.bd_zone = brightdata_zone or os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1")
        self.bd_render = os.environ.get("BRIGHTDATA_RENDER", "").lower() == "true"
        if not self.bd_api_key:
            raise RuntimeError("BRIGHTDATA_API_KEY env var or --brightdata-api-key arg required")
        self.bd_session = requests.Session()
        self.bd_session.headers.update({
            "Authorization": f"Bearer {self.bd_api_key}",
            "Content-Type": "application/json",
        })

    def _bd_request(self, url: str, render: bool) -> Optional[str]:
        payload = {"zone": self.bd_zone, "url": url, "format": "raw", "country": self.BD_COUNTRY}
        if render:
            payload["render"] = "true"  # fuerza browser rendering (doc BD)
        try:
            r = self.bd_session.post(self.BD_API_URL, json=payload, timeout=180)
        except requests.RequestException as e:
            logger.warning(f"  BD fetch failed for {url}: {e}")
            return None
        if r.status_code != 200:
            logger.warning(f"  BD HTTP {r.status_code} for {url}: {r.text[:200]}")
            return None
        r.encoding = "utf-8"
        return r.text

    def _bd_fetch(self, url: str) -> Optional[Adaptor]:
        # 1º intento sin render (barato). El /pl de fotocasa suele necesitar JS:
        # si el HTML no trae el JSON embebido (clientTypeId), retry con render.
        html = None
        if not self.bd_render:
            html = self._bd_request(url, render=False)
            if html is not None and "clientTypeId" not in html:
                snippet = ", body=" + repr(html[:120]) if len(html) < 2000 else ""
                logger.info(f"  body sin clientTypeId ({len(html)} bytes{snippet}) -> retry con render")
                html = None
        if html is None:
            html = self._bd_request(url, render=True)
            if html is not None and "clientTypeId" not in html:
                snippet = ", body=" + repr(html[:120]) if len(html) < 2000 else ""
                logger.warning(f"  render tampoco trae clientTypeId ({len(html)} bytes{snippet})")
        if html is None:
            self.stats["errors"] += 1
            return None
        adaptor = Adaptor(content=html, url=url)
        try:
            adaptor.status = 200  # type: ignore[attr-defined]
        except Exception:
            pass
        return adaptor

    def run(self) -> Dict[str, Any]:
        import time

        if not self.zones:
            self.zones = list(self.ZONAS.keys())

        # Expand composite zones (mismo comportamiento que ScraplingFotocasa.run)
        expanded = []
        for z in self.zones:
            info = self.ZONAS.get(z, {})
            if "composite" in info:
                expanded.extend(c for c in info["composite"] if c in self.ZONAS)
            elif z in self.ZONAS:
                expanded.append(z)
            else:
                logger.warning(f"[{self.PORTAL_NAME}-bd] Zone not found: {z}")
                self.stats["zones_failed"] += 1
        self.zones = expanded

        logger.info(
            f"[{self.PORTAL_NAME}-bd] Starting scrape | tenant={self.tenant_id} "
            f"zones={self.zones} max_pages={self.max_pages} zone={self.bd_zone} "
            f"render={self.bd_render}"
        )
        start = datetime.now()

        for zona_key in self.zones:
            before = dict(self.stats)
            t0 = time.time()
            try:
                self._scrape_zone_bd(zona_key)
                self.stats["zones_completed"] += 1
            except Exception as e:
                logger.exception(f"[{self.PORTAL_NAME}-bd] zone={zona_key} failed: {e}")
                self.stats["zones_failed"] += 1
                self.stats["errors"] += 1
            finally:
                self.record_zone_metrics(zona_key, before, time.time() - t0)

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[{self.PORTAL_NAME}-bd] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"errors={self.stats['errors']}"
        )
        return self.stats

    def _scrape_zone_bd(self, zona_key: str):
        for page_num in range(1, self.max_pages + 1):
            url = self.build_search_url(zona_key, page_num)
            logger.info(f"[{self.PORTAL_NAME}-bd] {zona_key} p{page_num}: {url}")
            page = self._bd_fetch(url)
            if page is None:
                break

            listings = self.parse_search_page(page, zona_key) or []
            self.stats["listings_found"] += len(listings)
            logger.info(f"  parsed {len(listings)} listings")
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

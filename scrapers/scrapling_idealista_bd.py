"""
Idealista scraper que fetchea vía Bright Data Web Unlocker API.

Motivación: IPRoyal residencial ES está flagged por DataDome para
idealista (403 desde local y desde GH Actions). BD Web Unlocker resuelve
el bypass como servicio gestionado (~$1.50/CPM = $0.0015/request).

Reusa todos los parsers de ScraplingIdealista; sustituye únicamente el
fetch (StealthySession -> BD API). Como BD API no ejecuta JS click,
las páginas de detalle se capturan SIN phone-reveal: el teléfono se
recupera más adelante o se acepta su ausencia para este portal.

Env vars requeridas:
- BRIGHTDATA_API_KEY
- BRIGHTDATA_ZONE (default: web_unlocker1)
"""
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from scrapling.parser import Adaptor

from scrapers.scrapling_idealista import ScraplingIdealista

logger = logging.getLogger(__name__)


class ScraplingIdealistaBD(ScraplingIdealista):
    BD_API_URL = "https://api.brightdata.com/request"
    BD_COUNTRY = "es"

    def __init__(self, *args, brightdata_api_key: Optional[str] = None,
                 brightdata_zone: str = "web_unlocker1", **kwargs):
        # Force only-search semantics: detail without phone has limited value;
        # keeping it for richer descriptions but tagging stats accordingly.
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

    def _bd_fetch(self, url: str) -> Optional[Adaptor]:
        payload = {"zone": self.bd_zone, "url": url, "format": "raw", "country": self.BD_COUNTRY}
        try:
            r = self.bd_session.post(self.BD_API_URL, json=payload, timeout=90)
        except requests.RequestException as e:
            logger.warning(f"  BD fetch failed for {url}: {e}")
            self.stats["errors"] += 1
            return None
        if r.status_code != 200:
            logger.warning(f"  BD HTTP {r.status_code} for {url}: {r.text[:200]}")
            self.stats["errors"] += 1
            return None
        # Force utf-8 — BD sometimes returns without explicit charset
        r.encoding = "utf-8"
        adaptor = Adaptor(content=r.text, url=url)
        # Mirror StealthySession page attributes consumed by parsers/_is_blocked_page
        try:
            adaptor.status = 200  # type: ignore[attr-defined]
        except Exception:
            pass
        return adaptor

    def run(self) -> Dict[str, Any]:
        if not self.zones:
            self.zones = list(self.ZONAS.keys())

        logger.info(
            f"[{self.PORTAL_NAME}-bd] Starting scrape | tenant={self.tenant_id} "
            f"zones={self.zones} max_pages={self.max_pages} zone={self.bd_zone}"
        )
        start = datetime.now()

        for zona_key in self.zones:
            if zona_key not in self.ZONAS:
                logger.warning(f"[{self.PORTAL_NAME}-bd] Zone not found: {zona_key}")
                self.stats["zones_failed"] += 1
                continue
            try:
                self._scrape_zone_bd(zona_key)
                self.stats["zones_completed"] += 1
            except Exception as e:
                logger.exception(f"[{self.PORTAL_NAME}-bd] zone={zona_key} failed: {e}")
                self.stats["zones_failed"] += 1
                self.stats["errors"] += 1

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
                break

            for listing in listings:
                if self.should_skip(listing):
                    self.stats["listings_skipped"] += 1
                    continue
                # Cost/time optimisation: each BD detail fetch costs a request
                # (~$0.0015) and ~20-25s. In coastal zones ~95% of cards are
                # agencies already flagged at card level (logo-branding). We
                # only fetch the detail page for cards that LOOK like a
                # particular, to CONFIRM via /pro/ + professional-name (detail
                # detection can only downgrade to professional, never the
                # reverse). Verified 27 May 2026: this skips ~28/30 fetches per
                # zone, cutting idealista from ~24 min/zone to ~1 min/zone and
                # letting the cron actually reach the interior zones where real
                # particulares exist.
                detail_url = listing.get("url_anuncio")
                if detail_url and listing.get("es_particular"):
                    time.sleep(2)  # small courtesy delay between BD requests
                    dpage = self._bd_fetch(detail_url)
                    if dpage is not None:
                        self.stats["details_fetched"] += 1
                        try:
                            listing = self.parse_detail_page(dpage, listing) or listing
                        except Exception as e:
                            logger.debug(f"  detail parse failed for {detail_url}: {e}")
                self.save_listing(listing)


def main():
    import argparse
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="+", required=True)
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true")
    ap.add_argument("--brightdata-zone", default=os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1"))
    args = ap.parse_args()

    scraper = ScraplingIdealistaBD(
        tenant_id=args.tenant_id,
        zones=args.zones,
        max_pages=args.max_pages,
        save_to_postgres=args.postgres,
        brightdata_zone=args.brightdata_zone,
    )
    stats = scraper.run()
    print("STATS:", stats)


if __name__ == "__main__":
    main()

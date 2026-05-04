"""
Fotocasa scraper basado en Scrapling.

Replaces camoufox_fotocasa.py — Patchright stealth + StealthySession bypass
GeeTest in most cases via solve_cloudflare=True. v1 NO incluye fallback 2Captcha
(se mantiene en camoufox_fotocasa.py si hace falta v2).
"""
import logging
import re
from typing import Any, Dict, List, Optional

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.botasaurus_fotocasa import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)


class ScraplingFotocasa(ScraplingBaseScraper):
    PORTAL_NAME = "fotocasa"
    BASE_URL = "https://www.fotocasa.es"
    ZONAS = ZONAS_GEOGRAFICAS

    DETAIL_DELAY_RANGE = (3.0, 6.0)
    SEARCH_DELAY_RANGE = (4.0, 7.0)

    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        zona = self.ZONAS.get(zona_key, {})
        url_path = zona.get("url_path", f"{zona_key}/todas-las-zonas")
        url = f"{self.BASE_URL}/es/comprar/viviendas/particulares/{url_path}/pl"
        if page > 1:
            url = f"{url}/{page}"
        return url

    def run(self) -> Dict[str, Any]:
        from scrapling.fetchers import StealthySession

        if not self.zones:
            self.zones = list(self.ZONAS.keys())

        # Expand composite zones (Fotocasa-specific)
        expanded: List[str] = []
        for z in self.zones:
            info = self.ZONAS.get(z, {})
            if "composite" in info:
                for child in info["composite"]:
                    if child in self.ZONAS:
                        expanded.append(child)
            elif z in self.ZONAS:
                expanded.append(z)
            else:
                logger.warning(f"[{self.PORTAL_NAME}] Zone not found: {z}")
                self.stats["zones_failed"] += 1
        self.zones = expanded

        from datetime import datetime
        logger.info(
            f"[{self.PORTAL_NAME}] Starting scrape | tenant={self.tenant_id} "
            f"zones={self.zones} max_pages={self.max_pages} proxy={'yes' if self.proxy else 'no'}"
        )
        start = datetime.now()

        kwargs = self.get_session_kwargs()
        kwargs["max_pages"] = max(kwargs.get("max_pages", 5), 5)

        with StealthySession(**kwargs) as session:
            for zona_key in self.zones:
                try:
                    self._scrape_zone(session, zona_key)
                    self.stats["zones_completed"] += 1
                except Exception as e:
                    logger.exception(f"[{self.PORTAL_NAME}] zone={zona_key} failed: {e}")
                    self.stats["zones_failed"] += 1
                    self.stats["errors"] += 1

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[{self.PORTAL_NAME}] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"errors={self.stats['errors']} blocked={self.stats['details_blocked']}"
        )
        return self.stats

    # ------------------------------------------------------------------
    # Search-page parsing
    # ------------------------------------------------------------------
    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            html = page.html_content or ""
        except Exception:
            html = ""

        if self._is_geetest(html):
            logger.warning(f"[fotocasa] GeeTest detected on {zona_key} — skipping (v1 no 2Captcha fallback)")
            self.stats["details_blocked"] += 1
            return results

        # Cut off agency listings (Fotocasa shows particulares first, then agencies after a divider)
        html_lower = html.lower()
        divider_pos = len(html)
        for marker in ("anuncios de inmobiliarias", "ver más anuncios", "mira algunos de los anuncios"):
            pos = html_lower.find(marker)
            if 0 < pos < divider_pos:
                divider_pos = pos
        particulares_html = html[:divider_pos]

        # Listing links carry numeric id at the end: /es/comprar/vivienda/<slug>/<id>/d
        links = re.findall(r'href="(/es/comprar/vivienda/[^"]+/(\d{7,})/d)', particulares_html)
        seen = set()
        zona_info = self.ZONAS.get(zona_key, {})

        for href, anuncio_id in links:
            if anuncio_id in seen:
                continue
            seen.add(anuncio_id)
            url_anuncio = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            results.append({
                "anuncio_id": anuncio_id,
                "titulo": "",
                "url_anuncio": url_anuncio,
                "zona_geografica": zona_info.get("nombre", zona_key),
                "zona_busqueda": zona_key,
                "es_particular": True,
                "tipo_inmueble": "piso",
            })

        if not results:
            logger.warning(f"[fotocasa] {zona_key}: no listings found (html={len(html)} bytes)")
        return results

    # ------------------------------------------------------------------
    # Detail-page enrichment
    # ------------------------------------------------------------------
    def parse_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        try:
            html = page.html_content or ""
        except Exception:
            html = ""

        if self._is_geetest(html):
            logger.debug(f"  GeeTest on detail {listing.get('url_anuncio', '')[:60]}")
            self.stats["details_blocked"] += 1
            return listing

        if not html or len(html) < 5000:
            return listing

        # Title
        title_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if title_match:
            listing["titulo"] = title_match.group(1).strip()[:200]

        # Price
        for pattern in (
            r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?',
            r'(\d{1,3}(?:\.\d{3})*)\s*(?:EUR|€)',
            r'class="[^"]*price[^"]*"[^>]*>([^<]+)',
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                price_str = re.sub(r"[^\d]", "", match.group(1))
                if price_str.isdigit() and int(price_str) > 10000:
                    listing["precio"] = float(price_str)
                    break

        # Surface (m2)
        for pattern in (r"<span[^>]*>\s*<span>(\d+)</span>\s*m[²2]", r"(\d+)\s*m[²2]"):
            match = re.search(pattern, html)
            if match:
                val = int(match.group(1))
                if 10 < val < 10000:
                    listing["metros"] = val
                    break

        # Rooms
        for pattern in (r"<span[^>]*>\s*<span>(\d+)</span>\s*hab", r"(\d+)\s*hab"):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                val = int(match.group(1))
                if 0 < val < 50:
                    listing["habitaciones"] = val
                    break

        # Description
        for pattern in (
            r'class="[^"]*(?:Description|description|comment)[^"]*"[^>]*>(.*?)</(?:div|p|section)',
            r'<meta\s+name="description"\s+content="([^"]{50,})"',
        ):
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                desc = re.sub(r"<[^>]+>", " ", match.group(1))
                desc = re.sub(r"\s+", " ", desc).strip()
                if len(desc) > 50:
                    listing["descripcion"] = desc[:2000]
                    break

        # Phone — only from description text (avoid scraping phones from ads/scripts)
        desc = listing.get("descripcion", "") or ""
        phone_match = re.search(
            r"(?:tel|tfno?|movil|llamar?)[\s.:]*(\d[\d\s]{7,12})", desc, re.IGNORECASE
        )
        if not phone_match:
            phone_match = re.search(r"\b(6\d{8}|7\d{8}|9\d{8})\b", desc)
        if phone_match:
            phone = re.sub(r"\s+", "", phone_match.group(1))
            if len(phone) == 9:
                listing["telefono"] = phone
                listing["telefono_norm"] = self.normalize_phone(phone)

        # Photos
        photos_raw = re.findall(
            r"https?://static\.fotocasa\.es/images/[^\"'<>\s]+", html, re.IGNORECASE
        )
        seen, unique_photos = set(), []
        for photo in photos_raw:
            base = re.sub(r"\?.*$", "", photo)
            if base not in seen and len(base) > 50:
                unique_photos.append(base + "?rule=original")
                seen.add(base)
        if unique_photos:
            listing["fotos"] = unique_photos[:10]

        # Particular vs agency
        html_lower = html.lower()
        is_particular = any(
            ind in html_lower
            for ind in ("anuncio particular", "particular_user_icon", "anunciante particular")
        )
        if not is_particular:
            agency_patterns = (r"partner\s+inmobiliario", r"tu\s+agente")
            is_particular = not any(re.search(p, html_lower) for p in agency_patterns)

        listing["es_particular"] = is_particular
        listing["vendedor"] = "Particular" if is_particular else "Agencia"
        listing["verified"] = True
        return listing

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_geetest(html: str) -> bool:
        if not html:
            return False
        return "SENTIMOS LA INTERRUPCI" in html or "geetest" in html.lower()


def main():
    import argparse, os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="+", required=True)
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true", default=True)
    ap.add_argument("--no-postgres", dest="postgres", action="store_false")
    ap.add_argument("--proxy", default=os.environ.get("DATADOME_PROXY", ""))
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = ScraplingFotocasa(
        tenant_id=args.tenant_id,
        zones=args.zones,
        max_pages=args.max_pages,
        save_to_postgres=args.postgres,
        proxy=args.proxy or None,
    )
    stats = s.run()
    print("STATS:", stats)
    try:
        from scrapers.error_handling import log_scraper_run
        log_scraper_run("fotocasa", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

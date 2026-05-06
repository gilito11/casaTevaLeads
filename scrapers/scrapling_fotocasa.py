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
from scrapers.zones.fotocasa import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)


class ScraplingFotocasa(ScraplingBaseScraper):
    PORTAL_NAME = "fotocasa"
    BASE_URL = "https://www.fotocasa.es"
    ZONAS = ZONAS_GEOGRAFICAS

    DETAIL_DELAY_RANGE = (3.0, 6.0)
    SEARCH_DELAY_RANGE = (4.0, 7.0)

    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        # Fotocasa's `/particulares/` URL filter returns an empty SPA shell
        # (no pre-rendered listings). Use the generic search URL — particular
        # vs profesional is detected later via 'Anunciante' label and the agency
        # divider in the HTML.
        zona = self.ZONAS.get(zona_key, {})
        url_path = zona.get("url_path", f"{zona_key}/todas-las-zonas")
        url = f"{self.BASE_URL}/es/comprar/viviendas/{url_path}/l"
        if page > 1:
            url = f"{url}/{page}"
        return url

    def search_page_action(self):
        """Scroll to hydrate lazy-loaded cards, then extract structured data
        from the live DOM (precio/m²/hab live in React-rendered text nodes
        that don't always survive into HTML serialization). Stash JSON in a
        <script id="__SCRAPLING_LISTINGS__"> tag for parse_search_page to read.
        """
        def _hydrate_and_extract(page):
            try:
                for _ in range(8):
                    page.evaluate("window.scrollBy(0, 900)")
                    page.wait_for_timeout(600)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(800)
                # Extract listings via DOM walk + stash as JSON script tag
                page.evaluate(r"""() => {
                    const seen = {};
                    const results = [];
                    document.querySelectorAll('a[href*="/es/comprar/vivienda/"]').forEach(link => {
                        const href = link.getAttribute('href');
                        const m = href.match(/\/(\d{7,})\//);
                        if (!m || seen[m[1]]) return;
                        seen[m[1]] = true;
                        const card = link.closest('article') || link.parentElement;
                        const text = card ? card.textContent.replace(/\s+/g, ' ').trim() : '';
                        results.push({href, id: m[1], text: text.slice(0, 2000)});
                    });
                    let s = document.getElementById('__SCRAPLING_LISTINGS__');
                    if (!s) {
                        s = document.createElement('script');
                        s.id = '__SCRAPLING_LISTINGS__';
                        s.type = 'application/json';
                        document.body.appendChild(s);
                    }
                    s.textContent = JSON.stringify(results);
                }""")
            except Exception:
                pass
        return _hydrate_and_extract

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

        zona_info = self.ZONAS.get(zona_key, {})

        # Preferred path: read structured listings stashed by search_page_action
        # via JS DOM extraction. Each entry has {href, id, text} where text
        # is the full card textContent post-hydration (precio, m², hab, vendedor).
        m = re.search(
            r'<script[^>]*id="__SCRAPLING_LISTINGS__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if m:
            try:
                import json as _json
                items = _json.loads(m.group(1)) or []
                logger.info(f"[fotocasa] {zona_key}: extracted {len(items)} items via JS DOM")
                for item in items:
                    listing = self._listing_from_card_text(item, zona_key, zona_info)
                    if listing:
                        results.append(listing)
                if results:
                    return results  # JS path won; skip HTML fallback
            except Exception as e:
                logger.warning(f"[fotocasa] JS-stashed listings parse error: {e}")

        # Fallback path: regex over server-rendered HTML (only ~2 cards visible)
        # Cut off agency listings (Fotocasa shows particulares first)
        html_lower = html.lower()
        divider_pos = len(html)
        for marker in ("anuncios de inmobiliarias", "ver más anuncios", "mira algunos de los anuncios"):
            pos = html_lower.find(marker)
            if 0 < pos < divider_pos:
                divider_pos = pos
        particulares_html = html[:divider_pos]

        links = re.findall(r'href="(/es/comprar/vivienda/[^"]+/(\d{7,})/d)', particulares_html)
        seen = set()

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
    # Helpers
    # ------------------------------------------------------------------
    # Spanish agency suffixes / patterns inside the rendered card text
    _AGENCY_NAME_RE = re.compile(
        r"\b(s\.?l\.?|s\.?a\.?|inmobiliaria|inmueble|inmuebles|inmofactory|fincas|"
        r"agencia|agency|gestor|asesor|properties|properti|partners?|grupo|"
        r"servicios inmobiliarios|imm?obili[a-z]*)\b",
        re.IGNORECASE,
    )

    def _listing_from_card_text(self, item: Dict[str, str], zona_key: str, zona_info: dict):
        """Convert a {href, id, text} entry from the JS DOM extraction into
        a full listing dict with precio/m²/hab/vendedor parsed out of text.
        """
        href = item.get("href") or ""
        anuncio_id = item.get("id") or ""
        text = item.get("text") or ""
        if not anuncio_id or not href or not text:
            return None

        # Skip "obra-nueva" promotional links (developer projects, not particular)
        if "/vivienda/obra-nueva/" in href:
            return None

        # Price: prefer the first standalone X.XXX € or XXX.XXX € that's > 10000
        precio = None
        for raw in re.findall(r"(\d{1,4}[.,]\d{3}(?:[.,]\d{3})?)\s*€", text):
            try:
                v = float(raw.replace(".", "").replace(",", "."))
                # Sanity: must be a real property price (10k–10M)
                if 10_000 < v < 10_000_000:
                    precio = v
                    break
            except Exception:
                pass

        # Surface: <number> m² / m2 — INT (dbt stg_fotocasa casts to INTEGER)
        metros = None
        m2_m = re.search(r"(\d{2,4})\s*m[²2]", text)
        if m2_m:
            try:
                metros = int(m2_m.group(1))
            except Exception:
                pass

        # Bedrooms: <number> habs / hab
        habitaciones = None
        hab_m = re.search(r"(\d+)\s*hab", text)
        if hab_m:
            try:
                habitaciones = int(hab_m.group(1))
            except Exception:
                pass

        # Particular vs Profesional. Fotocasa shows agency branding badges:
        # "Calidad Fotocasa", "Tu partner inmobiliario", "Top+", "Pro+"
        # are signals of a PAID agency account. "Tu agente" is the particular
        # widget (NOT an agency marker). Plain corporate suffixes (S.L., S.A.)
        # in the visible card text also identify agencies.
        es_particular = True
        vendedor = ""
        agency_signals = [
            "Calidad Fotocasa",
            "Tu partner inmobiliario",
            "Top+",
            "Pro+",
            "Anunciante: Profesional",
        ]
        if any(sig in text for sig in agency_signals):
            es_particular = False
        elif re.search(r"\b(S\.?L\.?|S\.?A\.?|S\.?L\.?U\.?)\b", text):
            es_particular = False

        # Extract clean agency name: prefer ALL-CAPS chunk before "·" separator.
        # If extraction is messy, leave empty rather than save garbage substring.
        if not es_particular:
            ag_m = re.search(r"([A-ZÁÉÍÓÚÑ]{2,}[A-ZÁÉÍÓÚÑ\s'\-\.]{2,40}[A-ZÁÉÍÓÚÑ])\s*(?:[·•]|inmobiliaria|IMMOBILIARIA|S\.?L\.?|S\.?A\.?)", text)
            if ag_m:
                cand = re.sub(r"\s+", " ", ag_m.group(1).strip())
                if 3 <= len(cand) <= 80 and not cand.isdigit():
                    vendedor = cand[:120]
        elif "Particular" in text:
            vendedor = "Particular"

        # Title fallback from text (something like "Apartamento en Carrer ...")
        titulo = ""
        title_m = re.search(
            r"(Apartamento|Piso|Casa|Chalet|D[uú]plex|[ÁA]tico|Loft|Estudio|Vivienda)\s+(?:en|de)\s+([^|·]{5,150})",
            text,
        )
        if title_m:
            titulo = (title_m.group(1) + " " + title_m.group(2)).strip()[:200]

        # Strip query params (`?from=list&isGalleryOpen=true&...`) — they
        # come from the gallery widget and trigger HTTP 405 on the detail page.
        clean_href = href.split("?", 1)[0]
        url_anuncio = clean_href if clean_href.startswith("http") else f"{self.BASE_URL}{clean_href}"

        return {
            "anuncio_id": anuncio_id,
            "titulo": titulo,
            "precio": precio,
            "habitaciones": habitaciones,
            "metros": metros,
            "url_anuncio": url_anuncio,
            "zona_geografica": zona_info.get("nombre", zona_key),
            "zona_busqueda": zona_key,
            "es_particular": es_particular,
            "vendedor": vendedor,
            "tipo_inmueble": "piso",
        }

    def _wants_detail(self) -> bool:
        # Fotocasa detail pages reliably return HTTP 405 (server rejects GET on
        # the detail URL pattern, even after stripping query params). The
        # search-page JS DOM extraction already gives us titulo/precio/m²/hab/
        # vendedor/es_particular — skip detail entirely.
        return False

    # ------------------------------------------------------------------
    # Detail-page enrichment (kept for fallback / future re-enable)
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
    ap.add_argument("--proxy", default="", help="Optional proxy http://user:pass@host:port (Scrapling does not need a proxy)")
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

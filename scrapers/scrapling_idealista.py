"""
Idealista scraper basado en Scrapling.

Replaces camoufox_idealista.py — bypassa DataDome SIN proxy gracias a
Patchright + StealthySession (cookies persistentes).

Probado contra:
- Búsqueda: 30 articles, HTML 688KB, 200 OK
- Detalle: precio extraído (€288.000, €325.000, €189.000) tras warmup en search
"""
import logging
import re
from typing import Any, Dict, List, Optional

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.zones.idealista import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)


class ScraplingIdealista(ScraplingBaseScraper):
    PORTAL_NAME = "idealista"
    BASE_URL = "https://www.idealista.com"
    ZONAS = ZONAS_GEOGRAFICAS

    # Idealista needs a slightly longer humanize delay between detail fetches
    DETAIL_DELAY_RANGE = (3.0, 6.0)
    SEARCH_DELAY_RANGE = (5.0, 9.0)

    # DataDome (idealista) flags the browser as bot if ANY of disable_resources,
    # block_ads or blocked_domains is enabled — even one of them shifts the
    # network/timing fingerprint enough to trigger a 403 on the first request.
    # Verified 26 May 2026: with all three on → 403; all three off → 200.
    # Bandwidth cost vs the other 3 portals is higher but unavoidable for now.
    SESSION_KWARGS = {
        **ScraplingBaseScraper.SESSION_KWARGS,
        "disable_resources": False,
        "block_ads": False,
        "blocked_domains": set(),
    }

    def should_skip(self, listing: Dict[str, Any]) -> bool:
        # Save both Particular and Profesional cards. Filtering happens in dbt
        # staging via raw_data->>'es_particular'. Skipping pre-detail loses
        # data we may want for future agency-detection improvements.
        precio = listing.get("precio")
        if precio is not None and precio < 10000:
            return True
        return False

    def detail_page_action(self):
        """Click the 'Ver teléfono' button so the phone number is revealed in
        the DOM by the time `page.html_content` is read. Idealista hides the
        number behind a click via JS — without this, parse_detail_page can
        never see a `tel:` link.
        """
        def _reveal_phone(page):
            # Brief settle before interacting
            try:
                page.wait_for_timeout(500)
            except Exception:
                pass
            for selector in (
                'button.see-phones-btn',
                'a.see-phones-btn',
                '.hidden-contact-phones_link',
                'button:has-text("Ver teléfono")',
                'a:has-text("Ver teléfono")',
            ):
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click(timeout=3000)
                        page.wait_for_timeout(1500)
                        return
                except Exception:
                    continue
        return _reveal_phone

    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        zona = self.ZONAS[zona_key]
        url = f"{self.BASE_URL}/venta-viviendas/{zona['url_path']}/"
        if page > 1:
            url = url.rstrip("/") + f"/pagina-{page}.htm"
        return url

    # ------------------------------------------------------------------
    # Search-page parsing
    # ------------------------------------------------------------------
    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        # Multiple selectors — idealista changes HTML frequently
        articles = (
            page.css("article.item")
            or page.css("article[data-element-id]")
            or page.css(".items-container article")
            or []
        )
        if not articles:
            logger.warning(f"[idealista] {zona_key}: no articles found")
            return results

        zona_info = self.ZONAS.get(zona_key, {})
        for art in articles:
            try:
                listing = self._parse_card(art, zona_key, zona_info)
                if listing:
                    results.append(listing)
            except Exception as e:
                logger.debug(f"  card parse error: {e}")
        return results

    def _parse_card(self, art, zona_key: str, zona_info: dict) -> Optional[Dict[str, Any]]:
        # Skip "nearby suggestion" cards from neighboring zones — not real listings
        cls = art.attrib.get("class", "")
        if "geo-reach-card" in cls:
            return None
        link_list = art.css("a.item-link")
        if not link_list:
            return None
        link = link_list[0]
        href = link.attrib.get("href", "")
        if not href:
            return None

        m = re.search(r"/inmueble/(\d+)/", href) or re.search(r"-(\d+)\.htm", href)
        if not m:
            return None
        anuncio_id = m.group(1)

        # Professional indicators on listing card (logo branding, agency icon)
        try:
            html = art.html_content
        except Exception:
            html = ""
        is_professional = "logo-branding" in html or "item-not-clickable-logo" in html

        # Title can be in the link or in .item-title
        title_el = art.css(".item-title") or art.css("h3")
        titulo = (title_el[0].text.clean() if title_el else "").strip() or link.attrib.get(
            "title", ""
        )

        precio = None
        price_el = art.css(".item-price") or art.css("span.item-price")
        if price_el:
            precio = self.parse_price(price_el[0].text.clean())

        habitaciones = None
        metros = None
        # Idealista renders one <span class="item-detail"> per feature
        # (hab, m², planta). Concatenate all.
        detail_text = " ".join(
            (el.text.clean() if hasattr(el, "text") else el.get_all_text() or "")
            for el in (art.css(".item-detail") or [])
        )
        if detail_text:
            rooms_m = re.search(r"(\d+)\s*hab", detail_text, re.I)
            if rooms_m:
                habitaciones = int(rooms_m.group(1))
            m2_m = re.search(r"(\d+)\s*m[²2]", detail_text)
            if m2_m:
                metros = float(m2_m.group(1))

        desc_el = art.css(".item-description") or art.css(".ellipsis")
        descripcion = desc_el[0].text.clean() if desc_el else ""

        loc_el = art.css(".item-location")
        ubicacion = loc_el[0].text.clean() if loc_el else ""

        url_anuncio = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        return {
            "anuncio_id": anuncio_id,
            "titulo": titulo[:200].strip(),
            "precio": precio,
            "habitaciones": habitaciones,
            "metros": metros,
            "descripcion": descripcion[:500].strip(),
            "ubicacion": ubicacion[:200].strip(),
            "zona_geografica": zona_info.get("nombre", zona_key),
            "zona_busqueda": zona_key,
            "url_anuncio": url_anuncio,
            "es_particular": not is_professional,
            "tipo_inmueble": "piso",
        }

    # ------------------------------------------------------------------
    # Detail-page enrichment
    # ------------------------------------------------------------------
    def parse_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich listing with description, photos, advertiser type, location."""
        try:
            html = page.html_content or ""
        except Exception:
            html = ""
        if not html or len(html) < 50000:
            return listing  # likely soft-blocked, keep search-page data

        # Detail-page Profesional detection — three highly reliable signals:
        #   1) <div class="professional-name"> block (sidebar advertiser card)
        #   2) <a href="/pro/<slug>/"> agency link (only agencies have a /pro/ profile)
        #   3) <input name="professional"> hidden form input
        # Any of these → professional. Otherwise keep card-level classification.
        is_pro = False
        try:
            if page.css(".professional-name"):
                is_pro = True
            elif re.search(r'href="/pro/[a-z0-9_-]+/?"', html, re.IGNORECASE):
                is_pro = True
            elif re.search(r'<input[^>]+name="professional"', html, re.IGNORECASE):
                is_pro = True
        except Exception:
            pass
        if is_pro:
            listing["es_particular"] = False

        # Capture advertiser/agency name when available (overrides empty card-level)
        try:
            adv_link = page.css('a.about-advertiser-name')
            if adv_link:
                name = (adv_link[0].text.clean() or "").strip()
                if name:
                    listing["vendedor"] = name[:120]
        except Exception:
            pass

        listing["verified"] = True

        # 2) Full description
        try:
            desc_blocks = page.css(".comment") + page.css(".adCommentsLanguage")
            if desc_blocks:
                full = desc_blocks[0].get_all_text() or ""
                if len(full) > len(listing.get("descripcion", "")):
                    listing["descripcion"] = full[:2000].strip()
        except Exception:
            pass

        # 3) Photos via regex (img3/img4.idealista.com)
        try:
            photos = sorted(set(
                re.findall(
                    r"https://img[34]\.idealista\.com/[^\"'<>\s]+\.(?:jpg|jpeg|png|webp)",
                    html,
                    re.IGNORECASE,
                )
            ))
            if photos:
                listing["fotos"] = photos[:30]
        except Exception:
            pass

        # 4) Phone — page_action `_reveal_phone` clicks "Ver teléfono" before
        # HTML is captured, so the tel: link is visible in `html` here.
        try:
            phones = re.findall(r"tel:(?:\+?34)?([679]\d{8})", html)
            if not phones:
                # Fallback: phone may be embedded in adProperties JSON or data-phone attrs
                phones = re.findall(r'data-phone="([679]\d{8})"', html)
            if phones:
                listing["telefono"] = phones[0]
                listing["telefono_norm"] = self.normalize_phone(phones[0])
        except Exception:
            pass

        return listing


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
    s = ScraplingIdealista(
        tenant_id=args.tenant_id,
        zones=args.zones,
        max_pages=args.max_pages,
        save_to_postgres=args.postgres,
        proxy=args.proxy or None,
    )
    stats = s.run()
    print("STATS:", stats)
    # Log run
    try:
        from scrapers.error_handling import log_scraper_run
        log_scraper_run("idealista", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

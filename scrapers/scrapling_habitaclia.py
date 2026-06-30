"""
Habitaclia scraper basado en Scrapling.

Replaces camoufox_habitaclia.py — bypassa Imperva/Incapsula SIN proxy gracias a
Patchright + StealthySession (cookies persistentes).
"""
import logging
import re
from typing import Any, Dict, List, Optional

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.zones.habitaclia import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)


def _extract_phone_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    clean = text.replace(" ", "").replace(".", "").replace("-", "").replace("/", "")
    phones = re.findall(r"[679]\d{8}", clean)
    BLACKLIST = {
        "666666666", "777777777", "999999999", "600000000",
        "700000000", "900000000", "123456789", "987654321",
    }
    for p in phones:
        if p not in BLACKLIST and len(set(p)) > 2:
            return p
    return None


class ScraplingHabitaclia(ScraplingBaseScraper):
    PORTAL_NAME = "habitaclia"
    BASE_URL = "https://www.habitaclia.com"
    ZONAS = ZONAS_GEOGRAFICAS

    DETAIL_DELAY_RANGE = (2.0, 5.0)
    SEARCH_DELAY_RANGE = (3.0, 6.0)

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------
    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        zona = self.ZONAS[zona_key]
        slug = zona["url_slug"]
        is_province = zona.get("is_province", False)

        if is_province:
            base = f"{self.BASE_URL}/viviendas-{slug}.htm"
            paged = f"{self.BASE_URL}/viviendas-{slug}-pag{page}.htm"
        elif self.only_private:
            base = f"{self.BASE_URL}/viviendas-particulares-{slug}.htm"
            paged = f"{self.BASE_URL}/viviendas-particulares-{slug}-pag{page}.htm"
        else:
            base = f"{self.BASE_URL}/viviendas-{slug}.htm"
            paged = f"{self.BASE_URL}/viviendas-{slug}-pag{page}.htm"

        return paged if page > 1 else base

    # ------------------------------------------------------------------
    # Search-page parsing (regex on full HTML — más fiable en habitaclia)
    # ------------------------------------------------------------------
    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        try:
            html = page.html_content or ""
        except Exception:
            html = ""

        if not html:
            logger.warning(f"[habitaclia] {zona_key}: empty HTML")
            return []

        zona_info = self.ZONAS.get(zona_key, {})
        zone_name = zona_info.get("nombre", zona_key)

        # Composite zones don't have url_slug → caller should pass child keys instead.
        # Here we just extract listing links from whatever HTML we got.
        links = re.findall(
            r'href="(https://www\.habitaclia\.com/comprar-(?:piso|casa|chalet|vivienda)[^"]+\.htm)[^"]*"',
            html,
        )
        links = list(dict.fromkeys(links))
        links = [l for l in links if "vistamapa" not in l and "-i" in l]
        logger.info(f"[habitaclia] {zona_key}: found {len(links)} listing links")

        results: List[Dict[str, Any]] = []
        for url in links[:30]:
            m = re.search(r"-i(\d{6,})", url)
            if not m:
                continue
            results.append({
                "anuncio_id": m.group(1),
                "url_anuncio": url,
                "tipo_inmueble": "piso",
                "zona_busqueda": zone_name,
                "zona_geografica": zone_name,
                "es_particular": True,  # provisional; verified on detail page
            })
        return results

    # ------------------------------------------------------------------
    # Detail-page enrichment
    # ------------------------------------------------------------------
    def parse_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        try:
            html = page.html_content or ""
        except Exception:
            html = ""
        if not html or len(html) < 5000:
            return listing

        # Guard anti-redirección: un anuncio retirado redirige a una página de
        # buscador ("Viviendas en Tarragona") que contiene OTROS anuncios
        # destacados. Su <title> NO tiene el patrón "... por <precio> €". Si no
        # lo tiene, no es la ficha real → no enriquecer (evita coger precio/datos
        # de un anuncio ajeno, p.ej. el bug del "sim-price" a 850.000 €).
        title_guard = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        if not title_guard or not re.search(
            r"\bpor\s+\d{1,3}(?:\.\d{3})*", title_guard.group(1), re.IGNORECASE
        ):
            return listing

        # Title
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if m:
            listing["titulo"] = m.group(1).strip()[:200]

        # Price — el <title> ("Piso por 165.000 € de ...") es la fuente más fiable
        # del precio DEL anuncio. OJO: la página incluye anuncios similares con
        # class="sim-price" (otro piso, otro precio); hay que excluirlos.
        precio = None
        tt = re.search(
            r"<title>[^<]*?\bpor\s+(\d{1,3}(?:\.\d{3})*)\b",
            html, re.IGNORECASE,
        )
        if tt:
            precio = float(tt.group(1).replace(".", ""))
        if precio is None:
            fc = re.search(
                r'class="[^"]*feature-container[^"]*"[^>]*>(.*?)</(?:ul|div)>',
                html, re.DOTALL | re.IGNORECASE,
            )
            if fc:
                pm = re.search(r"(\d{1,3}(?:\.\d{3})*)\s*€(?!/)", fc.group(1))
                if pm:
                    precio = float(pm.group(1).replace(".", ""))
        if precio is None:
            # class que contenga "price" pero NO "sim" (sim-price = anuncio similar)
            ph = re.search(
                r'class="(?![^"]*sim)[^"]*price[^"]*"[^>]*>[\s]*(\d{1,3}(?:\.\d{3})*)\s*€',
                html, re.IGNORECASE,
            )
            if ph:
                precio = float(ph.group(1).replace(".", ""))
        if precio is None:
            tp = re.search(r"por\s+(\d{1,3}(?:\.\d{3})*)\s*€", html, re.IGNORECASE)
            if tp:
                precio = float(tp.group(1).replace(".", ""))
        if precio is not None:
            listing["precio"] = precio

        # Rooms
        habs = re.search(r"<li>(\d+)\s*habitacion", html, re.IGNORECASE)
        if habs:
            listing["habitaciones"] = int(habs.group(1))

        # Size
        m2 = re.search(r"<li>Superficie\s*(\d+)(?:&nbsp;|\s)*m", html, re.IGNORECASE)
        if m2:
            listing["metros"] = int(m2.group(1))
        else:
            m2b = re.search(r"de\s+(\d+)\s+metros", html, re.IGNORECASE)
            if m2b:
                listing["metros"] = int(m2b.group(1))

        # Bathrooms
        b = re.search(r"<li>(\d+)\s*Ba[ñn]o", html, re.IGNORECASE)
        if b:
            listing["banos"] = int(b.group(1))

        # Location
        loc = re.search(r'class="[^"]*location[^"]*"[^>]*>([^<]+)', html, re.IGNORECASE)
        if loc:
            listing["ubicacion"] = loc.group(1).strip()[:200]

        # Description — prefer detail-description, fallback to <meta name="description">
        descripcion = ""
        dd = re.search(
            r'<p[^>]*class="[^"]*detail-description[^"]*"[^>]*>(.*?)</p>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if dd:
            txt = re.sub(r"<[^>]+>", "\n", dd.group(1))
            descripcion = re.sub(r"\n+", "\n", txt).strip()
        if not descripcion:
            md = re.search(
                r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                html, re.IGNORECASE,
            )
            if md:
                descripcion = md.group(1).strip()
        if descripcion:
            listing["descripcion"] = descripcion[:2000]

        # Phone — description first, then tel: links
        phone = _extract_phone_from_text(listing.get("descripcion", ""))
        if not phone:
            tl = re.search(r'href="tel:(?:\+?34)?([679]\d{8})"', html)
            if tl:
                phone = tl.group(1)
        if phone:
            listing["telefono"] = phone
            listing["telefono_norm"] = self.normalize_phone(phone)

        # Photos (habimg.com)
        photos = re.findall(
            r"(?:https?:)?//images\.habimg\.com/[^\"'<>\s]+\.(?:jpg|jpeg|png|webp)",
            html, re.IGNORECASE,
        )
        unique: List[str] = []
        seen = set()
        for ph in photos:
            if ph.startswith("//"):
                ph = "https:" + ph
            if "logo" in ph.lower():
                continue
            idm = re.search(
                r"/(?:imgh|thumb)/(\d+-\d+)/([^/]+?)(?:_(?:XXL|XL|L|M|S|T))?\.(?:jpg|jpeg|png|webp)$",
                ph, re.IGNORECASE,
            )
            if idm:
                uid = f"{idm.group(1)}/{idm.group(2)}"
                if uid not in seen:
                    seen.add(uid)
                    unique.append(
                        f"https://images.habimg.com/imgh/{idm.group(1)}/{idm.group(2)}_XXL.jpg"
                    )
        if unique:
            listing["fotos"] = unique[:10]

        # Particular vs agency (verified on detail)
        agency = re.search(
            r'class="[^"]*(?:agent|agency|professional|inmobiliaria)[^"]*"',
            html, re.IGNORECASE,
        )
        listing["es_particular"] = not bool(agency)
        listing["vendedor"] = "Inmobiliaria" if agency else "Particular"
        listing["verified"] = True

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
    ap.add_argument("--proxy", default="")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = ScraplingHabitaclia(
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
        log_scraper_run("habitaclia", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

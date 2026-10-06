"""
Habitaclia scraper basado en Scrapling.

Replaces camoufox_habitaclia.py — bypassa Imperva/Incapsula SIN proxy gracias a
Patchright + StealthySession (cookies persistentes).
"""
import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.zones.habitaclia import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)

_TIPO = {
    "flat": "piso", "apartment": "piso", "penthouse": "piso", "duplex": "piso",
    "studio": "piso", "loft": "piso", "house": "casa", "chalet": "casa",
    "detachedHouse": "casa", "semidetachedHouse": "casa", "terracedHouse": "casa",
    "rusticHouse": "casa", "countryHouse": "casa", "villa": "casa",
}


def _norm_muni(name: Optional[str]) -> str:
    """'Lleida Capital' / 'Albatàrrec' -> 'lleida' / 'albatarrec'."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"\s+capital$", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._list_urls: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------
    # Desde el 15 Sep 2026 habitaclia corre sobre la plataforma de fotocasa
    # (Adevinta): /viviendas-particulares-<slug>.htm redirige (301) a
    # /comprar/viviendas/<provincia>-provincia/<municipio>/particulares/s y la
    # pagina N es <esa url>/N. La p1 usa la URL antigua (la redireccion resuelve
    # provincia y slug nuevo, p.ej. lleida -> lleida-capital); las siguientes,
    # la URL canonica que trae el propio JSON de la p1.
    def build_search_url(self, zona_key: str, page: int = 1) -> Optional[str]:
        if page > 1:
            list_url, total_pages = self._list_urls.get(zona_key, (None, 0))
            if not list_url or page > total_pages:
                return None
            return f"{self.BASE_URL}{list_url}/{page}"

        zona = self.ZONAS[zona_key]
        slug = zona["url_slug"]
        if zona.get("is_province") or not self.only_private:
            return f"{self.BASE_URL}/viviendas-{slug}.htm"
        return f"{self.BASE_URL}/viviendas-particulares-{slug}.htm"

    def _wants_detail(self) -> bool:
        # El JSON del listado ya trae telefono, email, precio, m2, fotos,
        # descripcion, coordenadas y publisher.isAgent: la ficha no aporta.
        return False

    # ------------------------------------------------------------------
    # Search-page parsing (window.__INITIAL_PROPS__)
    # ------------------------------------------------------------------
    @staticmethod
    def _initial_props(html: str) -> Optional[dict]:
        m = re.search(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\((".*?")\);', html, re.S)
        if not m:
            return None
        try:
            return json.loads(json.loads(m.group(1)))
        except ValueError:
            return None

    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        try:
            html = page.html_content or ""
        except Exception:
            html = ""

        props = self._initial_props(html) if html else None
        ctx = ((props or {}).get("initialSearchResultsPage") or {}).get("initialSearchContext")
        if not ctx:
            # Sin JSON = cambio de plantilla o bloqueo: es un error, no "0 anuncios".
            logger.error(f"[habitaclia] {zona_key}: sin __INITIAL_PROPS__ (html={len(html)} bytes)")
            self.stats["errors"] += 1
            return []

        geo = ctx.get("geography") or {}
        results = ctx.get("results") or {}
        pag = results.get("pagination") or {}
        if pag.get("page", 1) == 1:
            self._list_urls[zona_key] = (
                (ctx.get("urls") or {}).get("list"), int(pag.get("totalPages") or 0)
            )

        zone_name = self.ZONAS.get(zona_key, {}).get("nombre", zona_key)
        # Solo se corrige la zona con busquedas por municipio: en una de distrito
        # (Chamartin) el municipio del anuncio (Madrid) no es la zona buscada.
        searched = _norm_muni(geo.get("name")) if geo.get("layer") == "municipality" else ""
        items = results.get("items") or []
        logger.info(
            f"[habitaclia] {zona_key}: {geo.get('layer')}/{geo.get('slug')} "
            f"p{pag.get('page')}/{pag.get('totalPages')} total={pag.get('totalCount')} items={len(items)}"
        )
        return [l for l in (self._item_to_listing(i, zone_name, searched) for i in items) if l]

    def _item_to_listing(self, item: dict, zone_name: str, searched: str) -> Optional[Dict[str, Any]]:
        # legacyNumericId = el id -i<num>.htm de la web antigua: mantiene el
        # upsert sobre los anuncios ya capturados.
        anuncio_id = str(item.get("legacyNumericId") or item.get("id") or "").strip()
        nav = item.get("navigationUrl") or (item.get("urls") or {}).get("canonical")
        if not anuncio_id or not nav:
            return None
        tx = item.get("transaction") or {}
        if tx.get("type") not in (None, "buy"):
            return None

        summary = item.get("summary") or {}
        prop = item.get("property") or {}
        loc = summary.get("location") or {}
        coords = loc.get("coordinates") or {}
        publisher = summary.get("publisher") or {}
        contact = item.get("contact") or {}
        price = tx.get("price") or {}
        precio = None if price.get("hidden") else price.get("amount")

        # Municipio real: si no es el buscado manda el real (la web antigua
        # "sangraba" pisos de Lleida capital en las busquedas de pueblos vecinos).
        municipio = re.sub(r"\s+capital$", "", (loc.get("municipality") or "").strip(), flags=re.I)
        zona = zone_name
        if municipio and searched and _norm_muni(municipio) != searched:
            zona = municipio

        es_agencia = bool(publisher.get("isAgent") or publisher.get("tradeName"))
        descripcion = (summary.get("description") or "").strip()[:2000]
        listing: Dict[str, Any] = {
            "anuncio_id": anuncio_id,
            "url_anuncio": f"{self.BASE_URL}{nav}",
            "titulo": (summary.get("title") or "").strip()[:200],
            "descripcion": descripcion,
            "precio": float(precio) if precio else None,
            "habitaciones": prop.get("rooms"),
            "banos": prop.get("bathrooms"),
            "metros": int(prop.get("builtSurface") or 0) or None,
            # None si el tipo no es vivienda conocida: dbt tira del titulo
            "tipo_inmueble": _TIPO.get(prop.get("propertyType")),
            "direccion": ", ".join(x for x in (loc.get("displayAddressLine"), loc.get("displayZoneLine")) if x),
            "municipio": municipio or None,
            "latitud": coords.get("latitude"),
            "longitud": coords.get("longitude"),
            "zona_busqueda": zona,
            "zona_geografica": zona,
            "email": contact.get("email"),
            "fotos": [i["url"] for i in ((summary.get("multimedia") or {}).get("images") or []) if i.get("url")][:10],
            "es_particular": not es_agencia,
            "vendedor": publisher.get("tradeName") or ("Inmobiliaria" if es_agencia else "Particular"),
            "verified": True,
        }
        phone = re.sub(r"^34(?=\d{9}$)", "", re.sub(r"\D", "", contact.get("phone") or ""))
        phone = phone or _extract_phone_from_text(descripcion)
        if phone:
            listing["telefono"] = phone
            listing["telefono_norm"] = self.normalize_phone(phone)
        return listing

    # ------------------------------------------------------------------
    # Detail-page enrichment
    # ------------------------------------------------------------------
    def parse_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Ficha nueva (/.../<uuid>/d): __INITIAL_PROPS__.listing tiene el mismo
        esquema que los items del listado. Un anuncio retirado redirige al
        buscador (__INITIAL_PROPS__.initialSearchResultsPage): se marca
        listing["retirado"] = True para que lead_refresher lo dé de baja."""
        try:
            html = page.html_content or ""
        except Exception:
            html = ""
        props = self._initial_props(html) if html else None
        if not props:
            return listing
        if "initialSearchResultsPage" in props and "listing" not in props:
            listing["retirado"] = True
            return listing
        item = props.get("listing")
        if not isinstance(item, dict):
            return listing
        zona = listing.get("zona_busqueda") or listing.get("zona_geografica") or ""
        parsed = self._item_to_listing(item, zona, _norm_muni(zona))
        if parsed:
            listing.update({k: v for k, v in parsed.items() if v not in (None, "", [])})
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

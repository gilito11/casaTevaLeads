"""
Wallapop scraper basado en Scrapling.

Wallapop usa Next.js con SSR: la vertical de inmobiliaria
`/inmobiliaria/<slug>` renderiza los anuncios server-side dentro del script
`__NEXT_DATA__` (no hay XHR a la API que interceptar). Parseamos ese JSON,
igual que el scraper de milanuncios hace con `__INITIAL_PROPS__`.

Ruta de los anuncios:  props.pageProps.seoLandingData.items  (≈80 por zona)
Cada item trae: id, title, description, price, categoryId (200=inmobiliaria),
seller{userName,...}, slugId, itemRealEstate{rooms,surface,...}, images.

Detección de profesional / inmobiliaria camuflada (p.ej. **yaencontre**):
- flag profesional del seller cuando exista (professional / kind / type)
- nombre del vendedor (seller.userName) contra patrones de agencia (yaencontre,
  .com, inmobiliaria, fincas, s.l./s.a., real estate, gestión, promotora,
  redpiso, tecnocasa, remax, century21, housfy, ...)
- "Ref:" al inicio de la descripción / frases de agencia
La capa dbt (stg_wallapop.sql) repite estos filtros como segunda barrera.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.zones.wallapop import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)

# Patrones de nombre de vendedor que delatan una inmobiliaria/profesional.
_AGENCY_NAME_RE = re.compile(
    r"(yaencontre|ya\s*encontr|inmobiliari|inmoblil|inmuebles?|fincas|finques|"
    r"agencia|agency|real\s*estate|properties|property|propiedad|gestion|"
    r"gesti[oó]n|gestora|gestor[ií]a|asesor|consult|promotora|promocion|"
    r"realty|homes|housfy|housell|tecnocasa|redpiso|red\s*piso|engel|"
    r"re\s*/?\s*max|remax|century\s*21|alfa\s*inmob|comprarcasa|grupo\s|"
    r"servicios?\s*inmobiliari|\bs\.?l\.?\b|\bs\.?a\.?\b|\.com\b|\.es\b|"
    r"administracion|administraci[oó]n|patrimoni|inversion)",
    re.IGNORECASE,
)

# Frases de agencia dentro de título/descripción.
_AGENCY_TEXT_RE = re.compile(
    r"(^\s*ref[:.\s]|nuestra\s+(agencia|inmobiliaria)|nuestro\s+despacho|"
    r"ll[aá]menos|contacte\s+con\s+nosotros|exclusiva\s+de\s+nuestra|"
    r"financiaci[oó]n\s+a\s+medida|gestionamos\s+(su|tu)\s+hipoteca)",
    re.IGNORECASE,
)


class ScraplingWallapop(ScraplingBaseScraper):
    PORTAL_NAME = "wallapop"
    BASE_URL = "https://es.wallapop.com"
    ZONAS = ZONAS_GEOGRAFICAS

    DETAIL_DELAY_RANGE = (2.0, 4.0)
    SEARCH_DELAY_RANGE = (4.0, 7.0)

    # SSR: el HTML inicial ya trae __NEXT_DATA__. Desactivamos los controles de
    # ancho de banda (como fotocasa) para no interferir con la hidratación/render.
    SESSION_KWARGS = {
        **ScraplingBaseScraper.SESSION_KWARGS,
        "disable_resources": False,
        "block_ads": False,
        "blocked_domains": set(),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._done_zones: set = set()

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------
    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        zona = self.ZONAS.get(zona_key, {})
        slug = zona.get("slug", "")
        return f"{self.BASE_URL}/inmobiliaria/{slug}" if slug else f"{self.BASE_URL}/inmobiliaria"

    # ------------------------------------------------------------------
    # __NEXT_DATA__ extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_next_data(html: str) -> Optional[Dict[str, Any]]:
        if not html:
            return None
        m = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL,
        )
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception as e:
            logger.debug(f"[wallapop] __NEXT_DATA__ decode failed: {e}")
            return None

    @staticmethod
    def _items_from_next_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ruta conocida: props.pageProps.seoLandingData.items. Con fallback a
        otras ubicaciones por si Wallapop cambia el shape."""
        try:
            page_props = (data.get("props") or {}).get("pageProps") or {}
        except Exception:
            return []
        for path in ("seoLandingData", "searchData", "listingData"):
            block = page_props.get(path)
            if isinstance(block, dict) and isinstance(block.get("items"), list):
                return block["items"]
        # Fallback genérico: buscar la primera lista de items con id+title
        return ScraplingWallapop._deep_find_items(page_props)

    @staticmethod
    def _deep_find_items(obj: Any, _depth: int = 0) -> List[Dict[str, Any]]:
        if _depth > 8 or obj is None:
            return []
        if isinstance(obj, list):
            if obj and isinstance(obj[0], dict):
                k = set(obj[0].keys())
                if ("id" in k or "itemId" in k) and (k & {"title", "price"}):
                    return obj
            for x in obj[:5]:
                r = ScraplingWallapop._deep_find_items(x, _depth + 1)
                if r:
                    return r
        elif isinstance(obj, dict):
            for v in obj.values():
                r = ScraplingWallapop._deep_find_items(v, _depth + 1)
                if r:
                    return r
        return []

    # ------------------------------------------------------------------
    # Parse search page
    # ------------------------------------------------------------------
    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        # Una sola navegación por zona basta (SSR trae ~80 items).
        if zona_key in self._done_zones:
            return []
        self._done_zones.add(zona_key)

        try:
            html = page.html_content or ""
        except Exception:
            html = ""

        data = self._extract_next_data(html)
        items = self._items_from_next_data(data) if data else []
        if not items:
            logger.warning(f"[wallapop] {zona_key}: 0 items en __NEXT_DATA__ (html={len(html)} bytes)")
            return []

        # Mapa id -> href real desde los anchors del DOM (URLs canónicas).
        href_by_id = {
            m.group(2): m.group(1)
            for m in re.finditer(r'href="(/item/[^"]*?-(\d{6,}))"', html)
        }

        zona_info = self.ZONAS.get(zona_key, {})
        results: List[Dict[str, Any]] = []
        for item in items:
            try:
                listing = self._item_to_listing(item, zona_key, zona_info, href_by_id)
                if listing:
                    results.append(listing)
            except Exception as e:
                logger.debug(f"[wallapop] item parse error: {e}")

        n_part = sum(1 for r in results if r.get("es_particular"))
        logger.info(
            f"[wallapop] {zona_key}: {len(results)} listings de {len(items)} items "
            f"({n_part} particulares, {len(results) - n_part} agencias/pro)"
        )
        return results

    def _item_to_listing(self, item: Dict[str, Any], zona_key: str, zona_info: dict,
                         href_by_id: Dict[str, str]) -> Optional[Dict[str, Any]]:
        iid = str(item.get("id") or item.get("itemId") or "").strip()
        if not iid:
            return None

        # Descartar vendidos / reservados (no son leads accionables).
        if item.get("sold") is True or item.get("reserved") is True:
            return None

        title = (item.get("title") or "")[:200]
        description = str(item.get("description") or "")[:2000]
        precio = self._coerce_price(item.get("price"))

        # URL: anchor real del DOM por id, si no slugId, si no por id.
        href = href_by_id.get(iid)
        if href:
            url_anuncio = f"{self.BASE_URL}{href}"
        elif item.get("slugId"):
            url_anuncio = f"{self.BASE_URL}/item/{item['slugId']}"
        else:
            url_anuncio = f"{self.BASE_URL}/item/{iid}"

        seller = item.get("seller") if isinstance(item.get("seller"), dict) else {}
        vendedor = seller.get("userName") or seller.get("name") or seller.get("micro_name") or ""

        habitaciones, metros, tipo_inmueble, operation = self._real_estate_attrs(item)
        fotos = self._extract_photos(item)

        is_pro = self._is_professional(seller, item, vendedor, title, description)
        es_particular = not is_pro

        return {
            "anuncio_id": iid,
            "titulo": title,
            "precio": precio,
            "descripcion": description,
            "ubicacion": zona_info.get("nombre", zona_key),
            "zona_geografica": zona_info.get("nombre", zona_key),
            "zona_busqueda": zona_key,
            "url_anuncio": url_anuncio,
            "es_particular": es_particular,
            "seller_type": "professional" if is_pro else "private",
            "vendedor": vendedor or ("Particular" if es_particular else "Profesional"),
            "tipo_inmueble": tipo_inmueble or "piso",
            "habitaciones": habitaciones,
            "metros": metros,
            "fotos": fotos,
        }

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_price(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict):
                for k in ("amount", "value", "cashPrice"):
                    if val.get(k) is not None:
                        return ScraplingWallapop._coerce_price(val[k])
                return None
            s = re.sub(r"[^0-9.,]", "", str(val)).replace(".", "").replace(",", ".")
            return float(s) if s else None
        except Exception:
            return None

    def _real_estate_attrs(self, item: Dict[str, Any]):
        habitaciones = metros = None
        tipo = operation = None
        attrs = item.get("itemRealEstate") or item.get("real_estate_attributes") or {}
        if isinstance(attrs, dict):
            habitaciones = self._to_int(
                attrs.get("rooms") or attrs.get("bedrooms") or attrs.get("numberOfRooms")
            )
            metros = self._to_int(
                attrs.get("surface") or attrs.get("m2") or attrs.get("surfaceArea")
            )
            tipo = attrs.get("typology") or attrs.get("type") or attrs.get("property_type")
            operation = attrs.get("operation") or attrs.get("operationType")

        if isinstance(tipo, str):
            t = tipo.lower()
            if "casa" in t or "chalet" in t or "house" in t or "villa" in t:
                tipo = "casa"
            elif "piso" in t or "flat" in t or "apart" in t or "atico" in t:
                tipo = "piso"
            elif "local" in t or "office" in t or "oficina" in t:
                tipo = "local"
            elif "terren" in t or "land" in t or "plot" in t:
                tipo = "terreno"
            else:
                tipo = None
        else:
            tipo = None
        return habitaciones, metros, tipo, (str(operation).lower() if operation else None)

    @staticmethod
    def _to_int(val: Any) -> Optional[int]:
        if val is None:
            return None
        try:
            m = re.search(r"\d+", str(val))
            return int(m.group()) if m else None
        except Exception:
            return None

    def _extract_photos(self, item: Dict[str, Any]) -> List[str]:
        fotos: List[str] = []
        images = item.get("images") or []
        if isinstance(images, dict):
            images = [images]
        for img in images[:10]:
            url = ""
            if isinstance(img, dict):
                urls = img.get("urls") if isinstance(img.get("urls"), dict) else None
                if urls:
                    url = (urls.get("big") or urls.get("medium") or urls.get("original")
                           or urls.get("small") or "")
                else:
                    url = (img.get("big") or img.get("medium") or img.get("original")
                           or img.get("url") or img.get("src") or "")
            elif isinstance(img, str):
                url = img
            if url:
                if url.startswith("//"):
                    url = "https:" + url
                fotos.append(url)
        return fotos

    def _is_professional(self, seller: dict, item: dict, vendedor: str,
                        title: str, description: str) -> bool:
        # 1) Flags explícitos del vendedor/anuncio (cuando Wallapop los expone)
        for obj in (seller, item):
            if not isinstance(obj, dict):
                continue
            if obj.get("professional") is True or obj.get("isProfessional") is True:
                return True
            if str(obj.get("kind", "")).lower() in ("professional", "profesional", "business"):
                return True
            if str(obj.get("type", "")).lower() in ("professional", "profesional", "business", "shop"):
                return True
        # 2) Nombre del vendedor (incluye yaencontre y portales camuflados)
        if vendedor and _AGENCY_NAME_RE.search(vendedor):
            return True
        # 3) Texto del anuncio (Ref:, frases de agencia)
        blob = f"{title}\n{description}"
        if _AGENCY_TEXT_RE.search(blob) or _AGENCY_NAME_RE.search(blob):
            return True
        return False

    def _wants_detail(self) -> bool:
        # El SSR (__NEXT_DATA__) ya trae título, descripción, precio, vendedor y
        # atributos -> no hace falta visitar el detalle.
        return False


def main():
    import argparse
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="+", required=True)
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--postgres", action="store_true", default=True)
    ap.add_argument("--no-postgres", dest="postgres", action="store_false")
    ap.add_argument("--proxy", default="", help="Optional proxy http://user:pass@host:port (Scrapling no lo necesita)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = ScraplingWallapop(
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
        log_scraper_run("wallapop", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

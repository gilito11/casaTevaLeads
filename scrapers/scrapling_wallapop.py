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
import math
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.zones.wallapop import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)

# Patrones de nombre de vendedor que delatan una inmobiliaria/profesional.
_AGENCY_NAME_RE = re.compile(
    r"(yaencontre|ya\s*encontr|\binmo\w*|inmuebles?|fincas|finques|"
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
    # Municipios sin vertical SEO (zona con slug=None): búsqueda geolocalizada.
    # Devuelve JSON: data.section.payload.items (40/pág), items con web_slug,
    # location{city,lat,lng} y type_attributes{operation,type,surface}.
    API_SEARCH_URL = "https://api.wallapop.com/api/v3/search"
    ZONAS = ZONAS_GEOGRAFICAS

    DETAIL_DELAY_RANGE = (2.0, 4.0)
    SEARCH_DELAY_RANGE = (4.0, 7.0)

    # SSR: el HTML inicial ya trae __NEXT_DATA__ con TODAS las URLs de fotos (texto).
    # No necesitamos que el navegador descargue los bytes de imagen/css/fuentes, que
    # es el grueso del ancho de banda del proxy. Bloqueándolos el coste de cada ficha
    # cae ~10x y seguimos extrayendo las 10 fotos del JSON.
    SESSION_KWARGS = {
        **ScraplingBaseScraper.SESSION_KWARGS,
        "disable_resources": True,
        "block_ads": True,
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
        if not slug and zona.get("lat") is not None:
            # Municipio sin vertical SEO (la landing devuelve 404): búsqueda
            # geolocalizada por API. Devuelve JSON con hasta 40 items cat. 200.
            params = urllib.parse.urlencode({
                "latitude": f"{zona['lat']:.4f}",
                "longitude": f"{zona['lng']:.4f}",
                "distance": str(int(float(zona.get("radius_km") or 4) * 1000)),
                "category_id": "200",
                "source": "search_box",
            })
            return f"{self.API_SEARCH_URL}?{params}"
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

        zona_cfg = self.ZONAS.get(zona_key, {})
        if not zona_cfg.get("slug"):
            # Zona sin vertical SEO: la respuesta es el JSON del API geolocalizado.
            return self._parse_api_results(html, zona_key, zona_cfg)

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
    # API geolocalizado (municipios sin vertical SEO)
    # ------------------------------------------------------------------
    def _parse_api_results(self, text: str, zona_key: str, zona_cfg: dict) -> List[Dict[str, Any]]:
        items = self._api_payload_items(text)
        if not items:
            logger.warning(f"[wallapop] {zona_key}: 0 items del API geolocalizado")
            return []

        results: List[Dict[str, Any]] = []
        fuera = 0
        for item in items:
            try:
                listing = self._api_item_to_listing(item, zona_key, zona_cfg)
                if listing is None:
                    continue
                # El radio del API es orientativo: con poco inventario lo expande.
                # Descartamos lo que caiga claramente fuera del municipio buscado.
                if not self._within_radius(item.get("location") or {}, zona_cfg):
                    fuera += 1
                    continue
                results.append(listing)
            except Exception as e:
                logger.debug(f"[wallapop] api item parse error: {e}")

        n_part = sum(1 for r in results if r.get("es_particular"))
        logger.info(
            f"[wallapop] {zona_key}: {len(results)} listings de {len(items)} items API "
            f"({n_part} particulares, {len(results) - n_part} agencias/pro, {fuera} fuera de radio)"
        )
        return results

    @staticmethod
    def _api_payload_items(text: str) -> List[Dict[str, Any]]:
        """Cuerpo JSON del API; tolera JSON envuelto en <pre> si la respuesta
        vino renderizada por un navegador."""
        raw = (text or "").strip()
        if not raw.startswith("{"):
            m = re.search(r"<pre[^>]*>(.*?)</pre>", raw, re.DOTALL)
            raw = (m.group(1) if m else "").strip()
        try:
            data = json.loads(raw)
        except Exception:
            return []
        payload = (((data.get("data") or {}).get("section") or {}).get("payload") or {})
        items = payload.get("items")
        return items if isinstance(items, list) else []

    def _api_item_to_listing(self, item: Dict[str, Any], zona_key: str,
                             zona_cfg: dict) -> Optional[Dict[str, Any]]:
        iid = str(item.get("id") or "").strip()
        if not iid:
            return None
        if (item.get("reserved") or {}).get("flag") is True:
            return None

        habitaciones, metros, tipo_inmueble, operation = self._real_estate_attrs(item)
        # El API geolocalizado mezcla venta y alquiler: solo venta.
        if operation == "rent":
            return None

        loc = item.get("location") or {}
        title = (item.get("title") or "")[:200]
        description = str(item.get("description") or "")[:2000]

        # El API no expone el nombre del vendedor (solo user_id): la detección
        # de agencia aquí es solo por texto; el detalle (parse_detail_page)
        # re-verifica con el perfil real del vendedor (itemSeller).
        is_pro = self._is_professional({}, item, "", title, description)

        return {
            "anuncio_id": iid,
            "titulo": title,
            "precio": self._coerce_price(item.get("price")),
            "descripcion": description,
            "ubicacion": loc.get("city") or zona_cfg.get("nombre", zona_key),
            "zona_geografica": zona_cfg.get("nombre", zona_key),
            "zona_busqueda": zona_key,
            "url_anuncio": f"{self.BASE_URL}/item/{item.get('web_slug') or iid}",
            "es_particular": not is_pro,
            "seller_type": "professional" if is_pro else "private",
            "vendedor": "Profesional" if is_pro else "Particular",
            "tipo_inmueble": tipo_inmueble or "piso",
            "habitaciones": habitaciones,
            "metros": metros,
            "fotos": [],
        }

    @staticmethod
    def _within_radius(loc: dict, zona_cfg: dict, slack: float = 1.6) -> bool:
        try:
            lat, lng = float(loc.get("latitude")), float(loc.get("longitude"))
            zlat, zlng = float(zona_cfg.get("lat")), float(zona_cfg.get("lng"))
            radius = float(zona_cfg.get("radius_km") or 4)
        except (TypeError, ValueError):
            return True  # sin coordenadas no podemos juzgar: dentro
        dx = (lng - zlng) * 111.32 * math.cos(math.radians(zlat))
        dy = (lat - zlat) * 111.32
        return (dx * dx + dy * dy) ** 0.5 <= radius * slack

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
        attrs = (item.get("itemRealEstate") or item.get("real_estate_attributes")
                 or item.get("type_attributes") or {})
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
        # Wallapop: NO guardamos fotos. Los bytes estan protegidos (hotlink) y se
        # bloquean a proposito en el navegador, asi que en el CRM salen en blanco.
        # No aportan nada util, asi que ni las almacenamos (sin badge "N fotos").
        return []
        fotos: List[str] = []
        images = item.get("images") or []
        if isinstance(images, dict):
            images = [images]
        for img in images[:10]:
            url = ""
            if isinstance(img, dict):
                urls = img.get("urls") if isinstance(img.get("urls"), dict) else None
                if urls:
                    # detalle: cada imagen trae urls.{small,medium,big}
                    url = (urls.get("big") or urls.get("medium") or urls.get("original")
                           or urls.get("small") or "")
                else:
                    # listado SSR: una sola miniatura como smallUrl (W320)
                    url = (img.get("bigUrl") or img.get("mediumUrl") or img.get("smallUrl")
                           or img.get("big") or img.get("medium") or img.get("original")
                           or img.get("url") or img.get("src") or "")
                # subir resolución de la miniatura del listado para la ficha
                if url and "pictureSize=W320" in url:
                    url = url.replace("pictureSize=W320", "pictureSize=W800")
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

    @staticmethod
    def _phone_from_text(text: str) -> Optional[str]:
        """Extrae un móvil/fijo ES (9 dígitos) de la descripción. Evita IDs de
        imagen (10 dígitos) con límites estrictos y números repetidos."""
        if not text:
            return None
        cleaned = re.sub(r"[\s.\-/]", "", text)
        for m in re.findall(r"(?<!\d)[6789]\d{8}(?!\d)", cleaned):
            if len(set(m)) > 3:
                return m
        return None

    def _wants_detail(self) -> bool:
        # El listado SSR solo trae 1 miniatura. Visitamos el detalle SOLO para
        # los anuncios que pasan should_skip (particulares con precio > umbral,
        # un puñado por zona) para sacar las 10 fotos, el teléfono y verificar al
        # vendedor con su perfil. Barato porque las agencias ya se filtraron antes.
        return True

    def parse_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        try:
            html = page.html_content or ""
        except Exception:
            html = ""
        data = self._extract_next_data(html)
        if not data:
            return listing
        pp = (data.get("props") or {}).get("pageProps") or {}
        item = pp.get("item") if isinstance(pp.get("item"), dict) else {}
        seller = pp.get("itemSeller") if isinstance(pp.get("itemSeller"), dict) else {}

        # Fotos completas (hasta 10) desde item.images (urls.{small,medium,big})
        fotos = self._extract_photos(item)
        if fotos:
            listing["fotos"] = fotos

        # Descripción más completa
        desc = item.get("description") or ""
        if isinstance(desc, str) and len(desc) > len(listing.get("descripcion", "")):
            listing["descripcion"] = desc[:2000]

        # Teléfono desde la descripción (Wallapop no expone teléfono directo)
        if not listing.get("telefono_norm"):
            phone = self._phone_from_text(listing.get("descripcion", ""))
            if phone:
                listing["telefono"] = phone
                listing["telefono_norm"] = phone

        # Re-verificar profesional con el perfil del vendedor (itemSeller)
        vendedor = (
            seller.get("userName") or seller.get("name")
            or seller.get("micro_name") or listing.get("vendedor") or ""
        )
        if seller and self._is_professional(
            seller, item, vendedor, listing.get("titulo", ""), listing.get("descripcion", "")
        ):
            listing["es_particular"] = False
            listing["seller_type"] = "professional"
            if vendedor:
                listing["vendedor"] = vendedor
        listing["verified"] = True
        return listing


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

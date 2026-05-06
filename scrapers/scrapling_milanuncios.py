"""
Milanuncios scraper basado en Scrapling.

Replaces camoufox_milanuncios.py — bypassa GeeTest sin proxy gracias a
Patchright + StealthySession (cookies persistentes).

Estrategia DUAL para parsing:
1. Primario: extraer JSON `window.__INITIAL_PROPS__` desde el HTML por regex
   (mucho más fiable que parsear DOM y aporta sellerType/shop/isPrivate).
2. Fallback: parser DOM con `article[data-testid="ad-card"]` o `article` genérico.

Detección de profesional (lessons-learned MEMORY):
- sellerType.value == "professional" (o string "professional"/"profesional")
- isPrivate is False, shop dict, hasShop, shopName, sellerBadge contiene "pro"
- DOM: badge "Profesional" visible
- "Ref:" al inicio de descripción → agencia
- Confiar en JSON sobre DOM cuando esté disponible.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from scrapers.scrapling_base import ScraplingBaseScraper
from scrapers.camoufox_milanuncios import ZONAS_GEOGRAFICAS

logger = logging.getLogger(__name__)


# Phone blacklist — placeholder numbers that show up in milanuncios ads
_PHONE_BLACKLIST = {
    '666666666', '777777777', '999999999',
    '600000000', '700000000', '900000000',
    '123456789', '987654321',
}


def _extract_phone_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.replace(' ', '').replace('.', '').replace('-', '').replace('/', '')
    for phone in re.findall(r'[679]\d{8}', cleaned):
        if phone not in _PHONE_BLACKLIST and len(set(phone)) > 2:
            return phone
    return None


class ScraplingMilanuncios(ScraplingBaseScraper):
    PORTAL_NAME = "milanuncios"
    BASE_URL = "https://www.milanuncios.com"
    ZONAS = ZONAS_GEOGRAFICAS

    DETAIL_DELAY_RANGE = (2.0, 4.0)
    SEARCH_DELAY_RANGE = (3.0, 6.0)

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------
    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        zona = self.ZONAS[zona_key]
        url = f"{self.BASE_URL}/{zona['url_path']}"
        if page > 1:
            url = url.rstrip('/') + f'?pagina={page}'
        return url

    # ------------------------------------------------------------------
    # JSON extraction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_initial_props(html: str) -> Optional[Dict[str, Any]]:
        """Extract window.__INITIAL_PROPS__ from raw HTML.

        Milanuncios serializes it in two flavours:
          1) `window.__INITIAL_PROPS__ = {...};`
          2) `window.__INITIAL_PROPS__ = JSON.parse("...escaped...");`
        Also tries `__NEXT_DATA__` (hydration script).
        """
        if not html:
            return None

        # Variant 2: JSON.parse("...")  — escaped string
        m = re.search(
            r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\(\s*"((?:\\.|[^"\\])*)"\s*\)',
            html,
            re.DOTALL,
        )
        if m:
            try:
                escaped = m.group(1)
                # Unescape JS string literal then parse JSON
                unescaped = bytes(escaped, "utf-8").decode("unicode_escape")
                return json.loads(unescaped)
            except Exception as e:
                logger.debug(f"INITIAL_PROPS JSON.parse decode failed: {e}")

        # Variant 1: literal object
        m = re.search(
            r'window\.__INITIAL_PROPS__\s*=\s*({.+?})\s*;\s*(?:window\.|</script>)',
            html,
            re.DOTALL,
        )
        if m:
            try:
                return json.loads(m.group(1))
            except Exception as e:
                logger.debug(f"INITIAL_PROPS literal decode failed: {e}")

        # __NEXT_DATA__ (Next.js hydration)
        m = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>\s*(\{.+?\})\s*</script>',
            html,
            re.DOTALL,
        )
        if m:
            try:
                next_data = json.loads(m.group(1))
                # Mimic structure expected by _parse_json_listings
                props = next_data.get("props") or {}
                page_props = props.get("pageProps") or {}
                # Merge so callers can find adListPagination/ads in either spot
                merged: Dict[str, Any] = {}
                merged.update(props)
                merged.update(page_props)
                return merged
            except Exception as e:
                logger.debug(f"__NEXT_DATA__ decode failed: {e}")

        return None

    @staticmethod
    def _coerce_seller_signals(ad: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Compute (is_professional, seller_type_str, extra_signals) from a JSON ad."""
        raw_seller_type = ad.get("sellerType", "")
        is_private: Optional[bool] = None
        if isinstance(raw_seller_type, dict):
            seller_type = str(raw_seller_type.get("value", "")).lower()
            is_private = raw_seller_type.get("isPrivate")
        else:
            seller_type = str(raw_seller_type).lower()
        seller_badge = str(ad.get("sellerBadge", "")).lower()
        user_type = str(ad.get("userType", "")).lower()
        shop = ad.get("shop")
        has_shop = bool(shop)
        shop_name = ""
        if isinstance(shop, dict):
            shop_name = shop.get("name", "") or ""

        is_professional = (
            seller_type in ("professional", "profesional")
            or is_private is False
            or has_shop
            or "pro" in seller_badge
            or user_type in ("professional", "profesional")
            or bool(ad.get("isProfessional"))
            or bool(ad.get("hasShop"))
        )

        extra = {
            "isPrivate": is_private,
            "hasShop": has_shop,
            "shopName": shop_name,
            "sellerBadge": seller_badge,
        }
        return is_professional, (seller_type or ("professional" if is_professional else "")), extra

    def _parse_json_listings(
        self, json_data: Dict[str, Any], zona_key: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Parse listings from milanuncios JSON. Returns (listings, json_had_ads)."""
        listings: List[Dict[str, Any]] = []
        ads = None
        if isinstance(json_data, dict):
            pagination = json_data.get("adListPagination")
            if isinstance(pagination, dict):
                ad_list = pagination.get("adList")
                if isinstance(ad_list, dict):
                    ads = ad_list.get("ads")
            if not ads:
                ads = json_data.get("ads")
            if not ads and "pageProps" in json_data:
                ads = (json_data.get("pageProps") or {}).get("ads")

        if not ads:
            keys = list(json_data.keys()) if isinstance(json_data, dict) else type(json_data)
            logger.warning(f"[milanuncios] No ads in JSON. Keys: {keys}")
            return [], False

        logger.info(f"[milanuncios] Found {len(ads)} ads in JSON")
        zona_info = self.ZONAS.get(zona_key, {})
        skipped_pro = 0
        skipped_price = 0

        for ad in ads:
            try:
                is_professional, seller_type, extra = self._coerce_seller_signals(ad)

                # Honour only_private but always keep the ad (let base class skip)
                anuncio_id = str(ad.get("id", ""))
                if not anuncio_id:
                    continue

                # Price (cashPrice.value preferred, then value, then numeric)
                precio: Optional[float] = None
                price_data = ad.get("price", {})
                if isinstance(price_data, dict):
                    cash_price = price_data.get("cashPrice", {})
                    if isinstance(cash_price, dict) and cash_price.get("value") is not None:
                        precio = cash_price.get("value")
                    elif "value" in price_data:
                        precio = price_data.get("value")
                elif isinstance(price_data, (int, float)):
                    precio = price_data
                try:
                    precio = float(precio) if precio is not None else None
                except (TypeError, ValueError):
                    precio = None

                if precio is not None and precio < 10000:
                    skipped_price += 1
                    continue

                if self.only_private and is_professional:
                    skipped_pro += 1
                    # Still add to stats but don't return: the base loop will also filter
                    continue

                # URL
                url_path = ad.get("url", "")
                if isinstance(url_path, str) and url_path.startswith("/"):
                    url_anuncio = f"{self.BASE_URL}{url_path}"
                else:
                    url_anuncio = url_path or ""

                # Location
                ubicacion = ""
                if isinstance(ad.get("city"), dict):
                    ubicacion = ad["city"].get("name", "") or ""
                elif "location" in ad:
                    ubicacion = ad.get("location", "") or ""

                # Photos
                fotos: List[str] = []
                images = ad.get("images") or []
                for img in images[:10]:
                    if isinstance(img, dict):
                        img_url = img.get("url", "") or img.get("src", "")
                    else:
                        img_url = str(img)
                    if not img_url:
                        continue
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    elif not img_url.startswith("http"):
                        img_url = "https://" + img_url
                    fotos.append(img_url)

                description = (ad.get("description", "") or "")[:2000]

                # Heuristic: "Ref:" or "Ref." at description start → agency
                if not is_professional and description:
                    if re.match(r"^\s*ref[:.]\s*", description, re.IGNORECASE):
                        is_professional = True
                        seller_type = seller_type or "professional"

                listing = {
                    "anuncio_id": anuncio_id,
                    "titulo": (ad.get("title", "") or "")[:200],
                    "precio": precio,
                    "descripcion": description,
                    "ubicacion": ubicacion,
                    "zona_geografica": zona_info.get("nombre", zona_key),
                    "zona_busqueda": zona_key,
                    "url_anuncio": url_anuncio,
                    "es_particular": not is_professional,
                    "seller_type": seller_type,
                    "tipo_inmueble": "piso",
                    "fotos": fotos,
                    # Extra signals → carried through into raw_data by base class
                    "isPrivate": extra["isPrivate"],
                    "hasShop": extra["hasShop"],
                    "shopName": extra["shopName"],
                    "sellerBadge": extra["sellerBadge"],
                }
                listings.append(listing)

            except Exception as e:
                logger.debug(f"[milanuncios] JSON ad parse error: {e}")

        logger.info(
            f"[milanuncios] JSON filter: {len(listings)} kept, "
            f"{skipped_pro} professional, {skipped_price} low price (of {len(ads)} total)"
        )
        return listings, True

    # ------------------------------------------------------------------
    # Search-page parsing
    # ------------------------------------------------------------------
    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        try:
            html = page.html_content or ""
        except Exception:
            html = ""

        # 1) JSON primary path
        json_data = self._extract_initial_props(html)
        if json_data:
            listings, json_had_ads = self._parse_json_listings(json_data, zona_key)
            if listings:
                return listings
            if json_had_ads:
                # JSON had ads but all filtered as pro/low — trust it, skip DOM
                logger.info("[milanuncios] JSON ads all filtered, skipping DOM fallback")
                return []
        else:
            logger.info("[milanuncios] No __INITIAL_PROPS__ JSON found, falling back to DOM")

        # 2) DOM fallback
        articles = (
            page.css('article[data-testid="ad-card"]')
            or page.css('article[class*="AdCard"]')
            or page.css('article.ma-AdCard')
            or page.css('article[data-ad-id]')
            or page.css('article')
            or []
        )
        if not articles:
            logger.warning(f"[milanuncios] {zona_key}: no articles found via DOM")
            return []

        zona_info = self.ZONAS.get(zona_key, {})
        results: List[Dict[str, Any]] = []
        for art in articles:
            try:
                listing = self._parse_dom_card(art, zona_key, zona_info)
                if listing:
                    results.append(listing)
            except Exception as e:
                logger.debug(f"[milanuncios] DOM card parse error: {e}")
        return results

    def _parse_dom_card(self, art, zona_key: str, zona_info: dict) -> Optional[Dict[str, Any]]:
        try:
            html = art.html_content or ""
        except Exception:
            html = ""
        low_html = html.lower()

        # Professional indicators in card HTML
        pro_markers = (
            "profesional", "professional", "inmobiliaria",
            "adtag--pro", 'seller-type="pro', "sellerbadge",
            "logo-branding",
        )
        is_professional = any(m in low_html for m in pro_markers)

        # Find link
        link = None
        for sel in ('a[href*=".htm"]', 'a[data-testid="ad-link"]', 'a[class*="Link"]', 'a'):
            hits = art.css(sel)
            if hits:
                link = hits[0]
                break
        if not link:
            return None
        href = link.attrib.get("href", "")
        if not href:
            return None

        # Extract anuncio_id
        anuncio_id = None
        for pattern in (r"-(\d{6,})\.htm", r"/(\d{6,})\.htm", r"-(\d{6,})$", r"(\d{6,})"):
            m = re.search(pattern, href)
            if m:
                anuncio_id = m.group(1)
                break
        if not anuncio_id:
            anuncio_id = art.attrib.get("data-ad-id") or art.attrib.get("data-id")
        if not anuncio_id:
            return None

        # Title
        titulo = ""
        for sel in ("h2", "h3", '[class*="title"]', '[class*="Title"]'):
            hits = art.css(sel)
            if hits:
                try:
                    titulo = (hits[0].text.clean() or "").strip()
                except Exception:
                    titulo = (hits[0].get_all_text() or "").strip()
                if titulo:
                    break

        # Price
        precio: Optional[float] = None
        for sel in ('[class*="price"]', '[class*="Price"]', '[data-testid="ad-price"]'):
            hits = art.css(sel)
            if hits:
                try:
                    txt = hits[0].text.clean()
                except Exception:
                    txt = hits[0].get_all_text() or ""
                precio = self.parse_price(txt)
                if precio:
                    break

        if precio is not None and precio < 10000:
            return None

        url_anuncio = f"{self.BASE_URL}{href}" if href.startswith("/") else href

        return {
            "anuncio_id": anuncio_id,
            "titulo": titulo[:200],
            "precio": precio,
            "descripcion": "",
            "ubicacion": "",
            "zona_geografica": zona_info.get("nombre", zona_key),
            "zona_busqueda": zona_key,
            "url_anuncio": url_anuncio,
            "es_particular": not is_professional,
            "seller_type": "professional" if is_professional else "",
            "tipo_inmueble": "piso",
            "fotos": [],
        }

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

        # 1) Detail JSON — best signal for seller type
        json_data = self._extract_initial_props(html)
        if json_data:
            ad = None
            if isinstance(json_data, dict):
                ad = (
                    json_data.get("adDetail")
                    or json_data.get("ad")
                    or (json_data.get("pageProps") or {}).get("adDetail")
                    or (json_data.get("pageProps") or {}).get("ad")
                )
            if isinstance(ad, dict):
                is_pro, seller_type, extra = self._coerce_seller_signals(ad)
                if is_pro:
                    listing["es_particular"] = False
                    listing["seller_type"] = "professional"
                    listing["verified"] = True
                    seller_obj = ad.get("seller") if isinstance(ad.get("seller"), dict) else None
                    name = (
                        extra["shopName"]
                        or (seller_obj.get("name") if seller_obj else "")
                        or ad.get("sellerName", "")
                        or ad.get("advertiserName", "")
                        or ""
                    )
                    if name:
                        listing["vendedor"] = name
                else:
                    seller_obj = ad.get("seller") if isinstance(ad.get("seller"), dict) else None
                    name = (seller_obj.get("name") if seller_obj else "") or ad.get("sellerName", "")
                    if name and not listing.get("vendedor"):
                        listing["vendedor"] = name
                    if seller_type and not listing.get("seller_type"):
                        listing["seller_type"] = seller_type

                # Description from JSON
                desc = ad.get("description") or ""
                if desc and len(desc) > len(listing.get("descripcion", "")):
                    listing["descripcion"] = str(desc)[:2000]

                # Pass through extra signals
                for k in ("isPrivate", "hasShop", "shopName", "sellerBadge"):
                    if k in extra:
                        listing[k] = extra[k]

        # 2) Visible "Profesional" badge in DOM (very reliable visual signal)
        if listing.get("es_particular", True):
            try:
                # Look for badge-like elements with that exact text
                badge_candidates = (
                    page.css('span') + page.css('p') + page.css('div[class*="Badge"]')
                    + page.css('[class*="badge"]')
                )
                for el in badge_candidates[:200]:
                    try:
                        txt = (el.text.clean() or "").strip()
                    except Exception:
                        try:
                            txt = (el.get_all_text() or "").strip()
                        except Exception:
                            txt = ""
                    if txt in ("Profesional", "Professional"):
                        listing["es_particular"] = False
                        listing["seller_type"] = "professional"
                        listing["verified"] = True
                        break
            except Exception:
                pass

        # 3) HTML regex final fallback for sellerType in any embedded JSON blob
        if listing.get("es_particular", True):
            try:
                if re.search(r'"sellerType"\s*:\s*"professional"', html, re.IGNORECASE):
                    listing["es_particular"] = False
                    listing["seller_type"] = "professional"
                    listing["verified"] = True
                # isPrivate=false also strong signal
                elif re.search(r'"isPrivate"\s*:\s*false', html):
                    listing["es_particular"] = False
                    listing["seller_type"] = listing.get("seller_type") or "professional"
                    listing["verified"] = True
            except Exception:
                pass

        # 4) Description fallback via DOM if still empty
        if not listing.get("descripcion") or len(listing.get("descripcion", "")) < 20:
            for sel in (
                '[data-testid="AD_DESCRIPTION"]',
                '[class*="AdDescription"]',
                '[class*="adDescription"]',
                '.ma-AdDetail-description',
                'section[class*="description"] p',
                '[class*="Description"] p',
            ):
                try:
                    hits = page.css(sel)
                    if hits:
                        text = hits[0].get_all_text() or ""
                        if len(text) > len(listing.get("descripcion", "")):
                            listing["descripcion"] = text[:2000].strip()
                            break
                except Exception:
                    continue

        # 5) Description regex fallback in HTML
        if not listing.get("descripcion") or len(listing.get("descripcion", "")) < 20:
            try:
                m = re.search(r'"description"\s*:\s*"([^"]{20,})"', html)
                if m:
                    desc = m.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                    listing["descripcion"] = desc[:2000]
            except Exception:
                pass

        # 6) Photos via regex (both old and new image domains)
        if not listing.get("fotos"):
            try:
                photo_ids = sorted(set(re.findall(
                    r'https?://images(?:-re)?\.milanuncios\.com/api/v1/ma-ad-media-pro/images/([a-f0-9-]{36})',
                    html,
                    re.IGNORECASE,
                )))
                if photo_ids:
                    listing["fotos"] = [
                        f"https://images-re.milanuncios.com/api/v1/ma-ad-media-pro/images/{pid}?rule=detail_640x480"
                        for pid in photo_ids[:10]
                    ]
            except Exception:
                pass

        # 7) Phone — first try tel: link, then description text
        if not listing.get("telefono_norm"):
            try:
                tel_match = re.search(r'tel:(?:\+?34)?([679]\d{8})', html)
                if tel_match:
                    raw = tel_match.group(1)
                    normalized = self.normalize_phone(raw)
                    if normalized:
                        listing["telefono"] = raw
                        listing["telefono_norm"] = normalized
            except Exception:
                pass

        if not listing.get("telefono_norm"):
            phone = _extract_phone_from_text(listing.get("descripcion", ""))
            if phone:
                listing["telefono"] = phone
                listing["telefono_norm"] = phone

        # 8) "Ref:" heuristic on detail-page description as a last check
        if listing.get("es_particular", True):
            desc = listing.get("descripcion", "") or ""
            if re.match(r"^\s*ref[:.]\s*", desc, re.IGNORECASE):
                listing["es_particular"] = False
                listing["seller_type"] = listing.get("seller_type") or "professional"
                listing["verified"] = True

        return listing

    def _wants_detail(self) -> bool:
        return True


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
    ap.add_argument("--proxy", default="", help="Optional proxy http://user:pass@host:port (Scrapling does not need a proxy)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = ScraplingMilanuncios(
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
        log_scraper_run("milanuncios", stats, args.tenant_id)
    except Exception as e:
        logger.debug(f"log_scraper_run failed: {e}")


if __name__ == "__main__":
    main()

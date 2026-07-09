"""
Watcher de promociones de obra nueva vía Bright Data Web Unlocker.

Objetivo: avisar por Telegram el día que una promoción nueva sale al mercado
en los portales, para llamar a la promotora antes que nadie. Flujo SEPARADO
del pipeline de particulares (las promotoras son profesionales): guarda en
raw.obra_nueva_promotions, NO toca raw.raw_listings ni dim_leads.

Fuentes (Lleida ciudad, foco Copa d'Or/Bordeta/Cappont):
- idealista: /venta-obranueva/lleida-lleida/ (HTML de promociones, via BD)
- fotocasa: API interna propertysearch ordenada por fecha (misma que
  scrapling_fotocasa_bd) — anuncios con promotionId = obra nueva

Deteccion: PK (portal, promo_id). Promo no vista -> INSERT + alerta Telegram.
--seed puebla la tabla sin alertar (primera ejecucion).

Env vars: BRIGHTDATA_API_KEY, BRIGHTDATA_ZONE, DATABASE_URL,
TELEGRAM_BOT_TOKEN/CHAT_ID (opcionales para --dry-run).

Coste: ~4 requests/dia (~$0.20/mes).
"""
import argparse
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

from scrapers.scrapling_base import get_db_config

logger = logging.getLogger(__name__)

BD_API_URL = "https://api.brightdata.com/request"
FC_SEARCH_API = "https://web.gw.fotocasa.es/v2/propertysearch/search"

IDEALISTA_URLS = {
    "lleida": "https://www.idealista.com/venta-obranueva/lleida-lleida/",
}
FOTOCASA_LOCATIONS = {
    "lleida": "lleida-capital/todas-las-zonas",
}


class ObraNuevaWatcher:
    def __init__(self, dry_run: bool = False, seed: bool = False,
                 dump_dir: Optional[str] = None):
        self.dry_run = dry_run
        self.seed = seed
        self.dump_dir = dump_dir
        api_key = os.environ.get("BRIGHTDATA_API_KEY")
        if not api_key:
            raise RuntimeError("BRIGHTDATA_API_KEY required")
        self.bd_zone = os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        self.conn = None
        if not dry_run:
            import psycopg2
            cfg = {k: v for k, v in get_db_config().items() if v is not None}
            self.conn = psycopg2.connect(**cfg)
            self._ensure_table()
        self.new_promos: List[Dict[str, Any]] = []
        self.errors = 0

    # ------------------------------------------------------------------
    def _bd_request(self, url: str) -> Optional[str]:
        payload = {"zone": self.bd_zone, "url": url, "format": "raw", "country": "es"}
        try:
            r = self.session.post(BD_API_URL, json=payload, timeout=150)
        except requests.RequestException as e:
            logger.warning(f"BD fetch failed for {url}: {e}")
            self.errors += 1
            return None
        if r.status_code != 200:
            logger.warning(f"BD HTTP {r.status_code} for {url}: {r.text[:200]}")
            self.errors += 1
            return None
        r.encoding = "utf-8"
        return r.text

    def _dump(self, name: str, content: str):
        if not self.dump_dir:
            return
        os.makedirs(self.dump_dir, exist_ok=True)
        path = os.path.join(self.dump_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"dumped {path} ({len(content)} bytes)")

    # ------------------------------------------------------------------
    def _ensure_table(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw.obra_nueva_promotions (
                portal       text NOT NULL,
                promo_id     text NOT NULL,
                nombre       text,
                url          text,
                zona         text,
                precio_desde numeric,
                promotora    text,
                raw_data     jsonb,
                first_seen   timestamptz DEFAULT now(),
                last_seen    timestamptz DEFAULT now(),
                PRIMARY KEY (portal, promo_id)
            )
            """
        )
        self.conn.commit()
        cur.close()

    def _upsert(self, promo: Dict[str, Any]) -> bool:
        """Insert/update. Returns True si la promo es NUEVA."""
        if self.dry_run:
            logger.info(f"[dry-run] promo: {promo['portal']}/{promo['promo_id']} "
                        f"{promo.get('nombre')!r} desde={promo.get('precio_desde')}")
            return False
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO raw.obra_nueva_promotions
              (portal, promo_id, nombre, url, zona, precio_desde, promotora, raw_data)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (portal, promo_id) DO UPDATE SET
              nombre = COALESCE(EXCLUDED.nombre, raw.obra_nueva_promotions.nombre),
              precio_desde = COALESCE(EXCLUDED.precio_desde, raw.obra_nueva_promotions.precio_desde),
              promotora = COALESCE(EXCLUDED.promotora, raw.obra_nueva_promotions.promotora),
              raw_data = EXCLUDED.raw_data,
              last_seen = now()
            RETURNING (xmax = 0)
            """,
            (promo["portal"], promo["promo_id"], promo.get("nombre"),
             promo.get("url"), promo.get("zona"), promo.get("precio_desde"),
             promo.get("promotora"), json.dumps(promo.get("raw_data") or {}, ensure_ascii=False)),
        )
        is_new = cur.fetchone()[0]
        self.conn.commit()
        cur.close()
        return bool(is_new)

    # ------------------------------------------------------------------
    # idealista: HTML de /venta-obranueva/
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        m = re.search(r"([\d.]{4,})\s*€", text or "")
        if not m:
            return None
        try:
            return float(m.group(1).replace(".", ""))
        except ValueError:
            return None

    def check_idealista(self, zona: str, url: str):
        # Parse por regex sobre el HTML crudo (validado contra dump real 9 Jul
        # 2026): cards <article> con href="/obra-nueva/<id>/", title=direccion,
        # precio en item-price h2-simulated y promotora en logo-branding alt.
        import html as htmllib
        raw = self._bd_request(url)
        if not raw:
            return
        self._dump(f"idealista_obranueva_{zona}.html", raw)

        seen_ids = set()
        for art in re.split(r"<article", raw)[1:]:
            m = re.search(r'href="(/obra-nueva/(\d+)/)"', art)
            if not m:
                continue
            href, promo_id = m.group(1), m.group(2)
            if promo_id in seen_ids:
                continue
            seen_ids.add(promo_id)
            title = re.search(r'class="item-link[^"]*"[^>]*title="([^"]+)"', art)
            price = re.search(r'item-price h2-simulated">([\d.]+)', art)
            brand = re.search(r'logo-branding.*?alt="([^"]*)"', art, re.DOTALL)
            detail = re.search(r'class="item-detail">([^<]+)', art)
            nombre = htmllib.unescape(title.group(1))[:200] if title else None
            if detail:
                tipologia = htmllib.unescape(detail.group(1)).strip()
                nombre = f"{nombre} — {tipologia}"[:200] if nombre else tipologia[:200]
            promo = {
                "portal": "idealista",
                "promo_id": promo_id,
                "nombre": nombre,
                "url": f"https://www.idealista.com{href}",
                "zona": zona,
                "precio_desde": self._parse_price(price.group(1) + " €") if price else None,
                "promotora": htmllib.unescape(brand.group(1))[:100] if brand and brand.group(1) else None,
                "raw_data": {"href": href},
            }
            if self._upsert(promo) and not self.seed:
                self.new_promos.append(promo)
        logger.info(f"[idealista] {zona}: {len(seen_ids)} promociones en pagina")

    # ------------------------------------------------------------------
    # fotocasa: API propertysearch, items con promotionId
    # ------------------------------------------------------------------
    def _fc_location_ids(self, url_path: str) -> Optional[str]:
        html = self._bd_request(f"https://www.fotocasa.es/es/comprar/viviendas/{url_path}/l")
        if not html:
            return None
        m = (re.search(r'combinedLocationIds=([0-9,]+)', html)
             or re.search(r'"combinedLocationIds":"([0-9,]+)"', html))
        return m.group(1) if m else None

    def check_fotocasa(self, zona: str, url_path: str, pages: int = 2):
        loc_ids = self._fc_location_ids(url_path)
        if not loc_ids:
            logger.warning(f"[fotocasa] {zona}: combinedLocationIds no encontrado")
            self.errors += 1
            return
        n_promo_ads = 0
        for page_num in range(1, pages + 1):
            api_url = (
                f"{FC_SEARCH_API}?combinedLocationIds={loc_ids}"
                f"&transactionTypeId=1&pageNumber={page_num}"
                f"&sortType=publicationDate&sortOrderDesc=true&pageSize=30"
            )
            body = self._bd_request(api_url)
            if body is None:
                break
            self._dump(f"fotocasa_api_{zona}_p{page_num}.json", body)
            try:
                data = json.loads(body)
            except ValueError:
                logger.warning(f"[fotocasa] respuesta no-JSON: {body[:150]!r}")
                self.errors += 1
                break
            for d in data.get("realEstates") or []:
                promo_id = d.get("promotionId")
                if not promo_id:
                    continue
                n_promo_ads += 1
                adv = d.get("advertiser") or {}
                addr = d.get("address") or {}
                loc = addr.get("location") or {}
                precio = None
                for t in (d.get("transactions") or []):
                    vals = t.get("value") or []
                    if vals:
                        try:
                            v = float(vals[0])
                            if v > 0:
                                precio = v
                                break
                        except (TypeError, ValueError):
                            pass
                detail = d.get("detail") or {}
                href = (detail.get("es") or "").split("?", 1)[0]
                promo = {
                    "portal": "fotocasa",
                    "promo_id": str(promo_id),
                    "nombre": (d.get("promotionTitle") or d.get("description") or "")[:200] or None,
                    "url": href if href.startswith("http") else f"https://www.fotocasa.es{href}",
                    "zona": (loc.get("level5") or loc.get("level4") or zona),
                    "precio_desde": precio,
                    "promotora": (adv.get("clientAlias") or "").strip() or None,
                    "raw_data": d,
                }
                if self._upsert(promo) and not self.seed:
                    self.new_promos.append(promo)
        logger.info(f"[fotocasa] {zona}: {n_promo_ads} anuncios de promocion vistos")

    # ------------------------------------------------------------------
    def alert(self):
        if not self.new_promos:
            logger.info("Sin promociones nuevas")
            return
        lines = ["🏗️ <b>Obra nueva: promociones NUEVAS detectadas</b>", ""]
        for p in self.new_promos:
            precio = f" — desde {p['precio_desde']:,.0f}€".replace(",", ".") if p.get("precio_desde") else ""
            promotora = f" ({p['promotora']})" if p.get("promotora") else ""
            lines.append(f"• [{p['portal']}] <a href=\"{p['url']}\">{p.get('nombre') or p['promo_id']}</a>"
                         f"{promotora} — {p.get('zona')}{precio}")
        lines.append("")
        lines.append("📞 Llamar a la promotora cuanto antes.")
        msg = "\n".join(lines)
        if self.dry_run:
            logger.info(f"[dry-run] Telegram:\n{msg}")
            return
        try:
            from scrapers.utils.telegram_alerts import send_telegram_alert
            send_telegram_alert(msg)
        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")

    def run(self):
        for zona, url in IDEALISTA_URLS.items():
            try:
                self.check_idealista(zona, url)
            except Exception as e:
                logger.exception(f"[idealista] {zona} failed: {e}")
                self.errors += 1
        for zona, url_path in FOTOCASA_LOCATIONS.items():
            try:
                self.check_fotocasa(zona, url_path)
            except Exception as e:
                logger.exception(f"[fotocasa] {zona} failed: {e}")
                self.errors += 1
        self.alert()
        logger.info(f"DONE | nuevas={len(self.new_promos)} errores={self.errors} seed={self.seed}")
        if self.conn:
            self.conn.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Sin BD ni Telegram (solo log)")
    ap.add_argument("--seed", action="store_true", help="Poblar tabla sin alertar")
    ap.add_argument("--dump-dir", default=None, help="Guardar HTML/JSON fetcheado (debug)")
    args = ap.parse_args()
    ObraNuevaWatcher(dry_run=args.dry_run, seed=args.seed, dump_dir=args.dump_dir).run()


if __name__ == "__main__":
    main()

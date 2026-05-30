"""
Re-scrape de leads existentes — verifica si los datos siguen vigentes.

A diferencia de listing_checker.py (que solo detecta bajas vía HTTP plano),
este módulo RE-EXTRAE la página de detalle con el parser real de cada portal y
reconcilia el lead con la realidad actual:

  - BAJA      : la página ya no existe / redirige → estado YA_VENDIDO
  - AGENCIA   : el anuncio ahora se detecta como profesional → blacklist + borrado
                (solo idealista/milanuncios: su página de detalle lleva la señal;
                 habitaclia/fotocasa detectan la agencia por URL/tarjeta, no por
                 detalle, así que no se re-evalúa la agencia en ellos)
  - PRECIO    : el precio cambió → actualiza raw + histórico (alimenta las alertas
                de bajada de precio existentes)

Reutiliza las clases ScraplingX (sesión + parse_detail_page) y el mecanismo de
blacklist del CRM (leads_anuncio_blacklist), idéntico al botón "Es agencia".

Uso:
  python -m scrapers.lead_refresher --portal habitaclia --limit 20
  python -m scrapers.lead_refresher --portal idealista --limit 20   # requiere BRIGHTDATA_API_KEY
  python -m scrapers.lead_refresher --limit 50 --dry-run            # todos los portales seguros
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg2

logger = logging.getLogger(__name__)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Estados del CRM que NO se tocan (ya gestionados por el comercial)
EXCLUDED_ESTADOS = (
    "YA_VENDIDO", "CLIENTE", "NO_CONTACTAR", "INTERESADO", "EN_PROCESO",
)

# Portales cuya página de detalle lleva señal fiable de profesional/particular.
AGENCY_REEVAL_PORTALS = ("idealista", "milanuncios")


def _db():
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL no definida")
    p = urlparse(url)
    return psycopg2.connect(
        host=p.hostname, port=p.port or 5432,
        database=p.path.lstrip("/").split("?")[0],
        user=p.username, password=p.password, sslmode="require",
    )


def _telegram(msg: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "parse_mode": "HTML", "text": msg}, timeout=15,
        )
    except Exception:
        pass


def _make_scraper(portal: str, proxy: Optional[str]):
    """Instancia la clase scraper del portal (sin abrir conexión PG propia)."""
    if portal == "habitaclia":
        from scrapers.scrapling_habitaclia import ScraplingHabitaclia
        return ScraplingHabitaclia(save_to_postgres=False, proxy=proxy)
    if portal == "fotocasa":
        from scrapers.scrapling_fotocasa import ScraplingFotocasa
        return ScraplingFotocasa(save_to_postgres=False, proxy=proxy)
    if portal == "milanuncios":
        from scrapers.scrapling_milanuncios import ScraplingMilanuncios
        return ScraplingMilanuncios(save_to_postgres=False, proxy=proxy)
    if portal == "idealista":
        from scrapers.scrapling_idealista_bd import ScraplingIdealistaBD
        return ScraplingIdealistaBD(save_to_postgres=False)
    raise ValueError(f"Portal desconocido: {portal}")


class LeadRefresher:
    DELAY = 2.5  # cortesía entre peticiones

    def __init__(self, dry_run: bool = False, proxy: Optional[str] = None,
                 update_prices: bool = False):
        self.conn = _db()
        self.dry_run = dry_run
        self.proxy = proxy
        # Price update is OPT-IN: the per-portal detail price parsers are not all
        # reliable (habitaclia's returns a constant bogus value), so writing the
        # re-parsed price by default would corrupt data. The authoritative
        # price-drop signal lives in raw.listing_price_history (scrape-time
        # prices) and is surfaced by scripts/opportunities_report.py instead.
        self.update_prices = update_prices
        self.stats = {
            "checked": 0, "removed": 0, "agency": 0,
            "price_changed": 0, "unchanged": 0, "errors": 0,
        }
        self.events: List[str] = []

    def _safe_rollback(self):
        try:
            self.conn.rollback()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def get_leads(self, portal: str, limit: int) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        # El anuncio_id real del portal (el que vive en raw_data->>'anuncio_id')
        # es el último segmento de data_lake_path, NO source_listing_id (que es
        # un id surrogate y solo coincide por casualidad en idealista). Usar el
        # id equivocado haría que los UPDATE/DELETE sobre raw no afectaran a
        # ninguna fila en habitaclia/fotocasa/milanuncios.
        cur.execute(
            """
            SELECT d.lead_id,
                   (regexp_match(d.data_lake_path, '([^/]+)$'))[1] AS anuncio_id,
                   d.listing_url, d.precio, d.es_particular, d.tenant_id, d.titulo
            FROM public_marts.dim_leads d
            LEFT JOIN leads_lead_estado e ON d.lead_id = e.lead_id
            WHERE d.source_portal = %s
              AND d.listing_url IS NOT NULL AND d.listing_url <> ''
              AND d.data_lake_path IS NOT NULL
              AND (e.estado IS NULL OR e.estado NOT IN %s)
            ORDER BY d.ultima_actualizacion ASC NULLS FIRST
            LIMIT %s
            """,
            (portal, EXCLUDED_ESTADOS, limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {"lead_id": r[0], "anuncio_id": str(r[1]) if r[1] else "", "url": r[2],
             "precio": r[3], "es_particular": r[4], "tenant_id": r[5], "titulo": r[6]}
            for r in rows
        ]

    # ------------------------------------------------------------------
    def _mark_sold(self, lead: Dict[str, Any]):
        if self.dry_run:
            return
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads_lead_estado (lead_id, tenant_id, telefono_norm, estado,
                fecha_cambio_estado, numero_intentos)
            VALUES (%s, %s, '', 'YA_VENDIDO', NOW(), 0)
            ON CONFLICT (lead_id) DO UPDATE SET estado='YA_VENDIDO', fecha_cambio_estado=NOW()
            """,
            (lead["lead_id"], lead["tenant_id"]),
        )
        self.conn.commit()
        cur.close()

    def _blacklist_agency(self, lead: Dict[str, Any]):
        """Mismo efecto que el botón 'Es agencia': blacklist + borra raw + dim_leads."""
        if self.dry_run:
            return
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads_anuncio_blacklist (tenant_id, portal, anuncio_id, url_anuncio, titulo, motivo, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (tenant_id, portal, anuncio_id) DO UPDATE SET motivo=EXCLUDED.motivo
            """,
            (lead["tenant_id"], lead["portal"], lead["anuncio_id"],
             lead["url"] or "", (lead["titulo"] or "")[:500],
             "Re-scrape: detectado como agencia"),
        )
        cur.execute(
            "DELETE FROM raw.raw_listings WHERE tenant_id=%s AND portal=%s AND raw_data->>'anuncio_id'=%s",
            (lead["tenant_id"], lead["portal"], lead["anuncio_id"]),
        )
        cur.execute(
            "DELETE FROM public_marts.dim_leads WHERE tenant_id=%s AND source_portal=%s AND lead_id=%s",
            (lead["tenant_id"], lead["portal"], lead["lead_id"]),
        )
        cur.execute("DELETE FROM leads_lead_estado WHERE lead_id=%s", (lead["lead_id"],))
        self.conn.commit()
        cur.close()

    def _update_price(self, lead: Dict[str, Any], nuevo: float):
        if self.dry_run:
            return
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE raw.raw_listings
            SET raw_data = jsonb_set(raw_data, '{precio}', to_jsonb(%s::numeric)),
                scraping_timestamp = NOW()
            WHERE tenant_id=%s AND portal=%s AND raw_data->>'anuncio_id'=%s
            """,
            (nuevo, lead["tenant_id"], lead["portal"], lead["anuncio_id"]),
        )
        cur.execute(
            """
            INSERT INTO raw.listing_price_history (tenant_id, portal, anuncio_id, precio)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, portal, anuncio_id, precio) DO NOTHING
            """,
            (lead["tenant_id"], lead["portal"], lead["anuncio_id"], nuevo),
        )
        self.conn.commit()
        cur.close()

    # ------------------------------------------------------------------
    def refresh_portal(self, portal: str, limit: int):
        leads = self.get_leads(portal, limit)
        if not leads:
            logger.info(f"[{portal}] sin leads que refrescar")
            return
        logger.info(f"[{portal}] refrescando {len(leads)} leads (dry_run={self.dry_run})")
        scraper = _make_scraper(portal, self.proxy)

        if portal == "idealista":
            self._refresh_with_bd(scraper, leads, portal)
        else:
            self._refresh_with_session(scraper, leads, portal)

    def _refresh_with_session(self, scraper, leads, portal):
        from scrapling.fetchers import StealthySession
        action = scraper.detail_page_action()
        with StealthySession(**scraper.get_session_kwargs()) as session:
            for lead in leads:
                lead["portal"] = portal
                try:
                    kw = {"network_idle": True, "wait": 2000}
                    if action is not None:
                        kw["page_action"] = action
                    page = session.fetch(lead["url"], **kw)
                    self._reconcile(scraper, page, lead, portal)
                except Exception as e:
                    logger.warning(f"  {lead['anuncio_id']} error: {e}")
                    self.stats["errors"] += 1
                    self._safe_rollback()
                time.sleep(self.DELAY)

    def _refresh_with_bd(self, scraper, leads, portal):
        for lead in leads:
            lead["portal"] = portal
            try:
                page = scraper._bd_fetch(lead["url"])
                if page is None:
                    self.stats["errors"] += 1
                    continue
                self._reconcile(scraper, page, lead, portal)
            except Exception as e:
                logger.warning(f"  {lead['anuncio_id']} error: {e}")
                self.stats["errors"] += 1
                self._safe_rollback()
            time.sleep(self.DELAY)

    def _reconcile(self, scraper, page, lead, portal):
        self.stats["checked"] += 1

        # 1) ¿Baja? — página bloqueada/vacía/redirigida
        if scraper._is_blocked_page(page):
            self.stats["removed"] += 1
            self.events.append(f"BAJA  {portal} {lead['anuncio_id']} ({lead['titulo'] or ''})")
            self._mark_sold(lead)
            return

        # Re-parse con el parser real del portal
        parsed = dict(lead)
        parsed["url_anuncio"] = lead["url"]
        parsed["es_particular"] = lead.get("es_particular", True)
        try:
            parsed = scraper.parse_detail_page(page, parsed) or parsed
        except Exception as e:
            logger.debug(f"  parse fallo {lead['anuncio_id']}: {e}")

        # 2) ¿Ahora es agencia? (solo portales con señal fiable en el detalle)
        if portal in AGENCY_REEVAL_PORTALS and parsed.get("es_particular") is False \
                and lead.get("es_particular") is True:
            self.stats["agency"] += 1
            self.events.append(f"AGENCIA  {portal} {lead['anuncio_id']} ({lead['titulo'] or ''})")
            self._blacklist_agency(lead)
            return

        # 3) ¿Cambió el precio? (solo si se pide explícitamente — ver __init__)
        if not self.update_prices:
            self.stats["unchanged"] += 1
            return
        nuevo = parsed.get("precio")
        viejo = float(lead["precio"]) if lead["precio"] is not None else None
        if nuevo is not None and viejo is not None and abs(float(nuevo) - viejo) >= 1:
            pct = 100 * (float(nuevo) - viejo) / viejo
            self.stats["price_changed"] += 1
            arrow = "v" if nuevo < viejo else "^"
            self.events.append(
                f"PRECIO {arrow} {portal} {lead['anuncio_id']}: {viejo:.0f}->{float(nuevo):.0f}EUR ({pct:+.1f}%)"
            )
            self._update_price(lead, float(nuevo))
        else:
            self.stats["unchanged"] += 1

    # ------------------------------------------------------------------
    def report(self):
        s = self.stats
        print("\n=== RE-SCRAPE DE LEADS ===")
        for k in ("checked", "removed", "agency", "price_changed", "unchanged", "errors"):
            print(f"  {k:14} {s[k]}")
        if self.events:
            print("\nEventos:")
            for e in self.events[:50]:
                print("  " + e)
        # Telegram
        if s["checked"] and (s["removed"] or s["agency"] or s["price_changed"]):
            msg = (f"<b>♻️ Re-scrape de leads</b>\n"
                   f"Revisados: {s['checked']}\n"
                   f"Bajas (vendidos): {s['removed']}\n"
                   f"Reclasificados agencia: {s['agency']}\n"
                   f"Cambios de precio: {s['price_changed']}")
            _telegram(msg)

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--portal", help="habitaclia|fotocasa|milanuncios|idealista (omitir = los seguros)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update-prices", action="store_true",
                    help="re-escribir precios desde el detalle (OJO: parsers no fiables)")
    ap.add_argument("--proxy", default=os.environ.get("DATADOME_PROXY", ""))
    args = ap.parse_args()

    portals = [args.portal] if args.portal else ["habitaclia", "fotocasa"]
    r = LeadRefresher(dry_run=args.dry_run, proxy=args.proxy or None,
                      update_prices=args.update_prices)
    try:
        for p in portals:
            r.refresh_portal(p, args.limit)
    finally:
        r.report()
        r.close()


if __name__ == "__main__":
    main()

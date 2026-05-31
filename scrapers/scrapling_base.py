"""
Base class para scrapers basados en Scrapling (Patchright stealth + curl_cffi).

Diferencias vs Camoufox:
- Bypass DataDome / Imperva sin proxy (probado contra los 4 portales)
- StealthySession con cookies persistentes (1 browser por scrape, todos los detalles dentro)
- API más simple (page.css(...), page.html_content)
- Sin dependencia 2Captcha para Cloudflare (solve_cloudflare=True nativo)

Uso típico (subclase):
    class ScraplingIdealista(ScraplingBaseScraper):
        PORTAL_NAME = "idealista"
        BASE_URL = "https://www.idealista.com"
        ZONAS = ZONAS_GEOGRAFICAS  # importado del scraper actual

        def build_search_url(self, zona_key, page=1): ...
        def parse_search_page(self, page) -> List[dict]: ...
        def parse_detail_page(self, page, listing) -> dict: ...

    s = ScraplingIdealista(tenant_id=1, zones=["salou"])
    s.run()
"""
import hashlib
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg2

logger = logging.getLogger(__name__)

# Load .env once on import — needed when running scrapers via `python -m scrapers.scrapling_*`
# without a wrapper. Project root is the parent of scrapers/.
try:
    from dotenv import load_dotenv as _load_dotenv
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # backend/.env is the source of truth (points to Neon); root .env is legacy localhost.
    # Load backend first so its DATABASE_URL wins over the root file.
    for _path in (
        os.path.join(_project_root, "backend", ".env"),
        os.path.join(_project_root, ".env"),
    ):
        if os.path.exists(_path):
            _load_dotenv(_path, override=False)
except ImportError:
    pass


def get_db_config() -> Dict[str, Any]:
    """Build psycopg2 config dict from DATABASE_URL or NEON_DATABASE_URL."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL or NEON_DATABASE_URL must be set")
    p = urlparse(url)
    return {
        "host": p.hostname,
        "port": p.port or 5432,
        "database": p.path.lstrip("/").split("?")[0],
        "user": p.username,
        "password": p.password,
        "sslmode": "require" if "neon.tech" in (p.hostname or "") else None,
    }


class ScraplingBaseScraper:
    """Base class for Scrapling-based portal scrapers."""

    # --- subclass overrides ---
    PORTAL_NAME: str = ""
    BASE_URL: str = ""
    ZONAS: Dict[str, Any] = {}

    # Domains observed wasting bandwidth in IPRoyal usage report (Feb–Mar 2026):
    # 5.75 GB consumed in 20 days; 76.8% was waste. Blocking these saves ~$45/mes.
    WASTE_DOMAINS = {
        # idealista HD video previews — 2.1 GB / 36% of total alone
        "st3v.idealista.com",
        # uBlock / malware / phishing filter lists fetched *through the proxy* (387 MB / 6.6%)
        "ublockorigin.pages.dev", "ublockorigin.github.io",
        "malware-filter.gitlab.io", "malware-filter.pages.dev",
        "phishing-filter.pages.dev",
        "pgl.yoyo.org", "filters.adtidy.org",
        "curbengh.github.io", "cdn.statically.io",
        # Google/Apple/embedded widgets — 280 MB / 4.8%
        "accounts.google.com", "apis.google.com", "play.google.com",
        "maps.googleapis.com", "maps.gstatic.com",
        "fonts.googleapis.com", "fonts.gstatic.com",
        "appleid.cdn-apple.com",
        # Third-party embeds inside portal pages
        "widget.trustpilot.com", "connect.facebook.net", "www.facebook.com",
        "sdk.privacy-center.org",
        "cdn.jsdelivr.net", "unpkg.com", "code.jquery.com",
        # OCSP / cert validation — tiny but adds up across requests
        "o.pki.goog", "ocsp.digicert.com", "ocsp.globalsign.com",
        "ocsp.r2m01.amazontrust.com", "ocsp.r2m04.amazontrust.com",
        "ocsp.e2m01.amazontrust.com", "status.rapidssl.com",
        # IP-check services the browser pings on startup
        "api.ipify.org", "ipv4.icanhazip.com", "checkip.amazonaws.com", "ipinfo.io",
    }

    # Stealth defaults — subclasses can tweak per portal.
    # Bandwidth controls (disable_resources, block_ads, blocked_domains) added
    # 2026-05-23 after the IPRoyal usage audit showed ~70% of traffic was
    # images/fonts/ads we never use. Image URLs are still preserved in <img src>
    # HTML attrs — only the binary download is dropped.
    SESSION_KWARGS: Dict[str, Any] = {
        "headless": True,
        "humanize": True,
        "block_webrtc": True,
        "solve_cloudflare": True,
        "google_search": True,
        "timeout": 60000,
        "max_pages": 5,
        "network_idle": True,
        "disable_resources": True,   # font/image/media/stylesheet/beacon/etc.
        "block_ads": True,           # ~3500 ad/tracking domains
        "blocked_domains": WASTE_DOMAINS,
    }

    DETAIL_DELAY_RANGE = (2.0, 5.0)
    SEARCH_DELAY_RANGE = (3.0, 6.0)

    def __init__(
        self,
        tenant_id: int = 1,
        zones: Optional[List[str]] = None,
        max_pages: int = 2,
        only_private: bool = True,
        save_to_postgres: bool = True,
        proxy: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.zones = zones or []
        self.max_pages = max_pages
        self.only_private = only_private
        self.save_to_postgres = save_to_postgres
        self.proxy = proxy
        self.postgres_conn: Optional[psycopg2.extensions.connection] = None
        self.stats = {
            "listings_found": 0,
            "listings_saved": 0,
            "listings_skipped": 0,
            "errors": 0,
            "details_fetched": 0,
            "details_blocked": 0,
            "zones_completed": 0,
            "zones_failed": 0,
        }
        if save_to_postgres:
            self._init_postgres()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    def _init_postgres(self):
        cfg = get_db_config()
        params = {k: v for k, v in cfg.items() if v is not None}
        self.postgres_conn = psycopg2.connect(**params)
        logger.info(f"PostgreSQL connected: {cfg['host']}")

    def _ensure_db(self):
        try:
            if self.postgres_conn and not self.postgres_conn.closed:
                cur = self.postgres_conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                return
        except Exception:
            logger.warning("DB connection dropped, reconnecting")
        self._init_postgres()

    # Label for the proxy/service used, recorded per-zone for the cost study.
    # Subclasses using a managed service (e.g. Bright Data) override this.
    SERVICE_LABEL: Optional[str] = None

    def _service_label(self) -> str:
        if self.SERVICE_LABEL:
            return self.SERVICE_LABEL
        return "proxy" if self.proxy else "none"

    def record_zone_metrics(self, zona_key: str, before: Dict[str, int], elapsed: float):
        """Persist per-zone operational metrics to raw.scraper_zone_runs.

        Complements raw.raw_listings (which captures yield/particular per zone)
        with the operational layer raw can't hold: timing, blocks, detail
        fetches and which proxy/service was used. Feeds the performance study
        (scripts/portal_zone_report.py) on the cost/speed axis.
        Best-effort: never let metrics logging break a scrape.
        """
        if not self.postgres_conn:
            return
        s = self.stats
        delta = {k: s.get(k, 0) - before.get(k, 0) for k in (
            "listings_found", "listings_saved", "listings_skipped",
            "details_fetched", "details_blocked", "errors",
        )}
        try:
            self._ensure_db()
            cur = self.postgres_conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS raw.scraper_zone_runs (
                    id              bigserial PRIMARY KEY,
                    tenant_id       integer,
                    portal          text,
                    zona            text,
                    scraped_at      timestamptz DEFAULT now(),
                    found           integer,
                    saved           integer,
                    skipped         integer,
                    details_fetched integer,
                    details_blocked integer,
                    errors          integer,
                    elapsed_seconds numeric,
                    service         text
                )
                """
            )
            cur.execute(
                """
                INSERT INTO raw.scraper_zone_runs
                  (tenant_id, portal, zona, found, saved, skipped,
                   details_fetched, details_blocked, errors, elapsed_seconds, service)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    self.tenant_id, self.PORTAL_NAME, zona_key,
                    delta["listings_found"], delta["listings_saved"], delta["listings_skipped"],
                    delta["details_fetched"], delta["details_blocked"], delta["errors"],
                    round(elapsed, 1), self._service_label(),
                ),
            )
            self.postgres_conn.commit()
            cur.close()
        except Exception as e:
            logger.debug(f"record_zone_metrics skipped: {e}")
            try:
                self.postgres_conn.rollback()
            except Exception:
                pass

    def _is_blacklisted(self, anuncio_id: str) -> bool:
        if not self.postgres_conn:
            return False
        try:
            cur = self.postgres_conn.cursor()
            cur.execute(
                "SELECT 1 FROM leads_anuncio_blacklist "
                "WHERE tenant_id = %s AND portal = %s AND anuncio_id = %s LIMIT 1",
                (self.tenant_id, self.PORTAL_NAME, anuncio_id),
            )
            r = cur.fetchone()
            cur.close()
            return r is not None
        except Exception:
            return False

    def save_listing(self, listing: Dict[str, Any]) -> bool:
        """Save listing to raw.raw_listings (JSONB). Schema-compatible with Camoufox scrapers."""
        if not self.save_to_postgres or not self.postgres_conn:
            return False

        anuncio_id = str(listing.get("anuncio_id", "")).strip()
        if not anuncio_id:
            self.stats["errors"] += 1
            return False

        if self._is_blacklisted(anuncio_id):
            self.stats["listings_skipped"] += 1
            return False

        # Data-quality gate: require at least titulo OR precio. Otherwise the
        # row is just (anuncio_id, url) which is useless and pollutes raw.
        # This typically happens when detail-page was blocked for portals
        # whose search card only carries the URL+id (e.g. fotocasa).
        if not (listing.get("titulo") or listing.get("precio")):
            self.stats["listings_skipped"] += 1
            return False

        # Mirror the schema used by camoufox scrapers (raw.raw_listings.raw_data JSONB)
        raw_data = {
            "anuncio_id": anuncio_id,
            "titulo": listing.get("titulo", ""),
            "telefono": listing.get("telefono", ""),
            "telefono_norm": listing.get("telefono_norm", ""),
            "email": listing.get("email"),
            "nombre": listing.get("vendedor", ""),
            "direccion": listing.get("direccion") or listing.get("ubicacion", ""),
            "zona": listing.get("zona_geografica", ""),
            "zona_busqueda": listing.get("zona_busqueda", ""),
            "zona_geografica": listing.get("zona_geografica", ""),
            "codigo_postal": listing.get("codigo_postal"),
            "tipo_inmueble": listing.get("tipo_inmueble", "piso"),
            "precio": listing.get("precio"),
            "habitaciones": listing.get("habitaciones"),
            "metros": listing.get("metros"),
            "descripcion": listing.get("descripcion", ""),
            "fotos": listing.get("fotos", []),
            "url": listing.get("url_anuncio", ""),
            "es_particular": listing.get("es_particular", False),
            "verified": listing.get("verified", False),
            "vendedor": listing.get("vendedor", ""),
            "seller_type": listing.get("seller_type"),
            "scraper_type": "scrapling",
        }
        # Optional portal-specific fields can be passed through unchanged
        for k in ("hasShop", "shopName", "isPrivate", "sellerBadge",
                  "municipio", "latitud", "longitud"):
            if listing.get(k) is not None:
                raw_data[k] = listing[k]

        try:
            self._ensure_db()
            cur = self.postgres_conn.cursor()
            now = datetime.now()
            data_lake_path = (
                f"scrapling/{self.PORTAL_NAME}/{now.strftime('%Y/%m/%d')}/{anuncio_id}"
            )
            cur.execute(
                """
                INSERT INTO raw.raw_listings (
                    tenant_id, portal, data_lake_path, raw_data, scraping_timestamp
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, portal, (raw_data->>'anuncio_id'))
                WHERE raw_data->>'anuncio_id' IS NOT NULL
                DO UPDATE SET
                    raw_data = EXCLUDED.raw_data,
                    scraping_timestamp = EXCLUDED.scraping_timestamp
                """,
                (
                    self.tenant_id,
                    self.PORTAL_NAME,
                    data_lake_path,
                    json.dumps(raw_data, ensure_ascii=False),
                    now,
                ),
            )
            saved = cur.rowcount > 0
            self.postgres_conn.commit()

            # Track price history
            precio = listing.get("precio")
            if precio and saved:
                try:
                    cur2 = self.postgres_conn.cursor()
                    cur2.execute(
                        """
                        INSERT INTO raw.listing_price_history (tenant_id, portal, anuncio_id, precio)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (tenant_id, portal, anuncio_id, precio) DO NOTHING
                        """,
                        (self.tenant_id, self.PORTAL_NAME, anuncio_id, precio),
                    )
                    self.postgres_conn.commit()
                    cur2.close()
                except Exception as e:
                    logger.debug(f"price_history insert skipped: {e}")

            cur.close()
            if saved:
                self.stats["listings_saved"] += 1
            return saved
        except Exception as e:
            logger.error(f"save_listing failed: {e}")
            self.stats["errors"] += 1
            try:
                self.postgres_conn.rollback()
            except Exception:
                pass
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def parse_price(text: str) -> Optional[float]:
        if not text:
            return None
        try:
            t = re.sub(r"[€$\s\xa0.]", "", text)
            t = t.replace(",", ".")
            return float(t) if t else None
        except Exception:
            return None

    @staticmethod
    def normalize_phone(phone: str) -> Optional[str]:
        if not phone:
            return None
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 9 and digits[0] in "6789":
            return digits
        if len(digits) == 11 and digits.startswith("34"):
            return digits[2:]
        return None

    def generate_lead_id(self, anuncio_id: str) -> int:
        s = f"{self.tenant_id}:{self.PORTAL_NAME}:{anuncio_id}"
        return int(hashlib.md5(s.encode()).hexdigest(), 16) % 2147483647

    def human_delay(self, range_t: tuple = None):
        a, b = range_t or self.DETAIL_DELAY_RANGE
        env_min = float(os.environ.get("SCRAPER_MIN_DELAY", "0"))
        a = max(a, env_min)
        b = max(b, a)
        time.sleep(random.uniform(a, b))

    def get_session_kwargs(self) -> Dict[str, Any]:
        kw = dict(self.SESSION_KWARGS)
        if self.proxy:
            proxy = self.proxy.strip()
            if proxy and "://" not in proxy:
                proxy = "http://" + proxy  # Scrapling requires scheme
            kw["proxy"] = proxy

        # Allow killing bandwidth controls per-run if a portal stops working
        # because of them. SCRAPLING_DISABLE_RESOURCES=false disables the block.
        if os.environ.get("SCRAPLING_DISABLE_RESOURCES", "").lower() == "false":
            kw.pop("disable_resources", None)
            logger.info(f"[{self.PORTAL_NAME}] disable_resources OFF (env override)")
        if os.environ.get("SCRAPLING_BLOCK_ADS", "").lower() == "false":
            kw.pop("block_ads", None)
        return kw

    # ------------------------------------------------------------------
    # Subclass-overridable methods
    # ------------------------------------------------------------------
    def build_search_url(self, zona_key: str, page: int = 1) -> str:
        raise NotImplementedError

    def parse_search_page(self, page, zona_key: str) -> List[Dict[str, Any]]:
        """Return list of listing dicts (must include 'anuncio_id' and 'url_anuncio')."""
        raise NotImplementedError

    def parse_detail_page(self, page, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Return enriched listing dict (telephone, fotos, descripcion, etc.).
        Default: return listing unchanged (search-only scrape)."""
        return listing

    def should_skip(self, listing: Dict[str, Any]) -> bool:
        """Subclass hook to filter listings (price floor, duplicates, etc.)."""
        precio = listing.get("precio")
        if precio is not None and precio < 10000:
            return True
        if self.only_private and listing.get("es_particular") is False:
            return True
        return False

    def detail_page_action(self):
        """Return a callable(page) -> None executed AFTER navigation on detail
        pages. Useful for clicking phone-reveal buttons or accepting cookies
        before the HTML is captured. Default: None (no action).
        Override in subclasses that need it (e.g. idealista phone reveal).
        """
        return None

    def search_page_action(self):
        """Return a callable(page) -> None executed AFTER navigation on search
        pages. Useful for scrolling to hydrate lazy-loaded cards. Default:
        None. Override in subclasses (e.g. fotocasa skeleton hydration).
        """
        return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        from scrapling.fetchers import StealthySession

        if not self.zones:
            self.zones = list(self.ZONAS.keys())

        logger.info(
            f"[{self.PORTAL_NAME}] Starting scrape | tenant={self.tenant_id} "
            f"zones={self.zones} max_pages={self.max_pages} proxy={'yes' if self.proxy else 'no'}"
        )
        start = datetime.now()

        kwargs = self.get_session_kwargs()
        # max_pages here is Scrapling's browser-tab pool, not URL pages
        # Bumping it slightly to allow concurrent fetches for details
        kwargs["max_pages"] = max(kwargs.get("max_pages", 5), 5)

        with StealthySession(**kwargs) as session:
            for zona_key in self.zones:
                if zona_key not in self.ZONAS:
                    logger.warning(f"[{self.PORTAL_NAME}] Zone not found: {zona_key}")
                    self.stats["zones_failed"] += 1
                    continue
                before = dict(self.stats)
                t0 = time.time()
                try:
                    self._scrape_zone(session, zona_key)
                    self.stats["zones_completed"] += 1
                except Exception as e:
                    logger.exception(f"[{self.PORTAL_NAME}] zone={zona_key} failed: {e}")
                    self.stats["zones_failed"] += 1
                    self.stats["errors"] += 1
                finally:
                    self.record_zone_metrics(zona_key, before, time.time() - t0)

        elapsed = (datetime.now() - start).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"[{self.PORTAL_NAME}] DONE in {elapsed:.0f}s | "
            f"found={self.stats['listings_found']} saved={self.stats['listings_saved']} "
            f"errors={self.stats['errors']} blocked={self.stats['details_blocked']}"
        )
        return self.stats

    def _scrape_zone(self, session, zona_key: str):
        for page_num in range(1, self.max_pages + 1):
            url = self.build_search_url(zona_key, page_num)
            logger.info(f"[{self.PORTAL_NAME}] {zona_key} p{page_num}: {url}")
            try:
                fetch_kwargs = {"network_idle": True, "wait": 2000}
                action = self.search_page_action()
                if action is not None:
                    fetch_kwargs["page_action"] = action
                page = session.fetch(url, **fetch_kwargs)
            except Exception as e:
                logger.warning(f"  fetch failed: {e}")
                self.stats["errors"] += 1
                break

            if self._is_blocked_page(page):
                logger.warning(f"  page blocked, stopping zone")
                self.stats["details_blocked"] += 1
                break

            listings = self.parse_search_page(page, zona_key) or []
            self.stats["listings_found"] += len(listings)
            logger.info(f"  parsed {len(listings)} listings")

            if not listings:
                break  # empty page = end of pagination

            for listing in listings:
                if self.should_skip(listing):
                    self.stats["listings_skipped"] += 1
                    continue
                # Optional detail enrichment
                detail_url = listing.get("url_anuncio")
                if detail_url and self._wants_detail():
                    try:
                        self.human_delay(self.DETAIL_DELAY_RANGE)
                        fetch_kwargs = {"network_idle": True, "wait": 2000}
                        action = self.detail_page_action()
                        if action is not None:
                            fetch_kwargs["page_action"] = action
                        dpage = session.fetch(detail_url, **fetch_kwargs)
                        if self._is_blocked_page(dpage):
                            self.stats["details_blocked"] += 1
                        else:
                            self.stats["details_fetched"] += 1
                            listing = self.parse_detail_page(dpage, listing) or listing
                    except Exception as e:
                        logger.debug(f"  detail fetch failed for {detail_url}: {e}")
                        self.stats["errors"] += 1

                self.save_listing(listing)

            self.human_delay(self.SEARCH_DELAY_RANGE)

    def _wants_detail(self) -> bool:
        """Override to disable detail-page enrichment (e.g. milanuncios where search has all data)."""
        return True

    def _is_blocked_page(self, page) -> bool:
        try:
            status = getattr(page, "status", None)
            if status in (403, 429, 503):
                return True
            html = getattr(page, "html_content", "") or ""
            if not html or len(html) < 5000:
                return True
            low = html.lower()
            if "geo.captcha-delivery.com" in low or "datadome" in low and len(html) < 50000:
                return True
            if "incapsula incident" in low or "_incapsula_resource" in low:
                return True
            return False
        except Exception:
            return False

"""
Test Scrapling vs los 4 portales SIN PROXY.

Objetivo: validar empíricamente si Scrapling+Patchright bypasea:
- DataDome (idealista)
- Imperva (habitaclia, fotocasa)
- GeeTest (milanuncios)

Uso:
    python scripts/test_scrapling_portals.py
    python scripts/test_scrapling_portals.py --portal idealista
    python scripts/test_scrapling_portals.py --proxy "http://user:pass@host:port"

Output: JSON por portal con bloqueo/contenido/listings
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from scrapling.fetchers import StealthyFetcher

# URLs de búsqueda reales (zonas pequeñas, pocos resultados)
TEST_URLS = {
    "idealista": "https://www.idealista.com/venta-viviendas/igualada-barcelona/",
    "fotocasa": "https://www.fotocasa.es/es/comprar/viviendas/salou/todas-las-zonas/l",
    "habitaclia": "https://www.habitaclia.com/viviendas-salou.htm",
    "milanuncios": "https://www.milanuncios.com/venta-de-pisos-en-tarragona/",
}

# Patrones que indican bloqueo
BLOCK_INDICATORS = {
    "datadome": [
        "geo.captcha-delivery.com",
        "datadome",
        "Please verify you are a human",
        "DDOS protection",
    ],
    "imperva": [
        "Incapsula incident",
        "incap_ses",
        "Pardon Our Interruption",
        "_Incapsula_Resource",
    ],
    "cloudflare": [
        "Just a moment...",
        "challenges.cloudflare.com",
        "cf-mitigated",
        "ray-id",
    ],
    "geetest": [
        "geetest",
        "captcha_id",
        "gt_captcha",
    ],
}

# Selectores básicos de listings (heurística — confirma que se ve la página real)
LISTING_SELECTORS = {
    "idealista": ["article.item", ".item-info-container", "a.item-link"],
    "fotocasa": ["a[href*='/es/comprar/vivienda/']", "article", ".re-Card"],
    "habitaclia": ["a[href*='/comprar-']", ".list-item-info"],
    "milanuncios": ["article", "a[href*='/anuncios/']", "[data-testid='ad-card']"],
}


def detect_block(html: str) -> dict:
    """Detect anti-bot indicators in HTML."""
    html_lower = html.lower()
    found = {}
    for system, patterns in BLOCK_INDICATORS.items():
        hits = [p for p in patterns if p.lower() in html_lower]
        if hits:
            found[system] = hits
    return found


def count_listings(page, portal: str) -> int:
    """Cuenta listings encontrados con selectores heurísticos."""
    selectors = LISTING_SELECTORS.get(portal, [])
    counts = {}
    for sel in selectors:
        try:
            elements = page.css(sel)
            counts[sel] = len(elements) if elements else 0
        except Exception as e:
            counts[sel] = f"ERROR: {e}"
    return counts


def test_portal(portal: str, url: str, proxy: Optional[str] = None, headless: bool = True) -> dict:
    """Test 1 portal con StealthyFetcher."""
    print(f"\n{'='*70}")
    print(f"TEST: {portal.upper()} - {url}")
    if proxy:
        print(f"PROXY: {proxy[:30]}...")
    else:
        print("PROXY: NONE (direct connection)")
    print(f"{'='*70}\n")

    result = {
        "portal": portal,
        "url": url,
        "proxy": bool(proxy),
        "headless": headless,
        "success": False,
        "status": None,
        "html_size": 0,
        "title": None,
        "blocked_by": {},
        "listings_found": {},
        "error": None,
        "duration_s": None,
    }

    start = time.time()
    try:
        kwargs = {
            "headless": headless,
            "network_idle": True,
            "timeout": 60000,
            "humanize": True,
            "block_webrtc": True,
            "solve_cloudflare": True,
            "google_search": True,
            "wait": 2000,
        }
        if proxy:
            kwargs["proxy"] = proxy

        page = StealthyFetcher.fetch(url, **kwargs)

        result["status"] = page.status if hasattr(page, "status") else "unknown"
        html = str(page)
        result["html_size"] = len(html)

        # Title
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            result["title"] = title_match.group(1).strip()[:200]

        # Block detection
        result["blocked_by"] = detect_block(html)

        # Listing count
        result["listings_found"] = count_listings(page, portal)

        # Success heuristic: has listings + no block
        has_listings = any(
            isinstance(c, int) and c > 0
            for c in result["listings_found"].values()
        )
        is_blocked = bool(result["blocked_by"])

        result["success"] = has_listings and not is_blocked

        print(f"Status: {result['status']}")
        print(f"HTML size: {result['html_size']:,} bytes")
        print(f"Title: {result['title']}")
        print(f"Blocked by: {result['blocked_by'] or 'NONE'}")
        print(f"Listings: {result['listings_found']}")
        print(f"SUCCESS: {result['success']}")

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        print(f"ERROR: {result['error']}")

    result["duration_s"] = round(time.time() - start, 2)
    print(f"Duration: {result['duration_s']}s")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portal", choices=list(TEST_URLS.keys()), help="Test 1 portal")
    ap.add_argument("--proxy", help="Optional proxy http://user:pass@host:port")
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--no-headless", dest="headless", action="store_false")
    ap.add_argument("--out", default="scripts/scrapling_test_results.json")
    args = ap.parse_args()

    portals_to_test = [args.portal] if args.portal else list(TEST_URLS.keys())
    results = []

    for p in portals_to_test:
        url = TEST_URLS[p]
        try:
            r = test_portal(p, url, proxy=args.proxy, headless=args.headless)
            results.append(r)
        except Exception as e:
            results.append({"portal": p, "error": f"FATAL: {e}"})

    # Save
    out = Path(args.out)
    out.parent.mkdir(exist_ok=True, parents=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"RESULTS SAVED: {out}")
    print(f"{'='*70}")
    success_count = sum(1 for r in results if r.get("success"))
    print(f"\nSUMMARY: {success_count}/{len(results)} portals scraped successfully")
    for r in results:
        flag = "OK " if r.get("success") else "FAIL"
        blocked = ",".join(r.get("blocked_by", {}).keys()) or "-"
        print(f"  [{flag}] {r['portal']:12s} blocked_by={blocked} listings_max={max((c for c in r.get('listings_found', {}).values() if isinstance(c, int)), default=0)}")


if __name__ == "__main__":
    main()

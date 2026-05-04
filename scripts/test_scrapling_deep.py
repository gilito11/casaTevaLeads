"""
Test PROFUNDO: extrae datos reales (title, prices, URLs) de cada portal.
Confirma que no es soft block ni página vacía.
"""
import json
import re
import sys
import time
from pathlib import Path

from scrapling.fetchers import StealthyFetcher

URLS = {
    "idealista": "https://www.idealista.com/venta-viviendas/igualada-barcelona/",
    "fotocasa": "https://www.fotocasa.es/es/comprar/viviendas/salou/todas-las-zonas/l",
    "habitaclia": "https://www.habitaclia.com/viviendas-salou.htm",
    "milanuncios": "https://www.milanuncios.com/venta-de-pisos-en-tarragona/",
}

# Selector strategies por portal (basado en scrapers actuales)
EXTRACTORS = {
    "idealista": {
        "container": "article.item",
        "title": "a.item-link",
        "price": ".item-price, span.item-price",
        "size": ".item-detail",
    },
    "fotocasa": {
        "container": "article",
        "title": "a[href*='/es/comprar/vivienda/']",
        "price": "[class*='price']",
        "size": "[class*='surface']",
    },
    "habitaclia": {
        "container": "article, .list-item-info, [class*='item']",
        "title": "a[href*='-i'], h3 a, .list-item-title",
        "price": "[class*='price'], .price",
        "size": "[class*='size'], [class*='m2']",
    },
    "milanuncios": {
        "container": "article, [class*='ListItem']",
        "title": "h3, [class*='title']",
        "price": "[class*='price']",
        "size": "[class*='size']",
    },
}


def text_or_empty(el):
    try:
        if el is None:
            return ""
        if hasattr(el, "text"):
            t = el.text
            return t.clean() if hasattr(t, "clean") else str(t).strip()
        return str(el).strip()
    except Exception:
        return ""


def extract_sample(page, portal: str, limit: int = 5):
    rules = EXTRACTORS[portal]
    samples = []
    try:
        containers = page.css(rules["container"])
        for c in (containers or [])[:limit]:
            sample = {}
            try:
                t_el = c.css_first(rules["title"])
                sample["title"] = text_or_empty(t_el)[:120]
                sample["url"] = t_el.attrib.get("href", "") if t_el else ""
            except Exception as e:
                sample["title_err"] = str(e)[:80]
            try:
                p_el = c.css_first(rules["price"])
                sample["price"] = text_or_empty(p_el)[:80]
            except Exception:
                sample["price"] = ""
            try:
                s_el = c.css_first(rules["size"])
                sample["size"] = text_or_empty(s_el)[:80]
            except Exception:
                sample["size"] = ""
            samples.append(sample)
    except Exception as e:
        return [{"error": str(e)}]
    return samples


def deep_test(portal: str, url: str):
    print(f"\n{'='*70}\n{portal.upper()}: {url}\n{'='*70}")
    start = time.time()
    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=60000,
            humanize=True,
            block_webrtc=True,
            solve_cloudflare=True,
            google_search=True,
            wait=3000,
        )
    except Exception as e:
        return {"portal": portal, "error": str(e)}

    duration = round(time.time() - start, 2)

    # Get full HTML — page is a Selector/Adaptor; .html_content is the property
    html = ""
    for attr in ("html_content", "body", "text"):
        try:
            v = getattr(page, attr, None)
            if v and isinstance(v, str) and len(v) > 100:
                html = v
                break
            if v and not isinstance(v, str):
                v_str = str(v)
                if len(v_str) > 100:
                    html = v_str
                    break
        except Exception:
            pass

    title = ""
    m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()[:200]

    samples = extract_sample(page, portal, limit=5)

    # Real-content heuristics: page must contain typical price markers
    has_price_markers = bool(re.search(r"€\s*\d|\d[.,]\d+\s*€|EUR", html, re.IGNORECASE))
    has_address_markers = bool(re.search(r"(Salou|Tarragona|Igualada|Barcelona|m²|m2)", html, re.IGNORECASE))

    result = {
        "portal": portal,
        "url": url,
        "duration_s": duration,
        "status": getattr(page, "status", None),
        "html_length": len(html),
        "title": title,
        "has_price_markers": has_price_markers,
        "has_address_markers": has_address_markers,
        "containers_found": len(page.css(EXTRACTORS[portal]["container"]) or []),
        "samples": samples,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
    return result


def main():
    portals = sys.argv[1].split(",") if len(sys.argv) > 1 else list(URLS.keys())
    out = {}
    for p in portals:
        if p not in URLS:
            print(f"Skip {p}")
            continue
        out[p] = deep_test(p, URLS[p])

    Path("scripts/scrapling_deep_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n\nSAVED: scripts/scrapling_deep_results.json")
    print("\nSUMMARY:")
    for p, r in out.items():
        if "error" in r:
            print(f"  [{p}] ERROR: {r['error']}")
            continue
        ok = (
            r["has_price_markers"]
            and r["has_address_markers"]
            and r["containers_found"] >= 5
            and r["html_length"] >= 50000
        )
        print(
            f"  [{'OK' if ok else 'FAIL'}] {p:12s} "
            f"html={r['html_length']:>7,}  containers={r['containers_found']:>3}  "
            f"prices={r['has_price_markers']}  addr={r['has_address_markers']}"
        )


if __name__ == "__main__":
    main()

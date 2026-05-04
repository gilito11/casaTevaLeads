"""
Test de RESISTENCIA: scrapea 5 páginas idealista seguidas + 3 detalles cada una.
Si DataDome aguanta este volumen sin proxy => migration viable a producción.
"""
import json
import re
import time
from pathlib import Path

from scrapling.fetchers import StealthyFetcher

# 5 zonas distintas para evitar caché
ZONES = [
    "https://www.idealista.com/venta-viviendas/igualada-barcelona/",
    "https://www.idealista.com/venta-viviendas/salou-tarragona/",
    "https://www.idealista.com/venta-viviendas/cambrils-tarragona/",
    "https://www.idealista.com/venta-viviendas/reus-tarragona/",
    "https://www.idealista.com/venta-viviendas/tarragona-tarragona/",
]


def fetch(url):
    return StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=True,
        timeout=60000,
        humanize=True,
        block_webrtc=True,
        solve_cloudflare=True,
        google_search=True,
        wait=2000,
    )


def is_blocked(page) -> bool:
    """Heuristic: DataDome usually drops HTML drastically + adds challenge."""
    html = getattr(page, "html_content", "") or ""
    html_low = html.lower()
    if "geo.captcha-delivery.com" in html_low:
        return True
    if "datadome" in html_low and len(html) < 100000:
        return True
    if "captcha" in html_low and len(html) < 50000:
        return True
    if len(html) < 50000:
        return True
    return False


def main():
    out = []
    detail_urls = []
    print(f"\n{'='*70}\nVOLUME TEST — 5 search pages + 3 details each (idealista)\n{'='*70}")
    for i, url in enumerate(ZONES, 1):
        print(f"\n[{i}/5] SEARCH: {url}")
        t = time.time()
        try:
            page = fetch(url)
            blocked = is_blocked(page)
            articles = page.css("article.item") or []
            html_size = len(getattr(page, "html_content", "") or "")
            title_m = re.search(
                r"<title>(.*?)</title>",
                getattr(page, "html_content", "") or "",
                re.IGNORECASE | re.DOTALL,
            )
            title = title_m.group(1).strip()[:120] if title_m else ""

            # Pick up to 3 detail urls
            picked = []
            for a in articles[:3]:
                try:
                    link = a.css("a.item-link")
                    if link:
                        href = link[0].attrib.get("href", "")
                        if href.startswith("/"):
                            href = "https://www.idealista.com" + href
                        if href:
                            picked.append(href)
                except Exception:
                    pass
            detail_urls.extend(picked)

            r = {
                "step": i,
                "type": "search",
                "url": url,
                "duration_s": round(time.time() - t, 2),
                "status": getattr(page, "status", None),
                "html_size": html_size,
                "title": title,
                "articles_found": len(articles),
                "blocked": blocked,
                "picked_details": picked,
            }
            print(f"  status={r['status']} html={html_size:,} articles={len(articles)} blocked={blocked} dur={r['duration_s']}s")
            out.append(r)
        except Exception as e:
            out.append({"step": i, "url": url, "error": str(e)})
            print(f"  ERROR: {e}")
        time.sleep(2)  # small delay between requests (real users do this)

    print(f"\n--- DETAILS ({len(detail_urls)} urls) ---")
    for j, durl in enumerate(detail_urls[:9], 1):  # cap at 9 to avoid overlong test
        print(f"\n[detail {j}/{min(9, len(detail_urls))}]: {durl}")
        t = time.time()
        try:
            page = fetch(durl)
            blocked = is_blocked(page)
            html_size = len(getattr(page, "html_content", "") or "")
            html = getattr(page, "html_content", "") or ""
            title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_m.group(1).strip()[:120] if title_m else ""
            # Extract price + size from detail page
            price_m = re.search(r'class="info-data-price[^"]*"[^>]*>\s*<span[^>]*>([\d.,]+)', html)
            price = price_m.group(1) if price_m else ""
            r = {
                "step": f"d{j}",
                "type": "detail",
                "url": durl,
                "duration_s": round(time.time() - t, 2),
                "status": getattr(page, "status", None),
                "html_size": html_size,
                "title": title,
                "price": price,
                "blocked": blocked,
            }
            print(f"  status={r['status']} html={html_size:,} title={title[:60]!r} blocked={blocked} dur={r['duration_s']}s")
            out.append(r)
        except Exception as e:
            out.append({"step": f"d{j}", "url": durl, "error": str(e)})
            print(f"  ERROR: {e}")
        time.sleep(1.5)

    Path("scripts/scrapling_volume_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSAVED: scripts/scrapling_volume_results.json")

    # Summary
    blocked_count = sum(1 for r in out if r.get("blocked"))
    success_count = sum(1 for r in out if r.get("status") == 200 and not r.get("blocked"))
    err_count = sum(1 for r in out if r.get("error"))
    total = len(out)
    print(f"\nSUMMARY: success={success_count}/{total}  blocked={blocked_count}/{total}  errors={err_count}/{total}")
    durations = [r["duration_s"] for r in out if "duration_s" in r]
    if durations:
        print(f"Avg duration: {sum(durations)/len(durations):.1f}s  Max: {max(durations):.1f}s")


if __name__ == "__main__":
    main()

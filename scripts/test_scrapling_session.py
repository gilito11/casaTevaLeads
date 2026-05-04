"""
Test con StealthySession (cookies persistentes) para validar que los
detalles de idealista NO bloquean cuando se mantiene la sesión
browser tras visitar la página de búsqueda.

Si esto funciona, Scrapling puede reemplazar Camoufox en producción.
"""
import json
import re
import time
from pathlib import Path

from scrapling.fetchers import StealthySession


def main():
    out = []

    # Open ONE session, do search → details (real-user flow)
    print("Opening StealthySession (single browser, persistent cookies)...")
    with StealthySession(
        headless=True,
        humanize=True,
        block_webrtc=True,
        solve_cloudflare=True,
        google_search=True,
        timeout=60000,
        max_pages=3,
    ) as session:
        # 1) Search page
        search_url = "https://www.idealista.com/venta-viviendas/igualada-barcelona/"
        print(f"\n[search] {search_url}")
        t = time.time()
        page = session.fetch(search_url, network_idle=True, wait=2000)
        html = getattr(page, "html_content", "") or ""
        articles = page.css("article.item") or []
        result = {
            "step": "search",
            "url": search_url,
            "status": getattr(page, "status", None),
            "html_size": len(html),
            "articles": len(articles),
            "duration_s": round(time.time() - t, 2),
        }
        print(f"  status={result['status']} html={result['html_size']:,} articles={result['articles']} dur={result['duration_s']}s")
        out.append(result)

        # 2) Pick 3 detail urls
        details = []
        for a in articles[:3]:
            try:
                link = a.css("a.item-link")
                if link:
                    href = link[0].attrib.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.idealista.com" + href
                    if href:
                        details.append(href)
            except Exception:
                pass
        print(f"\nFollowing {len(details)} details with same session...")

        for i, durl in enumerate(details, 1):
            t = time.time()
            page = session.fetch(durl, network_idle=True, wait=2000)
            html = getattr(page, "html_content", "") or ""
            status = getattr(page, "status", None)
            title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_m.group(1).strip()[:120] if title_m else ""
            blocked = (status == 403) or len(html) < 50000

            # Try to extract real data
            price_m = re.search(r'class="info-data-price[^"]*"[^>]*>[^<]*<span[^>]*>([\d.,]+)', html)
            price = price_m.group(1) if price_m else ""
            phone_m = re.search(r'(\b[6789]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}\b)', html)
            phone = phone_m.group(1) if phone_m else ""
            features = page.css(".info-features li") or []
            features_count = len(features)

            r = {
                "step": f"d{i}",
                "url": durl,
                "status": status,
                "html_size": len(html),
                "title": title,
                "blocked": blocked,
                "price": price,
                "phone_visible": bool(phone),
                "features_count": features_count,
                "duration_s": round(time.time() - t, 2),
            }
            print(f"  [d{i}] status={status} html={len(html):,} title={title[:50]!r} blocked={blocked} price={price!r} features={features_count} dur={r['duration_s']}s")
            out.append(r)
            time.sleep(2)

    Path("scripts/scrapling_session_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSAVED: scripts/scrapling_session_results.json")
    success = sum(1 for r in out if not r.get("blocked", False) and r.get("status") == 200)
    print(f"\nSUMMARY: {success}/{len(out)} pages NOT blocked")


if __name__ == "__main__":
    main()

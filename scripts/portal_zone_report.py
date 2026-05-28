"""
Estudio de rendimiento portal x zona — minado retroactivo de raw.raw_listings.

Responde: ¿qué portal rinde particulares (leads) en qué zona, y dónde gastamos
scrapes sin retorno? Usa TODO el histórico ya almacenado en el data lake — no
necesita instrumentación nueva.

Métricas por (portal, zona):
  - scrapes        : nº de días distintos en que se scrapeó esa zona
  - listings       : filas totales escritas en raw
  - particulares   : filas con es_particular=true (los leads reales)
  - yield%         : particulares / listings (relevante sobre todo en idealista,
                     que guarda particulares Y agencias; los demás portales ya
                     filtran agencias antes de guardar)
  - leads/scrape   : particulares / scrapes (valor de negocio por ejecución)

Uso:
  python -m scripts.portal_zone_report                  # estudio completo
  python -m scripts.portal_zone_report --portal idealista
  python -m scripts.portal_zone_report --days 30        # solo últimos 30 días
  python -m scripts.portal_zone_report --telegram       # envía resumen a Telegram
"""
import argparse
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import psycopg2

# Windows consoles default to cp1252 and choke on accents / symbols. Force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _p in (os.path.join(_root, "backend", ".env"), os.path.join(_root, ".env")):
        if os.path.exists(_p):
            load_dotenv(_p, override=False)
except ImportError:
    pass


def _norm_zona(s: str) -> str:
    """Normaliza la zona para agrupar entre portales (minúsculas, sin acentos)."""
    if not s:
        return "(sin zona)"
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    # Unifica formatos de zona entre portales: "miami_platja" / "miami platja",
    # "mont-roig" / "mont roig". Underscores y guiones -> espacio, colapsa.
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _connect():
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL no definida")
    p = urlparse(url)
    return psycopg2.connect(
        host=p.hostname, port=p.port or 5432,
        database=p.path.lstrip("/").split("?")[0],
        user=p.username, password=p.password, sslmode="require",
    )


def fetch_rows(conn, days=None, portal=None):
    where = []
    params = []
    if days:
        where.append("scraping_timestamp >= %s")
        params.append(datetime.utcnow() - timedelta(days=days))
    if portal:
        where.append("portal = %s")
        params.append(portal)
    sql = (
        "SELECT portal, "
        "COALESCE(NULLIF(raw_data->>'zona_busqueda',''), NULLIF(raw_data->>'zona_geografica',''), raw_data->>'zona') AS zona, "
        "(raw_data->>'es_particular')='true' AS es_part, "
        "scraping_timestamp::date AS dia "
        "FROM raw.raw_listings"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def aggregate(rows):
    # (portal, zona) -> {listings, particulares, dias:set}
    agg = defaultdict(lambda: {"listings": 0, "particulares": 0, "dias": set()})
    for portal, zona, es_part, dia in rows:
        key = (portal, _norm_zona(zona))
        a = agg[key]
        a["listings"] += 1
        if es_part:
            a["particulares"] += 1
        a["dias"].add(dia)
    return agg


def print_report(agg, portal_filter=None):
    portals = sorted({p for (p, _) in agg})
    print("\n" + "=" * 78)
    print("ESTUDIO DE RENDIMIENTO PORTAL x ZONA  (histórico raw.raw_listings)")
    print("=" * 78)
    print("Nota: fotocasa/habitaclia/milanuncios descartan agencias ANTES de guardar,")
    print("por eso su yield% es ~100% por construcción → su métrica útil es leads/scrape.")
    print("Solo idealista guarda particulares Y agencias, así que su yield% es real.")

    for portal in portals:
        items = []
        for (p, zona), a in agg.items():
            if p != portal:
                continue
            scrapes = len(a["dias"])
            part = a["particulares"]
            tot = a["listings"]
            items.append({
                "zona": zona, "scrapes": scrapes, "listings": tot,
                "particulares": part,
                "yield": (100 * part / tot) if tot else 0,
                "leads_scrape": (part / scrapes) if scrapes else 0,
            })
        if not items:
            continue
        items.sort(key=lambda x: (-x["leads_scrape"], -x["particulares"]))
        tot_p = sum(i["particulares"] for i in items)
        tot_l = sum(i["listings"] for i in items)
        print(f"\n### {portal.upper()}  —  {tot_p} particulares de {tot_l} anuncios "
              f"({100*tot_p//max(tot_l,1)}% yield global)")
        print(f"  {'zona':<22}{'scrapes':>8}{'anuncios':>9}{'particul.':>10}{'yield%':>8}{'leads/scrape':>13}")
        print(f"  {'-'*21:<22}{'-'*7:>8}{'-'*8:>9}{'-'*9:>10}{'-'*6:>8}{'-'*12:>13}")
        for i in items:
            print(f"  {i['zona']:<22}{i['scrapes']:>8}{i['listings']:>9}{i['particulares']:>10}"
                  f"{i['yield']:>7.0f}%{i['leads_scrape']:>13.1f}")


def print_learnings(agg):
    print("\n" + "=" * 78)
    print("APRENDIZAJES AUTOMÁTICOS")
    print("=" * 78)

    # Yield global por portal
    per_portal = defaultdict(lambda: {"part": 0, "tot": 0, "zonas": 0})
    for (p, zona), a in agg.items():
        per_portal[p]["part"] += a["particulares"]
        per_portal[p]["tot"] += a["listings"]
        per_portal[p]["zonas"] += 1
    print("\n• Yield de particulares por portal (sobre todo el histórico):")
    for p in sorted(per_portal, key=lambda x: -(per_portal[x]["part"] / max(per_portal[x]["tot"], 1))):
        d = per_portal[p]
        y = 100 * d["part"] / max(d["tot"], 1)
        verdict = "[*] productor fiable" if y >= 60 else ("util" if d["part"] > 0 else "[X] 0 leads -- candidato a retirar")
        print(f"    {p:<12} {d['part']:>4}/{d['tot']:<5} = {y:>5.1f}%  ({d['zonas']} zonas)  {verdict}")

    # Mejores combinaciones portal x zona
    combos = []
    for (p, zona), a in agg.items():
        scrapes = len(a["dias"])
        if scrapes and a["particulares"] > 0:
            combos.append((a["particulares"] / scrapes, p, zona, a["particulares"], scrapes))
    combos.sort(reverse=True)
    print("\n• Top 10 combinaciones portal×zona por leads/scrape (dónde concentrar esfuerzo):")
    for lps, p, zona, part, scr in combos[:10]:
        print(f"    {p:<11} {zona:<20} {lps:>5.1f} leads/scrape  ({part} en {scr} scrapes)")

    # Zonas que nunca dieron un particular (gasto sin retorno)
    dead = [(p, zona, len(a["dias"]), a["listings"]) for (p, zona), a in agg.items()
            if a["particulares"] == 0 and len(a["dias"]) >= 1]
    dead.sort(key=lambda x: -x[2])
    if dead:
        print("\n• Combinaciones portal×zona con 0 particulares (scrapes sin retorno):")
        for p, zona, scr, tot in dead[:15]:
            print(f"    {p:<11} {zona:<20} {scr} scrapes, {tot} anuncios → 0 leads")


def telegram_summary(agg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("(Telegram no configurado: faltan TELEGRAM_BOT_TOKEN/CHAT_ID)")
        return
    import requests
    per_portal = defaultdict(lambda: {"part": 0, "tot": 0})
    for (p, _), a in agg.items():
        per_portal[p]["part"] += a["particulares"]
        per_portal[p]["tot"] += a["listings"]
    lines = ["<b>📊 Rendimiento por portal (histórico)</b>", ""]
    for p in sorted(per_portal, key=lambda x: -per_portal[x]["part"]):
        d = per_portal[p]
        y = 100 * d["part"] / max(d["tot"], 1)
        lines.append(f"• {p}: {d['part']} leads / {d['tot']} anuncios ({y:.0f}%)")
    msg = "%0A".join(lines)
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat, "parse_mode": "HTML", "text": msg}, timeout=15,
    )
    print("Resumen enviado a Telegram.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="solo últimos N días")
    ap.add_argument("--portal", default=None, help="filtra por portal")
    ap.add_argument("--telegram", action="store_true", help="envía resumen a Telegram")
    args = ap.parse_args()

    conn = _connect()
    rows = fetch_rows(conn, days=args.days, portal=args.portal)
    conn.close()
    if not rows:
        print("Sin datos.")
        return
    agg = aggregate(rows)
    print_report(agg, portal_filter=args.portal)
    print_learnings(agg)
    if args.telegram:
        telegram_summary(agg)


if __name__ == "__main__":
    main()

"""
Informe de OPORTUNIDADES — vendedores motivados a quién contactar primero.

El mayor predictor de que un propietario particular acepte una agencia es la
MOTIVACIÓN: una bajada de precio reciente sobre un anuncio que lleva tiempo en
el mercado. Este informe cruza los leads activos (dim_leads) con el histórico
de precios (raw.listing_price_history) y los ordena por una puntuación de
motivación, produciendo la lista de "llamar/contactar hoy".

Por qué no usa dim_leads.precio_cambio_pct: ese campo está a 0 para todos los
leads (el cálculo de variación no se está materializando en dbt). El histórico
de precios es la fuente autoritativa, así que se calcula la bajada desde ahí.

Señales y puntuación (0-100):
  - bajada de precio %      : peso principal (un -10% pesa mucho)
  - nº de bajadas           : varias rebajas = urgencia creciente
  - días en mercado         : más tiempo sin vender = más receptivo
  - tiene teléfono          : contactable de inmediato (bonus)

Uso:
  python -m scripts.opportunities_report                 # tenant 1, top 30
  python -m scripts.opportunities_report --tenant 2
  python -m scripts.opportunities_report --min-drop 5    # solo bajadas >=5%
  python -m scripts.opportunities_report --telegram
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

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

EXCLUDED_ESTADOS = ("YA_VENDIDO", "CLIENTE", "NO_CONTACTAR", "NO_INTERESADO")


def _db():
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL", "")
    p = urlparse(url)
    return psycopg2.connect(
        host=p.hostname, port=p.port or 5432,
        database=p.path.lstrip("/").split("?")[0],
        user=p.username, password=p.password, sslmode="require",
    )


def fetch_opportunities(conn, tenant_id, min_drop):
    """Leads activos con bajada de precio, con métricas calculadas del histórico."""
    cur = conn.cursor()
    cur.execute(
        """
        WITH ph AS (
            SELECT tenant_id, portal, anuncio_id,
                   MAX(precio) FILTER (WHERE rn_first = 1) AS precio_inicial,
                   MAX(precio) FILTER (WHERE rn_last = 1)  AS precio_actual,
                   COUNT(*)                                AS n_precios,
                   MAX(fecha_captura)                      AS ultima_captura
            FROM (
                SELECT tenant_id, portal, anuncio_id, precio, fecha_captura,
                       ROW_NUMBER() OVER (PARTITION BY tenant_id,portal,anuncio_id ORDER BY fecha_captura ASC, precio DESC) rn_first,
                       ROW_NUMBER() OVER (PARTITION BY tenant_id,portal,anuncio_id ORDER BY fecha_captura DESC, precio ASC) rn_last
                FROM raw.listing_price_history
            ) x
            GROUP BY tenant_id, portal, anuncio_id
            HAVING COUNT(DISTINCT precio) > 1
        )
        SELECT d.lead_id, d.source_portal, d.source_listing_id, d.titulo,
               d.zona_clasificada, d.telefono_norm, d.listing_url,
               d.dias_en_mercado,
               ph.precio_inicial, ph.precio_actual, ph.n_precios
        FROM ph
        JOIN public_marts.dim_leads d
          ON d.tenant_id = ph.tenant_id AND d.source_portal = ph.portal
         -- The real portal anuncio_id is the last segment of data_lake_path
         -- (e.g. scrapling/habitaclia/2026/05/06/500006045580); dim_leads.
         -- source_listing_id is a different surrogate id and does NOT match
         -- raw.listing_price_history.anuncio_id except by luck on idealista.
         AND (regexp_match(d.data_lake_path, '([^/]+)$'))[1] = ph.anuncio_id
        LEFT JOIN leads_lead_estado e ON d.lead_id = e.lead_id
        WHERE d.tenant_id = %s
          AND COALESCE(d.es_particular, true) = true
          AND (e.estado IS NULL OR e.estado NOT IN %s)
          AND ph.precio_actual < ph.precio_inicial
        """,
        (tenant_id, EXCLUDED_ESTADOS),
    )
    rows = cur.fetchall()
    cur.close()

    out = []
    for r in rows:
        (lead_id, portal, aid, titulo, zona, tel, url, dias,
         p_ini, p_act, n_precios) = r
        if not p_ini or p_ini <= 0:
            continue
        drop_pct = 100.0 * (float(p_ini) - float(p_act)) / float(p_ini)
        if drop_pct < min_drop:
            continue
        dias = dias or 0
        n_bajadas = max(0, (n_precios or 1) - 1)
        # Puntuación de motivación (0-100): bajada domina, con bonus por nº de
        # rebajas, antigüedad y teléfono.
        score = min(100.0,
                    drop_pct * 4.0
                    + n_bajadas * 6.0
                    + min(dias, 180) / 6.0
                    + (8.0 if tel else 0.0))
        out.append({
            "lead_id": lead_id, "portal": portal, "titulo": titulo or "",
            "zona": zona or "", "tel": tel or "", "url": url or "",
            "dias": dias, "precio_ini": float(p_ini), "precio_act": float(p_act),
            "drop_pct": drop_pct, "n_bajadas": n_bajadas, "score": score,
        })
    out.sort(key=lambda x: -x["score"])
    return out


def print_report(items, top):
    print("\n" + "=" * 92)
    print("OPORTUNIDADES — vendedores motivados (bajada de precio) a contactar primero")
    print("=" * 92)
    if not items:
        print("Sin oportunidades con bajada de precio en este momento.")
        return
    print(f"{'score':>5}  {'portal':<11}{'zona':<16}{'precio ini→act':>22}{'baja%':>7}{'rebajas':>8}{'días':>6}  tel")
    print("-" * 92)
    for it in items[:top]:
        precio = f"{it['precio_ini']:,.0f}->{it['precio_act']:,.0f}EUR".replace(",", ".")
        tel = it["tel"] or "-"
        print(f"{it['score']:>5.0f}  {it['portal']:<11}{it['zona'][:15]:<16}{precio:>22}"
              f"{it['drop_pct']:>6.1f}%{it['n_bajadas']:>8}{it['dias']:>6}  {tel}")
    print(f"\nTotal oportunidades: {len(items)} (mostrando {min(top,len(items))})")


def telegram(items, top, tenant_id):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("(Telegram no configurado)")
        return
    if not items:
        return
    import requests
    lines = [f"<b>🔥 Oportunidades (tenant {tenant_id}): {len(items)} con bajada de precio</b>", ""]
    for it in items[:min(top, 10)]:
        lines.append(
            f"• {it['drop_pct']:.0f}% ↓ {it['precio_act']:,.0f}€ · {it['zona']} · {it['portal']}"
            .replace(",", "."))
    msg = "%0A".join(lines)
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  data={"chat_id": chat, "parse_mode": "HTML", "text": msg}, timeout=15)
    print("Resumen enviado a Telegram.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, default=1)
    ap.add_argument("--min-drop", type=float, default=1.0, help="bajada mínima %% para incluir")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()

    conn = _db()
    items = fetch_opportunities(conn, args.tenant, args.min_drop)
    conn.close()
    print_report(items, args.top)
    if args.telegram:
        telegram(items, args.top, args.tenant)


if __name__ == "__main__":
    main()

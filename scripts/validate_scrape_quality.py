#!/usr/bin/env python3
"""
Post-scrape data quality validation.

Spot-checks recent listings against live portal pages to verify
scraped data accuracy (price, m2, particular/professional, etc).
Sends Telegram alert with quality report.
"""

import os
import sys
import re
import json
import random
import logging
from datetime import datetime

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)

SAMPLES_PER_PORTAL = 3
QUALITY_THRESHOLD = 0.6  # Alert if below 60% field match rate

PORTAL_FIELD_CHECKS = {
    'fotocasa': ['precio', 'metros', 'habitaciones'],
    'idealista': ['precio', 'metros', 'habitaciones', 'es_particular'],
    'habitaclia': ['precio', 'metros', 'habitaciones'],
    'milanuncios': ['precio', 'metros', 'es_particular'],
}


def get_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def get_recent_listings(conn, hours_back=48):
    """Get recent raw listings grouped by portal."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, portal, raw_data, scraping_timestamp
            FROM raw.raw_listings
            WHERE scraping_timestamp >= NOW() - INTERVAL '%s hours'
              AND raw_data->>'url' IS NOT NULL
            ORDER BY scraping_timestamp DESC
        """, (hours_back,))
        rows = cur.fetchall()

    by_portal = {}
    for row in rows:
        portal = row['portal']
        by_portal.setdefault(portal, []).append(row)
    return by_portal


def sample_listings(by_portal, n=SAMPLES_PER_PORTAL):
    """Pick N random listings per portal for validation."""
    samples = {}
    for portal, listings in by_portal.items():
        samples[portal] = random.sample(listings, min(n, len(listings)))
    return samples


def fetch_live_page(url, timeout=15):
    """Fetch listing page HTML with browser-like headers."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return resp.status_code, resp.text
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None, None


def extract_price_from_html(html, portal):
    """Extract price from live page HTML."""
    patterns = {
        'fotocasa': [
            r'"price"\s*:\s*(\d[\d.]*)',
            r'(\d[\d.]+)\s*(?:€|EUR)',
        ],
        'idealista': [
            r'"price"\s*:\s*"?([\d.]+)',
            r'class="[^"]*price[^"]*"[^>]*>([\d.]+)',
            r'(\d[\d.]+)\s*(?:€|EUR)',
        ],
        'habitaclia': [
            r'"price"\s*:\s*"?([\d.]+)',
            r'(\d[\d.]+)\s*(?:€|EUR)',
        ],
        'milanuncios': [
            r'"price"\s*:\s*"?([\d.]+)',
            r'(\d[\d.]+)\s*(?:€|EUR)',
        ],
    }
    for pattern in patterns.get(portal, []):
        match = re.search(pattern, html)
        if match:
            try:
                val = match.group(1).replace('.', '')
                return int(val)
            except (ValueError, IndexError):
                continue
    return None


def extract_m2_from_html(html, portal):
    """Extract surface area from live page HTML."""
    patterns = [
        r'(\d+)\s*m²',
        r'(\d+)\s*m&sup2',
        r'"floorSpace"\s*:\s*"?(\d+)',
        r'"size"\s*:\s*"?(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue
    return None


def check_professional_markers(html, portal):
    """Check if listing page shows professional/agency indicators."""
    pro_markers = [
        r'(?i)inmobiliaria',
        r'(?i)agencia',
        r'(?i)profesional',
        r'(?i)agency',
        r'(?i)real\s*estate',
        r'(?i)ProBadge',
        r'(?i)SellerBadge',
    ]
    particular_markers = [
        r'(?i)particular',
        r'(?i)propietario',
        r'(?i)owner',
    ]

    pro_hits = sum(1 for p in pro_markers if re.search(p, html))
    part_hits = sum(1 for p in particular_markers if re.search(p, html))

    if pro_hits > part_hits:
        return False  # Professional
    elif part_hits > 0:
        return True  # Particular
    return None  # Can't determine


def validate_listing(row, portal):
    """Validate a single listing against its live page."""
    raw = row['raw_data'] if isinstance(row['raw_data'], dict) else json.loads(row['raw_data'])
    url = raw.get('url', '')

    if not url:
        return {'status': 'no_url', 'checks': {}}

    status_code, html = fetch_live_page(url)

    if status_code is None:
        return {'status': 'fetch_error', 'checks': {}}

    if status_code == 404 or status_code == 410:
        return {'status': 'removed', 'checks': {}}

    if status_code != 200:
        return {'status': f'http_{status_code}', 'checks': {}}

    checks = {}
    fields = PORTAL_FIELD_CHECKS.get(portal, [])

    # Price check
    if 'precio' in fields:
        scraped_price = raw.get('precio')
        if scraped_price:
            try:
                # Convert to float first to handle "690000.0" correctly,
                # then to int. Previous code did str().replace('.','') which
                # turned 690000.0 into 6900000 (x10 bug).
                scraped_price = int(float(scraped_price))
            except (ValueError, TypeError):
                scraped_price = None

        live_price = extract_price_from_html(html, portal)

        if scraped_price and live_price:
            diff_pct = abs(scraped_price - live_price) / max(scraped_price, live_price) * 100
            checks['precio'] = {
                'scraped': scraped_price,
                'live': live_price,
                'match': diff_pct < 5,  # Allow 5% tolerance
                'diff_pct': round(diff_pct, 1),
            }
        elif scraped_price and not live_price:
            checks['precio'] = {'scraped': scraped_price, 'live': None, 'match': None, 'note': 'could not extract from live page'}
        elif not scraped_price:
            checks['precio'] = {'scraped': None, 'live': live_price, 'match': None, 'note': 'not scraped'}

    # M2 check
    if 'metros' in fields:
        scraped_m2 = raw.get('metros')
        if scraped_m2:
            try:
                scraped_m2 = int(str(scraped_m2).replace('m²', '').replace('m2', '').strip())
            except (ValueError, TypeError):
                scraped_m2 = None

        live_m2 = extract_m2_from_html(html, portal)

        if scraped_m2 and live_m2:
            diff = abs(scraped_m2 - live_m2)
            checks['metros'] = {
                'scraped': scraped_m2,
                'live': live_m2,
                'match': diff <= 2,  # Allow 2m2 tolerance
                'diff': diff,
            }
        elif scraped_m2 and not live_m2:
            checks['metros'] = {'scraped': scraped_m2, 'live': None, 'match': None, 'note': 'could not extract from live page'}

    # Rooms check
    if 'habitaciones' in fields:
        scraped_rooms = raw.get('habitaciones')
        if scraped_rooms:
            try:
                scraped_rooms = int(str(scraped_rooms).strip())
            except (ValueError, TypeError):
                scraped_rooms = None
        # Simple presence check - room count rarely changes
        checks['habitaciones'] = {'scraped': scraped_rooms, 'present': scraped_rooms is not None}

    # Particular check
    if 'es_particular' in fields:
        scraped_particular = raw.get('es_particular')
        live_particular = check_professional_markers(html, portal)

        if scraped_particular is not None and live_particular is not None:
            checks['es_particular'] = {
                'scraped': scraped_particular,
                'live': live_particular,
                'match': bool(scraped_particular) == bool(live_particular),
            }
        else:
            checks['es_particular'] = {
                'scraped': scraped_particular,
                'live': live_particular,
                'match': None,
                'note': 'could not determine from live page',
            }

    # Description presence
    desc = raw.get('descripcion', '') or ''
    checks['descripcion'] = {
        'length': len(desc),
        'present': len(desc) > 10,
    }

    # Photos presence
    fotos = raw.get('fotos', []) or []
    checks['fotos'] = {
        'count': len(fotos),
        'present': len(fotos) > 0,
    }

    return {'status': 'ok', 'url': url, 'checks': checks}


def compute_quality_score(results):
    """Compute overall quality score from validation results."""
    total_checks = 0
    passed_checks = 0
    issues = []

    for portal, validations in results.items():
        for v in validations:
            if v['status'] != 'ok':
                if v['status'] == 'removed':
                    issues.append(f"{portal}: listing removed")
                continue

            for field, check in v['checks'].items():
                if 'match' in check and check['match'] is not None:
                    total_checks += 1
                    if check['match']:
                        passed_checks += 1
                    else:
                        issues.append(f"{portal}: {field} mismatch (scraped={check.get('scraped')}, live={check.get('live')})")

    score = passed_checks / total_checks if total_checks > 0 else 1.0
    return score, total_checks, passed_checks, issues


def build_report(results, score, total_checks, passed_checks, issues, scrape_counts):
    """Build Telegram-compatible quality report."""
    lines = [
        "<b>Data Quality Report</b>",
        "",
    ]

    # Scrape summary
    for portal, count in sorted(scrape_counts.items()):
        status = "OK" if count > 0 else "FAIL (0 listings)"
        lines.append(f"  {portal}: {count} listings {status}")
    lines.append("")

    # Quality score
    if total_checks > 0:
        pct = int(score * 100)
        indicator = "OK" if score >= QUALITY_THRESHOLD else "LOW"
        lines.append(f"Quality: <b>{pct}%</b> ({passed_checks}/{total_checks} checks) [{indicator}]")
    else:
        lines.append("Quality: No checks possible (0 listings)")

    # Issues
    if issues:
        lines.append("")
        lines.append("Issues:")
        for issue in issues[:8]:
            lines.append(f"  - {issue}")
        if len(issues) > 8:
            lines.append(f"  ...and {len(issues) - 8} more")

    # Zero-result portals
    zero_portals = [p for p, c in scrape_counts.items() if c == 0]
    if zero_portals:
        lines.append("")
        lines.append(f"<b>WARNING: 0 results from: {', '.join(zero_portals)}</b>")

    lines.append(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    conn = get_connection()

    # Get recent listings
    by_portal = get_recent_listings(conn, hours_back=48)
    conn.close()

    scrape_counts = {}
    expected_portals = ['fotocasa', 'idealista', 'habitaclia', 'milanuncios']
    for portal in expected_portals:
        scrape_counts[portal] = len(by_portal.get(portal, []))

    logger.info(f"Recent listings by portal: {scrape_counts}")

    # Sample and validate
    samples = sample_listings(by_portal, SAMPLES_PER_PORTAL)
    results = {}

    for portal, listings in samples.items():
        logger.info(f"Validating {len(listings)} samples from {portal}")
        portal_results = []
        for listing in listings:
            result = validate_listing(listing, portal)
            portal_results.append(result)
            logger.info(f"  {result['status']}: {result.get('url', 'N/A')[:60]}")
            for field, check in result.get('checks', {}).items():
                if 'match' in check and check['match'] is not None:
                    status = "PASS" if check['match'] else "FAIL"
                    logger.info(f"    {field}: {status} (scraped={check.get('scraped')}, live={check.get('live')})")
        results[portal] = portal_results

    # Compute quality
    score, total_checks, passed_checks, issues = compute_quality_score(results)
    logger.info(f"Quality score: {score:.0%} ({passed_checks}/{total_checks})")

    # Build report
    report = build_report(results, score, total_checks, passed_checks, issues, scrape_counts)
    logger.info(f"Report:\n{report}")

    # Send Telegram alert
    try:
        from scrapers.utils.telegram_alerts import send_telegram_alert

        # Always send if there are zero-result portals or low quality
        zero_portals = [p for p, c in scrape_counts.items() if c == 0]
        if zero_portals or score < QUALITY_THRESHOLD:
            send_telegram_alert(report)
            logger.info("Alert sent (quality issue detected)")
        else:
            logger.info("Quality OK - no alert needed")
    except ImportError:
        logger.warning("Could not import telegram_alerts")

    # Exit with error code if quality is bad
    if score < QUALITY_THRESHOLD:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

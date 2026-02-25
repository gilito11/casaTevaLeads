#!/usr/bin/env python3
"""
Portal Health Check - Quick interface change detection.
Checks if the 4 portals have changed their HTML structure.
Run: python scripts/check_portal_health.py
     python scripts/check_portal_health.py --verbose
     python scripts/check_portal_health.py --portal habitaclia
"""

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Pattern definitions per portal
# ---------------------------------------------------------------------------

@dataclass
class PortalPattern:
    name: str
    description: str
    regex: str
    required: bool = True  # If True, absence is a problem


@dataclass
class PortalCheck:
    name: str
    url: str
    patterns: List[PortalPattern]
    blocked_indicators: List[str] = field(default_factory=list)


PORTAL_CHECKS: Dict[str, PortalCheck] = {
    "habitaclia": PortalCheck(
        name="habitaclia",
        url="https://www.habitaclia.com/viviendas-particulares-salou.htm",
        patterns=[
            PortalPattern(
                "listing_links",
                "Listing href pattern",
                r'href="[^"]*habitaclia\.com/comprar-',
            ),
            PortalPattern(
                "price",
                "Price with euro symbol",
                r'\d+\.?\d*\s*\u20ac',
            ),
            PortalPattern(
                "image_domain",
                "Image hosting domain",
                r'images\.habimg\.com',
            ),
            PortalPattern(
                "listing_id",
                "Listing ID pattern (-iNNNNNNNNN)",
                r'-i\d{9,}',
            ),
        ],
        blocked_indicators=[
            r'captcha',
            r'challenge',
            r'access.denied',
        ],
    ),
    "fotocasa": PortalCheck(
        name="fotocasa",
        url="https://www.fotocasa.es/es/comprar/viviendas/particulares/salou/todas-las-zonas/pl",
        patterns=[
            PortalPattern(
                "listing_links",
                "Listing URL pattern",
                r'/es/comprar/vivienda/',
            ),
            PortalPattern(
                "agency_divider",
                "Particular/agency section divider",
                r'anuncios de inmobiliarias',
                required=False,
            ),
            PortalPattern(
                "price_class",
                "Price CSS class",
                r'price',
            ),
            PortalPattern(
                "image_domain",
                "Image hosting domain",
                r'static\.fotocasa\.es',
            ),
        ],
        blocked_indicators=[
            r'Imperva',
            r'incapsula',
            r'_Incapsula_Resource',
            r'access.denied',
        ],
    ),
    "idealista": PortalCheck(
        name="idealista",
        url="https://www.idealista.com/venta-viviendas/salou/con-publicado_ultimas-48-horas/",
        patterns=[
            PortalPattern(
                "article_tags",
                "Article elements for listings",
                r'<article\b',
            ),
            PortalPattern(
                "pro_marker_branding",
                "Professional logo-branding marker",
                r'logo-branding',
                required=False,
            ),
            PortalPattern(
                "pro_marker_logo",
                "Professional item-not-clickable-logo marker",
                r'item-not-clickable-logo',
                required=False,
            ),
            PortalPattern(
                "listing_url",
                "Listing URL pattern (/inmueble/ID/)",
                r'/inmueble/\d+/',
            ),
            PortalPattern(
                "price",
                "Euro currency indicator",
                r'\u20ac|EUR',
            ),
        ],
        blocked_indicators=[
            r'datadome',
            r'DataDome',
            r'geo\.captcha-delivery\.com',
            r'dd\.js',
            r'window\._dd',
        ],
    ),
    "milanuncios": PortalCheck(
        name="milanuncios",
        url="https://www.milanuncios.com/pisos-en-salou-tarragona/",
        patterns=[
            PortalPattern(
                "initial_props",
                "JSON data (__INITIAL_PROPS__ or __NEXT_DATA__)",
                r'__INITIAL_PROPS__|__NEXT_DATA__',
            ),
            PortalPattern(
                "ad_cards",
                "Ad card components",
                r'(?i)AdCard|ad-card|adcard',
            ),
            PortalPattern(
                "seller_type",
                "Seller type in JSON",
                r'sellerType',
            ),
            PortalPattern(
                "is_private",
                "isPrivate field in JSON (may only appear in detail pages)",
                r'isPrivate',
                required=False,
            ),
        ],
        blocked_indicators=[
            r'geetest',
            r'GeeTest',
            r'gt\.js',
            r'captcha',
        ],
    ),
}


# ---------------------------------------------------------------------------
# Check result
# ---------------------------------------------------------------------------

@dataclass
class PatternResult:
    name: str
    description: str
    found: bool
    required: bool
    match_count: int = 0


@dataclass
class PortalResult:
    portal: str
    status: str  # "ok", "blocked", "error", "degraded"
    http_status: Optional[int] = None
    score: int = 0  # 0-100
    patterns: List[PatternResult] = field(default_factory=list)
    blocked: bool = False
    error_message: Optional[str] = None

    @property
    def healthy(self) -> bool:
        return self.score >= 50


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """Fetch a page. Returns (status_code, html, error_message)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return resp.status_code, resp.text, None
    except requests.exceptions.Timeout:
        return None, None, "Connection timed out"
    except requests.exceptions.ConnectionError as e:
        return None, None, f"Connection error: {e}"
    except requests.exceptions.RequestException as e:
        return None, None, f"Request error: {e}"


def check_blocked(html: str, indicators: List[str]) -> bool:
    """Check if the response is a bot-challenge page."""
    for indicator in indicators:
        if re.search(indicator, html, re.IGNORECASE):
            return True
    return False


def check_portal(portal_check: PortalCheck, verbose: bool = False) -> PortalResult:
    """Run health check for a single portal."""
    result = PortalResult(portal=portal_check.name, status="ok")

    if verbose:
        logger.info(f"Fetching {portal_check.url}")

    status_code, html, error = fetch_page(portal_check.url)

    if error:
        result.status = "error"
        result.error_message = error
        result.score = 0
        return result

    result.http_status = status_code

    if status_code == 403 or status_code == 429:
        result.status = "blocked"
        result.blocked = True
        result.error_message = f"HTTP {status_code} - access denied"
        result.score = -1  # blocked, not a structural change
        return result

    if status_code != 200:
        result.status = "error"
        result.error_message = f"HTTP {status_code}"
        result.score = 0
        return result

    # Check for bot challenge pages
    if check_blocked(html, portal_check.blocked_indicators):
        result.status = "blocked"
        result.blocked = True
        result.error_message = "Bot challenge detected (expected for this portal)"
        result.score = -1  # blocked is expected, not a structural issue
        return result

    # Check patterns
    required_total = 0
    required_found = 0
    optional_total = 0
    optional_found = 0

    for pattern_def in portal_check.patterns:
        matches = re.findall(pattern_def.regex, html)
        found = len(matches) > 0
        pr = PatternResult(
            name=pattern_def.name,
            description=pattern_def.description,
            found=found,
            required=pattern_def.required,
            match_count=len(matches),
        )
        result.patterns.append(pr)

        if pattern_def.required:
            required_total += 1
            if found:
                required_found += 1
        else:
            optional_total += 1
            if found:
                optional_found += 1

        if verbose:
            status_str = "FOUND" if found else "MISSING"
            req_str = "required" if pattern_def.required else "optional"
            logger.info(
                f"  [{status_str}] {pattern_def.name} ({req_str}) "
                f"- {pattern_def.description} ({len(matches)} matches)"
            )

    # Score calculation: required patterns are 80% of score, optional 20%
    if required_total > 0:
        required_score = (required_found / required_total) * 80
    else:
        required_score = 80

    if optional_total > 0:
        optional_score = (optional_found / optional_total) * 20
    else:
        optional_score = 20

    result.score = int(required_score + optional_score)

    if result.score < 50:
        result.status = "degraded"
    elif result.score < 80:
        result.status = "degraded"

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(results: Dict[str, PortalResult]):
    """Print a summary table to stdout."""
    print()
    print("=" * 65)
    print("  PORTAL HEALTH CHECK")
    print("=" * 65)
    print(f"  {'Portal':<15} {'Status':<12} {'Score':<8} {'Details'}")
    print("-" * 65)

    for name, r in results.items():
        if r.blocked:
            score_str = "N/A"
            status_str = "BLOCKED"
        elif r.status == "error":
            score_str = "ERR"
            status_str = "ERROR"
        else:
            score_str = f"{r.score}%"
            status_str = "OK" if r.score >= 80 else ("WARN" if r.score >= 50 else "FAIL")

        details = r.error_message or ""
        if r.patterns:
            found = sum(1 for p in r.patterns if p.found)
            total = len(r.patterns)
            details = f"{found}/{total} patterns" + (f" | {details}" if details else "")

        print(f"  {name:<15} {status_str:<12} {score_str:<8} {details}")

    print("-" * 65)

    # Summary line
    unhealthy = [n for n, r in results.items() if not r.blocked and not r.healthy]
    blocked = [n for n, r in results.items() if r.blocked]

    if unhealthy:
        print(f"  UNHEALTHY: {', '.join(unhealthy)}")
    if blocked:
        print(f"  BLOCKED (expected): {', '.join(blocked)}")
    if not unhealthy:
        accessible = [n for n, r in results.items() if not r.blocked]
        if accessible:
            print(f"  All accessible portals healthy: {', '.join(accessible)}")
        else:
            print("  All portals blocked (use Camoufox scrapers to verify)")

    print("=" * 65)
    print()


def print_verbose_details(results: Dict[str, PortalResult]):
    """Print detailed pattern results."""
    for name, r in results.items():
        if not r.patterns:
            continue
        print(f"\n  {name.upper()} pattern details:")
        for p in r.patterns:
            marker = "[OK]" if p.found else "[--]"
            req = "*" if p.required else " "
            print(f"    {marker}{req} {p.name}: {p.description} ({p.match_count} matches)")


def build_telegram_message(results: Dict[str, PortalResult]) -> str:
    """Build Telegram alert message (HTML format)."""
    lines = [
        "<b>Portal Health Check Alert</b>",
        "",
    ]

    for name, r in results.items():
        if r.blocked:
            lines.append(f"  {name}: BLOCKED (expected)")
        elif r.status == "error":
            lines.append(f"  {name}: ERROR - {r.error_message}")
        else:
            indicator = "OK" if r.score >= 80 else ("WARN" if r.score >= 50 else "FAIL")
            found = sum(1 for p in r.patterns if p.found)
            total = len(r.patterns)
            lines.append(f"  {name}: <b>{r.score}%</b> ({found}/{total} patterns) [{indicator}]")

            # List missing required patterns
            missing = [p for p in r.patterns if not p.found and p.required]
            for p in missing:
                lines.append(f"    Missing: {p.description}")

    # Unhealthy portals
    unhealthy = [n for n, r in results.items() if not r.blocked and not r.healthy]
    if unhealthy:
        lines.append("")
        lines.append(f"<b>ACTION NEEDED: {', '.join(unhealthy)} may have changed HTML structure</b>")

    lines.append(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


def send_alert_if_needed(results: Dict[str, PortalResult]) -> bool:
    """Send Telegram alert if any accessible portal is unhealthy."""
    unhealthy = [n for n, r in results.items() if not r.blocked and not r.healthy]
    errors = [n for n, r in results.items() if r.status == "error"]

    if not unhealthy and not errors:
        logger.info("All accessible portals healthy - no alert needed")
        return False

    message = build_telegram_message(results)

    try:
        from scrapers.utils.telegram_alerts import send_telegram_alert
        sent = send_telegram_alert(message)
        if sent:
            logger.info("Telegram alert sent")
        else:
            logger.warning("Telegram alert not sent (not configured or failed)")
        return sent
    except ImportError:
        logger.warning("Could not import telegram_alerts - printing message instead")
        print(message)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check if real estate portals have changed their HTML interface"
    )
    parser.add_argument(
        "--portal",
        choices=list(PORTAL_CHECKS.keys()),
        help="Check a single portal instead of all",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed pattern match results",
    )
    parser.add_argument(
        "--no-alert",
        action="store_true",
        help="Skip sending Telegram alert",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Select portals to check
    if args.portal:
        portals = {args.portal: PORTAL_CHECKS[args.portal]}
    else:
        portals = PORTAL_CHECKS

    # Run checks
    results: Dict[str, PortalResult] = {}
    for name, check in portals.items():
        logger.info(f"Checking {name}...")
        results[name] = check_portal(check, verbose=args.verbose)

    # Print results
    if args.verbose:
        print_verbose_details(results)
    print_summary(results)

    # Send alert if needed
    if not args.no_alert:
        send_alert_if_needed(results)

    # Exit code: 1 if any accessible portal is unhealthy
    unhealthy = [n for n, r in results.items() if not r.blocked and not r.healthy]
    return 1 if unhealthy else 0


if __name__ == "__main__":
    sys.exit(main())

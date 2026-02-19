"""
Test script to verify a single idealista listing.
Requires Camoufox + IPRoyal proxy (DATADOME_PROXY env var).

Usage:
    DATADOME_PROXY="user:pass_country-es@geo.iproyal.com:12321" \
    python scripts/test_idealista_listing.py https://www.idealista.com/inmueble/110490011/
"""

import json
import logging
import os
import re
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_listing(url: str):
    from camoufox.sync_api import Camoufox

    proxy_str = os.environ.get('DATADOME_PROXY', '')
    if not proxy_str:
        logger.error("DATADOME_PROXY not set")
        sys.exit(1)

    # Parse proxy
    if '@' in proxy_str:
        auth, host_port = proxy_str.rsplit('@', 1)
        user, password = auth.split(':', 1)
        host, port = host_port.rsplit(':', 1)
    else:
        host, port = proxy_str.rsplit(':', 1)
        user = password = None

    proxy_config = {
        'server': f'http://{host}:{port}',
    }
    if user:
        proxy_config['username'] = user
        proxy_config['password'] = password

    headless = '--virtual' in sys.argv
    camoufox_opts = {
        'headless': headless,
        'proxy': proxy_config,
        'geoip': True,
    }

    logger.info(f"Testing listing: {url}")
    logger.info(f"Proxy: {host}:{port}")
    logger.info(f"Headless: {headless}")

    with Camoufox(**camoufox_opts) as browser:
        page = browser.new_page()

        # Warmup
        logger.info("Warmup: visiting idealista.com...")
        page.goto('https://www.idealista.com', timeout=60000)
        page.wait_for_timeout(3000)

        # Check for DataDome
        content = page.content()
        if 'captcha' in content.lower() or 'geo.captcha' in content.lower():
            logger.error("BLOCKED by DataDome on warmup!")
            return

        logger.info("Warmup OK, navigating to listing...")

        # Navigate to listing
        page.goto(url, timeout=60000)
        page.wait_for_timeout(3000)

        title = page.title()
        logger.info(f"Page title: {title}")

        # Check if listing exists
        html = page.content()

        # Detect removed listing
        if 'ya no está disponible' in html.lower() or 'anuncio no disponible' in html.lower():
            logger.info("RESULT: Listing REMOVED / no longer available")
            return

        # Extract listing data
        result = {'url': url}

        # Title
        title_elem = page.query_selector('h1, .main-info__title-main')
        if title_elem:
            result['titulo'] = title_elem.inner_text().strip()

        # Price
        price_elem = page.query_selector('.info-data-price, .price-features__container')
        if price_elem:
            result['precio'] = price_elem.inner_text().strip()

        # Check particular/professional
        sections = page.query_selector_all('[class*="contact"], [id*="contact"], [class*="advertiser"]')
        for sec in sections:
            try:
                text = sec.inner_text()
                if 'Particular' in text:
                    result['es_particular'] = True
                    result['vendor_text'] = text[:200]
                    break
                elif 'Profesional' in text or 'Referencia' in text:
                    result['es_particular'] = False
                    result['vendor_text'] = text[:200]
                    break
            except:
                continue

        # Try to get advertiser name
        adv_elem = page.query_selector('.professional-name, .advertiser-name, [class*="advertiser"] .name')
        if adv_elem:
            result['vendedor'] = adv_elem.inner_text().strip()

        # Phone button
        phone_btn = page.query_selector('a:has-text("Ver tel"), button:has-text("Ver tel")')
        result['has_phone_button'] = phone_btn is not None

        # Description
        desc_elem = page.query_selector('.comment, .adCommentsLanguage, [class*="description"]')
        if desc_elem:
            result['descripcion'] = desc_elem.inner_text()[:300]

        # Photos
        photos = page.query_selector_all('img[src*="img3.idealista"], img[src*="img4.idealista"]')
        result['num_fotos'] = len(photos)

        logger.info(f"\nRESULT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_idealista_listing.py <URL> [--virtual]")
        sys.exit(1)

    url = sys.argv[1]
    if not url.startswith('http'):
        url = f'https://www.idealista.com/inmueble/{url}/'

    test_listing(url)

"""
Idealista Contact Automation using Camoufox + 2Captcha DataDome solver.

Camoufox is an anti-detect Firefox browser that helps bypass fingerprinting.
If DataDome still triggers, we use 2Captcha to solve it.

Usage:
    python -m scrapers.contact_automation.camoufox_idealista --url <listing_url>

Environment:
    CAPTCHA_API_KEY: 2Captcha API key (for DataDome solving)
    IDEALISTA_EMAIL: Account email (required)
    IDEALISTA_PASSWORD: Account password (required)
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent / "cookies" / "idealista_camoufox_cookies.json"
EXISTING_COOKIES_FILE = Path(__file__).parent / "cookies" / "idealista_cookies.json"


class DataDomeSolver2Captcha:
    """2Captcha DataDome solver using the old in.php API (no proxy required)."""

    SUBMIT_URL = "https://2captcha.com/in.php"
    RESULT_URL = "https://2captcha.com/res.php"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def solve_sync(
        self,
        website_url: str,
        captcha_url: str,
        user_agent: str,
        proxy: Optional[str] = None,
        timeout: int = 180
    ) -> Optional[str]:
        """
        Solve DataDome challenge using 2Captcha old API (synchronous).

        Args:
            website_url: The protected website URL
            captcha_url: The DataDome captcha URL (geo.captcha-delivery.com/...)
            user_agent: Browser user agent string
            proxy: Optional proxy string (user:pass@ip:port)
            timeout: Max seconds to wait

        Returns:
            DataDome cookie value or None on failure
        """
        import requests

        try:
            # Submit request using old API
            submit_data = {
                'key': self.api_key,
                'method': 'datadome',
                'captcha_url': captcha_url,
                'pageurl': website_url,
                'userAgent': user_agent,
                'json': 1
            }

            if proxy:
                submit_data['proxy'] = proxy
                submit_data['proxytype'] = 'HTTP'

            logger.info(f"Submitting DataDome to 2Captcha (old API)...")
            resp = requests.post(self.SUBMIT_URL, data=submit_data, timeout=30)
            result = resp.json()

            if result.get('status') != 1:
                error_text = result.get('request', 'Unknown error')
                logger.error(f"2Captcha submit error: {error_text}")
                # Check if it's a specific error we can handle
                if 'ERROR_CAPTCHA_UNSOLVABLE' in str(error_text):
                    logger.error("DataDome captcha is unsolvable by 2Captcha")
                return None

            request_id = result['request']
            logger.info(f"2Captcha request ID: {request_id}")

            # Poll for result
            result_params = {
                'key': self.api_key,
                'action': 'get',
                'id': request_id,
                'json': 1
            }

            start = time.time()
            while time.time() - start < timeout:
                time.sleep(10)  # DataDome takes longer

                resp = requests.get(self.RESULT_URL, params=result_params, timeout=30)
                result = resp.json()

                if result.get('status') == 1:
                    # Result contains the datadome cookie value
                    cookie_value = result['request']
                    logger.info("DataDome solved successfully!")
                    return cookie_value
                elif result.get('request') == 'CAPCHA_NOT_READY':
                    logger.debug("Still processing...")
                    continue
                else:
                    error = result.get('request', 'Unknown')
                    logger.error(f"2Captcha result error: {error}")
                    return None

            logger.error("2Captcha timeout")
            return None

        except Exception as e:
            logger.error(f"DataDome solve error: {e}")
            return None


class CamoufoxIdealistaContact:
    """Idealista contact using Camoufox anti-detect browser."""

    BASE_URL = "https://www.idealista.com"
    LOGIN_URL = "https://www.idealista.com/login"

    def __init__(
        self,
        headless: bool = True,
        email: str = None,
        password: str = None,
        captcha_api_key: str = None
    ):
        self.headless = headless
        self.email = email or os.getenv("IDEALISTA_EMAIL")
        self.password = password or os.getenv("IDEALISTA_PASSWORD")
        self.captcha_api_key = captcha_api_key or os.getenv("CAPTCHA_API_KEY")
        self.browser = None
        self.page = None
        self.datadome_solver = None
        if self.captcha_api_key:
            self.datadome_solver = DataDomeSolver2Captcha(self.captcha_api_key)

    def _get_camoufox_options(self) -> dict:
        """Get Camoufox browser options."""
        return {
            "humanize": 2.5,  # Human-like behavior
            "headless": self.headless,
            "geoip": True,  # Spain geolocation
            "os": "windows",
            "block_webrtc": True,
            "locale": ["es-ES", "es"],
        }

    def _check_datadome(self) -> Optional[str]:
        """Check if DataDome challenge is present and return captcha URL if found."""
        try:
            content = self.page.content()
            url = self.page.url

            # Check if redirected to captcha-delivery
            if "geo.captcha-delivery.com" in url:
                return url

            # Check for DataDome in page content
            datadome_patterns = [
                r'(https://geo\.captcha-delivery\.com/captcha/[^\s"\']+)',
                r'datadome-captcha',
            ]

            for pattern in datadome_patterns:
                match = re.search(pattern, content)
                if match:
                    if pattern.startswith("(https"):
                        return match.group(1)
                    # Found datadome element, need to find URL
                    return url

            return None

        except Exception as e:
            logger.error(f"Error checking DataDome: {e}")
            return None

    def _solve_datadome_sync(self, captcha_url: str) -> bool:
        """Solve DataDome using 2Captcha (synchronous)."""
        if not self.datadome_solver:
            logger.error("No CAPTCHA_API_KEY for DataDome solving")
            return False

        try:
            # Get user agent from browser
            user_agent = self.page.evaluate("navigator.userAgent")

            # Solve using synchronous method
            cookie_value = self.datadome_solver.solve_sync(
                website_url=self.BASE_URL,
                captcha_url=captcha_url,
                user_agent=user_agent
            )

            if not cookie_value:
                return False

            # Set cookie
            self.page.context.add_cookies([{
                "name": "datadome",
                "value": cookie_value,
                "domain": ".idealista.com",
                "path": "/"
            }])

            logger.info("DataDome cookie set, reloading...")
            self.page.reload()
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            # Check if still blocked
            if self._check_datadome():
                logger.error("Still blocked after DataDome solution")
                return False

            return True

        except Exception as e:
            logger.error(f"DataDome solve error: {e}")
            return False

    def _load_cookies(self) -> list:
        """Load saved cookies, trying camoufox-specific first, then existing."""
        # Try camoufox-specific cookies first
        for cookies_file in [COOKIES_FILE, EXISTING_COOKIES_FILE]:
            if cookies_file.exists():
                try:
                    with open(cookies_file) as f:
                        cookies = json.load(f)
                        if cookies:
                            logger.info(f"Loaded {len(cookies)} cookies from {cookies_file.name}")
                            return cookies
                except Exception as e:
                    logger.error(f"Error loading cookies from {cookies_file}: {e}")
        return []

    def _save_cookies(self, cookies: list):
        """Save cookies to file."""
        COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
        logger.info(f"Cookies saved to {COOKIES_FILE}")

    def run_sync(self, listing_url: str, message: str) -> dict:
        """
        Run contact automation synchronously using Camoufox.

        Returns:
            Dict with success, phone, error keys
        """
        from camoufox.sync_api import Camoufox

        result = {
            "success": False,
            "phone": None,
            "error": None
        }

        try:
            options = self._get_camoufox_options()
            logger.info(f"Starting Camoufox with options: {options}")

            with Camoufox(**options) as browser:
                self.browser = browser
                self.page = browser.new_page()

                # Load saved cookies
                cookies = self._load_cookies()
                if cookies:
                    logger.info(f"Loading {len(cookies)} saved cookies")
                    self.page.context.add_cookies(cookies)

                # Navigate to listing
                logger.info(f"Navigating to: {listing_url}")
                self.page.goto(listing_url, timeout=60000)
                self.page.wait_for_load_state("domcontentloaded")
                time.sleep(3)

                # Check for DataDome
                captcha_url = self._check_datadome()
                if captcha_url:
                    logger.warning(f"DataDome detected: {captcha_url}")
                    if not self._solve_datadome_sync(captcha_url):
                        result["error"] = "DataDome challenge failed"
                        self.page.screenshot(path="debug_idealista_datadome.png")
                        return result

                # Accept cookies popup
                self._accept_cookies()

                # Check if logged in
                if not self._is_logged_in():
                    logger.info("Not logged in, attempting login...")
                    if not self._login():
                        result["error"] = "Login failed"
                        return result

                # Navigate back to listing
                self.page.goto(listing_url, timeout=60000)
                self.page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

                # Extract phone
                result["phone"] = self._extract_phone()

                # Send message
                if self._send_message(message):
                    result["success"] = True
                    # Save cookies for next time
                    cookies = self.page.context.cookies()
                    self._save_cookies(cookies)
                else:
                    result["error"] = "Failed to send message"

                return result

        except Exception as e:
            logger.error(f"Camoufox error: {e}")
            result["error"] = str(e)
            return result

    def _accept_cookies(self):
        """Accept cookies popup if present."""
        selectors = [
            'button:has-text("Aceptar")',
            'button:has-text("Aceptar todas")',
            '#didomi-notice-agree-button',
            'button:has-text("Aceptar y cerrar")',
        ]

        for selector in selectors:
            try:
                btn = self.page.query_selector(selector)
                if btn:
                    btn.click()
                    logger.info(f"Accepted cookies: {selector}")
                    time.sleep(1)
                    return
            except Exception:
                continue

    def _is_logged_in(self) -> bool:
        """Check if user is logged in."""
        content = self.page.content()

        logged_in_indicators = [
            "Mi idealista",
            "mi-idealista",
            "Cerrar sesión",
            "Mis búsquedas",
        ]

        for indicator in logged_in_indicators:
            if indicator in content:
                logger.info(f"Logged in (found: {indicator})")
                return True

        return False

    def _login(self) -> bool:
        """Login to Idealista."""
        if not self.email or not self.password:
            logger.error("IDEALISTA_EMAIL and IDEALISTA_PASSWORD required")
            return False

        try:
            logger.info("Navigating to login page...")
            self.page.goto(self.LOGIN_URL, timeout=60000)
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            self._accept_cookies()

            # Check for DataDome
            captcha_url = self._check_datadome()
            if captcha_url:
                if not self._solve_datadome_sync(captcha_url):
                    return False

            # Fill email
            logger.info("Filling email...")
            email_selectors = ['input[type="email"]', 'input[name="email"]', '#email']
            for selector in email_selectors:
                try:
                    email_input = self.page.query_selector(selector)
                    if email_input:
                        email_input.fill(self.email)
                        break
                except Exception:
                    continue
            else:
                logger.error("Email input not found")
                self.page.screenshot(path="debug_idealista_login.png")
                return False

            time.sleep(0.5)

            # Fill password
            logger.info("Filling password...")
            pwd_selectors = ['input[type="password"]', 'input[name="password"]', '#password']
            for selector in pwd_selectors:
                try:
                    pwd_input = self.page.query_selector(selector)
                    if pwd_input:
                        pwd_input.fill(self.password)
                        break
                except Exception:
                    continue
            else:
                logger.error("Password input not found")
                return False

            time.sleep(0.5)

            # Submit
            logger.info("Submitting login...")
            submit_selectors = ['button[type="submit"]', 'button:has-text("Entrar")', '.submit-button']
            for selector in submit_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn:
                        btn.click()
                        break
                except Exception:
                    continue

            time.sleep(5)

            # Check for DataDome after login
            captcha_url = self._check_datadome()
            if captcha_url:
                if not self._solve_datadome_sync(captcha_url):
                    return False

            # Verify login
            if self._is_logged_in():
                logger.info("Login successful!")
                cookies = self.page.context.cookies()
                self._save_cookies(cookies)
                return True

            logger.error("Login verification failed")
            self.page.screenshot(path="debug_idealista_login_failed.png")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def _extract_phone(self) -> Optional[str]:
        """Extract phone number from listing."""
        try:
            # Click "Ver teléfono" button
            phone_btns = [
                'button:has-text("Ver teléfono")',
                '[class*="show-phone"]',
                '[class*="phone"] button',
            ]

            for selector in phone_btns:
                try:
                    btn = self.page.query_selector(selector)
                    if btn:
                        btn.click()
                        time.sleep(2)
                        break
                except Exception:
                    continue

            content = self.page.content()

            # Look for tel: links
            tel_matches = re.findall(r'tel:(?:\+?34)?(\d{9})', content)
            if tel_matches:
                phone = tel_matches[0]
                if phone[0] in '6789':
                    logger.info(f"Phone found: {phone}")
                    return phone

            # Spanish mobile pattern
            mobile_pattern = r'(?<!\d)([67]\d{2}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)'
            matches = re.findall(mobile_pattern, content)
            if matches:
                phone = re.sub(r'[\s.-]', '', matches[0])
                logger.info(f"Phone found: {phone}")
                return phone

            return None

        except Exception as e:
            logger.error(f"Phone extraction error: {e}")
            return None

    def _send_message(self, message: str) -> bool:
        """Send contact message."""
        try:
            # Scroll down to contact section
            self.page.evaluate("window.scrollTo(0, 500)")
            time.sleep(1)

            # Click contact button
            contact_btns = [
                'button:has-text("Contactar")',
                'a:has-text("Contactar")',
                '[class*="contact-button"]',
            ]

            for selector in contact_btns:
                try:
                    btn = self.page.query_selector(selector)
                    if btn:
                        btn.click()
                        time.sleep(2)
                        break
                except Exception:
                    continue

            # Fill name if empty
            try:
                name_input = self.page.query_selector('input[name="name"], input[name="nombre"]')
                if name_input:
                    value = name_input.input_value()
                    if not value:
                        name = os.getenv("CONTACT_NAME", "Interesado")
                        name_input.fill(name)
            except Exception:
                pass

            # Fill email if empty
            try:
                email_input = self.page.query_selector('input[name="email"]')
                if email_input:
                    value = email_input.input_value()
                    if not value:
                        email = os.getenv("CONTACT_EMAIL", "")
                        if email:
                            email_input.fill(email)
            except Exception:
                pass

            # Fill phone if empty
            try:
                phone_input = self.page.query_selector('input[name="phone"], input[name="telefono"]')
                if phone_input:
                    value = phone_input.input_value()
                    if not value:
                        phone = os.getenv("CONTACT_PHONE", "")
                        if phone:
                            phone_input.fill(phone)
            except Exception:
                pass

            # Fill message
            textarea = self.page.query_selector("textarea")
            if not textarea:
                logger.error("Message textarea not found")
                self.page.screenshot(path="debug_idealista_no_textarea.png")
                return False

            textarea.fill("")
            # Type with delays for human-like behavior
            textarea.type(message, delay=50)
            logger.info("Message filled")

            time.sleep(1)

            # Submit
            send_btns = [
                'button:has-text("Enviar")',
                'button[type="submit"]',
                'button:has-text("Contactar")',
            ]

            for selector in send_btns:
                try:
                    btn = self.page.query_selector(selector)
                    if btn:
                        btn.click()
                        break
                except Exception:
                    continue

            time.sleep(3)

            # Check for DataDome after submit
            captcha_url = self._check_datadome()
            if captcha_url:
                if not self._solve_datadome_sync(captcha_url):
                    return False

            # Check for success
            content = self.page.content()
            success_indicators = [
                "enviado",
                "Mensaje enviado",
                "gracias",
                "te hemos enviado",
            ]

            for indicator in success_indicators:
                if indicator.lower() in content.lower():
                    logger.info("Message sent successfully!")
                    return True

            # Check for error
            if "error" in content.lower():
                logger.error("Error in response")
                self.page.screenshot(path="debug_idealista_error.png")
                return False

            logger.info("Message likely sent (no error detected)")
            return True

        except Exception as e:
            logger.error(f"Send message error: {e}")
            return False


def main():
    """Test the Camoufox Idealista contact."""
    import argparse

    parser = argparse.ArgumentParser(description="Idealista Contact with Camoufox")
    parser.add_argument("--url", required=True, help="Listing URL")
    parser.add_argument("--message", default="Hola, me interesa este inmueble. ¿Sigue disponible?")
    parser.add_argument("--headless", action="store_true", help="Run headless")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    contact = CamoufoxIdealistaContact(headless=args.headless)
    result = contact.run_sync(args.url, args.message)

    print(f"\n{'='*50}")
    print(f"Result: {result}")


if __name__ == "__main__":
    main()

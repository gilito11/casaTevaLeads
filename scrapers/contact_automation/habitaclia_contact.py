"""
Habitaclia Contact Automation with 2Captcha integration.

Habitaclia uses reCAPTCHA on contact forms, requiring a captcha solving service.

Usage:
    python -m scrapers.contact_automation.habitaclia_contact --url <listing_url>

Environment:
    CAPTCHA_API_KEY: 2Captcha API key
    HABITACLIA_EMAIL: Account email (optional)
    HABITACLIA_PASSWORD: Account password (optional)
"""

import asyncio
import logging
import os
import re
from typing import Optional

from .base import BaseContactAutomation, ContactResult

logger = logging.getLogger(__name__)


class TwoCaptchaSolver:
    """2Captcha API wrapper for solving reCAPTCHA v2."""

    API_URL = "https://2captcha.com"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def solve_recaptcha(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> Optional[str]:
        """
        Solve reCAPTCHA v2 and return the g-recaptcha-response token.

        Args:
            site_key: The site key from the reCAPTCHA div
            page_url: URL of the page with the captcha
            timeout: Max seconds to wait for solution

        Returns:
            g-recaptcha-response token or None on failure
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                # Submit captcha
                submit_url = f"{self.API_URL}/in.php"
                submit_params = {
                    'key': self.api_key,
                    'method': 'userrecaptcha',
                    'googlekey': site_key,
                    'pageurl': page_url,
                    'json': 1
                }

                async with session.get(submit_url, params=submit_params) as resp:
                    result = await resp.json()
                    if result.get('status') != 1:
                        logger.error(f"2Captcha submit error: {result}")
                        return None
                    request_id = result['request']
                    logger.info(f"2Captcha request submitted: {request_id}")

                # Poll for solution
                result_url = f"{self.API_URL}/res.php"
                result_params = {
                    'key': self.api_key,
                    'action': 'get',
                    'id': request_id,
                    'json': 1
                }

                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    await asyncio.sleep(5)  # 2Captcha recommends 5s between polls

                    async with session.get(result_url, params=result_params) as resp:
                        result = await resp.json()

                        if result.get('status') == 1:
                            token = result['request']
                            logger.info("2Captcha solved successfully")
                            return token
                        elif result.get('request') == 'CAPCHA_NOT_READY':
                            continue
                        else:
                            logger.error(f"2Captcha error: {result}")
                            return None

                logger.error("2Captcha timeout")
                return None

        except Exception as e:
            logger.error(f"2Captcha error: {e}")
            return None


class HabitacliaContact(BaseContactAutomation):
    """Contact automation for Habitaclia.com with 2Captcha support."""

    PORTAL_NAME = "habitaclia"

    # URLs
    BASE_URL = "https://www.habitaclia.com"
    LOGIN_URL = "https://www.habitaclia.com/usuarios/entrada.htm"

    # Selectors
    SELECTORS = {
        # Login
        'login_email': 'input[name="email"], input#email',
        'login_password': 'input[name="password"], input#password',
        'login_submit': 'button[type="submit"], input[type="submit"]',

        # Contact form
        'contact_btn': 'a.contactar, button.contactar, [class*="contact"]',
        'input_name': 'input[name="nombre"], input[name="name"]',
        'input_email': 'input[name="email"]',
        'input_phone': 'input[name="telefono"], input[name="phone"]',
        'input_message': 'textarea[name="mensaje"], textarea[name="message"], textarea',
        'recaptcha_div': '.g-recaptcha, [data-sitekey]',
        'contact_submit': 'button[type="submit"]:has-text("Enviar"), input[type="submit"]',

        # Phone
        'ver_telefono': 'a.ver-telefono, [class*="phone"] a, [onclick*="telefono"]',
        'phone_number': '.telefono, [class*="phone-number"]',
    }

    def __init__(
        self,
        headless: bool = False,
        captcha_api_key: str = None,
        contact_name: str = None,
        contact_email: str = None,
        contact_phone: str = None
    ):
        super().__init__(headless=headless)
        self.email = os.getenv('HABITACLIA_EMAIL')
        self.password = os.getenv('HABITACLIA_PASSWORD')
        self.captcha_api_key = captcha_api_key or os.getenv('CAPTCHA_API_KEY')
        self.captcha_solver = None
        if self.captcha_api_key:
            self.captcha_solver = TwoCaptchaSolver(self.captcha_api_key)
        # Contact info for forms (tenant-specific or fallback to env)
        self.contact_name = contact_name or os.getenv('CONTACT_NAME', 'Interesado')
        self.contact_email = contact_email or os.getenv('CONTACT_EMAIL', '')
        self.contact_phone = contact_phone or os.getenv('CONTACT_PHONE', '')

    async def accept_cookies(self):
        """Accept cookies dialog if present."""
        try:
            cookie_selectors = [
                'button:has-text("Aceptar")',
                'button:has-text("Aceptar todo")',
                '#onetrust-accept-btn-handler',
                '[id*="accept"]',
            ]
            for selector in cookie_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=2000)
                    if btn:
                        await btn.click()
                        logger.info(f"Clicked cookie accept: {selector}")
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
            return False
        except:
            return False

    async def is_logged_in(self) -> bool:
        """Check if session is active."""
        try:
            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)
            await self.accept_cookies()

            content = await self.page.content()

            # Look for login indicators
            if 'Mi cuenta' in content or 'Mis favoritos' in content:
                logger.info("Session is active")
                return True

            if 'Entrar' in content or 'entrada.htm' in content:
                logger.info("Not logged in")
                return False

            # If cookies exist, assume logged in
            if self.cookies_file.exists():
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking login: {e}")
            return self.cookies_file.exists()

    async def login(self, email: str = None, password: str = None) -> bool:
        """Login to Habitaclia."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.warning("No credentials provided, continuing without login")
            return True  # Habitaclia allows contact without login

        try:
            await self.page.goto(self.LOGIN_URL, wait_until='networkidle')
            await asyncio.sleep(2)
            await self.accept_cookies()

            # Fill email
            email_input = await self.page.wait_for_selector(
                self.SELECTORS['login_email'], timeout=5000
            )
            if email_input:
                await email_input.fill(email)

            # Fill password
            password_input = await self.page.wait_for_selector(
                self.SELECTORS['login_password'], timeout=5000
            )
            if password_input:
                await password_input.fill(password)

            # Submit
            submit_btn = await self.page.wait_for_selector(
                self.SELECTORS['login_submit'], timeout=5000
            )
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(3)

            if await self.is_logged_in():
                await self.save_cookies()
                return True

            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def extract_phone(self, listing_url: str) -> Optional[str]:
        """Extract phone number from listing."""
        try:
            if self.page.url != listing_url:
                await self.page.goto(listing_url, wait_until='networkidle')
                await asyncio.sleep(2)

            # Try clicking "Ver teléfono" button
            for selector in ['a.ver-telefono', '[onclick*="telefono"]', '.ver-telefono']:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except:
                    continue

            # Look for phone in page
            content = await self.page.content()

            # tel: links
            tel_matches = re.findall(r'tel:(\+?34)?(\d{9})', content)
            if tel_matches:
                phone = tel_matches[0][1]
                if phone[0] in '6789':
                    return phone

            # Search for phone ONLY in listing description (NOT full page HTML)
            try:
                desc_element = await self.page.query_selector(
                    '.detail-description, [class*="description"], [id*="description"]'
                )
                if desc_element:
                    desc_text = await desc_element.inner_text()
                    mobile_pattern = r'(?<!\d)([67]\d{2}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)'
                    matches = re.findall(mobile_pattern, desc_text)
                    if matches:
                        phone = re.sub(r'[\s.-]', '', matches[0])
                        logger.info(f"Phone found in description: {phone}")
                        return phone
            except:
                pass

            return None

        except Exception as e:
            logger.error(f"Error extracting phone: {e}")
            return None

    async def solve_captcha_on_page(self) -> bool:
        """Find and solve reCAPTCHA on the current page."""
        if not self.captcha_solver:
            logger.error("No CAPTCHA_API_KEY configured")
            return False

        try:
            # Find reCAPTCHA div and get site key
            recaptcha_el = await self.page.query_selector(self.SELECTORS['recaptcha_div'])
            if not recaptcha_el:
                logger.info("No reCAPTCHA found on page")
                return True  # No captcha needed

            site_key = await recaptcha_el.get_attribute('data-sitekey')
            if not site_key:
                logger.error("Could not find reCAPTCHA site key")
                return False

            logger.info(f"Found reCAPTCHA with site key: {site_key[:20]}...")

            # Solve captcha
            token = await self.captcha_solver.solve_recaptcha(
                site_key=site_key,
                page_url=self.page.url
            )

            if not token:
                logger.error("Failed to solve captcha")
                return False

            # Inject token into page
            await self.page.evaluate(f'''
                document.getElementById('g-recaptcha-response').value = '{token}';
                // Also set for any hidden textarea
                var textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"]');
                textareas.forEach(function(ta) {{ ta.value = '{token}'; }});
            ''')

            logger.info("Captcha token injected")
            return True

        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return False

    async def send_message(self, listing_url: str, message: str) -> bool:
        """Send contact message (with captcha solving)."""
        try:
            if self.page.url != listing_url:
                await self.page.goto(listing_url, wait_until='networkidle')
                await asyncio.sleep(2)

            # Click contact button if form not visible
            try:
                contact_btn = await self.page.wait_for_selector(
                    self.SELECTORS['contact_btn'], timeout=3000
                )
                if contact_btn:
                    await contact_btn.click()
                    await asyncio.sleep(2)
            except:
                pass

            # Fill form fields
            # Name
            try:
                name_input = await self.page.query_selector(self.SELECTORS['input_name'])
                if name_input:
                    value = await name_input.input_value()
                    if not value:
                        await name_input.fill(self.contact_name)
            except:
                pass

            # Email
            try:
                email_input = await self.page.query_selector(self.SELECTORS['input_email'])
                if email_input:
                    value = await email_input.input_value()
                    if not value and self.contact_email:
                        await email_input.fill(self.contact_email)
            except:
                pass

            # Phone
            try:
                phone_input = await self.page.query_selector(self.SELECTORS['input_phone'])
                if phone_input:
                    value = await phone_input.input_value()
                    if not value and self.contact_phone:
                        await phone_input.fill(self.contact_phone)
            except:
                pass

            # Message
            message_input = await self.page.wait_for_selector(
                self.SELECTORS['input_message'], timeout=5000
            )
            if message_input:
                await message_input.fill('')
                await self.human_type('textarea', message)
                logger.info("Message filled")

            # Solve captcha if present
            if not await self.solve_captcha_on_page():
                logger.error("Captcha solving failed")
                return False

            # Submit form
            submit_btn = await self.page.wait_for_selector(
                self.SELECTORS['contact_submit'], timeout=5000
            )
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(3)

                # Check for success
                content = await self.page.content()
                if 'enviado' in content.lower() or 'gracias' in content.lower():
                    logger.info("Message sent successfully")
                    return True

                # Check for error
                if 'error' in content.lower() or 'captcha' in content.lower():
                    logger.error("Error or captcha issue after submit")
                    return False

                # Assume success if no explicit error
                logger.info("Message likely sent (no error detected)")
                return True

            return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False


async def main():
    """Test the Habitaclia contact automation."""
    import argparse

    parser = argparse.ArgumentParser(description='Habitaclia Contact Automation')
    parser.add_argument('--url', required=True, help='Listing URL to contact')
    parser.add_argument('--message', default='Hola, me interesa este inmueble. ¿Podríamos hablar?')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    contact = HabitacliaContact(headless=args.headless)

    try:
        await contact.setup_browser()

        # Contact the lead
        result = await contact.contact_lead(
            lead_id="test",
            listing_url=args.url,
            message=args.message
        )

        print(f"\nResult: {result.to_dict()}")

    finally:
        await contact.close()


if __name__ == '__main__':
    asyncio.run(main())

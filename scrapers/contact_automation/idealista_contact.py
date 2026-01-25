"""
Idealista Contact Automation with DataDome bypass via 2Captcha.

Idealista uses DataDome anti-bot protection. 2Captcha can solve DataDome
challenges (~$2.99/1000 solutions).

Usage:
    python -m scrapers.contact_automation.idealista_contact --url <listing_url>

Environment:
    CAPTCHA_API_KEY: 2Captcha API key (required for DataDome)
    IDEALISTA_EMAIL: Account email (required)
    IDEALISTA_PASSWORD: Account password (required)
"""

import asyncio
import logging
import os
import re
from typing import Optional

from .base import BaseContactAutomation, ContactResult

logger = logging.getLogger(__name__)


class DataDomeSolver:
    """2Captcha API wrapper for solving DataDome slider challenges."""

    API_URL = "https://api.2captcha.com"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def solve_datadome(
        self,
        captcha_url: str,
        page_url: str,
        user_agent: str,
        proxy: Optional[str] = None,
        timeout: int = 180
    ) -> Optional[dict]:
        """
        Solve DataDome slider challenge using 2Captcha's new API.

        Args:
            captcha_url: The full DataDome captcha URL (geo.captcha-delivery.com/...)
            page_url: Original page URL that triggered DataDome
            user_agent: Browser user agent
            proxy: Optional proxy string (format: user:pass@ip:port or ip:port)
            timeout: Max seconds to wait for solution

        Returns:
            Dict with 'datadome' cookie value or None on failure
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                # Build task payload for new API
                task = {
                    "type": "DataDomeSliderTask",
                    "websiteURL": page_url,
                    "captchaUrl": captcha_url,
                    "userAgent": user_agent,
                }

                # Add proxy if provided (required for DataDome)
                if proxy:
                    # Parse proxy: user:pass@ip:port or ip:port
                    if '@' in proxy:
                        auth, addr = proxy.rsplit('@', 1)
                        user, passwd = auth.split(':', 1)
                        ip, port = addr.split(':')
                        task["proxyType"] = "http"
                        task["proxyAddress"] = ip
                        task["proxyPort"] = int(port)
                        task["proxyLogin"] = user
                        task["proxyPassword"] = passwd
                    else:
                        ip, port = proxy.split(':')
                        task["proxyType"] = "http"
                        task["proxyAddress"] = ip
                        task["proxyPort"] = int(port)

                payload = {
                    "clientKey": self.api_key,
                    "task": task
                }

                # Submit task
                logger.info(f"Submitting DataDome task for: {page_url}")
                async with session.post(
                    f"{self.API_URL}/createTask",
                    json=payload
                ) as resp:
                    result = await resp.json()
                    if result.get('errorId', 0) != 0:
                        logger.error(f"2Captcha DataDome submit error: {result}")
                        # Try legacy method as fallback
                        return await self._solve_legacy(captcha_url, page_url, user_agent, proxy, timeout)

                    task_id = result.get('taskId')
                    if not task_id:
                        logger.error(f"No taskId in response: {result}")
                        return await self._solve_legacy(captcha_url, page_url, user_agent, proxy, timeout)

                    logger.info(f"DataDome task submitted: {task_id}")

                # Poll for solution
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    await asyncio.sleep(10)

                    async with session.post(
                        f"{self.API_URL}/getTaskResult",
                        json={"clientKey": self.api_key, "taskId": task_id}
                    ) as resp:
                        result = await resp.json()

                        if result.get('errorId', 0) != 0:
                            logger.error(f"2Captcha poll error: {result}")
                            return None

                        status = result.get('status')
                        if status == 'ready':
                            solution = result.get('solution', {})
                            cookie = solution.get('cookie')
                            if cookie:
                                logger.info("DataDome solved successfully!")
                                return {'datadome': cookie}
                            else:
                                logger.error(f"No cookie in solution: {solution}")
                                return None
                        elif status == 'processing':
                            continue

                logger.error("DataDome solve timeout")
                return None

        except Exception as e:
            logger.error(f"2Captcha DataDome error: {e}")
            return None

    async def _solve_legacy(
        self,
        captcha_url: str,
        page_url: str,
        user_agent: str,
        proxy: Optional[str] = None,
        timeout: int = 180
    ) -> Optional[dict]:
        """Fallback to legacy in.php method."""
        import aiohttp

        logger.info("Trying legacy 2Captcha method...")

        try:
            async with aiohttp.ClientSession() as session:
                submit_data = {
                    'key': self.api_key,
                    'method': 'datadome',
                    'captcha_url': captcha_url,
                    'pageurl': page_url,
                    'userAgent': user_agent,
                    'json': 1
                }

                if proxy:
                    submit_data['proxy'] = proxy
                    submit_data['proxytype'] = 'HTTP'

                async with session.post(
                    "https://2captcha.com/in.php",
                    data=submit_data
                ) as resp:
                    result = await resp.json()
                    if result.get('status') != 1:
                        logger.error(f"Legacy submit error: {result}")
                        return None
                    request_id = result['request']
                    logger.info(f"Legacy request submitted: {request_id}")

                # Poll
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    await asyncio.sleep(10)

                    async with session.get(
                        "https://2captcha.com/res.php",
                        params={
                            'key': self.api_key,
                            'action': 'get',
                            'id': request_id,
                            'json': 1
                        }
                    ) as resp:
                        result = await resp.json()

                        if result.get('status') == 1:
                            cookie_value = result['request']
                            logger.info("Legacy DataDome solved!")
                            return {'datadome': cookie_value}
                        elif result.get('request') == 'CAPCHA_NOT_READY':
                            continue
                        else:
                            logger.error(f"Legacy poll error: {result}")
                            return None

                return None

        except Exception as e:
            logger.error(f"Legacy method error: {e}")
            return None


class IdealistaContact(BaseContactAutomation):
    """Contact automation for Idealista.com with DataDome bypass."""

    PORTAL_NAME = "idealista"

    # URLs
    BASE_URL = "https://www.idealista.com"
    LOGIN_URL = "https://www.idealista.com/login"

    # Selectors
    SELECTORS = {
        # Login
        'login_email': 'input[name="email"], input#email',
        'login_password': 'input[name="password"], input#password',
        'login_submit': 'button[type="submit"], .submit-button',

        # Logged in indicators
        'user_menu': '[class*="user-menu"], [class*="mi-idealista"]',

        # Contact form
        'contact_btn': 'button:has-text("Contactar"), a:has-text("Contactar"), [class*="contact-button"]',
        'input_name': 'input[name="name"], input[name="nombre"]',
        'input_email': 'input[name="email"]',
        'input_phone': 'input[name="phone"], input[name="telefono"]',
        'input_message': 'textarea, [name="message"]',
        'contact_submit': 'button[type="submit"]:has-text("Enviar"), button:has-text("Contactar")',

        # Phone
        'ver_telefono': '[class*="show-phone"], [class*="ver-telefono"], button:has-text("Ver teléfono")',
        'phone_number': '[class*="phone-number"], a[href^="tel:"]',

        # DataDome indicators
        'datadome_challenge': '#datadome-captcha, [class*="datadome"]',
    }

    # User agent (must match what 2Captcha uses)
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'

    def __init__(self, headless: bool = False, captcha_api_key: str = None, email: str = None, password: str = None, proxy: str = None):
        super().__init__(headless=headless)
        self.email = email or os.getenv('IDEALISTA_EMAIL')
        self.password = password or os.getenv('IDEALISTA_PASSWORD')
        self.captcha_api_key = captcha_api_key or os.getenv('CAPTCHA_API_KEY')
        # Proxy format: user:pass@ip:port or ip:port
        # Required for DataDome solving via 2Captcha
        self.proxy = proxy or os.getenv('DATADOME_PROXY')
        self.datadome_solver = None
        if self.captcha_api_key:
            self.datadome_solver = DataDomeSolver(self.captcha_api_key)

    async def accept_cookies(self):
        """Accept cookies dialog if present."""
        try:
            cookie_selectors = [
                'button:has-text("Aceptar")',
                'button:has-text("Aceptar todas")',
                '#didomi-notice-agree-button',
                '[id*="accept"]',
                'button:has-text("Aceptar y cerrar")',
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

    async def check_datadome_challenge(self) -> bool:
        """Check if DataDome challenge is present."""
        try:
            content = await self.page.content()

            # DataDome indicators
            datadome_indicators = [
                'geo.captcha-delivery.com',
                'datadome-captcha',
                'Please verify you are human',
                'Verificación de seguridad',
            ]

            for indicator in datadome_indicators:
                if indicator in content:
                    logger.warning(f"DataDome challenge detected: {indicator}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking DataDome: {e}")
            return False

    async def solve_datadome_challenge(self) -> bool:
        """Solve DataDome challenge if present."""
        if not self.datadome_solver:
            logger.error("No CAPTCHA_API_KEY configured for DataDome")
            return False

        try:
            # Get page content to find the DataDome captcha URL
            content = await self.page.content()
            current_url = self.page.url

            # Extract the full DataDome captcha URL (geo.captcha-delivery.com)
            captcha_url = None

            # Check if we're on a DataDome redirect page
            if 'geo.captcha-delivery.com' in current_url:
                captcha_url = current_url
            else:
                # Look for iframe or script with DataDome URL
                import re
                dd_pattern = r'(https://geo\.captcha-delivery\.com/captcha/[^"\'>\s]+)'
                matches = re.findall(dd_pattern, content)
                if matches:
                    captcha_url = matches[0]

            if not captcha_url:
                # Construct a basic captcha URL
                captcha_url = current_url
                logger.warning(f"Could not find DataDome URL, using: {captcha_url}")
            else:
                logger.info(f"Found DataDome captcha URL: {captcha_url[:100]}...")

            # Original page URL
            original_url = self.BASE_URL

            # Solve DataDome (requires proxy)
            if not self.proxy:
                logger.warning("No DATADOME_PROXY configured - DataDome solving may fail")
                logger.warning("Set DATADOME_PROXY=user:pass@ip:port or get residential proxy")

            result = await self.datadome_solver.solve_datadome(
                captcha_url=captcha_url,
                page_url=original_url,
                user_agent=self.USER_AGENT,
                proxy=self.proxy
            )

            if not result:
                logger.error("Failed to solve DataDome challenge")
                return False

            # Set the datadome cookie
            datadome_cookie = result.get('datadome')
            if datadome_cookie:
                await self.context.add_cookies([{
                    'name': 'datadome',
                    'value': datadome_cookie,
                    'domain': '.idealista.com',
                    'path': '/',
                }])
                logger.info("DataDome cookie set successfully")

                # Reload the page
                await self.page.reload()
                await asyncio.sleep(3)

                # Check if still blocked
                if await self.check_datadome_challenge():
                    logger.error("Still blocked after DataDome solution")
                    return False

                return True

            return False

        except Exception as e:
            logger.error(f"Error solving DataDome: {e}")
            return False

    async def navigate_with_datadome_handling(self, url: str) -> bool:
        """Navigate to URL, handling DataDome if triggered."""
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)

            # Accept cookies first
            await self.accept_cookies()

            # Check for DataDome
            if await self.check_datadome_challenge():
                logger.info("DataDome detected, attempting to solve...")
                if not await self.solve_datadome_challenge():
                    return False

            return True

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False

    async def is_logged_in(self) -> bool:
        """Check if session is active."""
        try:
            if not await self.navigate_with_datadome_handling(self.BASE_URL):
                return False

            content = await self.page.content()

            # Look for logged in indicators
            logged_in_indicators = [
                'Mi idealista',
                'mi-idealista',
                'Mis búsquedas',
                'Cerrar sesión',
            ]

            for indicator in logged_in_indicators:
                if indicator in content:
                    logger.info(f"Session is active (found: {indicator})")
                    return True

            # Check for login link (not logged in)
            if 'Iniciar sesión' in content or '/login' in content:
                logger.info("Not logged in")
                return False

            # If cookies exist, might be logged in
            if self.cookies_file.exists():
                logger.info("Cookies exist, assuming logged in")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking login: {e}")
            return self.cookies_file.exists()

    async def login(self, email: str = None, password: str = None) -> bool:
        """Login to Idealista."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("IDEALISTA_EMAIL and IDEALISTA_PASSWORD env vars required")
            return False

        try:
            logger.info("Navigating to Idealista login...")
            if not await self.navigate_with_datadome_handling(self.LOGIN_URL):
                return False

            await asyncio.sleep(2)

            # Fill email
            logger.info("Filling email...")
            email_input = None
            for selector in ['input[type="email"]', 'input[name="email"]', '#email']:
                try:
                    email_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if email_input:
                        break
                except:
                    continue

            if not email_input:
                logger.error("Could not find email input")
                await self.page.screenshot(path='debug_idealista_login.png')
                return False

            await email_input.fill(email)
            await asyncio.sleep(0.5)

            # Fill password
            logger.info("Filling password...")
            password_input = None
            for selector in ['input[type="password"]', 'input[name="password"]', '#password']:
                try:
                    password_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if password_input:
                        break
                except:
                    continue

            if not password_input:
                logger.error("Could not find password input")
                return False

            await password_input.fill(password)
            await asyncio.sleep(0.5)

            # Submit
            logger.info("Submitting login...")
            submit_btn = None
            for selector in ['button[type="submit"]', '.submit-button', 'button:has-text("Entrar")']:
                try:
                    submit_btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if submit_btn:
                        break
                except:
                    continue

            if submit_btn:
                await submit_btn.click()
            else:
                await password_input.press('Enter')

            await asyncio.sleep(5)

            # Check for DataDome after login
            if await self.check_datadome_challenge():
                if not await self.solve_datadome_challenge():
                    return False

            # Verify login
            if await self.is_logged_in():
                logger.info("Login successful!")
                await self.save_cookies()
                return True
            else:
                logger.error("Login failed")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def extract_phone(self, listing_url: str) -> Optional[str]:
        """Extract phone number from listing."""
        try:
            if self.page.url != listing_url:
                if not await self.navigate_with_datadome_handling(listing_url):
                    return None

            # Try clicking "Ver teléfono" button
            for selector in ['[class*="show-phone"]', 'button:has-text("Ver teléfono")', '[class*="phone"] button']:
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
                    logger.info(f"Phone found: {phone}")
                    return phone

            # Spanish mobile pattern
            mobile_pattern = r'(?<!\d)([67]\d{2}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)'
            matches = re.findall(mobile_pattern, content)
            if matches:
                phone = re.sub(r'[\s.-]', '', matches[0])
                logger.info(f"Phone found via pattern: {phone}")
                return phone

            logger.info("No phone number found")
            return None

        except Exception as e:
            logger.error(f"Error extracting phone: {e}")
            return None

    async def send_message(self, listing_url: str, message: str) -> bool:
        """Send contact message to seller."""
        try:
            if self.page.url != listing_url:
                if not await self.navigate_with_datadome_handling(listing_url):
                    return False

            await asyncio.sleep(2)

            # Scroll to contact section
            await self.page.evaluate('window.scrollTo(0, 500)')
            await asyncio.sleep(1)

            # Click contact button if form not visible
            for selector in ['button:has-text("Contactar")', 'a:has-text("Contactar")', '[class*="contact-button"]']:
                try:
                    contact_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if contact_btn:
                        await contact_btn.click()
                        await asyncio.sleep(2)
                        break
                except:
                    continue

            # Fill form fields
            # Name
            try:
                name_input = await self.page.query_selector('input[name="name"], input[name="nombre"]')
                if name_input:
                    value = await name_input.input_value()
                    if not value:
                        our_name = os.getenv('CONTACT_NAME', 'Interesado')
                        await name_input.fill(our_name)
            except:
                pass

            # Email
            try:
                email_input = await self.page.query_selector('input[name="email"]')
                if email_input:
                    value = await email_input.input_value()
                    if not value:
                        our_email = os.getenv('CONTACT_EMAIL', '')
                        if our_email:
                            await email_input.fill(our_email)
            except:
                pass

            # Phone
            try:
                phone_input = await self.page.query_selector('input[name="phone"], input[name="telefono"]')
                if phone_input:
                    value = await phone_input.input_value()
                    if not value:
                        our_phone = os.getenv('CONTACT_PHONE', '')
                        if our_phone:
                            await phone_input.fill(our_phone)
            except:
                pass

            # Message
            message_field = await self.page.wait_for_selector('textarea', timeout=5000)
            if message_field:
                await message_field.fill('')
                # Type message with human-like delays
                for char in message:
                    await message_field.type(char, delay=50)
                logger.info("Message filled")
            else:
                logger.error("Message field not found")
                return False

            await asyncio.sleep(1)

            # Submit
            send_btn = None
            for selector in ['button:has-text("Enviar")', 'button[type="submit"]', 'button:has-text("Contactar")']:
                try:
                    send_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if send_btn:
                        break
                except:
                    continue

            if not send_btn:
                logger.error("Send button not found")
                return False

            logger.info("Clicking send...")
            await send_btn.click()
            await asyncio.sleep(3)

            # Check for DataDome after submit
            if await self.check_datadome_challenge():
                if not await self.solve_datadome_challenge():
                    return False

            # Check for success
            content = await self.page.content()
            success_indicators = [
                'enviado',
                'Mensaje enviado',
                'gracias',
                'te hemos enviado',
            ]

            for indicator in success_indicators:
                if indicator.lower() in content.lower():
                    logger.info("Message sent successfully!")
                    return True

            # Check for error
            if 'error' in content.lower():
                logger.error("Error detected after submit")
                return False

            # Assume success if no explicit error
            logger.info("Message likely sent (no error detected)")
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False


async def main():
    """Test the Idealista contact automation."""
    import argparse

    parser = argparse.ArgumentParser(description='Idealista Contact Automation')
    parser.add_argument('--url', required=True, help='Listing URL to contact')
    parser.add_argument('--message', default='Hola, me interesa este inmueble. ¿Sigue disponible?')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--login', action='store_true', help='Force login')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    contact = IdealistaContact(headless=args.headless)

    try:
        await contact.setup_browser()

        # Check/perform login
        if args.login or not await contact.is_logged_in():
            success = await contact.login()
            if not success:
                print("Login failed. Set IDEALISTA_EMAIL and IDEALISTA_PASSWORD env vars.")
                return

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

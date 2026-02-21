"""
Milanuncios Contact Automation.

Automates:
1. Login with email/password
2. Extract phone from listing (if visible)
3. Send contact message via internal chat system

Usage:
    python -m scrapers.contact_automation.milanuncios_contact --url <listing_url>
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from .base import BaseContactAutomation, ContactResult

logger = logging.getLogger(__name__)


class MilanunciosContact(BaseContactAutomation):
    """Contact automation for Milanuncios.com using Camoufox anti-detect browser."""

    PORTAL_NAME = "milanuncios"

    # URLs
    BASE_URL = "https://www.milanuncios.com"
    LOGIN_URL = "https://www.milanuncios.com/login/"

    # Selectors
    SELECTORS = {
        # Login page
        'login_email': 'input[name="email"], input[type="email"], #email',
        'login_password': 'input[name="password"], input[type="password"], #password',
        'login_submit': 'button[type="submit"], [class*="submit"]',

        # Logged in indicator
        'user_menu': '[class*="user-menu"], [class*="UserMenu"], [class*="mi-cuenta"]',
        'user_name': '[class*="user-name"], [class*="UserName"]',

        # Contact form on listing
        'contact_button': 'button:has-text("Contactar"), a:has-text("Contactar"), [class*="contact-button"]',
        'message_input': 'textarea, [class*="message"] textarea, [name="message"]',
        'send_button': 'button:has-text("Enviar"), button[type="submit"]:has-text("Enviar")',

        # Phone (sometimes visible in listing)
        'phone_button': 'button:has-text("Ver teléfono"), [class*="phone-button"]',
        'phone_number': '[class*="phone-number"], a[href^="tel:"]',
    }

    def __init__(self, headless: bool = False, email: str = None, password: str = None, proxy: str = None):
        super().__init__(headless=headless, proxy=proxy)
        self.email = email or os.getenv('MILANUNCIOS_EMAIL')
        self.password = password or os.getenv('MILANUNCIOS_PASSWORD')
        if not self.proxy:
            self.proxy = os.getenv('DATADOME_PROXY')
        self._camoufox_cm = None

    async def setup_browser(self):
        """Initialize Camoufox anti-detect browser (bypasses GeeTest/bot detection)."""
        from camoufox.async_api import AsyncCamoufox
        from scrapers.camoufox_idealista import parse_proxy

        camoufox_opts = {
            "humanize": 2.5,
            "headless": self.headless,
            "geoip": True,
            "os": "windows",
            "block_webrtc": True,
            "locale": ["es-ES", "es"],
        }

        proxy_config = parse_proxy(self.proxy)
        if proxy_config:
            camoufox_opts["proxy"] = proxy_config
            logger.info(f"Camoufox proxy configured: {proxy_config['server']}")

        logger.info("Launching Camoufox browser for Milanuncios contact automation")

        self._camoufox_cm = AsyncCamoufox(**camoufox_opts)
        self.browser = await self._camoufox_cm.__aenter__()

        # Create context and page
        self.context = await self.browser.new_context()

        # Load saved cookies
        if self.cookies_file.exists():
            cookies = json.loads(self.cookies_file.read_text())
            await self.context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} cookies from {self.cookies_file}")

        self.page = await self.context.new_page()

    async def close(self):
        """Clean up Camoufox browser resources."""
        if self.context:
            await self.save_cookies()
        if self._camoufox_cm:
            await self._camoufox_cm.__aexit__(None, None, None)
        elif self.browser:
            await self.browser.close()

    async def accept_cookies(self):
        """Accept cookies dialog if present."""
        try:
            cookie_selectors = [
                '#onetrust-accept-btn-handler',
                'button:has-text("Aceptar")',
                'button:has-text("Aceptar todo")',
                'button:has-text("Aceptar y continuar")',
                '#didomi-notice-agree-button',
                '[class*="accept-cookies"]',
                'button[id*="accept"]',
            ]
            for selector in cookie_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=2000)
                    if btn:
                        await btn.click()
                        logger.info(f"Clicked cookie accept button: {selector}")
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
            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)

            # Accept cookies first
            await self.accept_cookies()
            await asyncio.sleep(1)

            content = await self.page.content()

            # Look for logged-in indicators
            logged_in_indicators = [
                'ma-UserNav',
                'Mi cuenta',
                'Mis anuncios',
                'Cerrar sesión',
                'mis-favoritos',
                'user-menu',
                'UserNav',
            ]

            for indicator in logged_in_indicators:
                if indicator in content:
                    logger.info(f"Session is active (found: {indicator})")
                    return True

            # Check if "Acceder" or "Iniciar sesión" link is visible
            if 'Acceder</a>' in content or 'Iniciar sesión' in content or '>Entrar<' in content:
                logger.info("Not logged in (login link visible)")
                return False

            # If cookies exist and no clear indicator, assume logged in
            if self.cookies_file.exists():
                logger.info("Cookies exist, assuming logged in")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            if self.cookies_file.exists():
                return True
            return False

    async def login(self, email: str = None, password: str = None) -> bool:
        """Login to Milanuncios by clicking 'Acceder' on homepage, then email → password flow."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("MILANUNCIOS_EMAIL and MILANUNCIOS_PASSWORD env vars required")
            return False

        try:
            # Always navigate fresh to homepage for login
            logger.info("Navigating to Milanuncios homepage...")
            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=45000)
            await asyncio.sleep(5)
            await self.accept_cookies()
            await asyncio.sleep(2)

            # Find login button via JS, then use Playwright click (triggers React events)
            logger.info("Looking for login button on homepage...")
            btn_box = await self.page.evaluate("""() => {
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                for (const btn of buttons) {
                    const text = (btn.textContent || '').trim().toLowerCase();
                    if (text.includes('iniciar sesi') || text.includes('acceder')
                        || text.includes('entrar') || text === 'login') {
                        const rect = btn.getBoundingClientRect();
                        return {
                            text: btn.textContent.trim(),
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2
                        };
                    }
                }
                return null;
            }""")

            if not btn_box:
                logger.error("Could not find login button on homepage")
                return False

            logger.info(f"Found login button: '{btn_box['text']}' at ({btn_box['x']:.0f}, {btn_box['y']:.0f})")

            # Listen for popup windows before clicking
            popup_page = None
            self.context.on("page", lambda page: setattr(self, '_popup_page', page))
            self._popup_page = None

            await self.page.mouse.click(btn_box['x'], btn_box['y'])
            logger.info("Clicked login button, waiting for login form...")
            await asyncio.sleep(5)

            # Check what happened after click
            logger.info(f"After click URL: {self.page.url}")

            # Check for popup window
            all_pages = self.context.pages
            logger.info(f"Open pages: {len(all_pages)}")
            for i, p in enumerate(all_pages):
                logger.info(f"  Page {i}: {p.url[:80]}")

            # Determine which page has the login form
            target_page = self.page
            if self._popup_page:
                logger.info(f"Popup detected: {self._popup_page.url[:80]}")
                target_page = self._popup_page
                await asyncio.sleep(3)
            elif len(all_pages) > 1:
                # Use the newest page (likely the login popup)
                target_page = all_pages[-1]
                logger.info(f"Using newest page: {target_page.url[:80]}")
                await asyncio.sleep(3)

            # Check for iframes (login might be in an iframe modal)
            frames = target_page.frames
            logger.info(f"Target page has {len(frames)} frames")
            for i, f in enumerate(frames):
                logger.info(f"  Frame {i}: {f.url[:80]}")

            # Check for modal dialog
            modal_info = await target_page.evaluate("""() => {
                // Check for dialog elements
                const dialogs = document.querySelectorAll('dialog, [role="dialog"], [class*="modal"], [class*="Modal"], [class*="overlay"], [class*="Overlay"]');
                const results = [];
                for (const d of dialogs) {
                    results.push({
                        tag: d.tagName,
                        class: (d.className || '').substring(0, 80),
                        visible: d.offsetParent !== null || d.style.display !== 'none',
                        inputs: d.querySelectorAll('input').length
                    });
                }
                return results;
            }""")
            logger.info(f"Modal/dialog elements: {modal_info}")

            # --- STEP 1: Email ---
            logger.info("Step 1: Filling email...")
            # Search for email input in target page and all frames
            email_input = None
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                '#email',
                'input[placeholder*="mail"]',
                'input[placeholder*="correo"]',
                'input[autocomplete="email"]',
                'input[autocomplete="username"]',
            ]

            search_targets = [target_page] + list(target_page.frames[1:])  # page + iframes
            for target in search_targets:
                for selector in email_selectors:
                    try:
                        email_input = await target.wait_for_selector(selector, timeout=3000)
                        if email_input:
                            logger.info(f"Found email input: {selector} in {target.url[:50]}")
                            target_page = target  # Use this frame for remaining steps
                            break
                    except:
                        continue
                if email_input:
                    break

            if not email_input:
                # Log what inputs exist for debugging
                input_count = await target_page.evaluate("() => document.querySelectorAll('input').length")
                logger.error(f"No email input found. Total inputs: {input_count}, URL: {target_page.url}")
                if input_count > 0:
                    input_info = await target_page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('input')).map(i => ({
                            type: i.type, name: i.name, id: i.id, placeholder: i.placeholder
                        }))
                    }""")
                    logger.info(f"Available inputs: {input_info}")
                return False

            await email_input.fill(email)
            await asyncio.sleep(1)

            # Click "Continuar" to go to password screen
            logger.info("Clicking Continuar...")
            continue_btn = None
            for selector in ['button:has-text("Continuar")', 'button[type="submit"]',
                             'button:has-text("Siguiente")', 'button:has-text("Next")']:
                try:
                    continue_btn = await target_page.wait_for_selector(selector, timeout=5000)
                    if continue_btn:
                        break
                except:
                    continue

            if continue_btn:
                await continue_btn.click()
            else:
                await email_input.press('Enter')

            await asyncio.sleep(3)
            logger.info(f"After Continuar URL: {target_page.url}")

            # --- STEP 2: Password ---
            logger.info("Step 2: Filling password...")
            password_input = None
            for selector in ['input[type="password"]', 'input[name="password"]', '#password']:
                try:
                    password_input = await target_page.wait_for_selector(selector, timeout=10000)
                    if password_input:
                        break
                except:
                    continue

            if not password_input:
                logger.error(f"Could not find password input. URL: {target_page.url}")
                return False

            await password_input.fill(password)
            await asyncio.sleep(1)

            # Click "Iniciar sesion" or submit
            logger.info("Submitting login...")
            submit_btn = None
            for selector in ['button:has-text("Iniciar")', 'button:has-text("Entrar")',
                             'button:has-text("Acceder")', 'button:has-text("Log in")',
                             'button[type="submit"]']:
                try:
                    submit_btn = await target_page.wait_for_selector(selector, timeout=5000)
                    if submit_btn:
                        break
                except:
                    continue

            if submit_btn:
                await submit_btn.click()
            else:
                await password_input.press('Enter')

            await asyncio.sleep(5)
            logger.info(f"After login URL: {self.page.url}")

            # Verify login
            if await self.is_logged_in():
                logger.info("Login successful!")
                await self.save_cookies()
                return True
            else:
                logger.error("Login failed - not logged in after submit")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def extract_phone(self, listing_url: str) -> Optional[str]:
        """Extract phone number from listing if visible."""
        try:
            # Make sure we're on the listing page
            if self.page.url != listing_url:
                await self.page.goto(listing_url, wait_until='networkidle')
                await asyncio.sleep(2)

            # Try to find phone button
            phone_btn = None
            for selector in ['button:has-text("Ver teléfono")', '[class*="phone"] button', '[class*="Phone"] button']:
                try:
                    phone_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if phone_btn:
                        break
                except:
                    continue

            if phone_btn:
                logger.info("Found 'Ver teléfono' button, clicking...")
                await phone_btn.click()
                await asyncio.sleep(3)

            # Try to find phone in tel: links
            try:
                phone_link = await self.page.query_selector('a[href^="tel:"]')
                if phone_link:
                    href = await phone_link.get_attribute('href')
                    if href:
                        phone = href.replace('tel:', '').replace('+34', '').replace(' ', '')
                        phone = re.sub(r'[^\d]', '', phone)
                        if len(phone) >= 9:
                            phone = phone[-9:]
                            if phone[0] in '6789':
                                logger.info(f"Phone found via tel: link: {phone}")
                                return phone
            except:
                pass

            # Search in page content
            page_content = await self.page.content()

            # Look for tel: patterns
            tel_matches = re.findall(r'tel:(\+?34)?(\d{9})', page_content)
            if tel_matches:
                phone = tel_matches[0][1]
                if phone[0] in '6789':
                    logger.info(f"Phone found via tel: pattern: {phone}")
                    return phone

            # Spanish mobile pattern
            mobile_pattern = r'(?<!\d)([67]\d{2}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)'
            matches = re.findall(mobile_pattern, page_content)
            if matches:
                phone = re.sub(r'[\s.-]', '', matches[0])
                logger.info(f"Phone found via mobile pattern: {phone}")
                return phone

            # Also check description text
            try:
                desc_element = await self.page.query_selector('[class*="description"], [class*="Description"]')
                if desc_element:
                    desc_text = await desc_element.inner_text()
                    matches = re.findall(mobile_pattern, desc_text)
                    if matches:
                        phone = re.sub(r'[\s.-]', '', matches[0])
                        logger.info(f"Phone found in description: {phone}")
                        return phone
            except:
                pass

            logger.info("No phone number found on listing")
            return None

        except Exception as e:
            logger.error(f"Error extracting phone: {e}")
            return None

    async def send_message(self, listing_url: str, message: str) -> bool:
        """Send contact message via Milanuncios internal chat."""
        try:
            # Make sure we're on the listing page
            if self.page.url != listing_url:
                await self.page.goto(listing_url, wait_until='networkidle')
                await asyncio.sleep(2)

            # Accept cookies if shown again
            await self.accept_cookies()

            # Scroll down to see contact options
            await self.page.evaluate('window.scrollTo(0, 500)')
            await asyncio.sleep(1)

            # Look for contact button
            contact_btn = None
            contact_selectors = [
                'button:has-text("Contactar")',
                'button:has-text("Enviar mensaje")',
                'a:has-text("Contactar")',
                '[class*="contact-button"]',
                '[class*="ContactButton"]',
                '[data-testid*="contact"]',
            ]

            for selector in contact_selectors:
                try:
                    contact_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if contact_btn:
                        logger.info(f"Found contact button: {selector}")
                        break
                except:
                    continue

            if contact_btn:
                await contact_btn.click()
                await asyncio.sleep(3)

            # Look for message input (textarea or text input)
            message_field = None
            message_selectors = [
                'textarea',
                'textarea[name="message"]',
                'textarea[placeholder*="mensaje"]',
                '[class*="message"] textarea',
                '[class*="chat"] textarea',
                'input[name="message"]',
            ]

            for selector in message_selectors:
                try:
                    message_field = await self.page.wait_for_selector(selector, timeout=5000)
                    if message_field:
                        logger.info(f"Found message field: {selector}")
                        break
                except:
                    continue

            if not message_field:
                logger.error("Message field not found")
                try:
                    await self.page.screenshot(path='debug_milanuncios_contact.png')
                except:
                    pass
                return False

            # Clear and fill message with human-like typing
            await message_field.fill('')
            await asyncio.sleep(0.5)

            # Type message character by character for human-like behavior
            for char in message:
                await message_field.type(char, delay=50)
                if char == '.' or char == ',':
                    await asyncio.sleep(0.2)

            logger.info("Message filled")
            await asyncio.sleep(1)

            # Find and click send button
            send_btn = None
            send_selectors = [
                'button:has-text("Enviar")',
                'button[type="submit"]',
                '[class*="send"] button',
                '[class*="Send"] button',
                'button:has-text("Enviar mensaje")',
            ]

            for selector in send_selectors:
                try:
                    send_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if send_btn:
                        logger.info(f"Found send button: {selector}")
                        break
                except:
                    continue

            if not send_btn:
                logger.error("Send button not found")
                return False

            logger.info("Clicking send...")
            await send_btn.click()
            await asyncio.sleep(3)

            # Check for success indicators
            success_indicators = [
                'text="Mensaje enviado"',
                'text="enviado correctamente"',
                '[class*="success"]',
                '[class*="Success"]',
                'text="Tu mensaje ha sido enviado"',
            ]

            for selector in success_indicators:
                try:
                    success = await self.page.wait_for_selector(selector, timeout=5000)
                    if success:
                        logger.info("Message sent successfully!")
                        return True
                except:
                    continue

            # Check for errors
            error = await self.page.query_selector('[class*="error"], [class*="Error"]')
            if error:
                error_text = await error.inner_text()
                logger.error(f"Error sending message: {error_text}")
                return False

            # If no explicit success/error, check if form is gone (usually means success)
            try:
                form_gone = await self.page.wait_for_selector(
                    'textarea', state='hidden', timeout=3000
                )
                logger.info("Message likely sent (form closed)")
                return True
            except:
                pass

            # Assume success if no error
            logger.info("Message likely sent (no error detected)")
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False


async def main():
    """Test the Milanuncios contact automation."""
    import argparse

    parser = argparse.ArgumentParser(description='Milanuncios Contact Automation')
    parser.add_argument('--url', required=True, help='Listing URL to contact')
    parser.add_argument('--message', default='Hola, me interesa este anuncio. ¿Sigue disponible?',
                        help='Message to send')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--login', action='store_true', help='Force login (ignore saved session)')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    contact = MilanunciosContact(headless=args.headless)

    try:
        await contact.setup_browser()

        # Check/perform login
        if args.login or not await contact.is_logged_in():
            success = await contact.login()
            if not success:
                print("Login failed. Set MILANUNCIOS_EMAIL and MILANUNCIOS_PASSWORD env vars.")
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

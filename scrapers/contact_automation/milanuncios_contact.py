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
import logging
import os
import re
from typing import Optional

from .base import BaseContactAutomation, ContactResult

logger = logging.getLogger(__name__)


class MilanunciosContact(BaseContactAutomation):
    """Contact automation for Milanuncios.com"""

    PORTAL_NAME = "milanuncios"

    # URLs
    BASE_URL = "https://www.milanuncios.com"
    LOGIN_URL = "https://www.milanuncios.com/mis/"

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

    def __init__(self, headless: bool = False, email: str = None, password: str = None):
        super().__init__(headless=headless)
        self.email = email or os.getenv('MILANUNCIOS_EMAIL')
        self.password = password or os.getenv('MILANUNCIOS_PASSWORD')

    async def accept_cookies(self):
        """Accept cookies dialog if present."""
        try:
            cookie_selectors = [
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
            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(3)

            # Accept cookies first
            await self.accept_cookies()
            await asyncio.sleep(1)

            content = await self.page.content()

            # Look for logged-in indicators
            logged_in_indicators = [
                'Mi cuenta',
                'Mis anuncios',
                'Cerrar sesión',
                'mis-favoritos',
                'user-menu',
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
        """Login to Milanuncios."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("MILANUNCIOS_EMAIL and MILANUNCIOS_PASSWORD env vars required")
            return False

        try:
            logger.info("Navigating to Milanuncios login page...")
            await self.page.goto(self.LOGIN_URL, wait_until='networkidle')
            await asyncio.sleep(3)

            # Accept cookies
            await self.accept_cookies()
            await asyncio.sleep(1)

            # Check if we're redirected to a login form
            # Milanuncios may use different login URLs
            current_url = self.page.url
            if 'login' not in current_url.lower() and 'acceder' not in current_url.lower():
                # Try to find and click login button
                login_links = [
                    'a:has-text("Acceder")',
                    'a:has-text("Entrar")',
                    'a:has-text("Iniciar sesión")',
                    '[href*="login"]',
                ]
                for selector in login_links:
                    try:
                        link = await self.page.wait_for_selector(selector, timeout=3000)
                        if link:
                            await link.click()
                            await asyncio.sleep(3)
                            break
                    except:
                        continue

            # Fill email
            logger.info("Filling email...")
            email_input = None
            for selector in ['input[type="email"]', 'input[name="email"]', '#email', 'input[placeholder*="mail"]']:
                try:
                    email_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if email_input:
                        break
                except:
                    continue

            if not email_input:
                logger.error("Could not find email input field")
                try:
                    await self.page.screenshot(path='debug_milanuncios_login.png')
                except:
                    pass
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
                logger.error("Could not find password input field")
                return False

            await password_input.fill(password)
            await asyncio.sleep(0.5)

            # Submit
            logger.info("Submitting login...")
            submit_btn = None
            for selector in ['button[type="submit"]', 'button:has-text("Entrar")', 'button:has-text("Acceder")', '[class*="submit"]']:
                try:
                    submit_btn = await self.page.wait_for_selector(selector, timeout=5000)
                    if submit_btn:
                        break
                except:
                    continue

            if submit_btn:
                await submit_btn.click()
            else:
                # Try pressing Enter
                await password_input.press('Enter')

            await asyncio.sleep(5)

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

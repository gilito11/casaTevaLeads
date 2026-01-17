"""
Fotocasa Contact Automation.

Automates:
1. Login with saved session
2. Extract phone via "Ver teléfono" button
3. Send contact message to seller

Usage:
    python -m scrapers.contact_automation.fotocasa_contact --url <listing_url>
"""

import asyncio
import logging
import os
import re
from typing import Optional

from .base import BaseContactAutomation, ContactResult

logger = logging.getLogger(__name__)


class FotocasaContact(BaseContactAutomation):
    """Contact automation for Fotocasa.es"""

    PORTAL_NAME = "fotocasa"

    # URLs
    BASE_URL = "https://www.fotocasa.es"
    LOGIN_URL = "https://www.fotocasa.es/es/usuario/acceso/"

    # Selectors (multiple options for robustness)
    SELECTORS = {
        # Login page
        'login_email': 'input[name="email"], input[type="email"], #email',
        'login_password': 'input[name="password"], input[type="password"], #password',
        'login_submit': 'button[type="submit"], .sui-AtomButton--primary',

        # Logged in indicator
        'user_menu': '.re-UserMenu, .sui-AtomButton--tertiary, [data-testid="user-menu"]',
        'user_avatar': '.re-UserAvatar, [class*="Avatar"]',

        # Phone reveal
        'ver_telefono': 'text="Ver teléfono", button:has-text("Ver teléfono"), [class*="phone"]',
        'phone_number': '[class*="phone-number"], [class*="Phone"], [data-testid="phone"]',

        # Contact form
        'contact_form': 'form[class*="contact"], [class*="ContactForm"]',
        'input_name': 'input[name="name"], input[placeholder*="nombre"]',
        'input_email': 'input[name="email"], input[type="email"]',
        'input_phone': 'input[name="phone"], input[placeholder*="teléfono"]',
        'input_message': 'textarea, [class*="message"], [class*="comment"]',
        'contact_submit': 'button:has-text("Contactar"), button[type="submit"]:has-text("Enviar")',

        # Seller info
        'seller_name': '[class*="particular"], [class*="Advertiser"], [class*="seller"]',
    }

    def __init__(self, headless: bool = False):
        super().__init__(headless=headless)
        self.email = os.getenv('FOTOCASA_EMAIL')
        self.password = os.getenv('FOTOCASA_PASSWORD')

    async def is_logged_in(self) -> bool:
        """Check if session is active."""
        try:
            await self.page.goto(self.BASE_URL, wait_until='networkidle')
            await asyncio.sleep(2)

            # Look for user menu or avatar indicating logged in state
            for selector in ['[class*="UserMenu"]', '[class*="Avatar"]', '[data-testid="user-menu"]']:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element:
                        logger.info("Session is active (found user element)")
                        return True
                except:
                    continue

            # Check if login link is visible (means NOT logged in)
            login_link = await self.page.query_selector('a[href*="acceso"], text="Acceder"')
            if login_link:
                logger.info("Not logged in (login link visible)")
                return False

            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    async def login(self, email: str = None, password: str = None) -> bool:
        """Login to Fotocasa."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("FOTOCASA_EMAIL and FOTOCASA_PASSWORD env vars required")
            return False

        try:
            logger.info("Navigating to login page...")
            await self.page.goto(self.LOGIN_URL, wait_until='networkidle')
            await asyncio.sleep(2)

            # Accept cookies if dialog appears
            try:
                accept_btn = await self.page.wait_for_selector(
                    'button:has-text("Aceptar"), [id*="accept"]', timeout=3000
                )
                if accept_btn:
                    await accept_btn.click()
                    await asyncio.sleep(1)
            except:
                pass

            # Fill email
            logger.info("Filling email...")
            email_input = await self.page.wait_for_selector(self.SELECTORS['login_email'])
            await email_input.fill(email)
            await asyncio.sleep(0.5)

            # Fill password
            logger.info("Filling password...")
            password_input = await self.page.wait_for_selector(self.SELECTORS['login_password'])
            await password_input.fill(password)
            await asyncio.sleep(0.5)

            # Submit
            logger.info("Submitting login...")
            submit_btn = await self.page.wait_for_selector(self.SELECTORS['login_submit'])
            await submit_btn.click()

            # Wait for redirect/login completion
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
        """Click 'Ver teléfono' and extract phone number."""
        try:
            # Make sure we're on the listing page
            if self.page.url != listing_url:
                await self.page.goto(listing_url, wait_until='networkidle')
                await asyncio.sleep(2)

            # Try to find and click "Ver teléfono" button
            phone_btn = None
            for selector in ['text="Ver teléfono"', 'button:has-text("teléfono")', '[class*="phone"] button']:
                try:
                    phone_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if phone_btn:
                        break
                except:
                    continue

            if phone_btn:
                logger.info("Found 'Ver teléfono' button, clicking...")
                await phone_btn.click()
                await asyncio.sleep(2)

                # Try to extract the revealed phone number
                page_content = await self.page.content()

                # Spanish phone patterns
                phone_patterns = [
                    r'(\+34\s?)?[6789]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}',
                    r'[6789]\d{8}',
                ]

                for pattern in phone_patterns:
                    matches = re.findall(pattern, page_content)
                    if matches:
                        # Clean and return first valid phone
                        phone = re.sub(r'[\s.-]', '', matches[0])
                        if len(phone) >= 9:
                            return phone[-9:]  # Last 9 digits (remove +34)

                logger.warning("Phone button clicked but number not found in page")
                return None
            else:
                logger.info("'Ver teléfono' button not found - may need login or already visible")

                # Try to find phone directly in page (some listings show it)
                page_text = await self.page.inner_text('body')
                for pattern in [r'[6789]\d{8}', r'[6789]\d{2}\s?\d{3}\s?\d{3}']:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        phone = re.sub(r'\s', '', matches[0])
                        return phone

                return None

        except Exception as e:
            logger.error(f"Error extracting phone: {e}")
            return None

    async def send_message(self, listing_url: str, message: str) -> bool:
        """Send contact message to seller."""
        try:
            # Make sure we're on the listing page
            if self.page.url != listing_url:
                await self.page.goto(listing_url, wait_until='networkidle')
                await asyncio.sleep(2)

            # Scroll to contact form (usually in sidebar)
            await self.page.evaluate('window.scrollTo(0, 500)')
            await asyncio.sleep(1)

            # Look for contact form or contact button
            contact_form = None
            for selector in ['form[class*="contact"]', '[class*="ContactForm"]', '[class*="contactar"]']:
                try:
                    contact_form = await self.page.wait_for_selector(selector, timeout=3000)
                    if contact_form:
                        break
                except:
                    continue

            if not contact_form:
                # Try clicking a "Contactar" button that opens the form
                try:
                    contact_btn = await self.page.wait_for_selector(
                        'button:has-text("Contactar"), a:has-text("Contactar")', timeout=3000
                    )
                    if contact_btn:
                        await contact_btn.click()
                        await asyncio.sleep(2)
                except:
                    pass

            # Fill message field
            message_field = None
            for selector in ['textarea', 'textarea[name*="message"]', '[class*="comment"] textarea']:
                try:
                    message_field = await self.page.wait_for_selector(selector, timeout=3000)
                    if message_field:
                        break
                except:
                    continue

            if message_field:
                await message_field.fill('')  # Clear first
                await self.human_type('textarea', message)
                logger.info("Message filled")
            else:
                logger.warning("Message field not found")

            # Fill phone if empty (our phone)
            try:
                phone_input = await self.page.query_selector('input[name="phone"], input[placeholder*="teléfono"]')
                if phone_input:
                    value = await phone_input.input_value()
                    if not value:
                        our_phone = os.getenv('CONTACT_PHONE', '')
                        if our_phone:
                            await phone_input.fill(our_phone)
            except:
                pass

            # Submit form
            submit_btn = None
            for selector in ['button:has-text("Contactar")', 'button[type="submit"]', '.sui-AtomButton--primary']:
                try:
                    submit_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if submit_btn:
                        break
                except:
                    continue

            if submit_btn:
                logger.info("Clicking submit...")
                await submit_btn.click()
                await asyncio.sleep(3)

                # Check for success message
                try:
                    success = await self.page.wait_for_selector(
                        'text="enviado", text="Mensaje enviado", [class*="success"]',
                        timeout=5000
                    )
                    if success:
                        logger.info("Message sent successfully!")
                        return True
                except:
                    pass

                # If no explicit success, assume it worked if no error
                error = await self.page.query_selector('[class*="error"], [class*="Error"]')
                if not error:
                    logger.info("Message likely sent (no error detected)")
                    return True
                else:
                    logger.error("Error detected after submit")
                    return False
            else:
                logger.error("Submit button not found")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def get_seller_name(self) -> Optional[str]:
        """Extract seller name from listing page."""
        try:
            for selector in ['[class*="particular"]', '[class*="Advertiser"]', '[class*="seller-name"]']:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=2000)
                    if element:
                        text = await element.inner_text()
                        # Clean up "Particular: Name" format
                        if ':' in text:
                            return text.split(':')[-1].strip()
                        return text.strip()
                except:
                    continue
            return None
        except:
            return None


async def main():
    """Test the Fotocasa contact automation."""
    import argparse

    parser = argparse.ArgumentParser(description='Fotocasa Contact Automation')
    parser.add_argument('--url', required=True, help='Listing URL to contact')
    parser.add_argument('--message', default='Hola, me interesa este inmueble. ¿Podríamos hablar?',
                        help='Message to send')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--login', action='store_true', help='Force login (ignore saved session)')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    contact = FotocasaContact(headless=args.headless)

    try:
        await contact.setup_browser()

        # Check/perform login
        if args.login or not await contact.is_logged_in():
            success = await contact.login()
            if not success:
                print("Login failed. Set FOTOCASA_EMAIL and FOTOCASA_PASSWORD env vars.")
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

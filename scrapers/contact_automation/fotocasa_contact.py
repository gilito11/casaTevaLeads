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

    def __init__(self, headless: bool = False, email: str = None, password: str = None):
        super().__init__(headless=headless)
        self.email = email or os.getenv('FOTOCASA_EMAIL')
        self.password = password or os.getenv('FOTOCASA_PASSWORD')

    async def accept_cookies(self):
        """Accept cookies dialog if present."""
        try:
            # Common cookie accept button selectors for Fotocasa
            cookie_selectors = [
                'button:has-text("Aceptar")',
                'button:has-text("Aceptar todo")',
                'button:has-text("Aceptar y cerrar")',
                '#didomi-notice-agree-button',
                '[id*="accept"]',
                '.didomi-continue-without-agreeing',
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
        """Check if session is active by looking for user name in header."""
        try:
            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(3)

            # Accept cookies first
            await self.accept_cookies()
            await asyncio.sleep(1)

            # Get page content
            content = await self.page.content()

            # If we see a username/name in the header, we're logged in
            # Look for patterns like user menus or profile indicators
            if 'Eric' in content or 'Mi cuenta' in content or 'Mis alertas' in content:
                logger.info("Session is active (found user indicators)")
                return True

            # Check if "Acceder" link is visible (means NOT logged in)
            if 'Acceder</a>' in content or '>Acceder<' in content:
                logger.info("Not logged in (Acceder link visible)")
                return False

            # If cookies exist, assume logged in
            if self.cookies_file.exists():
                logger.info("Cookies exist, assuming logged in")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            # If cookies exist, try anyway
            if self.cookies_file.exists():
                logger.info("Error but cookies exist, assuming logged in")
                return True
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
            await asyncio.sleep(3)

            # Accept cookies dialog
            await self.accept_cookies()
            await asyncio.sleep(1)

            # Fill email - try multiple selectors
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
                # Take screenshot for debugging
                try:
                    await self.page.screenshot(path='debug_login_page.png')
                    logger.info("Screenshot saved to debug_login_page.png")
                except:
                    pass
                # Print page content for debugging
                content = await self.page.content()
                if 'SENTIMOS LA' in content:
                    logger.error("Fotocasa is blocking - anti-bot detected")
                elif 'email' in content.lower():
                    logger.error("Email field exists in HTML but selector not matching")
                return False

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
                await asyncio.sleep(3)

                # Try to find phone in specific elements first
                phone_selectors = [
                    'a[href^="tel:"]',
                    '[class*="phone"] a',
                    '[class*="Phone"] a',
                    '[data-testid*="phone"]',
                ]

                for sel in phone_selectors:
                    try:
                        phone_el = await self.page.query_selector(sel)
                        if phone_el:
                            href = await phone_el.get_attribute('href')
                            if href and 'tel:' in href:
                                phone = href.replace('tel:', '').replace('+34', '').replace(' ', '')
                                if len(phone) == 9 and phone[0] in '6789':
                                    logger.info(f"Phone found via tel: link: {phone}")
                                    return phone
                            text = await phone_el.inner_text()
                            if text:
                                phone = re.sub(r'[^\d]', '', text)
                                if len(phone) >= 9:
                                    phone = phone[-9:]
                                    if phone[0] in '6789':
                                        logger.info(f"Phone found in element text: {phone}")
                                        return phone
                    except:
                        continue

                # Fallback: search page content with strict pattern
                page_content = await self.page.content()

                # Look for tel: links first (most reliable)
                tel_matches = re.findall(r'tel:(\+?34)?(\d{9})', page_content)
                if tel_matches:
                    phone = tel_matches[0][1]
                    if phone[0] in '6789':
                        logger.info(f"Phone found via tel: pattern: {phone}")
                        return phone

                # Spanish mobile pattern (6xx, 7xx) - most common for particulares
                mobile_pattern = r'(?<!\d)([67]\d{2}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)'
                matches = re.findall(mobile_pattern, page_content)
                if matches:
                    phone = re.sub(r'[\s.-]', '', matches[0])
                    logger.info(f"Phone found via mobile pattern: {phone}")
                    return phone

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

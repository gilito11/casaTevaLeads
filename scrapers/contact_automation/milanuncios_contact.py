"""
Milanuncios Contact Automation.

Automates:
1. Login with email/password
2. Extract phone from listing (if visible)
3. Send contact message via internal chat system

Uses Camoufox anti-detect browser to bypass GeeTest/bot detection.

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

        # Create context with explicit viewport (Camoufox virtual display may be wider)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
        )

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

    async def _find_login_page(self) -> 'Page':
        """Find the page containing the login form (could be popup, redirect, or current page)."""
        # Check all open pages for login-related URLs or forms
        for page in self.context.pages:
            url = page.url.lower()
            if any(x in url for x in ['login', 'schibsted', 'authn', 'auth', 'acceso', 'registro']):
                logger.info(f"Found login page: {page.url[:80]}")
                return page
            # Check if page has email input (not search)
            try:
                has_login = await page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input[type="email"], input[name="email"], input[autocomplete="email"]');
                    return inputs.length > 0;
                }""")
                if has_login:
                    logger.info(f"Found page with email input: {page.url[:80]}")
                    return page
            except:
                continue
        return self.page

    async def login(self, email: str = None, password: str = None) -> bool:
        """Login to Milanuncios via Schibsted OAuth (popup or redirect flow)."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            logger.error("MILANUNCIOS_EMAIL and MILANUNCIOS_PASSWORD env vars required")
            return False

        try:
            # Go directly to /registro (proven working method)
            logger.info("Navigating to /registro...")
            target_page = self.page
            has_email_input = False

            login_urls = [
                "https://www.milanuncios.com/registro",
                "https://login.schibsted.com/authn/identifier",
            ]
            for url in login_urls:
                try:
                    logger.info(f"Trying {url}...")
                    await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await self.accept_cookies()
                    # Wait for SPA JS to render the form
                    for wait in [3, 5, 5]:
                        has_email_input = await self.page.evaluate("""() => {
                            const inputs = document.querySelectorAll('input[type="email"], input[name="email"], input[type="text"], input[type="password"]');
                            return inputs.length > 0;
                        }""")
                        if has_email_input:
                            break
                        logger.info(f"No inputs yet, waiting {wait}s for SPA to render...")
                        await asyncio.sleep(wait)
                    if has_email_input:
                        target_page = self.page
                        logger.info(f"Found login form at {self.page.url}")
                        break
                    else:
                        body_len = await self.page.evaluate("() => document.body.innerHTML.length")
                        logger.info(f"No form at {self.page.url[:60]} (body: {body_len} bytes)")
                except Exception as e:
                    logger.info(f"Failed loading {url}: {e}")
                    continue

            if not has_email_input:
                # Debug: dump page info
                page_info = await target_page.evaluate("""() => ({
                    url: location.href,
                    title: document.title,
                    inputs: Array.from(document.querySelectorAll('input')).map(i => ({
                        type: i.type, name: i.name, id: i.id,
                        placeholder: i.placeholder,
                    })),
                    bodyLen: document.body.innerHTML.length,
                    pages: 'N/A',
                })""")
                logger.error(f"No login form found after all methods. Page info: {json.dumps(page_info, indent=2)}")
                return False

            # --- FILL LOGIN FORM ---
            logger.info(f"Login form found on: {target_page.url[:80]}")

            # If on /registro, click "Iniciar sesión" to switch to login mode
            if '/registro' in target_page.url:
                logger.info("On registration page, clicking 'Iniciar sesión' to switch to login...")
                await target_page.evaluate("""() => {
                    const els = document.querySelectorAll('a, button');
                    for (const el of els) {
                        const text = (el.textContent || '').trim().toLowerCase();
                        if (text.includes('iniciar sesi') || text.includes('inicia sesi')) {
                            el.click();
                            return;
                        }
                    }
                }""")
                await asyncio.sleep(3)

                # Check if a modal appeared (ModalAuthenticationOnboarding)
                modal_info = await target_page.evaluate("""() => {
                    const modal = document.querySelector('#modal-react-portal .sui-MoleculeModal');
                    if (!modal) return null;
                    const inputs = modal.querySelectorAll('input');
                    const buttons = Array.from(modal.querySelectorAll('button, a')).map(b => ({
                        text: b.textContent.trim().substring(0, 50),
                        tag: b.tagName,
                        class: (b.className || '').substring(0, 60),
                    }));
                    return {
                        hasModal: true,
                        inputCount: inputs.length,
                        buttons: buttons,
                        text: modal.textContent.substring(0, 200),
                    };
                }""")

                if modal_info:
                    logger.info(f"Auth modal detected: {json.dumps(modal_info)}")

                    # Look for "Continuar con email" or "Email" button in modal
                    email_btn_clicked = await target_page.evaluate("""() => {
                        const modal = document.querySelector('#modal-react-portal .sui-MoleculeModal');
                        if (!modal) return false;
                        const buttons = modal.querySelectorAll('button, a');
                        for (const btn of buttons) {
                            const text = (btn.textContent || '').trim().toLowerCase();
                            if (text.includes('email') || text.includes('correo')
                                || text.includes('continuar con e')) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                    if email_btn_clicked:
                        logger.info("Clicked 'email' button in modal")
                        await asyncio.sleep(3)

                    # Check if modal has an email input now
                    modal_email = await target_page.evaluate("""() => {
                        const modal = document.querySelector('#modal-react-portal');
                        if (!modal) return null;
                        const input = modal.querySelector('input[type="email"], input#email, input[type="text"]');
                        return input ? { type: input.type, id: input.id } : null;
                    }""")
                    if modal_email:
                        logger.info(f"Found email input inside modal: {modal_email}")

            await self.accept_cookies()

            # Step 1: Email - look for input in modal first, then in page
            logger.info("Step 1: Filling email...")
            email_input = None

            # Priority 1: input inside modal portal
            email_input_h = await target_page.evaluate_handle("""() => {
                const modal = document.querySelector('#modal-react-portal');
                if (modal) {
                    const inp = modal.querySelector('input[type="email"], input#email, input[type="text"]');
                    if (inp) return inp;
                }
                return null;
            }""")
            if email_input_h:
                email_input = email_input_h.as_element()
                if email_input:
                    logger.info("Using email input from modal")

            # Priority 2: page-level email input (for direct login pages)
            if not email_input:
                for selector in ['input[type="email"]', 'input[name="email"]', 'input#email']:
                    try:
                        email_input = await target_page.wait_for_selector(selector, timeout=5000)
                        if email_input:
                            logger.info(f"Found email input: {selector}")
                            break
                    except:
                        continue

            if not email_input:
                # Debug dump
                all_inputs = await target_page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('input')).map(i => ({
                        type: i.type, id: i.id, name: i.name,
                        inModal: !!i.closest('#modal-react-portal'),
                        visible: i.offsetParent !== null,
                    }))
                }""")
                logger.error(f"No email input found. All inputs: {json.dumps(all_inputs)}")
                return False

            # Use click + type (NOT fill) to trigger React state updates
            await email_input.click()
            await asyncio.sleep(0.3)
            await email_input.press('Control+a')
            await target_page.keyboard.type(email, delay=50)
            logger.info("Email typed (keyboard)")
            await asyncio.sleep(1)

            # Click "Continuar" / submit - prefer buttons inside modal
            continue_clicked = await target_page.evaluate("""() => {
                // Try modal buttons first
                const modal = document.querySelector('#modal-react-portal');
                const containers = modal ? [modal, document] : [document];
                for (const container of containers) {
                    const buttons = container.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = (btn.textContent || '').trim().toLowerCase();
                        if (text === 'continuar' || text === 'siguiente' || text === 'continue') {
                            btn.click();
                            return true;
                        }
                    }
                    // Try submit buttons
                    const submit = container.querySelector('button[type="submit"]');
                    if (submit) { submit.click(); return true; }
                }
                return false;
            }""")

            if continue_clicked:
                logger.info("Clicked Continuar via JS")
            else:
                await email_input.press('Enter')
                logger.info("Pressed Enter on email input")

            await asyncio.sleep(3)
            logger.info(f"After email submit URL: {target_page.url}")

            # Step 2: Password (may appear in modal, same page, or new page)
            logger.info("Step 2: Filling password...")
            password_input = None

            # Check modal first, then page-level
            password_input_h = await target_page.evaluate_handle("""() => {
                // Check inside modal first
                const modal = document.querySelector('#modal-react-portal');
                if (modal) {
                    const inp = modal.querySelector('input[type="password"]');
                    if (inp) return inp;
                }
                // Then check page
                return document.querySelector('input[type="password"]');
            }""")
            if password_input_h:
                password_input = password_input_h.as_element()
                if password_input:
                    logger.info("Found password input")

            if not password_input:
                # Wait for it to appear (might need time after email submit)
                for selector in ['input[type="password"]', 'input#password']:
                    try:
                        password_input = await target_page.wait_for_selector(selector, timeout=10000)
                        if password_input:
                            break
                    except:
                        continue

            # Check other pages (popup scenario)
            if not password_input:
                for p in self.context.pages:
                    if p == target_page:
                        continue
                    try:
                        password_input = await p.wait_for_selector('input[type="password"]', timeout=5000)
                        if password_input:
                            target_page = p
                            logger.info(f"Found password on other page: {p.url[:60]}")
                            break
                    except:
                        continue

            if not password_input:
                # Debug: check what's on the page now
                page_state = await target_page.evaluate("""() => ({
                    url: location.href,
                    inputs: Array.from(document.querySelectorAll('input')).map(i => ({
                        type: i.type, id: i.id, inModal: !!i.closest('#modal-react-portal'),
                    })),
                    modalPresent: !!document.querySelector('#modal-react-portal .sui-MoleculeModal'),
                })""")
                logger.error(f"Password input not found. State: {json.dumps(page_state)}")
                return False

            # Use click + type (NOT fill) to trigger React state updates
            await password_input.click()
            await asyncio.sleep(0.3)
            await password_input.press('Control+a')
            await target_page.keyboard.type(password, delay=50)
            await asyncio.sleep(1)

            # Verify fields have values before submitting
            field_values = await target_page.evaluate("""() => {
                const modal = document.querySelector('#modal-react-portal');
                const container = modal || document;
                const emailEl = container.querySelector('input[type="email"], input#email, input[type="text"]');
                const passEl = container.querySelector('input[type="password"]');
                return {
                    email: emailEl ? emailEl.value : null,
                    emailLen: emailEl ? emailEl.value.length : 0,
                    passLen: passEl ? passEl.value.length : 0,
                };
            }""")
            logger.info(f"Pre-submit field check - email: {field_values.get('email', '?')}, "
                        f"emailLen: {field_values.get('emailLen')}, passLen: {field_values.get('passLen')}")

            # Submit login via Enter on password field (most reliable for modal forms)
            logger.info("Submitting login via Enter key on password field...")
            await password_input.press('Enter')
            await asyncio.sleep(5)

            # Check for errors in modal (wrong password, etc.)
            error_info = await target_page.evaluate("""() => {
                const modal = document.querySelector('#modal-react-portal');
                if (!modal) return null;
                // Look for error messages
                const errorEls = modal.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"]');
                const errors = Array.from(errorEls).map(e => e.textContent.trim()).filter(t => t.length > 0);
                // Check if modal is still open (login didn't succeed)
                const stillOpen = !!modal.querySelector('.sui-MoleculeModal.is-MoleculeModal-open');
                // Check all buttons still visible
                const buttons = Array.from(modal.querySelectorAll('button')).map(b => b.textContent.trim()).filter(t => t.length > 0);
                return { errors, stillOpen, buttons };
            }""")
            logger.info(f"After submit - modal state: {json.dumps(error_info)}")

            # If modal still open and no errors, try clicking submit button inside modal
            if error_info and error_info.get('stillOpen') and not error_info.get('errors'):
                logger.info("Modal still open after Enter, trying button click...")
                submit_clicked = await target_page.evaluate("""() => {
                    const modal = document.querySelector('#modal-react-portal .sui-MoleculeModal');
                    if (!modal) return null;
                    // Find submit-like button inside modal (not the X close button)
                    const buttons = modal.querySelectorAll('button:not(.sui-MoleculeModal-close)');
                    for (const btn of buttons) {
                        const text = (btn.textContent || '').trim().toLowerCase();
                        // Look specifically for login submit buttons
                        if (text === 'iniciar sesión' || text === 'entrar'
                            || text === 'acceder' || text === 'log in' || text === 'submit') {
                            btn.click();
                            return text;
                        }
                    }
                    // Try type=submit inside modal
                    const submitBtn = modal.querySelector('button[type="submit"]');
                    if (submitBtn) { submitBtn.click(); return 'submit-type'; }
                    // Try the primary action button (last non-link button)
                    const primaryBtns = modal.querySelectorAll('.sui-AtomButton--primary:not(.sui-AtomButton--link)');
                    if (primaryBtns.length > 0) {
                        const last = primaryBtns[primaryBtns.length - 1];
                        last.click();
                        return 'primary: ' + last.textContent.trim();
                    }
                    return null;
                }""")
                if submit_clicked:
                    logger.info(f"Clicked modal submit button: '{submit_clicked}'")
                    await asyncio.sleep(5)

            # Wait for redirect / session to establish
            await asyncio.sleep(5)

            current_url = self.page.url
            logger.info(f"After login submit URL: {current_url}")

            # If URL changed from /registro, login might have worked
            for p in self.context.pages:
                logger.info(f"Open page: {p.url[:80]}")

            # Check for login errors
            final_error = await target_page.evaluate("""() => {
                const modal = document.querySelector('#modal-react-portal');
                if (!modal) return null;
                const errorEls = modal.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"], [class*="warning"]');
                return Array.from(errorEls).map(e => e.textContent.trim()).filter(t => t.length > 0);
            }""")
            if final_error:
                logger.error(f"Login errors detected: {final_error}")

            # If modal closed without errors, login succeeded (Schibsted behavior)
            if error_info and not error_info.get('stillOpen') and not error_info.get('errors'):
                logger.info("Login successful! (modal closed without errors)")
                await self.save_cookies()
                return True

            # Fallback: verify via homepage check
            if await self.is_logged_in():
                logger.info("Login successful! (verified via homepage)")
                await self.save_cookies()
                return True
            else:
                logger.error("Login failed - not logged in after submit")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            import traceback
            logger.error(traceback.format_exc())
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

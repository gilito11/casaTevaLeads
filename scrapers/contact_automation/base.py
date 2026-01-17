"""
Base class for contact automation across real estate portals.

Conservative approach: max 5 contacts/day with long delays to avoid detection.
"""

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ContactResult:
    """Result of a contact attempt."""

    def __init__(
        self,
        success: bool,
        lead_id: str,
        portal: str,
        phone_extracted: Optional[str] = None,
        message_sent: bool = False,
        error: Optional[str] = None
    ):
        self.success = success
        self.lead_id = lead_id
        self.portal = portal
        self.phone_extracted = phone_extracted
        self.message_sent = message_sent
        self.error = error
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'success': self.success,
            'lead_id': self.lead_id,
            'portal': self.portal,
            'phone_extracted': self.phone_extracted,
            'message_sent': self.message_sent,
            'error': self.error,
            'timestamp': self.timestamp.isoformat()
        }


class BaseContactAutomation(ABC):
    """
    Base class for portal contact automation.

    Features:
    - Session persistence via cookies
    - Human-like delays (2-5 min between contacts)
    - Max 5 contacts per day (configurable)
    - Stealth mode with playwright-stealth
    """

    PORTAL_NAME: str = "base"
    COOKIES_DIR = Path(__file__).parent / "cookies"

    # Conservative limits
    MAX_CONTACTS_PER_DAY = 5
    MIN_DELAY_SECONDS = 120  # 2 minutes
    MAX_DELAY_SECONDS = 300  # 5 minutes

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.contacts_today = 0

        # Ensure cookies directory exists
        self.COOKIES_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def cookies_file(self) -> Path:
        return self.COOKIES_DIR / f"{self.PORTAL_NAME}_cookies.json"

    async def setup_browser(self):
        """Initialize Playwright with stealth settings."""
        from playwright.async_api import async_playwright

        # Temporarily disable stealth - causing browser close issues
        self.has_stealth = False
        self.stealth = None
        # try:
        #     from playwright_stealth import Stealth
        #     self.stealth = Stealth(navigator_webdriver=True)
        #     self.has_stealth = True
        # except ImportError:
        #     logger.warning("playwright-stealth not installed, running without stealth")
        #     self.stealth = None

        self.playwright = await async_playwright().start()

        # Use Chromium - better compatibility with most sites
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=50,  # Slow down actions to appear human
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context with saved cookies if available
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'locale': 'es-ES',
            'timezone_id': 'Europe/Madrid',
        }

        self.context = await self.browser.new_context(**context_options)

        # Apply stealth to context if available
        if self.has_stealth and self.stealth:
            await self.stealth.apply_stealth_async(self.context)
            logger.info("Stealth mode applied to context")

        # Load saved cookies
        if self.cookies_file.exists():
            cookies = json.loads(self.cookies_file.read_text())
            await self.context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} cookies from {self.cookies_file}")

        self.page = await self.context.new_page()

    async def save_cookies(self):
        """Save session cookies for future use."""
        cookies = await self.context.cookies()
        self.cookies_file.write_text(json.dumps(cookies, indent=2))
        logger.info(f"Saved {len(cookies)} cookies to {self.cookies_file}")

    async def close(self):
        """Clean up browser resources."""
        if self.context:
            await self.save_cookies()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def human_delay(self, min_sec: float = None, max_sec: float = None):
        """Wait a random human-like delay."""
        min_sec = min_sec or self.MIN_DELAY_SECONDS
        max_sec = max_sec or self.MAX_DELAY_SECONDS
        delay = random.uniform(min_sec, max_sec)
        logger.info(f"Waiting {delay:.1f}s before next action...")
        await asyncio.sleep(delay)

    async def human_type(self, selector: str, text: str):
        """Type text with human-like delays between keystrokes."""
        element = await self.page.wait_for_selector(selector)
        await element.click()
        for char in text:
            await self.page.keyboard.type(char, delay=random.randint(50, 150))
            # Occasional pause mid-typing
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    @abstractmethod
    async def is_logged_in(self) -> bool:
        """Check if we have a valid logged-in session."""
        pass

    @abstractmethod
    async def login(self, email: str, password: str) -> bool:
        """Perform login if needed."""
        pass

    @abstractmethod
    async def extract_phone(self, listing_url: str) -> Optional[str]:
        """Click 'Ver teléfono' and extract the phone number."""
        pass

    @abstractmethod
    async def send_message(self, listing_url: str, message: str) -> bool:
        """Send a contact message to the seller."""
        pass

    async def contact_lead(
        self,
        lead_id: str,
        listing_url: str,
        message: str,
        extract_phone: bool = True
    ) -> ContactResult:
        """
        Contact a single lead.

        Args:
            lead_id: Internal lead ID
            listing_url: URL of the property listing
            message: Message to send to seller
            extract_phone: Whether to try extracting phone number

        Returns:
            ContactResult with details of the operation
        """
        if self.contacts_today >= self.MAX_CONTACTS_PER_DAY:
            return ContactResult(
                success=False,
                lead_id=lead_id,
                portal=self.PORTAL_NAME,
                error=f"Daily limit reached ({self.MAX_CONTACTS_PER_DAY})"
            )

        phone = None
        message_sent = False
        error = None

        try:
            logger.info(f"Contacting lead {lead_id} at {listing_url}")

            # Navigate to listing
            await self.page.goto(listing_url, wait_until='networkidle')
            await asyncio.sleep(random.uniform(2, 4))  # Human pause

            # Extract phone if requested
            if extract_phone:
                phone = await self.extract_phone(listing_url)
                if phone:
                    logger.info(f"Extracted phone: {phone}")

            # Send message
            message_sent = await self.send_message(listing_url, message)

            if message_sent:
                self.contacts_today += 1
                logger.info(f"Message sent successfully ({self.contacts_today}/{self.MAX_CONTACTS_PER_DAY} today)")

        except Exception as e:
            error = str(e)
            logger.error(f"Error contacting lead {lead_id}: {e}")

        return ContactResult(
            success=message_sent or phone is not None,
            lead_id=lead_id,
            portal=self.PORTAL_NAME,
            phone_extracted=phone,
            message_sent=message_sent,
            error=error
        )

    async def contact_batch(
        self,
        leads: list[dict],
        message_template: str,
        max_contacts: int = None
    ) -> list[ContactResult]:
        """
        Contact multiple leads with delays between each.

        Args:
            leads: List of dicts with 'lead_id' and 'listing_url'
            message_template: Message to send (can use {titulo} placeholder)
            max_contacts: Override daily limit for this batch

        Returns:
            List of ContactResults
        """
        max_contacts = max_contacts or self.MAX_CONTACTS_PER_DAY
        results = []

        for i, lead in enumerate(leads[:max_contacts]):
            if self.contacts_today >= self.MAX_CONTACTS_PER_DAY:
                logger.warning("Daily limit reached, stopping batch")
                break

            # Personalize message if template has placeholders
            message = message_template
            if '{titulo}' in message_template and 'titulo' in lead:
                message = message_template.format(titulo=lead['titulo'])

            result = await self.contact_lead(
                lead_id=lead['lead_id'],
                listing_url=lead['listing_url'],
                message=message
            )
            results.append(result)

            # Human delay between contacts (skip after last)
            if i < len(leads) - 1 and result.success:
                await self.human_delay()

        return results

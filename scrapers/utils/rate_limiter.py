"""
Rate limiter for scrapers.

Ensures minimum delay between page navigations to avoid anti-bot detection.
Configurable via environment variables:

    SCRAPER_MIN_DELAY=1.0    # Min seconds between requests (default: 1.0)
    SCRAPER_MAX_DELAY=3.0    # Max seconds between requests (default: 3.0)
"""

import os
import random
import time
import threading


class RateLimiter:
    """Thread-safe rate limiter that enforces minimum delay between calls."""

    def __init__(self, min_delay: float = None, max_delay: float = None):
        self.min_delay = min_delay or float(os.environ.get('SCRAPER_MIN_DELAY', '1.0'))
        self.max_delay = max_delay or float(os.environ.get('SCRAPER_MAX_DELAY', '3.0'))
        self._last_request = 0.0
        self._lock = threading.Lock()

    def wait(self, min_delay: float = None, max_delay: float = None):
        """Wait for a random delay between min and max, ensuring min gap since last call."""
        min_d = min_delay if min_delay is not None else self.min_delay
        max_d = max_delay if max_delay is not None else self.max_delay

        with self._lock:
            now = time.time()
            elapsed = now - self._last_request
            min_gap = min_d

            if elapsed < min_gap:
                time.sleep(min_gap - elapsed)

            delay = random.uniform(min_d, max_d)
            time.sleep(delay)
            self._last_request = time.time()

    def get_delay_config(self) -> dict:
        """Return current delay configuration."""
        return {
            'min_delay': self.min_delay,
            'max_delay': self.max_delay,
        }


# Global instance for shared use
_default_limiter = None


def get_rate_limiter(**kwargs) -> RateLimiter:
    """Get or create the default rate limiter."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(**kwargs)
    return _default_limiter

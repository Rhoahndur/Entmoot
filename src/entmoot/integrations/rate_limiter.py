"""
Shared rate limiter for API integrations.

Implements a token bucket algorithm suitable for controlling
the rate of outbound HTTP requests to external services.
"""

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, calls: int, period: float) -> None:
        """
        Initialize rate limiter.

        Args:
            calls: Maximum number of calls per period
            period: Time period in seconds
        """
        self.calls = calls
        self.period = period
        self.tokens = float(calls)
        self.last_update = time.time()

    def acquire(self) -> bool:
        """
        Acquire a token for making an API call.

        Returns:
            True if token acquired, False if rate limited
        """
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens based on elapsed time
        self.tokens = min(self.calls, self.tokens + elapsed * (self.calls / self.period))
        self.last_update = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True

        return False

    def wait_time(self) -> float:
        """
        Calculate wait time until next token is available.

        Returns:
            Wait time in seconds
        """
        if self.tokens >= 1:
            return 0.0

        tokens_needed = 1 - self.tokens
        return tokens_needed * (self.period / self.calls)

    async def wait_if_needed(self) -> None:
        """Block until a token is available (async-friendly)."""
        while not self.acquire():
            await asyncio.sleep(self.wait_time())

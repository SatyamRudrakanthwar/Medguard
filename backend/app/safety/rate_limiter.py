"""
In-memory rate limiter — 10 reviews per IP per hour.
Uses a sliding window counter keyed by IP address.
Replaced by Redis-backed limiter when Redis is available.
"""
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _Window:
    timestamps: list[float] = field(default_factory=list)


class InMemoryRateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 3600):
        self._max = max_requests
        self._window = window_seconds
        self._store: dict[str, _Window] = defaultdict(_Window)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Returns (allowed, remaining_requests).
        Prunes expired timestamps on every check.
        """
        now = time.time()
        cutoff = now - self._window
        window = self._store[key]

        # Prune old timestamps
        window.timestamps = [t for t in window.timestamps if t > cutoff]

        if len(window.timestamps) >= self._max:
            remaining = 0
            logger.warning("Rate limit exceeded for key: %s", key[:20])
            return False, remaining

        window.timestamps.append(now)
        remaining = self._max - len(window.timestamps)
        return True, remaining

    def reset(self, key: str) -> None:
        """Reset the counter for a key (useful in tests)."""
        self._store.pop(key, None)


# Singleton — imported by the FastAPI middleware
rate_limiter = InMemoryRateLimiter()

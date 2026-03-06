"""In-memory cache for OSM Overpass API responses."""

import hashlib
import logging
import time
from typing import Dict, Optional, Tuple

from entmoot.models.existing_conditions import ExistingConditionsData

logger = logging.getLogger(__name__)


class OSMCache:
    """Simple in-memory cache with TTL for OSM query results."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        """Initialize cache with configurable TTL."""
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[ExistingConditionsData, float]] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
        """Generate a cache key from bbox coordinates."""
        raw = f"{min_lon:.8f},{min_lat:.8f},{max_lon:.8f},{max_lat:.8f}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[ExistingConditionsData]:
        """Return cached data if present and not expired."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            age = time.monotonic() - timestamp
            if age < self.ttl_seconds:
                self._hits += 1
                logger.debug(f"OSM cache hit for key {key[:8]}... (age: {age:.0f}s)")
                return data
            else:
                logger.debug(f"OSM cache expired for key {key[:8]}... (age: {age:.0f}s)")
                del self._cache[key]

        self._misses += 1
        return None

    def put(self, key: str, data: ExistingConditionsData) -> None:
        """Store data in cache."""
        self._cache[key] = (data, time.monotonic())
        logger.debug(f"OSM cache stored key {key[:8]}...")

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(self._hits / total * 100, 2) if total else 0,
            "ttl_seconds": self.ttl_seconds,
        }

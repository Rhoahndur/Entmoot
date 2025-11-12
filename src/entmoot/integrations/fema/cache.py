"""
Caching layer for FEMA API responses.

Supports both Redis (if available) and in-memory caching with automatic fallback.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from entmoot.models.regulatory import FloodplainData

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Tuple[FloodplainData, float]]:
        """
        Get data from cache.

        Args:
            key: Cache key

        Returns:
            Tuple of (FloodplainData, timestamp) or None
        """
        pass

    @abstractmethod
    def put(self, key: str, data: FloodplainData, timestamp: float) -> None:
        """
        Store data in cache.

        Args:
            key: Cache key
            data: FloodplainData to cache
            timestamp: Timestamp when cached
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete entry from cache.

        Args:
            key: Cache key
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        pass


class InMemoryCache(CacheBackend):
    """In-memory cache backend using Python dictionary."""

    def __init__(self) -> None:
        """Initialize in-memory cache."""
        self._cache: Dict[str, Tuple[FloodplainData, float]] = {}
        self._hits = 0
        self._misses = 0
        logger.info("Initialized in-memory cache backend")

    def get(self, key: str) -> Optional[Tuple[FloodplainData, float]]:
        """Get data from in-memory cache."""
        if key in self._cache:
            self._hits += 1
            return self._cache[key]

        self._misses += 1
        return None

    def put(self, key: str, data: FloodplainData, timestamp: float) -> None:
        """Store data in in-memory cache."""
        self._cache[key] = (data, timestamp)

    def delete(self, key: str) -> None:
        """Delete entry from in-memory cache."""
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear in-memory cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get in-memory cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "backend": "in-memory",
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
        }


class RedisCache(CacheBackend):
    """Redis cache backend (optional, with fallback to in-memory)."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "fema:") -> None:
        """
        Initialize Redis cache backend.

        Args:
            redis_url: Redis connection URL
            prefix: Key prefix for namespacing

        Raises:
            ImportError: If redis package not installed
            ConnectionError: If cannot connect to Redis
        """
        self.prefix = prefix
        self._hits = 0
        self._misses = 0

        try:
            import redis

            self.redis = redis.from_url(redis_url, decode_responses=False)
            # Test connection
            self.redis.ping()
            logger.info(f"Initialized Redis cache backend at {redis_url}")

        except ImportError:
            raise ImportError(
                "Redis package not installed. Install with: pip install redis"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def _serialize_data(self, data: FloodplainData, timestamp: float) -> bytes:
        """
        Serialize FloodplainData to bytes for Redis storage.

        Args:
            data: FloodplainData object
            timestamp: Cache timestamp

        Returns:
            Serialized bytes
        """
        cache_entry = {
            "data": data.model_dump(mode="json"),
            "timestamp": timestamp,
        }
        return json.dumps(cache_entry).encode("utf-8")

    def _deserialize_data(self, raw_data: bytes) -> Tuple[FloodplainData, float]:
        """
        Deserialize bytes from Redis to FloodplainData.

        Args:
            raw_data: Raw bytes from Redis

        Returns:
            Tuple of (FloodplainData, timestamp)
        """
        cache_entry = json.loads(raw_data.decode("utf-8"))
        data = FloodplainData(**cache_entry["data"])
        timestamp = cache_entry["timestamp"]
        return data, timestamp

    def get(self, key: str) -> Optional[Tuple[FloodplainData, float]]:
        """Get data from Redis cache."""
        try:
            redis_key = f"{self.prefix}{key}"
            raw_data = self.redis.get(redis_key)

            if raw_data:
                self._hits += 1
                return self._deserialize_data(raw_data)

            self._misses += 1
            return None

        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._misses += 1
            return None

    def put(self, key: str, data: FloodplainData, timestamp: float) -> None:
        """Store data in Redis cache."""
        try:
            redis_key = f"{self.prefix}{key}"
            serialized = self._serialize_data(data, timestamp)
            # Set with no expiration (handled by application logic)
            self.redis.set(redis_key, serialized)

        except Exception as e:
            logger.error(f"Redis put error: {e}")

    def delete(self, key: str) -> None:
        """Delete entry from Redis cache."""
        try:
            redis_key = f"{self.prefix}{key}"
            self.redis.delete(redis_key)

        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    def clear(self) -> None:
        """Clear all cache entries with our prefix."""
        try:
            # Find all keys with our prefix
            pattern = f"{self.prefix}*"
            keys = list(self.redis.scan_iter(match=pattern))

            if keys:
                self.redis.delete(*keys)

            self._hits = 0
            self._misses = 0

        except Exception as e:
            logger.error(f"Redis clear error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics."""
        try:
            # Count keys with our prefix
            pattern = f"{self.prefix}*"
            entry_count = sum(1 for _ in self.redis.scan_iter(match=pattern))

            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            # Get Redis server info
            info = self.redis.info("memory")

            return {
                "backend": "redis",
                "entries": entry_count,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
                "used_memory_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
            }

        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {
                "backend": "redis",
                "entries": 0,
                "error": str(e),
            }


class CacheManager:
    """
    Cache manager with automatic fallback from Redis to in-memory.

    Tries to use Redis if available, otherwise falls back to in-memory caching.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 2592000,  # 30 days
    ) -> None:
        """
        Initialize cache manager.

        Args:
            redis_url: Redis connection URL (optional)
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.ttl_seconds = ttl_seconds
        self._backend: CacheBackend

        # Try Redis first if URL provided
        if redis_url:
            try:
                self._backend = RedisCache(redis_url)
                logger.info("Using Redis cache backend")
                return
            except (ImportError, ConnectionError) as e:
                logger.warning(f"Redis unavailable, falling back to in-memory cache: {e}")

        # Fallback to in-memory
        self._backend = InMemoryCache()
        logger.info("Using in-memory cache backend")

    def get(self, key: str) -> Optional[FloodplainData]:
        """
        Get data from cache if available and not expired.

        Args:
            key: Cache key

        Returns:
            Cached FloodplainData or None
        """
        result = self._backend.get(key)

        if result:
            data, timestamp = result
            age = time.time() - timestamp

            if age < self.ttl_seconds:
                logger.debug(f"Cache hit for key {key[:8]}... (age: {age:.1f}s)")
                data.cache_hit = True
                return data
            else:
                # Expired, delete it
                logger.debug(f"Cache expired for key {key[:8]}... (age: {age:.1f}s)")
                self._backend.delete(key)

        return None

    def put(self, key: str, data: FloodplainData) -> None:
        """
        Store data in cache.

        Args:
            key: Cache key
            data: FloodplainData to cache
        """
        timestamp = time.time()
        self._backend.put(key, data, timestamp)
        logger.debug(f"Cached data for key {key[:8]}...")

    def delete(self, key: str) -> None:
        """
        Delete entry from cache.

        Args:
            key: Cache key
        """
        self._backend.delete(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._backend.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats including TTL
        """
        stats = self._backend.get_stats()
        stats["ttl_seconds"] = self.ttl_seconds
        return stats

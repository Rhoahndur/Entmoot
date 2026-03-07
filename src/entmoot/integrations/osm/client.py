"""OpenStreetMap Overpass API client for fetching existing conditions."""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field

from entmoot.integrations.rate_limiter import RateLimiter
from entmoot.models.existing_conditions import ExistingConditionsData

from .cache import OSMCache
from .parser import OSMResponseParser

logger = logging.getLogger(__name__)


class OSMClientConfig(BaseModel):
    """Configuration for the Overpass API client."""

    base_url: str = Field(
        default="https://overpass-api.de/api/interpreter",
        description="Overpass API endpoint",
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds", ge=1.0, le=120.0)
    max_retries: int = Field(default=2, description="Maximum retry attempts", ge=0, le=5)
    retry_backoff_factor: float = Field(default=1.0, description="Backoff factor", ge=0.1)
    rate_limit_calls: int = Field(default=2, description="Max calls per rate window", ge=1)
    rate_limit_period: float = Field(default=10.0, description="Rate window in seconds", ge=1.0)
    cache_ttl: int = Field(default=86400, description="Cache TTL in seconds (24h)", ge=0)


class OSMClient:
    """
    Async client for the Overpass API.

    Follows the same patterns as FEMAClient: httpx, rate limiting,
    retry with exponential backoff, in-memory caching, and graceful
    degradation (returns empty data on failure instead of raising).
    """

    def __init__(self, config: Optional[OSMClientConfig] = None) -> None:
        """Initialize OSM client with optional configuration."""
        self.config = config or OSMClientConfig()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            follow_redirects=True,
        )
        self.rate_limiter = RateLimiter(
            self.config.rate_limit_calls,
            self.config.rate_limit_period,
        )
        self._cache = OSMCache(ttl_seconds=self.config.cache_ttl)
        self._parser = OSMResponseParser()

        logger.info(
            f"OSM client initialized: {self.config.base_url}, " f"timeout={self.config.timeout}s"
        )

    async def __aenter__(self) -> "OSMClient":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query_existing_conditions(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
    ) -> ExistingConditionsData:
        """Fetch existing features within the given bounding box.

        Returns empty ExistingConditionsData on any failure (never blocks
        the optimizer).
        """
        bbox = {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat}

        # Check cache
        cache_key = self._cache.make_key(min_lon, min_lat, max_lon, max_lat)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Build Overpass QL query
        bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        query = (
            f"[out:json][timeout:{int(self.config.timeout)}];\n"
            f"(\n"
            f'  way["building"]({bbox_str});\n'
            f'  way["highway"]({bbox_str});\n'
            f'  way["power"="line"]({bbox_str});\n'
            f'  way["man_made"="pipeline"]({bbox_str});\n'
            f'  way["natural"="water"]({bbox_str});\n'
            f'  way["waterway"]({bbox_str});\n'
            f'  way["natural"="wetland"]({bbox_str});\n'
            f");\n"
            f"out body;\n"
            f">;\n"
            f"out skel qt;"
        )

        try:
            data = await self._make_request(query)
            result = self._parser.parse_response(data, bbox=bbox)
        except Exception as e:
            logger.warning(f"OSM query/parse failed, returning empty data: {e}")
            return ExistingConditionsData(bbox=bbox)

        self._cache.put(cache_key, result)
        logger.info(f"OSM query returned {result.feature_count} features")
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _make_request(
        self,
        query: str,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """POST the Overpass QL query with rate limiting and retries."""
        # Rate limit
        while not self.rate_limiter.acquire():
            wait = self.rate_limiter.wait_time()
            logger.debug(f"OSM rate limited, waiting {wait:.2f}s")
            await asyncio.sleep(wait)

        try:
            response = await self.client.post(
                self.config.base_url,
                data={"data": query},
            )
            response.raise_for_status()
            result: Dict[str, Any] = response.json()
            return result

        except httpx.HTTPStatusError as e:
            # Retry on 429 (rate limited) and 5xx (server errors); propagate 4xx
            if e.response.status_code == 429 or e.response.status_code >= 500:
                logger.warning(f"OSM request failed (attempt {retry_count + 1}): {e}")
                if retry_count < self.config.max_retries:
                    backoff = self.config.retry_backoff_factor * (2**retry_count)
                    logger.info(f"Retrying OSM request in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)
                    return await self._make_request(query, retry_count + 1)
            raise

        except httpx.RequestError as e:
            logger.warning(f"OSM request failed (attempt {retry_count + 1}): {e}")

            if retry_count < self.config.max_retries:
                backoff = self.config.retry_backoff_factor * (2**retry_count)
                logger.info(f"Retrying OSM request in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                return await self._make_request(query, retry_count + 1)

            raise

    def clear_cache(self) -> None:
        """Clear the OSM response cache."""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Return cache statistics."""
        return self._cache.get_stats()

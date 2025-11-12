"""
FEMA National Flood Hazard Layer (NFHL) API client.

Implements API client with:
- Authentication (API key if required)
- Rate limiting
- Retry logic with exponential backoff
- Timeout handling
- Error handling
- Caching
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from entmoot.models.regulatory import FloodplainData, RegulatoryDataSource

logger = logging.getLogger(__name__)


class FEMAClientConfig(BaseModel):
    """Configuration for FEMA API client."""

    base_url: str = Field(
        default="https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer",
        description="Base URL for FEMA NFHL service",
    )
    flood_zone_layer: int = Field(default=28, description="Layer ID for flood hazard zones")
    timeout: float = Field(default=5.0, description="Request timeout in seconds", ge=1.0, le=30.0)
    max_retries: int = Field(default=3, description="Maximum number of retries", ge=0, le=10)
    retry_backoff_factor: float = Field(
        default=1.0, description="Exponential backoff factor", ge=0.1, le=10.0
    )
    max_records: int = Field(
        default=1000, description="Maximum records per request", ge=1, le=2000
    )
    rate_limit_calls: int = Field(default=10, description="Max calls per time window", ge=1)
    rate_limit_period: float = Field(default=1.0, description="Rate limit window in seconds", ge=0.1)
    api_key: Optional[str] = Field(None, description="API key if required")
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_ttl: int = Field(default=2592000, description="Cache TTL in seconds (30 days)", ge=0)


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


class FEMAClient:
    """
    Client for FEMA National Flood Hazard Layer REST API.

    Provides methods to query flood hazard data by point or bounding box.
    Includes rate limiting, retries, caching, and error handling.
    """

    def __init__(self, config: Optional[FEMAClientConfig] = None) -> None:
        """
        Initialize FEMA API client.

        Args:
            config: Client configuration
        """
        self.config = config or FEMAClientConfig()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            follow_redirects=True,
        )
        self.rate_limiter = RateLimiter(
            self.config.rate_limit_calls,
            self.config.rate_limit_period,
        )
        self._cache: Dict[str, Tuple[FloodplainData, float]] = {}

        logger.info(
            f"FEMA client initialized with base URL: {self.config.base_url}, "
            f"timeout: {self.config.timeout}s"
        )

    async def __aenter__(self) -> "FEMAClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    def _generate_cache_key(self, **kwargs: Any) -> str:
        """
        Generate cache key from query parameters.

        Args:
            **kwargs: Query parameters

        Returns:
            SHA256 hash of parameters
        """
        # Sort parameters for consistent hashing
        sorted_params = sorted(kwargs.items())
        key_string = str(sorted_params)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[FloodplainData]:
        """
        Get data from cache if available and not expired.

        Args:
            cache_key: Cache key

        Returns:
            Cached FloodplainData or None
        """
        if not self.config.cache_enabled:
            return None

        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            age = time.time() - timestamp

            if age < self.config.cache_ttl:
                logger.debug(f"Cache hit for key {cache_key[:8]}... (age: {age:.1f}s)")
                data.cache_hit = True
                data.data_source = RegulatoryDataSource.CACHED
                return data
            else:
                # Expired cache entry
                logger.debug(f"Cache expired for key {cache_key[:8]}... (age: {age:.1f}s)")
                del self._cache[cache_key]

        return None

    def _put_in_cache(self, cache_key: str, data: FloodplainData) -> None:
        """
        Store data in cache.

        Args:
            cache_key: Cache key
            data: FloodplainData to cache
        """
        if not self.config.cache_enabled:
            return

        self._cache[cache_key] = (data, time.time())
        logger.debug(f"Cached data for key {cache_key[:8]}...")

    async def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting and retries.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            retry_count: Current retry attempt

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: On request failure after retries
        """
        # Rate limiting
        while not self.rate_limiter.acquire():
            wait_time = self.rate_limiter.wait_time()
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await httpx.AsyncClient().aclose()  # Release any connection
            time.sleep(wait_time)

        url = f"{self.config.base_url}/{endpoint}"

        # Add API key if configured
        if self.config.api_key:
            params["token"] = self.config.api_key

        try:
            logger.debug(f"Making request to {url} with params: {params}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Check for ArcGIS error response
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown ArcGIS error")
                logger.error(f"ArcGIS API error: {error_msg}")
                raise httpx.HTTPStatusError(
                    error_msg,
                    request=response.request,
                    response=response,
                )

            return data

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"Request failed (attempt {retry_count + 1}): {e}")

            # Retry with exponential backoff
            if retry_count < self.config.max_retries:
                backoff = self.config.retry_backoff_factor * (2**retry_count)
                logger.info(f"Retrying in {backoff:.2f}s...")
                time.sleep(backoff)
                return await self._make_request(endpoint, params, retry_count + 1)

            # Max retries exceeded
            logger.error(f"Max retries exceeded for {url}")
            raise

    async def query_by_point(
        self,
        longitude: float,
        latitude: float,
        buffer_meters: float = 0,
    ) -> FloodplainData:
        """
        Query flood hazard data for a specific point.

        Args:
            longitude: Longitude coordinate (WGS84)
            latitude: Latitude coordinate (WGS84)
            buffer_meters: Buffer distance in meters around point

        Returns:
            FloodplainData for the location

        Raises:
            httpx.HTTPError: On API request failure
        """
        # Check cache
        cache_key = self._generate_cache_key(
            lon=longitude,
            lat=latitude,
            buffer=buffer_meters,
            query_type="point",
        )

        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Build query parameters
        params = {
            "geometry": f"{longitude},{latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,  # WGS84
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "json",
            "returnZ": "false",
            "returnM": "false",
        }

        if buffer_meters > 0:
            params["distance"] = buffer_meters
            params["units"] = "esriSRUnit_Meter"

        endpoint = f"{self.config.flood_zone_layer}/query"

        try:
            data = await self._make_request(endpoint, params)

            # Parse response using parser
            from .parser import FEMAResponseParser

            parser = FEMAResponseParser()
            floodplain_data = parser.parse_query_response(
                data,
                longitude=longitude,
                latitude=latitude,
            )

            # Cache the result
            self._put_in_cache(cache_key, floodplain_data)

            return floodplain_data

        except Exception as e:
            logger.error(f"Failed to query flood data for point ({longitude}, {latitude}): {e}")
            # Return empty result on failure
            return FloodplainData(
                location_lon=longitude,
                location_lat=latitude,
                data_source=RegulatoryDataSource.FEMA_NFHL,
            )

    async def query_by_bbox(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
    ) -> FloodplainData:
        """
        Query flood hazard data for a bounding box.

        Args:
            min_lon: Minimum longitude (WGS84)
            min_lat: Minimum latitude (WGS84)
            max_lon: Maximum longitude (WGS84)
            max_lat: Maximum latitude (WGS84)

        Returns:
            FloodplainData for the area

        Raises:
            httpx.HTTPError: On API request failure
        """
        # Check cache
        cache_key = self._generate_cache_key(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            query_type="bbox",
        )

        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Build bounding box string
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

        params = {
            "geometry": bbox,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "json",
            "returnZ": "false",
            "returnM": "false",
            "resultRecordCount": self.config.max_records,
        }

        endpoint = f"{self.config.flood_zone_layer}/query"

        try:
            data = await self._make_request(endpoint, params)

            # Parse response
            from .parser import FEMAResponseParser

            parser = FEMAResponseParser()
            floodplain_data = parser.parse_query_response(
                data,
                bbox_min_lon=min_lon,
                bbox_min_lat=min_lat,
                bbox_max_lon=max_lon,
                bbox_max_lat=max_lat,
            )

            # Cache the result
            self._put_in_cache(cache_key, floodplain_data)

            return floodplain_data

        except Exception as e:
            logger.error(
                f"Failed to query flood data for bbox "
                f"({min_lon}, {min_lat}, {max_lon}, {max_lat}): {e}"
            )
            # Return empty result on failure
            return FloodplainData(
                bbox_min_lon=min_lon,
                bbox_min_lat=min_lat,
                bbox_max_lon=max_lon,
                bbox_max_lat=max_lat,
                data_source=RegulatoryDataSource.FEMA_NFHL,
            )

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "enabled": self.config.cache_enabled,
            "entries": len(self._cache),
            "ttl_seconds": self.config.cache_ttl,
        }

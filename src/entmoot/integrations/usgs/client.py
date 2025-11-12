"""
USGS 3D Elevation Program (3DEP) API client.

Implements client for:
- USGS Elevation Point Query Service (EPQS)
- 3DEP DEM tile downloads
- Batch elevation queries
- Rate limiting and retry logic
"""

import asyncio
import hashlib
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
import numpy as np
import rasterio
from pydantic import BaseModel, Field
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling

from entmoot.models.elevation import (
    DEMTileMetadata,
    DEMTileRequest,
    ElevationBatchResponse,
    ElevationDataSource,
    ElevationDatum,
    ElevationPoint,
    ElevationQuery,
    ElevationQueryStatus,
    ElevationUnit,
    USRegion,
)

logger = logging.getLogger(__name__)


class USGSClientConfig(BaseModel):
    """Configuration for USGS API client."""

    epqs_base_url: str = Field(
        default="https://epqs.nationalmap.gov/v1",
        description="Base URL for Elevation Point Query Service",
    )
    timeout: float = Field(default=10.0, description="Request timeout in seconds", ge=1.0, le=60.0)
    max_retries: int = Field(default=3, description="Maximum number of retries", ge=0, le=10)
    retry_backoff_factor: float = Field(
        default=1.0, description="Exponential backoff factor", ge=0.1, le=10.0
    )
    rate_limit_calls: int = Field(default=20, description="Max calls per time window", ge=1)
    rate_limit_period: float = Field(default=1.0, description="Rate limit window in seconds", ge=0.1)
    batch_size: int = Field(default=100, description="Max points per batch query", ge=1, le=1000)
    cache_dir: Optional[Path] = Field(
        default=None, description="Directory for DEM tile cache"
    )
    point_cache_ttl: int = Field(
        default=2592000, description="Point query cache TTL (30 days)", ge=0
    )
    tile_cache_permanent: bool = Field(
        default=True, description="DEM tiles cached permanently"
    )


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


class USGSClient:
    """
    Client for USGS 3D Elevation Program (3DEP) API.

    Provides methods to:
    - Query elevation for single points
    - Query elevation for multiple points (batch)
    - Download DEM tiles
    - Mosaic multiple tiles
    """

    def __init__(self, config: Optional[USGSClientConfig] = None) -> None:
        """
        Initialize USGS API client.

        Args:
            config: Client configuration
        """
        self.config = config or USGSClientConfig()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            follow_redirects=True,
        )
        self.rate_limiter = RateLimiter(
            self.config.rate_limit_calls,
            self.config.rate_limit_period,
        )

        # Set up cache directory
        if self.config.cache_dir is None:
            self.config.cache_dir = Path.home() / ".entmoot" / "dem_cache"
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache for point queries
        self._point_cache: Dict[str, Tuple[ElevationPoint, float]] = {}

        logger.info(
            f"USGS client initialized with EPQS URL: {self.config.epqs_base_url}, "
            f"cache dir: {self.config.cache_dir}"
        )

    async def __aenter__(self) -> "USGSClient":
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
        sorted_params = sorted(kwargs.items())
        key_string = str(sorted_params)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_point_from_cache(self, cache_key: str) -> Optional[ElevationPoint]:
        """
        Get point data from cache if available and not expired.

        Args:
            cache_key: Cache key

        Returns:
            Cached ElevationPoint or None
        """
        if cache_key in self._point_cache:
            point, timestamp = self._point_cache[cache_key]
            age = time.time() - timestamp

            if age < self.config.point_cache_ttl:
                logger.debug(f"Point cache hit for key {cache_key[:8]}... (age: {age:.1f}s)")
                return point
            else:
                logger.debug(f"Point cache expired for key {cache_key[:8]}... (age: {age:.1f}s)")
                del self._point_cache[cache_key]

        return None

    def _put_point_in_cache(self, cache_key: str, point: ElevationPoint) -> None:
        """
        Store point data in cache.

        Args:
            cache_key: Cache key
            point: ElevationPoint to cache
        """
        self._point_cache[cache_key] = (point, time.time())
        logger.debug(f"Cached point data for key {cache_key[:8]}...")

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting and retries.

        Args:
            url: Request URL
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
            await asyncio.sleep(wait_time)

        try:
            logger.debug(f"Making request to {url} with params: {params}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            return data

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"Request failed (attempt {retry_count + 1}): {e}")

            # Retry with exponential backoff
            if retry_count < self.config.max_retries:
                backoff = self.config.retry_backoff_factor * (2**retry_count)
                logger.info(f"Retrying in {backoff:.2f}s...")
                await asyncio.sleep(backoff)
                return await self._make_request(url, params, retry_count + 1)

            # Max retries exceeded
            logger.error(f"Max retries exceeded for {url}")
            raise

    async def query_point_elevation(
        self,
        longitude: float,
        latitude: float,
        unit: ElevationUnit = ElevationUnit.METERS,
    ) -> ElevationPoint:
        """
        Query elevation for a single point.

        Args:
            longitude: Longitude coordinate (WGS84)
            latitude: Latitude coordinate (WGS84)
            unit: Desired elevation unit

        Returns:
            ElevationPoint with elevation data

        Raises:
            httpx.HTTPError: On API request failure
        """
        # Check cache
        cache_key = self._generate_cache_key(
            lon=longitude,
            lat=latitude,
            unit=unit.value,
            query_type="point",
        )

        cached = self._get_point_from_cache(cache_key)
        if cached:
            return cached

        # Build query URL
        url = f"{self.config.epqs_base_url}/json"
        params = {
            "x": longitude,
            "y": latitude,
            "units": "Meters" if unit == ElevationUnit.METERS else "Feet",
            "wkid": 4326,  # WGS84
            "includeDate": "false",
        }

        try:
            data = await self._make_request(url, params)

            # Parse response
            if "value" in data and data["value"] is not None:
                elevation = float(data["value"])

                # Determine data source from resolution
                resolution = data.get("resolution", 1.0)
                if resolution <= 1.0:
                    data_source = ElevationDataSource.USGS_3DEP_1ARC
                elif resolution <= 2.0:
                    data_source = ElevationDataSource.USGS_3DEP_2ARC
                else:
                    data_source = ElevationDataSource.NED

                point = ElevationPoint(
                    longitude=longitude,
                    latitude=latitude,
                    elevation=elevation,
                    unit=unit,
                    datum=ElevationDatum.NAVD88,
                    resolution=resolution,
                    data_source=data_source,
                )

                # Cache the result
                self._put_point_in_cache(cache_key, point)

                return point
            else:
                # No elevation data available
                logger.warning(f"No elevation data for point ({longitude}, {latitude})")
                return ElevationPoint(
                    longitude=longitude,
                    latitude=latitude,
                    elevation=None,
                    unit=unit,
                    data_source=ElevationDataSource.UNKNOWN,
                )

        except Exception as e:
            logger.error(f"Failed to query elevation for point ({longitude}, {latitude}): {e}")
            return ElevationPoint(
                longitude=longitude,
                latitude=latitude,
                elevation=None,
                unit=unit,
                data_source=ElevationDataSource.UNKNOWN,
            )

    async def query_batch_elevation(
        self,
        points: List[Tuple[float, float]],
        unit: ElevationUnit = ElevationUnit.METERS,
    ) -> ElevationBatchResponse:
        """
        Query elevation for multiple points.

        Args:
            points: List of (longitude, latitude) tuples
            unit: Desired elevation unit

        Returns:
            ElevationBatchResponse with all point elevations
        """
        query_id = str(uuid.uuid4())
        start_time = time.time()

        query = ElevationQuery(
            query_id=query_id,
            query_type="batch",
            point_count=len(points),
        )

        elevation_points: List[ElevationPoint] = []
        success_count = 0
        failed_count = 0

        # Process points in batches
        batch_size = self.config.batch_size
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]

            # Query each point (could be parallelized)
            tasks = [self.query_point_elevation(lon, lat, unit) for lon, lat in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"Batch query failed for point: {result}")
                elif result.elevation is not None:
                    success_count += 1
                    elevation_points.append(result)
                else:
                    failed_count += 1
                    elevation_points.append(result)

        # Update query metadata
        duration_ms = (time.time() - start_time) * 1000
        query.success_count = success_count
        query.failed_count = failed_count
        query.duration_ms = duration_ms

        if success_count == len(points):
            query.status = ElevationQueryStatus.SUCCESS
        elif success_count > 0:
            query.status = ElevationQueryStatus.PARTIAL
        else:
            query.status = ElevationQueryStatus.FAILED

        # Create response
        response = ElevationBatchResponse(
            query=query,
            points=elevation_points,
        )

        # Compute statistics
        response.compute_statistics()

        return response

    def _calculate_tile_bounds(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> List[Tuple[int, int]]:
        """
        Calculate which 1-degree tiles are needed for a bounding box.

        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude

        Returns:
            List of (lon_deg, lat_deg) tuples for tile corners
        """
        # Round to tile boundaries (1-degree tiles)
        lon_start = int(np.floor(min_lon))
        lon_end = int(np.ceil(max_lon))
        lat_start = int(np.floor(min_lat))
        lat_end = int(np.ceil(max_lat))

        tiles = []
        for lon in range(lon_start, lon_end):
            for lat in range(lat_start, lat_end):
                tiles.append((lon, lat))

        logger.info(
            f"Calculated {len(tiles)} tiles needed for bbox "
            f"({min_lon}, {min_lat}, {max_lon}, {max_lat})"
        )

        return tiles

    def _get_tile_filename(self, lon: int, lat: int, resolution: float = 1.0) -> str:
        """
        Generate filename for DEM tile.

        Args:
            lon: Longitude (integer degree)
            lat: Latitude (integer degree)
            resolution: Resolution in arc-seconds

        Returns:
            Filename string
        """
        lon_dir = "e" if lon >= 0 else "w"
        lat_dir = "n" if lat >= 0 else "s"
        return f"usgs_dem_{lat_dir}{abs(lat):02d}_{lon_dir}{abs(lon):03d}_{int(resolution)}as.tif"

    def _get_tile_path(self, lon: int, lat: int, resolution: float = 1.0) -> Path:
        """
        Get local file path for DEM tile.

        Args:
            lon: Longitude (integer degree)
            lat: Latitude (integer degree)
            resolution: Resolution in arc-seconds

        Returns:
            Path object
        """
        filename = self._get_tile_filename(lon, lat, resolution)
        return self.config.cache_dir / filename  # type: ignore

    async def download_dem_tile(
        self,
        lon: int,
        lat: int,
        resolution: float = 1.0,
    ) -> Optional[DEMTileMetadata]:
        """
        Download a single DEM tile.

        Note: This is a simplified implementation. In production, you would
        use the actual USGS 3DEP API or TNM Download API to get the tiles.

        Args:
            lon: Longitude (integer degree)
            lat: Latitude (integer degree)
            resolution: Resolution in arc-seconds

        Returns:
            DEMTileMetadata if successful, None otherwise
        """
        tile_path = self._get_tile_path(lon, lat, resolution)

        # Check if tile already exists in cache
        if tile_path.exists():
            logger.info(f"DEM tile already cached: {tile_path}")

            metadata = DEMTileMetadata(
                tile_id=f"{lat}_{lon}_{resolution}",
                min_lon=float(lon),
                min_lat=float(lat),
                max_lon=float(lon + 1),
                max_lat=float(lat + 1),
                resolution=resolution,
                unit=ElevationUnit.METERS,
                datum=ElevationDatum.NAVD88,
                data_source=ElevationDataSource.USGS_3DEP_1ARC,
                file_path=str(tile_path),
                file_size_bytes=tile_path.stat().st_size,
            )

            return metadata

        # In a real implementation, download from USGS here
        logger.warning(
            f"DEM tile download not implemented for ({lon}, {lat}). "
            "Would download from USGS 3DEP TNM API."
        )

        return None

    async def download_dem_for_bbox(
        self,
        request: DEMTileRequest,
    ) -> List[DEMTileMetadata]:
        """
        Download all DEM tiles needed for a bounding box.

        Args:
            request: DEM tile request with bounding box

        Returns:
            List of DEMTileMetadata for downloaded tiles
        """
        # Calculate needed tiles
        tiles = self._calculate_tile_bounds(
            request.min_lon, request.min_lat, request.max_lon, request.max_lat
        )

        # Download tiles
        tile_metadata: List[DEMTileMetadata] = []
        for lon, lat in tiles:
            metadata = await self.download_dem_tile(lon, lat, request.resolution)
            if metadata:
                tile_metadata.append(metadata)

        logger.info(f"Downloaded {len(tile_metadata)} tiles for bbox {request.bounds}")

        return tile_metadata

    def mosaic_dem_tiles(
        self,
        tile_metadata: List[DEMTileMetadata],
        output_path: Path,
    ) -> Optional[Path]:
        """
        Mosaic multiple DEM tiles into a single GeoTIFF.

        Args:
            tile_metadata: List of tile metadata
            output_path: Output file path

        Returns:
            Output path if successful, None otherwise
        """
        if not tile_metadata:
            logger.error("No tiles to mosaic")
            return None

        try:
            # Open all tiles
            src_files = []
            for meta in tile_metadata:
                if meta.file_path and Path(meta.file_path).exists():
                    src = rasterio.open(meta.file_path)
                    src_files.append(src)

            if not src_files:
                logger.error("No valid tile files found")
                return None

            # Mosaic tiles
            mosaic, out_transform = merge(src_files)

            # Write output
            out_meta = src_files[0].meta.copy()
            out_meta.update(
                {
                    "driver": "GTiff",
                    "height": mosaic.shape[1],
                    "width": mosaic.shape[2],
                    "transform": out_transform,
                    "compress": "lzw",
                }
            )

            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(mosaic)

            # Close source files
            for src in src_files:
                src.close()

            logger.info(f"Mosaicked {len(src_files)} tiles to {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Failed to mosaic DEM tiles: {e}")
            return None

    def clear_point_cache(self) -> None:
        """Clear the in-memory point query cache."""
        self._point_cache.clear()
        logger.info("Point cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        tile_count = 0
        total_size = 0

        if self.config.cache_dir and self.config.cache_dir.exists():
            tile_files = list(self.config.cache_dir.glob("*.tif"))
            tile_count = len(tile_files)
            total_size = sum(f.stat().st_size for f in tile_files)

        return {
            "point_cache_entries": len(self._point_cache),
            "point_cache_ttl_seconds": self.config.point_cache_ttl,
            "tile_cache_dir": str(self.config.cache_dir),
            "tile_count": tile_count,
            "tile_cache_size_bytes": total_size,
            "tile_cache_size_mb": total_size / (1024 * 1024),
        }

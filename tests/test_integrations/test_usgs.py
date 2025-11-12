"""
Tests for USGS elevation integration.

Tests cover:
- USGS API client functionality
- Point elevation queries
- Batch elevation queries
- DEM tile downloads
- Response parsing
- Caching
- Error handling
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from entmoot.integrations.usgs.cache import ElevationCacheManager
from entmoot.integrations.usgs.client import (
    RateLimiter,
    USGSClient,
    USGSClientConfig,
)
from entmoot.integrations.usgs.parser import USGSResponseParser
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


# Fixtures


@pytest.fixture
def usgs_config() -> USGSClientConfig:
    """Create test USGS client configuration."""
    return USGSClientConfig(
        timeout=5.0,
        max_retries=2,
        rate_limit_calls=10,
        rate_limit_period=1.0,
        batch_size=50,
    )


@pytest.fixture
def usgs_client(tmp_path: Path, usgs_config: USGSClientConfig) -> USGSClient:
    """Create USGS client for testing."""
    usgs_config.cache_dir = tmp_path / "cache"
    return USGSClient(config=usgs_config)


@pytest.fixture
def cache_manager(tmp_path: Path) -> ElevationCacheManager:
    """Create cache manager for testing."""
    return ElevationCacheManager(
        cache_dir=tmp_path / "cache",
        point_cache_ttl=3600,
        max_memory_entries=100,
    )


@pytest.fixture
def parser() -> USGSResponseParser:
    """Create response parser for testing."""
    return USGSResponseParser()


@pytest.fixture
def mock_epqs_response() -> Dict[str, Any]:
    """Mock EPQS API response."""
    return {
        "value": 123.45,
        "resolution": 1.0,
        "units": "Meters",
        "data_source": "3DEP 1 arc-second",
        "x": -105.5,
        "y": 40.0,
    }


@pytest.fixture
def mock_epqs_response_null() -> Dict[str, Any]:
    """Mock EPQS API response with null value."""
    return {
        "value": None,
        "resolution": 1.0,
        "units": "Meters",
        "message": "No elevation data available",
    }


# Rate Limiter Tests


def test_rate_limiter_initialization() -> None:
    """Test rate limiter initialization."""
    limiter = RateLimiter(calls=10, period=1.0)
    assert limiter.calls == 10
    assert limiter.period == 1.0
    assert limiter.tokens == 10.0


def test_rate_limiter_acquire() -> None:
    """Test rate limiter token acquisition."""
    limiter = RateLimiter(calls=5, period=1.0)

    # Should be able to acquire 5 tokens
    for i in range(5):
        assert limiter.acquire() is True

    # 6th attempt should fail
    assert limiter.acquire() is False


def test_rate_limiter_refill() -> None:
    """Test rate limiter token refill."""
    limiter = RateLimiter(calls=10, period=1.0)

    # Exhaust tokens
    for _ in range(10):
        limiter.acquire()

    # Wait and tokens should refill
    time.sleep(0.5)
    assert limiter.acquire() is True


def test_rate_limiter_wait_time() -> None:
    """Test rate limiter wait time calculation."""
    limiter = RateLimiter(calls=10, period=1.0)

    # With full tokens, wait time should be 0
    assert limiter.wait_time() == 0.0

    # Exhaust tokens
    for _ in range(10):
        limiter.acquire()

    # Wait time should be positive
    wait = limiter.wait_time()
    assert wait > 0


# Parser Tests


def test_parser_epqs_response_success(
    parser: USGSResponseParser, mock_epqs_response: Dict[str, Any]
) -> None:
    """Test parsing successful EPQS response."""
    point = parser.parse_epqs_response(
        mock_epqs_response, longitude=-105.5, latitude=40.0
    )

    assert point.longitude == -105.5
    assert point.latitude == 40.0
    assert point.elevation == 123.45
    assert point.unit == ElevationUnit.METERS
    assert point.resolution == 1.0
    assert point.data_source == ElevationDataSource.USGS_3DEP_1ARC


def test_parser_epqs_response_null_value(
    parser: USGSResponseParser, mock_epqs_response_null: Dict[str, Any]
) -> None:
    """Test parsing EPQS response with null value."""
    point = parser.parse_epqs_response(
        mock_epqs_response_null, longitude=-105.5, latitude=40.0
    )

    assert point.longitude == -105.5
    assert point.latitude == 40.0
    assert point.elevation is None


def test_parser_determine_data_source(parser: USGSResponseParser) -> None:
    """Test data source determination."""
    # Test explicit data source
    data = {"data_source": "3DEP 1-meter"}
    source = parser._determine_data_source(data, None)
    assert source == ElevationDataSource.USGS_3DEP_1M

    # Test inference from resolution
    source = parser._determine_data_source({}, 0.33)
    assert source == ElevationDataSource.USGS_3DEP_1_3M

    source = parser._determine_data_source({}, 1.0)
    assert source == ElevationDataSource.USGS_3DEP_1ARC


def test_parser_extract_datum(parser: USGSResponseParser) -> None:
    """Test datum extraction."""
    # Test explicit datum
    data = {"datum": "NAVD88"}
    datum = parser._extract_datum(data)
    assert datum == ElevationDatum.NAVD88

    data = {"vertical_datum": "NGVD29"}
    datum = parser._extract_datum(data)
    assert datum == ElevationDatum.NGVD29

    # Test default
    datum = parser._extract_datum({})
    assert datum == ElevationDatum.NAVD88


def test_parser_error_response(parser: USGSResponseParser) -> None:
    """Test error response parsing."""
    # Test explicit error
    data = {"error": {"message": "Invalid coordinates"}}
    error = parser.parse_error_response(data)
    assert error == "Invalid coordinates"

    # Test status error
    data = {"status": "error", "message": "Request failed"}
    error = parser.parse_error_response(data)
    assert error == "Request failed"

    # Test no error
    data = {"value": 123.45}
    error = parser.parse_error_response(data)
    assert error is None


def test_parser_validate_response(parser: USGSResponseParser) -> None:
    """Test response validation."""
    # Valid response
    data = {"value": 123.45}
    valid, error = parser.validate_response(data)
    assert valid is True
    assert error is None

    # Missing value field
    data = {}
    valid, error = parser.validate_response(data)
    assert valid is False
    assert "value" in error.lower()

    # Invalid value
    data = {"value": "not a number"}
    valid, error = parser.validate_response(data)
    assert valid is False


def test_parser_extract_metadata(parser: USGSResponseParser) -> None:
    """Test metadata extraction."""
    data = {
        "resolution": 1.0,
        "units": "Meters",
        "datum": "NAVD88",
        "x": -105.5,
        "y": 40.0,
        "extra_field": "ignored",
    }

    metadata = parser.extract_metadata(data)
    assert "resolution" in metadata
    assert "units" in metadata
    assert "datum" in metadata
    assert "extra_field" not in metadata


# USGS Client Tests


@pytest.mark.asyncio
async def test_client_initialization(usgs_client: USGSClient) -> None:
    """Test USGS client initialization."""
    assert usgs_client.config.timeout == 5.0
    assert usgs_client.config.max_retries == 2
    assert usgs_client.rate_limiter is not None
    assert usgs_client.config.cache_dir is not None


@pytest.mark.asyncio
async def test_client_context_manager(tmp_path: Path) -> None:
    """Test USGS client as async context manager."""
    config = USGSClientConfig(cache_dir=tmp_path / "cache")

    async with USGSClient(config=config) as client:
        assert client is not None
        assert client.client is not None


@pytest.mark.asyncio
async def test_query_point_elevation_success(
    usgs_client: USGSClient, mock_epqs_response: Dict[str, Any]
) -> None:
    """Test successful point elevation query."""
    with patch.object(usgs_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_epqs_response

        point = await usgs_client.query_point_elevation(-105.5, 40.0)

        assert point.longitude == -105.5
        assert point.latitude == 40.0
        assert point.elevation == 123.45
        assert point.unit == ElevationUnit.METERS

        # Check that it's cached
        cache_key = usgs_client._generate_cache_key(
            lon=-105.5, lat=40.0, unit=ElevationUnit.METERS.value, query_type="point"
        )
        cached = usgs_client._get_point_from_cache(cache_key)
        assert cached is not None


@pytest.mark.asyncio
async def test_query_point_elevation_null_value(
    usgs_client: USGSClient, mock_epqs_response_null: Dict[str, Any]
) -> None:
    """Test point elevation query with null value."""
    with patch.object(usgs_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_epqs_response_null

        point = await usgs_client.query_point_elevation(-105.5, 40.0)

        assert point.longitude == -105.5
        assert point.latitude == 40.0
        assert point.elevation is None


@pytest.mark.asyncio
async def test_query_point_elevation_cache_hit(usgs_client: USGSClient) -> None:
    """Test point elevation query cache hit."""
    # Pre-populate cache
    cached_point = ElevationPoint(
        longitude=-105.5,
        latitude=40.0,
        elevation=100.0,
        unit=ElevationUnit.METERS,
    )

    cache_key = usgs_client._generate_cache_key(
        lon=-105.5, lat=40.0, unit=ElevationUnit.METERS.value, query_type="point"
    )
    usgs_client._put_point_in_cache(cache_key, cached_point)

    # Query should return cached value without API call
    with patch.object(usgs_client, "_make_request", new_callable=AsyncMock) as mock_request:
        point = await usgs_client.query_point_elevation(-105.5, 40.0)

        assert point.elevation == 100.0
        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_query_point_elevation_error(usgs_client: USGSClient) -> None:
    """Test point elevation query error handling."""
    with patch.object(usgs_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = httpx.HTTPError("Network error")

        point = await usgs_client.query_point_elevation(-105.5, 40.0)

        assert point.longitude == -105.5
        assert point.latitude == 40.0
        assert point.elevation is None
        assert point.data_source == ElevationDataSource.UNKNOWN


@pytest.mark.asyncio
async def test_query_batch_elevation(
    usgs_client: USGSClient, mock_epqs_response: Dict[str, Any]
) -> None:
    """Test batch elevation query."""
    points = [
        (-105.5, 40.0),
        (-105.6, 40.1),
        (-105.7, 40.2),
    ]

    with patch.object(usgs_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_epqs_response

        response = await usgs_client.query_batch_elevation(points)

        assert isinstance(response, ElevationBatchResponse)
        assert response.query.point_count == 3
        assert len(response.points) == 3
        assert response.query.success_count == 3
        assert response.min_elevation is not None
        assert response.max_elevation is not None


@pytest.mark.asyncio
async def test_query_batch_elevation_partial_success(usgs_client: USGSClient) -> None:
    """Test batch elevation query with partial success."""
    points = [
        (-105.5, 40.0),
        (-105.6, 40.1),
    ]

    async def mock_query_side_effect(lon: float, lat: float, unit: ElevationUnit) -> ElevationPoint:
        if lon == -105.5:
            return ElevationPoint(longitude=lon, latitude=lat, elevation=100.0, unit=unit)
        else:
            return ElevationPoint(longitude=lon, latitude=lat, elevation=None, unit=unit)

    with patch.object(
        usgs_client, "query_point_elevation", new_callable=AsyncMock
    ) as mock_query:
        mock_query.side_effect = mock_query_side_effect

        response = await usgs_client.query_batch_elevation(points)

        assert response.query.point_count == 2
        assert response.query.success_count == 1
        assert response.query.failed_count == 1
        assert response.query.status == ElevationQueryStatus.PARTIAL


@pytest.mark.asyncio
async def test_calculate_tile_bounds(usgs_client: USGSClient) -> None:
    """Test DEM tile bounds calculation."""
    tiles = usgs_client._calculate_tile_bounds(-105.5, 39.5, -104.5, 40.5)

    # Should cover 2x2 = 4 tiles
    assert len(tiles) == 4
    assert (-106, 39) in tiles
    assert (-105, 39) in tiles
    assert (-106, 40) in tiles
    assert (-105, 40) in tiles


def test_get_tile_filename(usgs_client: USGSClient) -> None:
    """Test tile filename generation."""
    filename = usgs_client._get_tile_filename(-105, 40, 1.0)
    # The function takes (lon, lat), so lon=-105, lat=40
    # Should have latitude indicator (n40 or s40) and longitude indicator (w105 or e105)
    assert ("n40" in filename or "s40" in filename) or ("40" in filename)
    assert ("w105" in filename or "e105" in filename) or ("105" in filename)
    assert "1as" in filename or "1" in filename
    assert filename.endswith(".tif")


def test_get_tile_path(usgs_client: USGSClient) -> None:
    """Test tile path generation."""
    path = usgs_client._get_tile_path(40, -105, 1.0)
    assert isinstance(path, Path)
    assert path.suffix == ".tif"


@pytest.mark.asyncio
async def test_download_dem_tile_cached(usgs_client: USGSClient, tmp_path: Path) -> None:
    """Test DEM tile download when already cached."""
    # Create a fake cached tile (lon, lat order)
    tile_path = usgs_client._get_tile_path(-105, 40)
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_text("fake tile data")

    metadata = await usgs_client.download_dem_tile(-105, 40)

    assert metadata is not None
    assert metadata.tile_id == "40_-105_1.0"
    assert metadata.file_path is not None
    assert Path(metadata.file_path).exists()


@pytest.mark.asyncio
async def test_download_dem_for_bbox(usgs_client: USGSClient, tmp_path: Path) -> None:
    """Test DEM download for bounding box."""
    # Create fake cached tiles
    tiles = [
        (40, -105),
        (40, -106),
    ]

    for lat, lon in tiles:
        tile_path = usgs_client._get_tile_path(lon, lat)
        tile_path.parent.mkdir(parents=True, exist_ok=True)
        tile_path.write_text("fake tile data")

    request = DEMTileRequest(
        min_lon=-106.5,
        min_lat=39.5,
        max_lon=-104.5,
        max_lat=40.5,
        resolution=1.0,
    )

    metadata_list = await usgs_client.download_dem_for_bbox(request)

    # Should find some cached tiles
    assert isinstance(metadata_list, list)


def test_cache_stats(usgs_client: USGSClient) -> None:
    """Test cache statistics."""
    stats = usgs_client.get_cache_stats()

    assert "point_cache_entries" in stats
    assert "tile_cache_dir" in stats
    assert "tile_count" in stats
    assert "tile_cache_size_mb" in stats


def test_clear_point_cache(usgs_client: USGSClient) -> None:
    """Test clearing point cache."""
    # Add some cached points
    point = ElevationPoint(longitude=-105.5, latitude=40.0, elevation=100.0)
    cache_key = "test_key"
    usgs_client._put_point_in_cache(cache_key, point)

    assert len(usgs_client._point_cache) > 0

    usgs_client.clear_point_cache()

    assert len(usgs_client._point_cache) == 0


# Cache Manager Tests


def test_cache_manager_initialization(cache_manager: ElevationCacheManager) -> None:
    """Test cache manager initialization."""
    assert cache_manager.cache_dir.exists()
    assert cache_manager.tiles_dir.exists()
    assert cache_manager.metadata_dir.exists()
    assert cache_manager.point_cache_ttl == 3600
    assert cache_manager.max_memory_entries == 100


def test_cache_manager_point_operations(cache_manager: ElevationCacheManager) -> None:
    """Test point cache operations."""
    point = ElevationPoint(
        longitude=-105.5,
        latitude=40.0,
        elevation=123.45,
        unit=ElevationUnit.METERS,
    )

    cache_key = "test_key_123"

    # Put and get
    cache_manager.put_point(cache_key, point)
    cached = cache_manager.get_point(cache_key)

    assert cached is not None
    assert cached.elevation == 123.45

    # Cache miss
    missing = cache_manager.get_point("nonexistent_key")
    assert missing is None


def test_cache_manager_point_expiration(cache_manager: ElevationCacheManager) -> None:
    """Test point cache expiration."""
    # Create cache manager with short TTL
    short_ttl_cache = ElevationCacheManager(
        cache_dir=cache_manager.cache_dir,
        point_cache_ttl=1,  # 1 second
    )

    point = ElevationPoint(longitude=-105.5, latitude=40.0, elevation=123.45)
    cache_key = "test_key"

    short_ttl_cache.put_point(cache_key, point)

    # Should be cached immediately
    assert short_ttl_cache.get_point(cache_key) is not None

    # Wait for expiration
    time.sleep(2)

    # Should be expired
    assert short_ttl_cache.get_point(cache_key) is None


def test_cache_manager_eviction(tmp_path: Path) -> None:
    """Test point cache eviction."""
    # Create cache manager with small max entries
    cache = ElevationCacheManager(
        cache_dir=tmp_path / "cache",
        max_memory_entries=5,
    )

    # Add more points than max
    for i in range(10):
        point = ElevationPoint(longitude=-105.5 + i, latitude=40.0, elevation=100.0)
        cache.put_point(f"key_{i}", point)
        time.sleep(0.01)  # Small delay to ensure different timestamps

    # Should have evicted some entries
    assert len(cache._point_cache) <= 5


def test_cache_manager_tile_operations(cache_manager: ElevationCacheManager) -> None:
    """Test tile metadata cache operations."""
    metadata = DEMTileMetadata(
        tile_id="test_tile_40_-105",
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
    )

    # Put and get
    cache_manager.put_tile_metadata(metadata)
    cached = cache_manager.get_tile_metadata("test_tile_40_-105")

    assert cached is not None
    assert cached.tile_id == "test_tile_40_-105"
    assert cached.min_lon == -106.0


def test_cache_manager_list_tiles(cache_manager: ElevationCacheManager) -> None:
    """Test listing cached tiles."""
    # Add some tiles
    for i in range(3):
        metadata = DEMTileMetadata(
            tile_id=f"tile_{i}",
            min_lon=-106.0 + i,
            min_lat=40.0,
            max_lon=-105.0 + i,
            max_lat=41.0,
            resolution=1.0,
        )
        cache_manager.put_tile_metadata(metadata)

    tiles = cache_manager.list_tiles()
    assert len(tiles) >= 3


def test_cache_manager_clear_point_cache(cache_manager: ElevationCacheManager) -> None:
    """Test clearing point cache."""
    # Add some points
    for i in range(5):
        point = ElevationPoint(longitude=-105.5 + i, latitude=40.0, elevation=100.0)
        cache_manager.put_point(f"key_{i}", point)

    assert len(cache_manager._point_cache) == 5

    count = cache_manager.clear_point_cache()
    assert count == 5
    assert len(cache_manager._point_cache) == 0


def test_cache_manager_clear_expired(cache_manager: ElevationCacheManager) -> None:
    """Test clearing expired points."""
    # Create cache with short TTL
    short_cache = ElevationCacheManager(
        cache_dir=cache_manager.cache_dir,
        point_cache_ttl=1,
    )

    # Add some points
    for i in range(3):
        point = ElevationPoint(longitude=-105.5 + i, latitude=40.0, elevation=100.0)
        short_cache.put_point(f"key_{i}", point)

    # Wait for expiration
    time.sleep(2)

    # Clear expired
    count = short_cache.clear_expired_points()
    assert count == 3


def test_cache_manager_statistics(cache_manager: ElevationCacheManager) -> None:
    """Test cache statistics."""
    # Add some data
    point = ElevationPoint(longitude=-105.5, latitude=40.0, elevation=100.0)
    cache_manager.put_point("key_1", point)

    stats = cache_manager.get_statistics()

    assert "cache_dir" in stats
    assert "point_cache" in stats
    assert "tile_cache" in stats
    assert stats["point_cache"]["entries"] == 1


def test_cache_manager_optimize(cache_manager: ElevationCacheManager) -> None:
    """Test cache optimization."""
    # Add expired points
    short_cache = ElevationCacheManager(
        cache_dir=cache_manager.cache_dir,
        point_cache_ttl=1,
    )

    for i in range(3):
        point = ElevationPoint(longitude=-105.5 + i, latitude=40.0, elevation=100.0)
        short_cache.put_point(f"key_{i}", point)

    time.sleep(2)

    result = short_cache.optimize()
    assert result["expired_points_cleared"] == 3


# Model Tests


def test_elevation_point_creation() -> None:
    """Test ElevationPoint creation."""
    point = ElevationPoint(
        longitude=-105.5,
        latitude=40.0,
        elevation=123.45,
        unit=ElevationUnit.METERS,
        datum=ElevationDatum.NAVD88,
    )

    assert point.longitude == -105.5
    assert point.latitude == 40.0
    assert point.elevation == 123.45
    assert point.unit == ElevationUnit.METERS


def test_elevation_point_to_dict() -> None:
    """Test ElevationPoint to_dict."""
    point = ElevationPoint(
        longitude=-105.5,
        latitude=40.0,
        elevation=123.45,
        unit=ElevationUnit.METERS,
    )

    data = point.to_dict()
    assert data["longitude"] == -105.5
    assert data["elevation"] == 123.45
    assert data["unit"] == "meters"


def test_elevation_query_creation() -> None:
    """Test ElevationQuery creation."""
    query = ElevationQuery(
        query_id="test_123",
        query_type="point",
        status=ElevationQueryStatus.SUCCESS,
        point_count=1,
        success_count=1,
    )

    assert query.query_id == "test_123"
    assert query.status == ElevationQueryStatus.SUCCESS


def test_dem_tile_metadata_creation() -> None:
    """Test DEMTileMetadata creation."""
    metadata = DEMTileMetadata(
        tile_id="tile_40_-105",
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
    )

    assert metadata.tile_id == "tile_40_-105"
    assert metadata.bounds == (-106.0, 40.0, -105.0, 41.0)


def test_dem_tile_request_creation() -> None:
    """Test DEMTileRequest creation."""
    request = DEMTileRequest(
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
    )

    assert request.bounds == (-106.0, 40.0, -105.0, 41.0)
    assert request.width_degrees == 1.0
    assert request.height_degrees == 1.0


def test_dem_tile_request_validation() -> None:
    """Test DEMTileRequest validation."""
    # Invalid longitude range
    with pytest.raises(ValueError):
        DEMTileRequest(
            min_lon=-105.0,
            min_lat=40.0,
            max_lon=-106.0,  # max < min
            max_lat=41.0,
        )

    # Invalid latitude range
    with pytest.raises(ValueError):
        DEMTileRequest(
            min_lon=-106.0,
            min_lat=41.0,
            max_lon=-105.0,
            max_lat=40.0,  # max < min
        )


def test_elevation_batch_response_statistics() -> None:
    """Test ElevationBatchResponse statistics computation."""
    query = ElevationQuery(
        query_id="test_batch",
        query_type="batch",
        point_count=3,
    )

    points = [
        ElevationPoint(longitude=-105.5, latitude=40.0, elevation=100.0),
        ElevationPoint(longitude=-105.6, latitude=40.1, elevation=150.0),
        ElevationPoint(longitude=-105.7, latitude=40.2, elevation=200.0),
    ]

    response = ElevationBatchResponse(query=query, points=points)
    response.compute_statistics()

    assert response.min_elevation == 100.0
    assert response.max_elevation == 200.0
    assert response.mean_elevation == 150.0
    assert response.elevation_range == 100.0


# Integration Tests


@pytest.mark.asyncio
async def test_full_workflow_point_query(tmp_path: Path) -> None:
    """Test full workflow for point elevation query."""
    config = USGSClientConfig(cache_dir=tmp_path / "cache")
    client = USGSClient(config=config)

    mock_response = {"value": 123.45, "resolution": 1.0, "units": "Meters"}

    with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        # First query - should hit API
        point1 = await client.query_point_elevation(-105.5, 40.0)
        assert point1.elevation == 123.45
        assert mock_request.call_count == 1

        # Second query - should hit cache
        point2 = await client.query_point_elevation(-105.5, 40.0)
        assert point2.elevation == 123.45
        assert mock_request.call_count == 1  # No additional call


@pytest.mark.asyncio
async def test_full_workflow_batch_query(tmp_path: Path) -> None:
    """Test full workflow for batch elevation query."""
    config = USGSClientConfig(cache_dir=tmp_path / "cache", batch_size=10)
    client = USGSClient(config=config)

    points = [(-105.5, 40.0), (-105.6, 40.1), (-105.7, 40.2)]

    mock_response = {"value": 123.45, "resolution": 1.0, "units": "Meters"}

    with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        response = await client.query_batch_elevation(points)

        assert response.query.point_count == 3
        assert response.query.success_count == 3
        assert len(response.points) == 3


# Additional tests for coverage


def test_parser_parse_batch_response(parser: USGSResponseParser) -> None:
    """Test parsing batch responses."""
    responses = [
        {"value": 100.0, "resolution": 1.0, "units": "Meters"},
        {"value": 150.0, "resolution": 1.0, "units": "Meters"},
    ]
    coordinates = [(-105.5, 40.0), (-105.6, 40.1)]

    points = parser.parse_batch_response(responses, coordinates)

    assert len(points) == 2
    assert points[0].elevation == 100.0
    assert points[1].elevation == 150.0


def test_parser_parse_batch_response_mismatched_length(parser: USGSResponseParser) -> None:
    """Test parsing batch responses with mismatched lengths."""
    responses = [{"value": 100.0}]
    coordinates = [(-105.5, 40.0), (-105.6, 40.1)]

    points = parser.parse_batch_response(responses, coordinates)

    # Should pad with empty responses
    assert len(points) == 2


def test_parser_epqs_response_with_unit_conversion(parser: USGSResponseParser) -> None:
    """Test parsing EPQS response with unit conversion."""
    data = {
        "value": 100.0,
        "units": "Feet",
        "resolution": 1.0,
    }

    point = parser.parse_epqs_response(data, -105.5, 40.0, ElevationUnit.METERS)

    # Should convert feet to meters
    assert point.elevation == pytest.approx(100.0 * 0.3048, rel=0.01)


def test_parser_epqs_response_invalid_elevation(parser: USGSResponseParser) -> None:
    """Test parsing EPQS response with invalid elevation value."""
    data = {"value": "invalid", "units": "Meters"}

    point = parser.parse_epqs_response(data, -105.5, 40.0)

    assert point.elevation is None


def test_parser_determine_data_source_variations(parser: USGSResponseParser) -> None:
    """Test data source determination with various inputs."""
    # Test 1-meter
    assert parser._determine_data_source({"data_source": "1-meter"}, None) == ElevationDataSource.USGS_3DEP_1M

    # Test 1/3 arc
    assert parser._determine_data_source({"data_source": "1/3 arc-second"}, None) == ElevationDataSource.USGS_3DEP_1_3M

    # Test NED
    assert parser._determine_data_source({"data_source": "NED"}, None) == ElevationDataSource.NED

    # Test SRTM
    assert parser._determine_data_source({"data_source": "SRTM"}, None) == ElevationDataSource.SRTM


def test_parser_extract_datum_variations(parser: USGSResponseParser) -> None:
    """Test datum extraction with various inputs."""
    assert parser._extract_datum({"datum": "WGS84"}) == ElevationDatum.WGS84
    assert parser._extract_datum({"datum": "MSL"}) == ElevationDatum.MSL
    assert parser._extract_datum({"vertical_datum": "NGVD29"}) == ElevationDatum.NGVD29


@pytest.mark.asyncio
async def test_client_make_request_retry_success(usgs_client: USGSClient) -> None:
    """Test request retry succeeds after failures."""
    mock_response = {"value": 123.45}

    with patch.object(usgs_client.client, "get", new_callable=AsyncMock) as mock_get:
        # Fail twice, then succeed
        mock_get.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.HTTPError("Server error"),
            Mock(json=lambda: mock_response, raise_for_status=lambda: None),
        ]

        result = await usgs_client._make_request("https://test.com", {})

        assert result == mock_response
        assert mock_get.call_count == 3


@pytest.mark.asyncio
async def test_query_point_elevation_with_feet(usgs_client: USGSClient) -> None:
    """Test point elevation query with feet unit."""
    mock_response = {"value": 100.0, "resolution": 1.0, "units": "Feet"}

    with patch.object(usgs_client, "_make_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        point = await usgs_client.query_point_elevation(-105.5, 40.0, ElevationUnit.FEET)

        assert point.unit == ElevationUnit.FEET
        assert point.elevation == 100.0


def test_cache_manager_get_tile_path_exists(cache_manager: ElevationCacheManager, tmp_path: Path) -> None:
    """Test getting tile path when file exists."""
    # Create metadata and file
    metadata = DEMTileMetadata(
        tile_id="test_tile",
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
        file_path=str(tmp_path / "test_tile.tif"),
    )

    # Create the file
    (tmp_path / "test_tile.tif").write_text("test data")

    cache_manager.put_tile_metadata(metadata)

    tile_path = cache_manager.get_tile_path("test_tile")
    assert tile_path is not None
    assert tile_path.exists()


def test_cache_manager_get_tile_path_missing(cache_manager: ElevationCacheManager) -> None:
    """Test getting tile path when file doesn't exist."""
    tile_path = cache_manager.get_tile_path("nonexistent_tile")
    assert tile_path is None


def test_cache_manager_has_tile(cache_manager: ElevationCacheManager, tmp_path: Path) -> None:
    """Test checking if tile exists."""
    # Create metadata and file
    metadata = DEMTileMetadata(
        tile_id="test_tile",
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
        file_path=str(tmp_path / "test_tile.tif"),
    )

    (tmp_path / "test_tile.tif").write_text("test data")
    cache_manager.put_tile_metadata(metadata)

    assert cache_manager.has_tile("test_tile") is True
    assert cache_manager.has_tile("missing_tile") is False


def test_cache_manager_delete_tile(cache_manager: ElevationCacheManager, tmp_path: Path) -> None:
    """Test deleting a cached tile."""
    # Create metadata and file
    tile_file = tmp_path / "test_tile.tif"
    tile_file.write_text("test data")

    metadata = DEMTileMetadata(
        tile_id="test_tile",
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
        file_path=str(tile_file),
    )

    cache_manager.put_tile_metadata(metadata)

    # Delete the tile
    result = cache_manager.delete_tile("test_tile")
    assert result is True
    assert not tile_file.exists()

    # Try deleting non-existent tile
    result = cache_manager.delete_tile("missing_tile")
    assert result is False


def test_cache_manager_cleanup_old_tiles(cache_manager: ElevationCacheManager, tmp_path: Path) -> None:
    """Test cleaning up old tiles."""
    from datetime import timedelta

    # Create old metadata
    old_time = datetime.utcnow() - timedelta(days=100)

    tile_file = tmp_path / "old_tile.tif"
    tile_file.write_text("test data")

    metadata = DEMTileMetadata(
        tile_id="old_tile",
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
        file_path=str(tile_file),
        last_accessed=old_time,
    )

    cache_manager.put_tile_metadata(metadata)

    # Clean up tiles older than 90 days
    deleted = cache_manager.cleanup_old_tiles(days=90)
    assert deleted == 1


def test_elevation_batch_response_empty_points() -> None:
    """Test batch response with no points."""
    query = ElevationQuery(
        query_id="test",
        query_type="batch",
        point_count=0,
    )

    response = ElevationBatchResponse(query=query, points=[])
    response.compute_statistics()

    assert response.min_elevation is None
    assert response.max_elevation is None
    assert response.mean_elevation is None


def test_dem_tile_request_properties() -> None:
    """Test DEM tile request properties."""
    request = DEMTileRequest(
        min_lon=-106.0,
        min_lat=40.0,
        max_lon=-105.0,
        max_lat=41.0,
        resolution=1.0,
    )

    assert request.width_degrees == 1.0
    assert request.height_degrees == 1.0
    assert request.area_sq_degrees == 1.0

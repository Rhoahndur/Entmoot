"""
Tests for FEMA National Flood Hazard Layer integration.

Tests API client, parser, caching, and error handling with mocked responses.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict

import httpx
import pytest
import respx

from entmoot.integrations.fema.cache import CacheManager, InMemoryCache
from entmoot.integrations.fema.client import FEMAClient, FEMAClientConfig, RateLimiter
from entmoot.integrations.fema.parser import FEMAResponseParser
from entmoot.models.regulatory import (
    FloodplainData,
    FloodZone,
    FloodZoneType,
    RegulatoryDataSource,
)


# Mock FEMA API responses
MOCK_ZONE_AE_FEATURE = {
    "attributes": {
        "FLD_ZONE": "AE",
        "ZONE_SUBTY": None,
        "STATIC_BFE": 15.5,
        "DEPTH": None,
        "VELOCITY": None,
        "FLOODWAY": "NOT FLOODWAY",
        "EFF_DATE": 1592524800000,  # 2020-06-19 in milliseconds
        "STUDY_TYP": "Detailed Study",
        "SOURCE_CIT": "06085C0125E",
        "V_DATUM": "NAVD88",
    },
    "geometry": {
        "rings": [
            [
                [-122.084, 37.422],
                [-122.083, 37.422],
                [-122.083, 37.421],
                [-122.084, 37.421],
                [-122.084, 37.422],
            ]
        ]
    },
}

MOCK_ZONE_X_FEATURE = {
    "attributes": {
        "FLD_ZONE": "X",
        "ZONE_SUBTY": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
        "STATIC_BFE": None,
        "DEPTH": None,
        "VELOCITY": None,
        "FLOODWAY": "NOT FLOODWAY",
        "EFF_DATE": 1592524800000,
        "STUDY_TYP": "Detailed Study",
        "SOURCE_CIT": "06085C0125E",
        "V_DATUM": "NAVD88",
    },
    "geometry": {
        "rings": [
            [
                [-122.085, 37.423],
                [-122.084, 37.423],
                [-122.084, 37.422],
                [-122.085, 37.422],
                [-122.085, 37.423],
            ]
        ]
    },
}

MOCK_QUERY_RESPONSE_WITH_ZONE = {
    "features": [MOCK_ZONE_AE_FEATURE],
    "fieldAliases": {},
}

MOCK_QUERY_RESPONSE_EMPTY = {
    "features": [],
    "fieldAliases": {},
}

MOCK_QUERY_RESPONSE_MULTIPLE = {
    "features": [MOCK_ZONE_AE_FEATURE, MOCK_ZONE_X_FEATURE],
    "fieldAliases": {},
}


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter(calls=10, period=1.0)
        assert limiter.calls == 10
        assert limiter.period == 1.0
        assert limiter.tokens == 10.0

    def test_rate_limiter_acquire_tokens(self) -> None:
        """Test acquiring tokens from rate limiter."""
        limiter = RateLimiter(calls=5, period=1.0)

        # Should be able to acquire 5 tokens immediately
        for _ in range(5):
            assert limiter.acquire() is True

        # 6th call should fail (no tokens left)
        assert limiter.acquire() is False

    def test_rate_limiter_wait_time(self) -> None:
        """Test calculating wait time for next token."""
        limiter = RateLimiter(calls=10, period=1.0)

        # Consume all tokens
        for _ in range(10):
            limiter.acquire()

        # Should need to wait for next token
        wait_time = limiter.wait_time()
        assert wait_time > 0
        assert wait_time <= 0.2  # Should be ~0.1s per token

    def test_rate_limiter_token_refill(self) -> None:
        """Test tokens refill over time."""
        limiter = RateLimiter(calls=5, period=0.5)

        # Consume all tokens
        for _ in range(5):
            limiter.acquire()

        # Wait for tokens to refill
        time.sleep(0.6)

        # Should be able to acquire tokens again
        assert limiter.acquire() is True


class TestFEMAResponseParser:
    """Tests for the FEMAResponseParser class."""

    def test_parser_initialization(self) -> None:
        """Test parser initializes correctly."""
        parser = FEMAResponseParser()
        assert parser is not None

    def test_parse_zone_type_ae(self) -> None:
        """Test parsing AE zone type."""
        parser = FEMAResponseParser()
        zone_type = parser._parse_zone_type("AE")
        assert zone_type == FloodZoneType.AE

    def test_parse_zone_type_variations(self) -> None:
        """Test parsing various zone type formats."""
        parser = FEMAResponseParser()

        test_cases = [
            ("A", FloodZoneType.A),
            ("AE", FloodZoneType.AE),
            ("X", FloodZoneType.X),
            ("VE", FloodZoneType.VE),
            ("OPEN WATER", FloodZoneType.OPEN_WATER),
            (None, FloodZoneType.UNKNOWN),
            ("", FloodZoneType.UNKNOWN),
            ("INVALID", FloodZoneType.UNKNOWN),
        ]

        for input_zone, expected_type in test_cases:
            result = parser._parse_zone_type(input_zone)
            assert result == expected_type, f"Failed for input: {input_zone}"

    def test_parse_geometry_polygon(self) -> None:
        """Test parsing ArcGIS polygon geometry to WKT."""
        parser = FEMAResponseParser()

        geometry = {
            "rings": [
                [
                    [-122.084, 37.422],
                    [-122.083, 37.422],
                    [-122.083, 37.421],
                    [-122.084, 37.421],
                    [-122.084, 37.422],
                ]
            ]
        }

        wkt = parser._parse_geometry(geometry)
        assert wkt is not None
        assert wkt.startswith("POLYGON")
        assert "-122.084" in wkt
        assert "37.422" in wkt

    def test_parse_bfe_numeric(self) -> None:
        """Test parsing numeric BFE values."""
        parser = FEMAResponseParser()

        assert parser._parse_bfe(15.5) == 15.5
        assert parser._parse_bfe(100) == 100.0
        assert parser._parse_bfe("20.3") == 20.3
        assert parser._parse_bfe("+15.5") == 15.5
        assert parser._parse_bfe(None) is None
        assert parser._parse_bfe("") is None
        assert parser._parse_bfe("N/A") is None

    def test_parse_date_timestamp(self) -> None:
        """Test parsing FEMA date timestamps."""
        parser = FEMAResponseParser()

        # FEMA uses milliseconds since epoch
        timestamp_ms = 1592524800000  # 2020-06-19
        result = parser._parse_date(timestamp_ms)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2020
        assert result.month == 6
        assert result.day == 19

    def test_parse_feature_complete(self) -> None:
        """Test parsing a complete FEMA feature."""
        parser = FEMAResponseParser()
        zone = parser._parse_feature(MOCK_ZONE_AE_FEATURE)

        assert zone is not None
        assert isinstance(zone, FloodZone)
        assert zone.zone_type == FloodZoneType.AE
        assert zone.base_flood_elevation == 15.5
        assert zone.geometry_wkt is not None
        assert zone.floodway is False
        assert zone.coastal_zone is False
        assert zone.effective_date is not None

    def test_parse_feature_no_geometry(self) -> None:
        """Test parsing feature with no geometry returns None."""
        parser = FEMAResponseParser()

        feature_no_geom = {
            "attributes": {"FLD_ZONE": "AE"},
            "geometry": None,
        }

        zone = parser._parse_feature(feature_no_geom)
        assert zone is None

    def test_parse_query_response_empty(self) -> None:
        """Test parsing empty query response."""
        parser = FEMAResponseParser()
        result = parser.parse_query_response(
            MOCK_QUERY_RESPONSE_EMPTY,
            longitude=-122.084,
            latitude=37.422,
        )

        assert isinstance(result, FloodplainData)
        assert len(result.zones) == 0
        assert result.in_sfha is False
        assert result.insurance_required is False
        assert result.location_lon == -122.084
        assert result.location_lat == 37.422

    def test_parse_query_response_with_zone(self) -> None:
        """Test parsing query response with flood zone."""
        parser = FEMAResponseParser()
        result = parser.parse_query_response(
            MOCK_QUERY_RESPONSE_WITH_ZONE,
            longitude=-122.084,
            latitude=37.422,
        )

        assert isinstance(result, FloodplainData)
        assert len(result.zones) == 1
        assert result.zones[0].zone_type == FloodZoneType.AE
        assert result.in_sfha is True
        assert result.insurance_required is True
        assert result.highest_risk_zone == FloodZoneType.AE

    def test_parse_query_response_multiple_zones(self) -> None:
        """Test parsing response with multiple zones."""
        parser = FEMAResponseParser()
        result = parser.parse_query_response(
            MOCK_QUERY_RESPONSE_MULTIPLE,
            longitude=-122.084,
            latitude=37.422,
        )

        assert len(result.zones) == 2
        assert result.highest_risk_zone == FloodZoneType.AE  # AE is higher risk than X
        assert result.in_sfha is True

    def test_determine_highest_risk_zone(self) -> None:
        """Test determining highest risk zone from multiple zones."""
        parser = FEMAResponseParser()

        zones = [
            FloodZone(
                zone_type=FloodZoneType.X,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            ),
            FloodZone(
                zone_type=FloodZoneType.AE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            ),
            FloodZone(
                zone_type=FloodZoneType.VE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            ),
        ]

        highest = parser._determine_highest_risk_zone(zones)
        assert highest == FloodZoneType.VE  # VE is highest risk


class TestInMemoryCache:
    """Tests for the InMemoryCache backend."""

    def test_cache_initialization(self) -> None:
        """Test cache initializes correctly."""
        cache = InMemoryCache()
        assert cache is not None
        stats = cache.get_stats()
        assert stats["backend"] == "in-memory"
        assert stats["entries"] == 0

    def test_cache_put_and_get(self) -> None:
        """Test storing and retrieving from cache."""
        cache = InMemoryCache()

        data = FloodplainData(location_lon=-122.0, location_lat=37.0)
        timestamp = time.time()

        cache.put("test_key", data, timestamp)

        result = cache.get("test_key")
        assert result is not None
        retrieved_data, retrieved_timestamp = result
        assert retrieved_data.location_lon == -122.0
        assert retrieved_timestamp == timestamp

    def test_cache_miss(self) -> None:
        """Test cache miss returns None."""
        cache = InMemoryCache()
        result = cache.get("nonexistent_key")
        assert result is None

    def test_cache_delete(self) -> None:
        """Test deleting from cache."""
        cache = InMemoryCache()

        data = FloodplainData(location_lon=-122.0, location_lat=37.0)
        cache.put("test_key", data, time.time())

        # Verify it's there
        assert cache.get("test_key") is not None

        # Delete it
        cache.delete("test_key")

        # Verify it's gone
        assert cache.get("test_key") is None

    def test_cache_clear(self) -> None:
        """Test clearing entire cache."""
        cache = InMemoryCache()

        # Add multiple entries
        for i in range(5):
            data = FloodplainData(location_lon=-122.0 + i, location_lat=37.0)
            cache.put(f"key_{i}", data, time.time())

        stats = cache.get_stats()
        assert stats["entries"] == 5

        # Clear cache
        cache.clear()

        stats = cache.get_stats()
        assert stats["entries"] == 0

    def test_cache_stats(self) -> None:
        """Test cache statistics tracking."""
        cache = InMemoryCache()

        data = FloodplainData(location_lon=-122.0, location_lat=37.0)
        cache.put("test_key", data, time.time())

        # Hit
        cache.get("test_key")
        # Miss
        cache.get("nonexistent")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0


class TestCacheManager:
    """Tests for the CacheManager."""

    def test_manager_initialization_in_memory(self) -> None:
        """Test manager initializes with in-memory backend."""
        manager = CacheManager(redis_url=None, ttl_seconds=300)
        assert manager is not None

        stats = manager.get_stats()
        assert stats["backend"] == "in-memory"
        assert stats["ttl_seconds"] == 300

    def test_manager_put_and_get(self) -> None:
        """Test manager put and get operations."""
        manager = CacheManager(ttl_seconds=10)

        data = FloodplainData(
            location_lon=-122.084,
            location_lat=37.422,
            in_sfha=True,
        )

        manager.put("test_key", data)

        result = manager.get("test_key")
        assert result is not None
        assert result.location_lon == -122.084
        assert result.cache_hit is True

    def test_manager_expiration(self) -> None:
        """Test cache entry expiration."""
        manager = CacheManager(ttl_seconds=1)

        data = FloodplainData(location_lon=-122.0, location_lat=37.0)
        manager.put("test_key", data)

        # Should be available immediately
        assert manager.get("test_key") is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        assert manager.get("test_key") is None

    def test_manager_clear(self) -> None:
        """Test clearing cache manager."""
        manager = CacheManager()

        data = FloodplainData(location_lon=-122.0, location_lat=37.0)
        manager.put("test_key", data)

        assert manager.get("test_key") is not None

        manager.clear()

        assert manager.get("test_key") is None


@pytest.mark.asyncio
class TestFEMAClient:
    """Tests for the FEMAClient class."""

    def test_client_initialization(self) -> None:
        """Test client initializes with default config."""
        client = FEMAClient()
        assert client is not None
        assert client.config.base_url is not None
        assert client.config.timeout == 5.0

    def test_client_custom_config(self) -> None:
        """Test client initializes with custom config."""
        config = FEMAClientConfig(
            timeout=10.0,
            max_retries=5,
            cache_ttl=3600,
        )
        client = FEMAClient(config)
        assert client.config.timeout == 10.0
        assert client.config.max_retries == 5
        assert client.config.cache_ttl == 3600

    def test_generate_cache_key(self) -> None:
        """Test cache key generation."""
        client = FEMAClient()

        key1 = client._generate_cache_key(lon=-122.084, lat=37.422)
        key2 = client._generate_cache_key(lon=-122.084, lat=37.422)
        key3 = client._generate_cache_key(lon=-122.085, lat=37.422)

        # Same params should generate same key
        assert key1 == key2
        # Different params should generate different key
        assert key1 != key3

    @respx.mock
    async def test_query_by_point_success(self) -> None:
        """Test successful point query."""
        # Mock the FEMA API endpoint
        respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(return_value=httpx.Response(200, json=MOCK_QUERY_RESPONSE_WITH_ZONE))

        async with FEMAClient() as client:
            result = await client.query_by_point(-122.084, 37.422)

            assert isinstance(result, FloodplainData)
            assert result.location_lon == -122.084
            assert result.location_lat == 37.422
            assert len(result.zones) == 1
            assert result.in_sfha is True

    @respx.mock
    async def test_query_by_point_empty_response(self) -> None:
        """Test point query with no flood zones."""
        respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(return_value=httpx.Response(200, json=MOCK_QUERY_RESPONSE_EMPTY))

        async with FEMAClient() as client:
            result = await client.query_by_point(-122.084, 37.422)

            assert len(result.zones) == 0
            assert result.in_sfha is False

    @respx.mock
    async def test_query_by_bbox_success(self) -> None:
        """Test successful bounding box query."""
        respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(return_value=httpx.Response(200, json=MOCK_QUERY_RESPONSE_MULTIPLE))

        async with FEMAClient() as client:
            result = await client.query_by_bbox(
                min_lon=-122.085,
                min_lat=37.421,
                max_lon=-122.083,
                max_lat=37.423,
            )

            assert isinstance(result, FloodplainData)
            assert len(result.zones) == 2
            assert result.bbox_min_lon == -122.085
            assert result.bbox_max_lon == -122.083

    @respx.mock
    async def test_query_caching(self) -> None:
        """Test that queries are cached."""
        mock_route = respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(return_value=httpx.Response(200, json=MOCK_QUERY_RESPONSE_WITH_ZONE))

        async with FEMAClient() as client:
            # First query - should hit API
            result1 = await client.query_by_point(-122.084, 37.422)
            assert result1.cache_hit is False

            # Second query - should hit cache
            result2 = await client.query_by_point(-122.084, 37.422)
            assert result2.cache_hit is True

            # API should only be called once
            assert mock_route.call_count == 1

    @respx.mock
    async def test_query_timeout_retry(self) -> None:
        """Test retry logic on timeout."""
        # First two attempts timeout, third succeeds
        mock_route = respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                httpx.TimeoutException("Timeout"),
                httpx.Response(200, json=MOCK_QUERY_RESPONSE_WITH_ZONE),
            ]
        )

        config = FEMAClientConfig(max_retries=3, retry_backoff_factor=0.1)
        async with FEMAClient(config) as client:
            result = await client.query_by_point(-122.084, 37.422)

            assert isinstance(result, FloodplainData)
            assert mock_route.call_count == 3

    @respx.mock
    async def test_query_max_retries_exceeded(self) -> None:
        """Test behavior when max retries exceeded."""
        respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(side_effect=httpx.TimeoutException("Timeout"))

        config = FEMAClientConfig(max_retries=2, retry_backoff_factor=0.1)
        async with FEMAClient(config) as client:
            # Should return empty result gracefully
            result = await client.query_by_point(-122.084, 37.422)

            assert isinstance(result, FloodplainData)
            assert len(result.zones) == 0

    @respx.mock
    async def test_query_api_error(self) -> None:
        """Test handling of API error responses."""
        error_response = {
            "error": {
                "code": 400,
                "message": "Invalid geometry",
            }
        }

        respx.get(
            "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
        ).mock(return_value=httpx.Response(200, json=error_response))

        async with FEMAClient() as client:
            # Should return empty result gracefully
            result = await client.query_by_point(-122.084, 37.422)

            assert isinstance(result, FloodplainData)
            assert len(result.zones) == 0

    async def test_cache_stats(self) -> None:
        """Test getting cache statistics."""
        client = FEMAClient()
        stats = client.get_cache_stats()

        assert "enabled" in stats
        assert "entries" in stats
        assert "ttl_seconds" in stats
        assert stats["enabled"] is True

    async def test_clear_cache(self) -> None:
        """Test clearing client cache."""
        client = FEMAClient()

        # Add something to cache
        data = FloodplainData(location_lon=-122.0, location_lat=37.0)
        cache_key = client._generate_cache_key(lon=-122.0, lat=37.0)
        client._put_in_cache(cache_key, data)

        stats_before = client.get_cache_stats()
        assert stats_before["entries"] > 0

        client.clear_cache()

        stats_after = client.get_cache_stats()
        assert stats_after["entries"] == 0


class TestFloodZoneModels:
    """Tests for FloodZone model methods."""

    def test_flood_zone_is_high_risk(self) -> None:
        """Test identifying high-risk flood zones."""
        zone_ae = FloodZone(
            zone_type=FloodZoneType.AE,
            geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
        assert zone_ae.is_high_risk() is True

        zone_x = FloodZone(
            zone_type=FloodZoneType.X,
            geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
        assert zone_x.is_high_risk() is False

    def test_flood_zone_requires_insurance(self) -> None:
        """Test determining if insurance is required."""
        zone_ve = FloodZone(
            zone_type=FloodZoneType.VE,
            geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
        assert zone_ve.requires_flood_insurance() is True

        zone_c = FloodZone(
            zone_type=FloodZoneType.C,
            geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
        assert zone_c.requires_flood_insurance() is False


class TestFloodplainDataModels:
    """Tests for FloodplainData model methods."""

    def test_get_max_bfe(self) -> None:
        """Test getting maximum BFE from multiple zones."""
        zones = [
            FloodZone(
                zone_type=FloodZoneType.AE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
                base_flood_elevation=15.5,
            ),
            FloodZone(
                zone_type=FloodZoneType.AE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
                base_flood_elevation=18.2,
            ),
            FloodZone(
                zone_type=FloodZoneType.X,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
                base_flood_elevation=None,
            ),
        ]

        data = FloodplainData(zones=zones)
        max_bfe = data.get_max_bfe()

        assert max_bfe == 18.2

    def test_get_max_bfe_no_zones(self) -> None:
        """Test getting max BFE with no zones."""
        data = FloodplainData(zones=[])
        assert data.get_max_bfe() is None

    def test_get_zone_summary(self) -> None:
        """Test getting zone type summary."""
        zones = [
            FloodZone(
                zone_type=FloodZoneType.AE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            ),
            FloodZone(
                zone_type=FloodZoneType.AE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            ),
            FloodZone(
                zone_type=FloodZoneType.X,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            ),
        ]

        data = FloodplainData(zones=zones)
        summary = data.get_zone_summary()

        assert summary["AE"] == 2
        assert summary["X"] == 1


class TestRegulatoryConstraint:
    """Tests for RegulatoryConstraint model."""

    def test_from_floodplain_data_with_sfha(self) -> None:
        """Test creating RegulatoryConstraint from FloodplainData with SFHA."""
        from entmoot.models.regulatory import RegulatoryConstraint

        zones = [
            FloodZone(
                zone_type=FloodZoneType.AE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
                base_flood_elevation=15.5,
                effective_date=datetime(2020, 6, 19),
            ),
        ]

        floodplain = FloodplainData(
            zones=zones,
            in_sfha=True,
            insurance_required=True,
            community_name="Test County",
            panel_id="12345C0125E",
        )

        constraint = RegulatoryConstraint.from_floodplain_data(floodplain)

        assert constraint is not None
        assert constraint.constraint_type == "floodplain"
        assert constraint.severity == "high"
        assert constraint.affects_development is True
        assert constraint.requires_permit is True
        assert "AE" in constraint.description
        assert "15.5" in constraint.description

    def test_from_floodplain_data_no_sfha(self) -> None:
        """Test creating RegulatoryConstraint from FloodplainData without SFHA."""
        from entmoot.models.regulatory import RegulatoryConstraint

        floodplain = FloodplainData(
            zones=[],
            in_sfha=False,
        )

        constraint = RegulatoryConstraint.from_floodplain_data(floodplain)
        assert constraint is None

    def test_from_floodplain_data_v_zone(self) -> None:
        """Test constraint from V zone (highest severity)."""
        from entmoot.models.regulatory import RegulatoryConstraint

        zones = [
            FloodZone(
                zone_type=FloodZoneType.VE,
                geometry_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
                base_flood_elevation=20.0,
            ),
        ]

        floodplain = FloodplainData(
            zones=zones,
            in_sfha=True,
        )

        constraint = RegulatoryConstraint.from_floodplain_data(floodplain)
        assert constraint.severity == "high"


class TestParserEdgeCases:
    """Additional tests for parser edge cases."""

    def test_parse_zone_type_floodway(self) -> None:
        """Test parsing floodway zone type."""
        parser = FEMAResponseParser()
        zone_type = parser._parse_zone_type("FLOODWAY")
        assert zone_type == FloodZoneType.AE

    def test_parse_zone_type_x_protected(self) -> None:
        """Test parsing X protected zone type."""
        parser = FEMAResponseParser()
        zone_type = parser._parse_zone_type("X PROTECTED BY LEVEE")
        assert zone_type == FloodZoneType.X_PROTECTED

    def test_parse_bfe_with_plus(self) -> None:
        """Test parsing BFE with plus sign."""
        parser = FEMAResponseParser()
        assert parser._parse_bfe("+15.5") == 15.5

    def test_parse_date_string_formats(self) -> None:
        """Test parsing various date string formats."""
        parser = FEMAResponseParser()

        date1 = parser._parse_date("2020-06-19")
        assert date1 is not None
        assert date1.year == 2020

        date2 = parser._parse_date("06/19/2020")
        assert date2 is not None
        assert date2.year == 2020

    def test_parse_feature_with_floodway(self) -> None:
        """Test parsing feature with floodway."""
        parser = FEMAResponseParser()

        feature = {
            "attributes": {
                "FLD_ZONE": "AE",
                "FLOODWAY": "FLOODWAY",
            },
            "geometry": {
                "rings": [
                    [
                        [-122.084, 37.422],
                        [-122.083, 37.422],
                        [-122.083, 37.421],
                        [-122.084, 37.421],
                        [-122.084, 37.422],
                    ]
                ]
            },
        }

        zone = parser._parse_feature(feature)
        assert zone is not None
        assert zone.floodway is True

    def test_parse_query_response_invalid_data(self) -> None:
        """Test parsing response with invalid data."""
        parser = FEMAResponseParser()

        invalid_response = {"features": "not a list"}

        result = parser.parse_query_response(
            invalid_response,
            longitude=-122.0,
            latitude=37.0,
        )

        assert isinstance(result, FloodplainData)
        assert len(result.zones) == 0

    def test_determine_highest_risk_zone_empty(self) -> None:
        """Test determining highest risk with empty list."""
        parser = FEMAResponseParser()
        result = parser._determine_highest_risk_zone([])
        assert result is None

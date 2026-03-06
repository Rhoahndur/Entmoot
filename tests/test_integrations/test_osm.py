"""Tests for OpenStreetMap Overpass API integration."""

import time

import httpx
import pytest
import respx

from entmoot.integrations.osm.cache import OSMCache
from entmoot.integrations.osm.client import OSMClient, OSMClientConfig
from entmoot.integrations.osm.parser import OSMResponseParser
from entmoot.models.existing_conditions import (
    ExistingConditionsData,
    OSMFeatureType,
    OSMRoadClass,
    OSMUtilityType,
    OSMWaterType,
)

# ---------------------------------------------------------------------------
# Mock Overpass API responses
# ---------------------------------------------------------------------------

MOCK_NODES = [
    {"type": "node", "id": 1, "lon": -122.084, "lat": 37.422},
    {"type": "node", "id": 2, "lon": -122.083, "lat": 37.422},
    {"type": "node", "id": 3, "lon": -122.083, "lat": 37.421},
    {"type": "node", "id": 4, "lon": -122.084, "lat": 37.421},
    # Road nodes
    {"type": "node", "id": 10, "lon": -122.085, "lat": 37.422},
    {"type": "node", "id": 11, "lon": -122.082, "lat": 37.422},
    # Utility nodes
    {"type": "node", "id": 20, "lon": -122.086, "lat": 37.423},
    {"type": "node", "id": 21, "lon": -122.081, "lat": 37.423},
    # Water nodes
    {"type": "node", "id": 30, "lon": -122.085, "lat": 37.420},
    {"type": "node", "id": 31, "lon": -122.083, "lat": 37.420},
]

MOCK_BUILDING_WAY = {
    "type": "way",
    "id": 100,
    "nodes": [1, 2, 3, 4, 1],
    "tags": {"building": "yes", "building:levels": "2"},
}

MOCK_ROAD_RESIDENTIAL = {
    "type": "way",
    "id": 200,
    "nodes": [10, 11],
    "tags": {"highway": "residential", "name": "Oak Street"},
}

MOCK_ROAD_MOTORWAY = {
    "type": "way",
    "id": 201,
    "nodes": [10, 11],
    "tags": {"highway": "motorway", "ref": "I-280"},
}

MOCK_ROAD_SERVICE = {
    "type": "way",
    "id": 202,
    "nodes": [10, 11],
    "tags": {"highway": "service"},
}

MOCK_POWER_LINE = {
    "type": "way",
    "id": 300,
    "nodes": [20, 21],
    "tags": {"power": "line", "voltage": "115000"},
}

MOCK_POWER_LINE_LOW = {
    "type": "way",
    "id": 301,
    "nodes": [20, 21],
    "tags": {"power": "line", "voltage": "12000"},
}

MOCK_PIPELINE_GAS = {
    "type": "way",
    "id": 302,
    "nodes": [20, 21],
    "tags": {"man_made": "pipeline", "substance": "gas"},
}

MOCK_STREAM = {
    "type": "way",
    "id": 400,
    "nodes": [30, 31],
    "tags": {"waterway": "stream", "name": "Deer Creek"},
}

MOCK_RIVER = {
    "type": "way",
    "id": 401,
    "nodes": [30, 31],
    "tags": {"waterway": "river", "name": "Big River"},
}

MOCK_WETLAND = {
    "type": "way",
    "id": 402,
    "nodes": [1, 2, 3, 4, 1],
    "tags": {"natural": "wetland"},
}

MOCK_LAKE = {
    "type": "way",
    "id": 403,
    "nodes": [1, 2, 3, 4, 1],
    "tags": {"natural": "water", "water": "lake"},
}

MOCK_FULL_RESPONSE = {
    "version": 0.6,
    "elements": MOCK_NODES
    + [
        MOCK_BUILDING_WAY,
        MOCK_ROAD_RESIDENTIAL,
        MOCK_POWER_LINE,
        MOCK_STREAM,
    ],
}

MOCK_EMPTY_RESPONSE = {"version": 0.6, "elements": []}


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestOSMResponseParser:
    """Tests for the OSM response parser."""

    def setup_method(self) -> None:
        """Set up parser instance for each test."""
        self.parser = OSMResponseParser()

    def test_parse_empty_response(self) -> None:
        """Empty response produces zero features."""
        result = self.parser.parse_response(MOCK_EMPTY_RESPONSE)
        assert result.feature_count == 0
        assert len(result.buildings) == 0
        assert len(result.roads) == 0

    def test_parse_building(self) -> None:
        """Building way is parsed with correct type and polygon geometry."""
        data = {"elements": MOCK_NODES + [MOCK_BUILDING_WAY]}
        result = self.parser.parse_response(data)
        assert len(result.buildings) == 1
        assert result.buildings[0].feature_type == OSMFeatureType.BUILDING
        assert result.buildings[0].osm_id == 100
        assert "POLYGON" in result.buildings[0].geometry_wkt

    def test_parse_road_residential(self) -> None:
        """Residential road is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_ROAD_RESIDENTIAL]}
        result = self.parser.parse_response(data)
        assert len(result.roads) == 1
        assert result.roads[0].road_class == OSMRoadClass.RESIDENTIAL

    def test_parse_road_motorway(self) -> None:
        """Motorway is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_ROAD_MOTORWAY]}
        result = self.parser.parse_response(data)
        assert len(result.roads) == 1
        assert result.roads[0].road_class == OSMRoadClass.MOTORWAY

    def test_parse_road_service(self) -> None:
        """Service road is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_ROAD_SERVICE]}
        result = self.parser.parse_response(data)
        assert len(result.roads) == 1
        assert result.roads[0].road_class == OSMRoadClass.SERVICE

    def test_parse_high_voltage_line(self) -> None:
        """High voltage power line is classified as HIGH_VOLTAGE."""
        data = {"elements": MOCK_NODES + [MOCK_POWER_LINE]}
        result = self.parser.parse_response(data)
        assert len(result.utilities) == 1
        assert result.utilities[0].utility_type == OSMUtilityType.HIGH_VOLTAGE

    def test_parse_low_voltage_line(self) -> None:
        """Low voltage power line is classified as POWER_LINE."""
        data = {"elements": MOCK_NODES + [MOCK_POWER_LINE_LOW]}
        result = self.parser.parse_response(data)
        assert len(result.utilities) == 1
        assert result.utilities[0].utility_type == OSMUtilityType.POWER_LINE

    def test_parse_gas_pipeline(self) -> None:
        """Gas pipeline is classified as GAS_LINE."""
        data = {"elements": MOCK_NODES + [MOCK_PIPELINE_GAS]}
        result = self.parser.parse_response(data)
        assert len(result.utilities) == 1
        assert result.utilities[0].utility_type == OSMUtilityType.GAS_LINE

    def test_parse_stream(self) -> None:
        """Stream waterway is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_STREAM]}
        result = self.parser.parse_response(data)
        assert len(result.water_features) == 1
        assert result.water_features[0].water_type == OSMWaterType.STREAM

    def test_parse_river(self) -> None:
        """River waterway is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_RIVER]}
        result = self.parser.parse_response(data)
        assert len(result.water_features) == 1
        assert result.water_features[0].water_type == OSMWaterType.RIVER

    def test_parse_wetland(self) -> None:
        """Wetland is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_WETLAND]}
        result = self.parser.parse_response(data)
        assert len(result.water_features) == 1
        assert result.water_features[0].water_type == OSMWaterType.WETLAND

    def test_parse_lake(self) -> None:
        """Lake is classified correctly."""
        data = {"elements": MOCK_NODES + [MOCK_LAKE]}
        result = self.parser.parse_response(data)
        assert len(result.water_features) == 1
        assert result.water_features[0].water_type == OSMWaterType.LAKE

    def test_parse_full_response(self) -> None:
        """Full response with all feature types is parsed correctly."""
        result = self.parser.parse_response(MOCK_FULL_RESPONSE)
        assert len(result.buildings) == 1
        assert len(result.roads) == 1
        assert len(result.utilities) == 1
        assert len(result.water_features) == 1
        assert result.feature_count == 4

    def test_parse_preserves_bbox(self) -> None:
        """Bbox is preserved in parsed result."""
        bbox = {"min_lon": -122.1, "min_lat": 37.4, "max_lon": -122.0, "max_lat": 37.5}
        result = self.parser.parse_response(MOCK_EMPTY_RESPONSE, bbox=bbox)
        assert result.bbox == bbox

    def test_skips_nodes(self) -> None:
        """Parser should only process ways and relations, not bare nodes."""
        data = {"elements": MOCK_NODES}
        result = self.parser.parse_response(data)
        assert result.feature_count == 0

    def test_skips_way_with_missing_nodes(self) -> None:
        """Ways referencing non-existent nodes should be skipped."""
        bad_way = {
            "type": "way",
            "id": 999,
            "nodes": [9999, 9998],  # nodes not in index
            "tags": {"highway": "residential"},
        }
        data = {"elements": MOCK_NODES + [bad_way]}
        result = self.parser.parse_response(data)
        assert len(result.roads) == 0


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


class TestOSMCache:
    """Tests for the OSM cache."""

    def test_put_and_get(self) -> None:
        """Stored data can be retrieved before TTL expires."""
        cache = OSMCache(ttl_seconds=3600)
        data = ExistingConditionsData()
        key = cache.make_key(-122.0, 37.0, -121.0, 38.0)
        cache.put(key, data)
        result = cache.get(key)
        assert result is not None
        assert result.feature_count == 0

    def test_cache_miss(self) -> None:
        """Missing key returns None."""
        cache = OSMCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_expiry(self) -> None:
        """Expired entries return None."""
        cache = OSMCache(ttl_seconds=0)  # immediate expiry
        data = ExistingConditionsData()
        key = "testkey"
        cache.put(key, data)
        # Entry should be expired on next get
        time.sleep(0.01)
        result = cache.get(key)
        assert result is None

    def test_cache_stats(self) -> None:
        """Hit and miss counters are tracked correctly."""
        cache = OSMCache()
        data = ExistingConditionsData()
        cache.put("k", data)
        cache.get("k")  # hit
        cache.get("missing")  # miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1

    def test_cache_clear(self) -> None:
        """Clear removes all entries and resets stats."""
        cache = OSMCache()
        cache.put("k", ExistingConditionsData())
        cache.clear()
        assert cache.get("k") is None
        stats = cache.get_stats()
        assert stats["entries"] == 0

    def test_key_deterministic(self) -> None:
        """Same bbox produces same cache key."""
        k1 = OSMCache.make_key(-122.0, 37.0, -121.0, 38.0)
        k2 = OSMCache.make_key(-122.0, 37.0, -121.0, 38.0)
        assert k1 == k2

    def test_key_differs_for_different_bbox(self) -> None:
        """Different bbox produces different cache key."""
        k1 = OSMCache.make_key(-122.0, 37.0, -121.0, 38.0)
        k2 = OSMCache.make_key(-122.0, 37.0, -121.0, 38.1)
        assert k1 != k2


# ---------------------------------------------------------------------------
# Client tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestOSMClient:
    """Tests for the OSM client with mocked HTTP."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_query_success(self) -> None:
        """Successful Overpass query returns parsed data."""
        respx.post("https://overpass-api.de/api/interpreter").mock(
            return_value=httpx.Response(200, json=MOCK_FULL_RESPONSE)
        )
        async with OSMClient() as client:
            result = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
        assert result.feature_count == 4
        assert len(result.buildings) == 1
        assert len(result.roads) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_query_empty(self) -> None:
        """Empty Overpass response returns empty data."""
        respx.post("https://overpass-api.de/api/interpreter").mock(
            return_value=httpx.Response(200, json=MOCK_EMPTY_RESPONSE)
        )
        async with OSMClient() as client:
            result = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
        assert result.feature_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_graceful_degradation_on_error(self) -> None:
        """Client returns empty data on HTTP error instead of raising."""
        config = OSMClientConfig(max_retries=0)
        respx.post("https://overpass-api.de/api/interpreter").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        async with OSMClient(config) as client:
            result = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
        assert result.feature_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_graceful_degradation_on_timeout(self) -> None:
        """Client returns empty data on timeout instead of raising."""
        config = OSMClientConfig(timeout=1.0, max_retries=0)
        respx.post("https://overpass-api.de/api/interpreter").mock(
            side_effect=httpx.ReadTimeout("read timed out")
        )
        async with OSMClient(config) as client:
            result = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
        assert result.feature_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_failure(self) -> None:
        """Client retries on transient failure then succeeds."""
        route = respx.post("https://overpass-api.de/api/interpreter")
        route.side_effect = [
            httpx.Response(429, text="Rate limited"),
            httpx.Response(200, json=MOCK_FULL_RESPONSE),
        ]
        config = OSMClientConfig(max_retries=1, retry_backoff_factor=0.1)
        async with OSMClient(config) as client:
            result = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
        assert result.feature_count == 4

    @pytest.mark.asyncio
    @respx.mock
    async def test_cache_hit(self) -> None:
        """Second query with same bbox should hit cache."""
        route = respx.post("https://overpass-api.de/api/interpreter").mock(
            return_value=httpx.Response(200, json=MOCK_FULL_RESPONSE)
        )
        async with OSMClient() as client:
            r1 = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
            r2 = await client.query_existing_conditions(-122.1, 37.4, -122.0, 37.5)
        assert r1.feature_count == 4
        assert r2.feature_count == 4
        assert route.call_count == 1  # only one HTTP call made

"""Tests for the ExistingConditionsService."""

from unittest.mock import AsyncMock, patch

import pytest
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon

from entmoot.core.constraints.buffers import (
    ROAD_SETBACK,
    WATER_FEATURE_SETBACK,
    RoadType,
    WaterFeatureType,
)
from entmoot.models.existing_conditions import (
    ExistingConditionsData,
    OSMFeature,
    OSMFeatureType,
    OSMRoadClass,
    OSMUtilityType,
    OSMWaterType,
)
from entmoot.services.existing_conditions_service import (
    BUILDING_BUFFER_M,
    ExistingConditionsResult,
    ExistingConditionsService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A simple 100m x 100m site in UTM coordinates
SITE_UTM = ShapelyPolygon([(0, 0), (100, 0), (100, 100), (0, 100)])

# The same site in "fake WGS84" (small numbers, doesn't matter for unit tests)
SITE_WGS84 = ShapelyPolygon([(-122.01, 37.01), (-122.0, 37.01), (-122.0, 37.02), (-122.01, 37.02)])


def _make_building_feature(osm_id: int = 1) -> OSMFeature:
    """Create a building feature with a small polygon in WGS84."""
    poly = ShapelyPolygon(
        [
            (-122.005, 37.015),
            (-122.004, 37.015),
            (-122.004, 37.016),
            (-122.005, 37.016),
        ]
    )
    return OSMFeature(
        osm_id=osm_id,
        feature_type=OSMFeatureType.BUILDING,
        geometry_wkt=poly.wkt,
        tags={"building": "yes"},
    )


def _make_road_feature(
    osm_id: int = 2, road_class: OSMRoadClass = OSMRoadClass.RESIDENTIAL
) -> OSMFeature:
    """Create a road feature (linestring) in WGS84."""
    line = LineString([(-122.006, 37.015), (-122.003, 37.015)])
    return OSMFeature(
        osm_id=osm_id,
        feature_type=OSMFeatureType.ROAD,
        geometry_wkt=line.wkt,
        tags={"highway": "residential"},
        road_class=road_class,
    )


def _make_water_feature(
    osm_id: int = 3, water_type: OSMWaterType = OSMWaterType.STREAM
) -> OSMFeature:
    """Create a water feature (linestring) in WGS84."""
    line = LineString([(-122.006, 37.012), (-122.003, 37.012)])
    return OSMFeature(
        osm_id=osm_id,
        feature_type=OSMFeatureType.WATER,
        geometry_wkt=line.wkt,
        tags={"waterway": "stream"},
        water_type=water_type,
    )


def _make_utility_feature(
    osm_id: int = 4, utility_type: OSMUtilityType = OSMUtilityType.POWER_LINE
) -> OSMFeature:
    """Create a utility feature (linestring) in WGS84."""
    line = LineString([(-122.006, 37.018), (-122.003, 37.018)])
    return OSMFeature(
        osm_id=osm_id,
        feature_type=OSMFeatureType.UTILITY,
        geometry_wkt=line.wkt,
        tags={"power": "line"},
        utility_type=utility_type,
    )


class FakeTransformer:
    """Fake CRS transformer that scales WGS84 to UTM-like coords.

    Maps roughly: lon → x * 100000, lat → y * 100000
    so a 0.001 degree feature becomes ~100m.
    """

    def transform(self, x: float, y: float):
        """Transform WGS84 to fake UTM coordinates."""
        return (x + 122.005) * 100_000, (y - 37.01) * 100_000


class FakeInverseTransformer:
    """Inverse of FakeTransformer."""

    def transform(self, x: float, y: float):
        """Transform fake UTM coordinates back to WGS84."""
        return x / 100_000 - 122.005, y / 100_000 + 37.01


# A site boundary in the "fake UTM" space that covers the features
SITE_UTM_LARGE = ShapelyPolygon([(-200, -200), (200, -200), (200, 1200), (-200, 1200)])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExistingConditionsService:
    """Tests for ExistingConditionsService.fetch_and_process."""

    def _make_osm_data(self, **kwargs) -> ExistingConditionsData:
        """Create ExistingConditionsData with given keyword args."""
        return ExistingConditionsData(**kwargs)

    @pytest.mark.asyncio
    async def test_empty_osm_data_returns_empty_result(self) -> None:
        """Empty OSM response produces empty result without crashing."""
        osm_data = self._make_osm_data()

        with patch("entmoot.services.existing_conditions_service.OSMClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.query_existing_conditions.return_value = osm_data
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            service = ExistingConditionsService()
            result = await service.fetch_and_process(
                site_boundary_wgs84=SITE_WGS84,
                transformer=FakeTransformer(),
                inverse_transformer=FakeInverseTransformer(),
                site_boundary_utm=SITE_UTM_LARGE,
            )

        assert isinstance(result, ExistingConditionsResult)
        assert len(result.exclusion_zones) == 0
        assert result.feature_count == 0

    @pytest.mark.asyncio
    async def test_building_creates_exclusion_zone(self) -> None:
        """A building feature should create a buffered exclusion zone."""
        osm_data = self._make_osm_data(buildings=[_make_building_feature()])

        with patch("entmoot.services.existing_conditions_service.OSMClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.query_existing_conditions.return_value = osm_data
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            service = ExistingConditionsService()
            result = await service.fetch_and_process(
                site_boundary_wgs84=SITE_WGS84,
                transformer=FakeTransformer(),
                inverse_transformer=FakeInverseTransformer(),
                site_boundary_utm=SITE_UTM_LARGE,
            )

        assert len(result.exclusion_zones) == 1
        zone = result.exclusion_zones[0]
        # Buffer should make it larger than the raw footprint
        assert zone.area > 0

    @pytest.mark.asyncio
    async def test_road_creates_exclusion_zone(self) -> None:
        """A road feature should create a setback exclusion zone."""
        osm_data = self._make_osm_data(
            roads=[_make_road_feature(road_class=OSMRoadClass.RESIDENTIAL)]
        )

        with patch("entmoot.services.existing_conditions_service.OSMClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.query_existing_conditions.return_value = osm_data
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            service = ExistingConditionsService()
            result = await service.fetch_and_process(
                site_boundary_wgs84=SITE_WGS84,
                transformer=FakeTransformer(),
                inverse_transformer=FakeInverseTransformer(),
                site_boundary_utm=SITE_UTM_LARGE,
            )

        assert len(result.exclusion_zones) == 1

    @pytest.mark.asyncio
    async def test_road_entry_point_detected(self) -> None:
        """Road entry point should be set to nearest road point to boundary."""
        osm_data = self._make_osm_data(roads=[_make_road_feature()])

        with patch("entmoot.services.existing_conditions_service.OSMClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.query_existing_conditions.return_value = osm_data
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            service = ExistingConditionsService()
            result = await service.fetch_and_process(
                site_boundary_wgs84=SITE_WGS84,
                transformer=FakeTransformer(),
                inverse_transformer=FakeInverseTransformer(),
                site_boundary_utm=SITE_UTM_LARGE,
            )

        # Should have a road entry point (not just centroid fallback)
        assert result.road_entry_point is not None
        assert len(result.road_entry_point) == 2

    @pytest.mark.asyncio
    async def test_entry_point_fallback_to_centroid(self) -> None:
        """Without roads, entry point falls back to site centroid."""
        osm_data = self._make_osm_data(buildings=[_make_building_feature()])

        with patch("entmoot.services.existing_conditions_service.OSMClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.query_existing_conditions.return_value = osm_data
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            service = ExistingConditionsService()
            result = await service.fetch_and_process(
                site_boundary_wgs84=SITE_WGS84,
                transformer=FakeTransformer(),
                inverse_transformer=FakeInverseTransformer(),
                site_boundary_utm=SITE_UTM_LARGE,
            )

        # Entry point should be site centroid
        cx, cy = SITE_UTM_LARGE.centroid.x, SITE_UTM_LARGE.centroid.y
        assert result.road_entry_point is not None
        assert abs(result.road_entry_point[0] - cx) < 1
        assert abs(result.road_entry_point[1] - cy) < 1

    @pytest.mark.asyncio
    async def test_display_features_created(self) -> None:
        """Display features should be created for frontend rendering."""
        osm_data = self._make_osm_data(
            buildings=[_make_building_feature()],
            roads=[_make_road_feature()],
        )

        with patch("entmoot.services.existing_conditions_service.OSMClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.query_existing_conditions.return_value = osm_data
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            service = ExistingConditionsService()
            result = await service.fetch_and_process(
                site_boundary_wgs84=SITE_WGS84,
                transformer=FakeTransformer(),
                inverse_transformer=FakeInverseTransformer(),
                site_boundary_utm=SITE_UTM_LARGE,
            )

        assert len(result.display_features) == len(result.exclusion_zones)
        for df in result.display_features:
            assert df.id is not None
            assert len(df.polygon) > 0

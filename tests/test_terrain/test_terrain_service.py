"""
Tests for terrain service — TerrainData and prepare_terrain_data().
"""

import math
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import Affine
from shapely.geometry import Polygon, box

from entmoot.services.terrain_service import TerrainData, prepare_terrain_data

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


@pytest.fixture
def flat_terrain():
    """10x10 flat DEM at 1650 m elevation, 1 m cells."""
    elevation = np.full((10, 10), 1650.0, dtype=np.float32)
    slope = np.zeros((10, 10), dtype=np.float32)
    transform = Affine(1.0, 0, 500000.0, 0, -1.0, 4400010.0)
    return TerrainData(
        elevation=elevation,
        slope_percent=slope,
        transform=transform,
        cell_size=1.0,
        bounds=(500000.0, 4400000.0, 500010.0, 4400010.0),
    )


@pytest.fixture
def sloped_terrain():
    """10x10 linearly-sloped DEM (slope increases south to north)."""
    elevation = np.zeros((10, 10), dtype=np.float32)
    for r in range(10):
        elevation[r, :] = 1650.0 + (9 - r) * 2.0  # 2 m rise per row
    slope = np.full((10, 10), 20.0, dtype=np.float32)  # ~20 % slope
    transform = Affine(1.0, 0, 500000.0, 0, -1.0, 4400010.0)
    return TerrainData(
        elevation=elevation,
        slope_percent=slope,
        transform=transform,
        cell_size=1.0,
        bounds=(500000.0, 4400000.0, 500010.0, 4400010.0),
    )


# -----------------------------------------------------------------------
# TerrainData unit tests
# -----------------------------------------------------------------------


class TestTerrainDataSampling:
    def test_sample_elevation_within_grid(self, flat_terrain):
        val = flat_terrain.sample_elevation(500005.5, 4400005.5)
        assert val is not None
        assert val == pytest.approx(1650.0, abs=0.1)

    def test_sample_elevation_outside_grid(self, flat_terrain):
        assert flat_terrain.sample_elevation(0.0, 0.0) is None

    def test_sample_slope_within_grid(self, flat_terrain):
        val = flat_terrain.sample_slope(500005.5, 4400005.5)
        assert val is not None
        assert val == pytest.approx(0.0, abs=0.1)

    def test_sample_slope_outside_grid(self, flat_terrain):
        assert flat_terrain.sample_slope(0.0, 0.0) is None

    def test_get_mean_slope_in_footprint(self, sloped_terrain):
        # A 4x4 m box in the centre
        poly = box(500003.0, 4400003.0, 500007.0, 4400007.0)
        mean_slope = sloped_terrain.get_mean_slope_in_footprint(poly)
        assert mean_slope is not None
        assert mean_slope == pytest.approx(20.0, abs=0.5)

    def test_get_mean_slope_no_overlap(self, flat_terrain):
        poly = box(0.0, 0.0, 1.0, 1.0)
        assert flat_terrain.get_mean_slope_in_footprint(poly) is None

    def test_get_elevation_under_footprint(self, flat_terrain):
        poly = box(500002.0, 4400002.0, 500008.0, 4400008.0)
        elevations = flat_terrain.get_elevation_under_footprint(poly)
        assert len(elevations) > 0
        assert np.allclose(elevations, 1650.0, atol=0.1)

    def test_get_elevation_under_footprint_no_overlap(self, flat_terrain):
        poly = box(0.0, 0.0, 1.0, 1.0)
        elevations = flat_terrain.get_elevation_under_footprint(poly)
        assert len(elevations) == 0


# -----------------------------------------------------------------------
# prepare_terrain_data() tests (requires sample files)
# -----------------------------------------------------------------------


@pytest.mark.skipif(
    not (SAMPLES_DIR / "elevation.tif").exists(),
    reason="Sample elevation.tif not found",
)
class TestPrepareTerrainData:
    def _load_boundary(self):
        import json
        from shapely.geometry import shape

        geojson_path = SAMPLES_DIR / "property_boundary.geojson"
        with open(geojson_path) as f:
            data = json.load(f)
        if data.get("type") == "FeatureCollection":
            geom = data["features"][0]["geometry"]
        elif data.get("type") == "Feature":
            geom = data["geometry"]
        else:
            geom = data
        return shape(geom)

    def _get_utm_boundary(self):
        from pyproj import Transformer

        raw = self._load_boundary()
        # Approximate UTM zone for Denver area
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32613", always_xy=True)
        from shapely.ops import transform as shapely_transform

        return shapely_transform(transformer.transform, raw)

    def test_prepare_terrain_data_succeeds(self):
        utm_boundary = self._get_utm_boundary()
        td = prepare_terrain_data(
            SAMPLES_DIR / "elevation.tif",
            utm_boundary,
            target_crs_epsg=32613,
        )
        assert td.elevation.shape[0] > 0
        assert td.slope_percent.shape == td.elevation.shape
        assert td.cell_size > 0

    def test_sampling_after_prepare(self):
        utm_boundary = self._get_utm_boundary()
        td = prepare_terrain_data(
            SAMPLES_DIR / "elevation.tif",
            utm_boundary,
            target_crs_epsg=32613,
        )
        cx, cy = utm_boundary.centroid.x, utm_boundary.centroid.y
        elev = td.sample_elevation(cx, cy)
        # Should return something reasonable (Denver area ~1650 m)
        assert elev is not None
        assert 1500.0 < elev < 2000.0

    def test_invalid_dem_path_raises(self):
        from entmoot.core.errors import ValidationError

        utm_boundary = self._get_utm_boundary()
        with pytest.raises(ValidationError):
            prepare_terrain_data(
                Path("/nonexistent/fake.tif"),
                utm_boundary,
                target_crs_epsg=32613,
            )


# -----------------------------------------------------------------------
# Objective evaluation with terrain data
# -----------------------------------------------------------------------


class TestObjectiveWithTerrain:
    """Test OptimizationObjective with real vs. None terrain_data."""

    def _make_objective(self, terrain_data=None):
        from entmoot.core.optimization.problem import (
            OptimizationObjective,
            OptimizationConstraints,
            ObjectiveWeights,
        )

        site = box(0, 0, 200, 200)
        constraints = OptimizationConstraints(site_boundary=site)
        weights = ObjectiveWeights(
            cut_fill_weight=0.3,
            accessibility_weight=0.2,
            road_length_weight=0.2,
            compactness_weight=0.15,
            slope_variance_weight=0.15,
        )
        return OptimizationObjective(
            constraints=constraints,
            weights=weights,
            elevation_data=terrain_data.elevation if terrain_data else None,
            slope_data=terrain_data.slope_percent if terrain_data else None,
            transform=terrain_data.transform if terrain_data else None,
            terrain_data=terrain_data,
        )

    def test_no_terrain_returns_neutral_cut_fill(self):
        obj = self._make_objective(terrain_data=None)
        assert obj._evaluate_cut_fill.__func__  # method exists
        # With no elevation_data, should return 50.0
        from entmoot.core.optimization.problem import PlacementSolution

        sol = PlacementSolution(assets=[], fitness=0.0)
        # elevation_data is None, so the guard returns 50.0
        score = obj._evaluate_cut_fill(sol)
        assert score == 50.0

    def test_no_terrain_returns_neutral_slope_variance(self):
        obj = self._make_objective(terrain_data=None)
        from entmoot.core.optimization.problem import PlacementSolution

        sol = PlacementSolution(assets=[], fitness=0.0)
        score = obj._evaluate_slope_variance(sol)
        assert score == 50.0

    def test_flat_terrain_high_cut_fill_score(self):
        """Flat terrain should yield high cut/fill score (little earthwork)."""
        elevation = np.full((100, 100), 1650.0, dtype=np.float32)
        slope = np.zeros((100, 100), dtype=np.float32)
        transform = Affine(2.0, 0, 0.0, 0, -2.0, 200.0)
        td = TerrainData(
            elevation=elevation,
            slope_percent=slope,
            transform=transform,
            cell_size=2.0,
            bounds=(0.0, 0.0, 200.0, 200.0),
        )
        obj = self._make_objective(terrain_data=td)

        from entmoot.core.optimization.problem import PlacementSolution
        from unittest.mock import MagicMock

        # Create a mock asset placed in the middle
        asset = MagicMock()
        asset.position = (100.0, 100.0)
        asset.dimensions = (20.0, 20.0)
        asset.rotation = 0.0
        asset.area_sqm = 400.0
        asset.get_geometry.return_value = box(90, 90, 110, 110)

        sol = PlacementSolution(assets=[asset], fitness=0.0)
        score = obj._evaluate_cut_fill(sol)
        # Flat terrain → zero variance → score = 100
        assert score == pytest.approx(100.0, abs=1.0)

    def test_steep_terrain_low_slope_variance_score(self):
        """Steep terrain should yield low slope variance score."""
        elevation = np.zeros((100, 100), dtype=np.float32)
        slope = np.full((100, 100), 30.0, dtype=np.float32)  # 30% everywhere
        transform = Affine(2.0, 0, 0.0, 0, -2.0, 200.0)
        td = TerrainData(
            elevation=elevation,
            slope_percent=slope,
            transform=transform,
            cell_size=2.0,
            bounds=(0.0, 0.0, 200.0, 200.0),
        )
        obj = self._make_objective(terrain_data=td)

        from entmoot.core.optimization.problem import PlacementSolution
        from unittest.mock import MagicMock

        asset = MagicMock()
        asset.position = (100.0, 100.0)
        asset.get_geometry.return_value = box(90, 90, 110, 110)

        sol = PlacementSolution(assets=[asset], fitness=0.0)
        score = obj._evaluate_slope_variance(sol)
        # 30% average slope → slope_score = max(0, 1 - 30/25) = 0
        # So overall score should be low
        assert score < 50.0

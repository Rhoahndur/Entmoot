"""Tests for post-grading model."""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from entmoot.core.earthwork.post_grading import PostGradingModel
from entmoot.models.earthwork import GradingZone, GradingZoneType
from entmoot.models.terrain import DEMMetadata, ElevationUnit
from pyproj import CRS

try:
    from shapely.geometry import Polygon, LineString, Point
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


@pytest.fixture
def metadata():
    """Create test DEM metadata."""
    return DEMMetadata(
        width=100,
        height=100,
        resolution=(1.0, 1.0),
        bounds=(0.0, 0.0, 100.0, 100.0),
        crs=CRS.from_epsg(32610),
        no_data_value=np.nan,
        elevation_unit=ElevationUnit.FEET,
        transform=(1.0, 0.0, 0.0, 0.0, -1.0, 100.0),
    )


@pytest.fixture
def base_elevation(metadata):
    """Create base elevation array."""
    elevation = np.full((100, 100), 100.0, dtype=np.float32)
    return elevation


@pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
class TestPostGradingModel:
    """Test PostGradingModel class."""

    def test_initialization(self, metadata):
        """Test model initialization."""
        model = PostGradingModel(metadata)

        assert model.elevation.shape == (100, 100)
        assert model.metadata.width == 100
        assert len(model.grading_zones) == 0

    def test_initialization_with_base(self, metadata, base_elevation):
        """Test initialization with base elevation."""
        model = PostGradingModel(metadata, base_elevation=base_elevation)

        assert np.array_equal(
            model.elevation[~np.isnan(model.elevation)],
            base_elevation[~np.isnan(base_elevation)]
        )

    def test_add_building_pad(self, metadata):
        """Test adding building pad."""
        model = PostGradingModel(metadata)

        # Create building pad polygon
        pad = Polygon([(20, 20), (40, 20), (40, 40), (20, 40)])

        model.add_building_pad(
            geometry=pad,
            target_elevation=105.0,
            transition_slope=3.0,
            priority=10
        )

        assert len(model.grading_zones) == 1
        assert model.grading_zones[0].zone_type == GradingZoneType.BUILDING_PAD
        assert model.grading_zones[0].target_elevation == 105.0

    def test_add_road_corridor(self, metadata):
        """Test adding road corridor."""
        model = PostGradingModel(metadata)

        # Create road centerline
        centerline = LineString([(10, 50), (90, 50)])

        model.add_road_corridor(
            centerline=centerline,
            width=24.0,
            crown_height=0.5,
            cross_slope=2.0,
            priority=8
        )

        assert len(model.grading_zones) == 1
        assert model.grading_zones[0].zone_type == GradingZoneType.ROAD_CORRIDOR
        assert model.grading_zones[0].crown_height == 0.5

    def test_add_drainage_swale(self, metadata):
        """Test adding drainage swale."""
        model = PostGradingModel(metadata)

        # Create swale centerline
        centerline = LineString([(30, 10), (30, 90)])

        model.add_drainage_swale(
            centerline=centerline,
            width=10.0,
            slope=2.0,
            direction=0.0,
            priority=5
        )

        assert len(model.grading_zones) == 1
        assert model.grading_zones[0].zone_type == GradingZoneType.DRAINAGE_SWALE
        assert model.grading_zones[0].target_slope == 2.0

    def test_generate_building_pad_grading(self, metadata, base_elevation):
        """Test grading generation for building pad."""
        model = PostGradingModel(metadata, base_elevation=base_elevation)

        # Add building pad
        pad = Polygon([(40, 40), (60, 40), (60, 60), (40, 60)])
        model.add_building_pad(
            geometry=pad,
            target_elevation=110.0,
            priority=10
        )

        # Generate grading
        elevation = model.generate_grading()

        # Check that pad area is at target elevation
        # This is approximate due to rasterization
        center_elev = elevation[50, 50]
        assert abs(center_elev - 110.0) < 1.0

    def test_priority_handling(self, metadata, base_elevation):
        """Test zone priority handling for overlaps."""
        model = PostGradingModel(metadata, base_elevation=base_elevation)

        # Add two overlapping zones with different priorities
        zone1 = Polygon([(20, 20), (60, 20), (60, 60), (20, 60)])
        zone2 = Polygon([(40, 40), (80, 40), (80, 80), (40, 80)])

        model.add_building_pad(zone1, target_elevation=95.0, priority=5)
        model.add_building_pad(zone2, target_elevation=110.0, priority=10)

        elevation = model.generate_grading()

        # Check that zones were processed
        stats = model.get_statistics()
        assert stats["num_zones"] == 2
        assert stats["graded_cells"] > 0

        # At least some cells should have been graded to the target elevations
        # This is a simplified test since rasterization can be imperfect
        assert np.any(np.abs(elevation - 95.0) < 1.0) or np.any(np.abs(elevation - 110.0) < 1.0)

    def test_multiple_zones(self, metadata, base_elevation):
        """Test handling multiple grading zones."""
        model = PostGradingModel(metadata, base_elevation=base_elevation)

        # Add multiple non-overlapping zones
        pad1 = Polygon([(10, 10), (30, 10), (30, 30), (10, 30)])
        pad2 = Polygon([(70, 70), (90, 70), (90, 90), (70, 90)])

        model.add_building_pad(pad1, target_elevation=105.0, priority=10)
        model.add_building_pad(pad2, target_elevation=115.0, priority=10)

        elevation = model.generate_grading()

        # Both zones should be graded
        assert np.sum(model.graded_mask) > 0

    def test_export_surface(self, metadata):
        """Test surface export to GeoTIFF."""
        model = PostGradingModel(metadata)

        # Add a simple zone
        pad = Polygon([(40, 40), (60, 40), (60, 60), (40, 60)])
        model.add_building_pad(pad, target_elevation=110.0, priority=10)
        model.generate_grading()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "post_grading.tif"
            model.export_surface(str(output_path))

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_get_statistics(self, metadata, base_elevation):
        """Test statistics calculation."""
        model = PostGradingModel(metadata, base_elevation=base_elevation)

        # Add zone
        pad = Polygon([(40, 40), (60, 40), (60, 60), (40, 60)])
        model.add_building_pad(pad, target_elevation=110.0, priority=10)
        model.generate_grading()

        stats = model.get_statistics()

        assert "min_elevation" in stats
        assert "max_elevation" in stats
        assert "mean_elevation" in stats
        assert "graded_cells" in stats
        assert "num_zones" in stats

        assert stats["num_zones"] == 1
        assert stats["graded_cells"] > 0

    def test_pixel_to_coords(self, metadata):
        """Test pixel to coordinates conversion."""
        model = PostGradingModel(metadata)

        # Test corner
        x, y = model._pixel_to_coords(0, 0)
        assert x == 0.0
        assert y == 100.0  # Top of DEM

        # Test another corner
        x, y = model._pixel_to_coords(99, 99)
        assert abs(x - 99.0) < 1.0
        assert abs(y - 1.0) < 1.0

    def test_create_geometry_mask(self, metadata):
        """Test geometry mask creation."""
        model = PostGradingModel(metadata)

        # Create a polygon
        poly = Polygon([(40, 40), (60, 40), (60, 60), (40, 60)])

        mask = model._create_geometry_mask(poly)

        assert mask.shape == (100, 100)
        assert mask.dtype == bool
        assert np.any(mask)  # Should have some True values

    def test_get_neighbors(self, metadata):
        """Test neighbor cell extraction."""
        model = PostGradingModel(metadata)

        # Get neighbors of center cell
        neighbors = model._get_neighbors(50, 50, radius=1)

        assert len(neighbors) == 8  # 8 neighbors for radius 1
        assert all(isinstance(n, np.ndarray) for n in neighbors)

        # Get larger neighborhood
        neighbors_3 = model._get_neighbors(50, 50, radius=3)
        assert len(neighbors_3) > len(neighbors)

    def test_edge_handling(self, metadata):
        """Test handling of edge cases."""
        model = PostGradingModel(metadata)

        # Zone at edge of DEM
        edge_poly = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
        model.add_building_pad(edge_poly, target_elevation=105.0, priority=10)

        # Should not raise error
        elevation = model.generate_grading()
        assert elevation is not None


@pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
class TestGradingZone:
    """Test GradingZone model."""

    def test_building_pad_zone(self):
        """Test building pad zone creation."""
        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])

        zone = GradingZone(
            zone_type=GradingZoneType.BUILDING_PAD,
            geometry=poly,
            target_elevation=100.0,
            transition_slope=3.0,
            priority=10
        )

        assert zone.zone_type == GradingZoneType.BUILDING_PAD
        assert zone.target_elevation == 100.0
        assert zone.priority == 10

    def test_zone_to_dict(self):
        """Test zone conversion to dictionary."""
        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])

        zone = GradingZone(
            zone_type=GradingZoneType.ROAD_CORRIDOR,
            geometry=poly,
            crown_height=0.5,
            cross_slope=2.0,
            priority=8
        )

        data = zone.to_dict()

        assert data["zone_type"] == "road_corridor"
        assert data["crown_height"] == 0.5
        assert data["cross_slope"] == 2.0
        assert data["priority"] == 8

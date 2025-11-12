"""Tests for pre-grading model."""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from entmoot.core.earthwork.pre_grading import PreGradingModel
from entmoot.models.terrain import DEMData, DEMMetadata, ElevationUnit
from pyproj import CRS


@pytest.fixture
def metadata():
    """Create test DEM metadata."""
    return DEMMetadata(
        width=50,
        height=50,
        resolution=(1.0, 1.0),
        bounds=(0.0, 0.0, 50.0, 50.0),
        crs=CRS.from_epsg(32610),
        no_data_value=np.nan,
        elevation_unit=ElevationUnit.FEET,
        transform=(1.0, 0.0, 0.0, 0.0, -1.0, 50.0),
    )


@pytest.fixture
def flat_dem(metadata):
    """Create flat DEM."""
    elevation = np.full((50, 50), 100.0, dtype=np.float32)
    return DEMData(elevation=elevation, metadata=metadata)


@pytest.fixture
def sloped_dem(metadata):
    """Create sloped DEM."""
    elevation = np.zeros((50, 50), dtype=np.float32)
    for i in range(50):
        elevation[i, :] = 100.0 + i * 0.5
    return DEMData(elevation=elevation, metadata=metadata)


class TestPreGradingModel:
    """Test PreGradingModel class."""

    def test_initialization(self, flat_dem):
        """Test model initialization."""
        model = PreGradingModel(flat_dem)

        assert model.elevation.shape == (50, 50)
        assert model.surface_area_sf > 0
        assert model.metadata.width == 50
        assert model.metadata.height == 50

    def test_surface_area_flat(self, flat_dem):
        """Test surface area calculation for flat terrain."""
        model = PreGradingModel(flat_dem)

        # For flat terrain, 3D surface area should equal planar area
        # 50x50 cells, each 1m x 1m = 3.28084 ft x 3.28084 ft = 10.764 sq ft
        expected_area = 50 * 50 * 10.764

        # Allow some tolerance for calculation differences
        assert abs(model.surface_area_sf - expected_area) / expected_area < 0.05

    def test_surface_area_sloped(self, sloped_dem):
        """Test surface area calculation for sloped terrain."""
        model = PreGradingModel(sloped_dem)

        # Sloped terrain should have larger surface area than planar
        planar_area = 50 * 50 * 10.764
        assert model.surface_area_sf > planar_area

    def test_get_elevation_at_point(self, flat_dem):
        """Test elevation at specific point."""
        model = PreGradingModel(flat_dem)

        # Point in middle of DEM
        elev = model.get_elevation_at_point(25.0, 25.0)

        assert elev is not None
        assert abs(elev - 100.0) < 0.1

    def test_get_elevation_outside_bounds(self, flat_dem):
        """Test elevation query outside DEM bounds."""
        model = PreGradingModel(flat_dem)

        # Point outside DEM
        elev = model.get_elevation_at_point(-10.0, -10.0)

        assert elev is None

    def test_get_elevation_profile(self, sloped_dem):
        """Test elevation profile extraction."""
        model = PreGradingModel(sloped_dem)

        distance, elevation = model.get_elevation_profile(
            start=(5.0, 5.0),
            end=(45.0, 45.0),
            num_points=50
        )

        assert len(distance) == 50
        assert len(elevation) == 50

        # Distance should increase monotonically
        assert np.all(np.diff(distance) > 0)

        # Elevation should vary for sloped terrain
        valid_elev = elevation[~np.isnan(elevation)]
        assert len(valid_elev) > 0
        assert np.std(valid_elev) > 0

    def test_get_statistics(self, sloped_dem):
        """Test statistics calculation."""
        model = PreGradingModel(sloped_dem)

        stats = model.get_statistics()

        assert "min_elevation" in stats
        assert "max_elevation" in stats
        assert "mean_elevation" in stats
        assert "surface_area_sf" in stats

        # Check values are reasonable
        assert stats["min_elevation"] > 0
        assert stats["max_elevation"] > stats["min_elevation"]
        assert stats["mean_elevation"] > stats["min_elevation"]
        assert stats["surface_area_sf"] > 0

    def test_export_surface(self, flat_dem):
        """Test surface export to GeoTIFF."""
        model = PreGradingModel(flat_dem)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pre_grading.tif"
            model.export_surface(output_path)

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_to_dict(self, flat_dem):
        """Test conversion to dictionary."""
        model = PreGradingModel(flat_dem)

        data = model.to_dict()

        assert "metadata" in data
        assert "statistics" in data
        assert isinstance(data["metadata"], dict)
        assert isinstance(data["statistics"], dict)

    def test_nan_handling(self, metadata):
        """Test handling of NaN values in DEM."""
        elevation = np.full((50, 50), 100.0, dtype=np.float32)
        elevation[0:10, 0:10] = np.nan

        dem_data = DEMData(elevation=elevation, metadata=metadata)
        model = PreGradingModel(dem_data)

        stats = model.get_statistics()

        # Statistics should ignore NaN values
        assert not np.isnan(stats["mean_elevation"])
        assert stats["mean_elevation"] > 0

    def test_coords_to_pixel(self, flat_dem):
        """Test coordinate to pixel conversion."""
        model = PreGradingModel(flat_dem)

        # Test corner point
        col, row = model._coords_to_pixel(0.0, 50.0)
        assert col == 0
        assert row == 0

        # Test center point
        col, row = model._coords_to_pixel(25.0, 25.0)
        assert 20 <= col <= 30
        assert 20 <= row <= 30

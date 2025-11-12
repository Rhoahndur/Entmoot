"""
Tests for terrain data models.
"""

import pytest
import numpy as np
from pyproj import CRS

from entmoot.models.terrain import (
    DEMData,
    DEMMetadata,
    DEMValidationResult,
    ElevationUnit,
    InterpolationMethod,
    ResamplingMethod,
    TerrainMetrics,
)


class TestDEMMetadata:
    """Test DEMMetadata model."""

    def test_create_valid_metadata(self):
        """Test creating valid metadata."""
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
            no_data_value=np.nan,
            elevation_unit=ElevationUnit.METERS,
        )

        assert metadata.width == 100
        assert metadata.height == 100
        assert metadata.resolution == (1.0, 1.0)
        assert metadata.bounds == (0, 0, 100, 100)

    def test_invalid_width(self):
        """Test validation of invalid width."""
        with pytest.raises(ValueError, match="Width must be positive"):
            DEMMetadata(
                width=0,
                height=100,
                resolution=(1.0, 1.0),
                bounds=(0, 0, 100, 100),
                crs=CRS.from_epsg(32633),
            )

    def test_invalid_height(self):
        """Test validation of invalid height."""
        with pytest.raises(ValueError, match="Height must be positive"):
            DEMMetadata(
                width=100,
                height=-1,
                resolution=(1.0, 1.0),
                bounds=(0, 0, 100, 100),
                crs=CRS.from_epsg(32633),
            )

    def test_invalid_resolution(self):
        """Test validation of invalid resolution."""
        with pytest.raises(ValueError, match="Resolution must be positive"):
            DEMMetadata(
                width=100,
                height=100,
                resolution=(-1.0, 1.0),
                bounds=(0, 0, 100, 100),
                crs=CRS.from_epsg(32633),
            )

    def test_invalid_bounds(self):
        """Test validation of invalid bounds."""
        with pytest.raises(ValueError, match="min_x.*must be less than max_x"):
            DEMMetadata(
                width=100,
                height=100,
                resolution=(1.0, 1.0),
                bounds=(100, 0, 0, 100),  # min_x > max_x
                crs=CRS.from_epsg(32633),
            )

    def test_pixel_count(self):
        """Test pixel count calculation."""
        metadata = DEMMetadata(
            width=100,
            height=50,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 50),
            crs=CRS.from_epsg(32633),
        )

        assert metadata.pixel_count == 5000

    def test_area_sqm(self):
        """Test area calculation."""
        metadata = DEMMetadata(
            width=100,
            height=50,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 50),
            crs=CRS.from_epsg(32633),
        )

        # Area should be approximately width * height * resolution^2
        expected_area = 100 * 50 * 1.0 * 1.0
        assert abs(metadata.area_sqm - expected_area) < 1.0

    def test_to_dict(self):
        """Test converting to dictionary."""
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
            elevation_unit=ElevationUnit.METERS,
        )

        metadata_dict = metadata.to_dict()

        assert metadata_dict["width"] == 100
        assert metadata_dict["height"] == 100
        assert metadata_dict["pixel_count"] == 10000
        assert "crs" in metadata_dict


class TestTerrainMetrics:
    """Test TerrainMetrics model."""

    def test_create_metrics(self):
        """Test creating terrain metrics."""
        metrics = TerrainMetrics(
            min_elevation=100.0,
            max_elevation=200.0,
            mean_elevation=150.0,
            median_elevation=150.0,
            std_elevation=25.0,
            elevation_range=100.0,
            valid_pixel_count=10000,
            no_data_pixel_count=0,
            no_data_percentage=0.0,
        )

        assert metrics.min_elevation == 100.0
        assert metrics.max_elevation == 200.0
        assert metrics.elevation_range == 100.0

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = TerrainMetrics(
            min_elevation=100.0,
            max_elevation=200.0,
            mean_elevation=150.0,
            median_elevation=150.0,
            std_elevation=25.0,
            elevation_range=100.0,
            valid_pixel_count=10000,
            no_data_pixel_count=0,
            no_data_percentage=0.0,
        )

        metrics_dict = metrics.to_dict()

        assert metrics_dict["min_elevation"] == 100.0
        assert metrics_dict["max_elevation"] == 200.0
        assert metrics_dict["valid_pixel_count"] == 10000


class TestDEMData:
    """Test DEMData model."""

    def test_create_valid_dem_data(self):
        """Test creating valid DEM data."""
        elevation = np.zeros((100, 100), dtype=np.float32) + 100
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
        )

        dem_data = DEMData(elevation=elevation, metadata=metadata)

        assert dem_data.elevation.shape == (100, 100)
        assert dem_data.metadata.width == 100

    def test_invalid_dimensions(self):
        """Test validation of dimension mismatch."""
        elevation = np.zeros((3, 100, 100), dtype=np.float32)  # 3D array
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
        )

        with pytest.raises(ValueError, match="must be 2D"):
            DEMData(elevation=elevation, metadata=metadata)

    def test_shape_mismatch(self):
        """Test validation of shape mismatch."""
        elevation = np.zeros((50, 50), dtype=np.float32)
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
        )

        with pytest.raises(ValueError, match="does not match"):
            DEMData(elevation=elevation, metadata=metadata)

    def test_compute_metrics_valid_data(self):
        """Test computing metrics for valid data."""
        elevation = np.arange(10000, dtype=np.float32).reshape(100, 100) + 100
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
        )
        dem_data = DEMData(elevation=elevation, metadata=metadata)

        metrics = dem_data.compute_metrics()

        assert isinstance(metrics, TerrainMetrics)
        assert metrics.min_elevation == 100.0
        assert metrics.max_elevation == 10099.0
        assert metrics.valid_pixel_count == 10000
        assert metrics.no_data_pixel_count == 0

    def test_compute_metrics_with_nodata(self):
        """Test computing metrics with no-data values."""
        elevation = np.ones((100, 100), dtype=np.float32) * 100
        elevation[:10, :] = np.nan  # 10% no-data

        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
            no_data_value=np.nan,
        )
        dem_data = DEMData(elevation=elevation, metadata=metadata)

        metrics = dem_data.compute_metrics()

        assert metrics.valid_pixel_count == 9000
        assert metrics.no_data_pixel_count == 1000
        assert metrics.no_data_percentage == 10.0

    def test_compute_metrics_all_nodata(self):
        """Test computing metrics with all no-data."""
        elevation = np.full((100, 100), np.nan, dtype=np.float32)
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
            no_data_value=np.nan,
        )
        dem_data = DEMData(elevation=elevation, metadata=metadata)

        metrics = dem_data.compute_metrics()

        assert metrics.valid_pixel_count == 0
        assert metrics.no_data_percentage == 100.0
        assert np.isnan(metrics.min_elevation)

    def test_get_metrics_cached(self):
        """Test that metrics are cached."""
        elevation = np.ones((100, 100), dtype=np.float32) * 100
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
        )
        dem_data = DEMData(elevation=elevation, metadata=metadata)

        # First call computes metrics
        metrics1 = dem_data.get_metrics()
        # Second call should return cached metrics
        metrics2 = dem_data.get_metrics()

        assert metrics1 is metrics2

    def test_to_dict(self):
        """Test converting DEM data to dictionary."""
        elevation = np.ones((10, 10), dtype=np.float32) * 100
        metadata = DEMMetadata(
            width=10,
            height=10,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 10, 10),
            crs=CRS.from_epsg(32633),
        )
        dem_data = DEMData(elevation=elevation, metadata=metadata)

        data_dict = dem_data.to_dict()

        assert "metadata" in data_dict
        assert "metrics" in data_dict
        assert data_dict["shape"] == (10, 10)


class TestDEMValidationResult:
    """Test DEMValidationResult model."""

    def test_create_valid_result(self):
        """Test creating valid result."""
        result = DEMValidationResult(is_valid=True)

        assert result.is_valid
        assert len(result.issues) == 0
        assert len(result.warnings) == 0

    def test_add_issue(self):
        """Test adding issue."""
        result = DEMValidationResult(is_valid=True)
        result.add_issue("Test issue")

        assert not result.is_valid
        assert "Test issue" in result.issues

    def test_add_warning(self):
        """Test adding warning."""
        result = DEMValidationResult(is_valid=True)
        result.add_warning("Test warning")

        assert result.is_valid
        assert "Test warning" in result.warnings

    def test_to_dict_basic(self):
        """Test converting result to dictionary."""
        result = DEMValidationResult(is_valid=True)
        result.add_issue("Issue 1")
        result.add_warning("Warning 1")

        result_dict = result.to_dict()

        assert not result_dict["is_valid"]
        assert "Issue 1" in result_dict["issues"]
        assert "Warning 1" in result_dict["warnings"]

    def test_to_dict_with_metadata(self):
        """Test converting result with metadata to dictionary."""
        metadata = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(32633),
        )
        result = DEMValidationResult(is_valid=True, metadata=metadata)

        result_dict = result.to_dict()

        assert "metadata" in result_dict
        assert result_dict["metadata"]["width"] == 100


class TestEnums:
    """Test enum types."""

    def test_elevation_unit_values(self):
        """Test ElevationUnit enum values."""
        assert ElevationUnit.METERS.value == "meters"
        assert ElevationUnit.FEET.value == "feet"

    def test_interpolation_method_values(self):
        """Test InterpolationMethod enum values."""
        assert InterpolationMethod.NEAREST.value == "nearest"
        assert InterpolationMethod.LINEAR.value == "linear"
        assert InterpolationMethod.CUBIC.value == "cubic"

    def test_resampling_method_values(self):
        """Test ResamplingMethod enum values."""
        assert ResamplingMethod.NEAREST.value == "nearest"
        assert ResamplingMethod.BILINEAR.value == "bilinear"
        assert ResamplingMethod.CUBIC.value == "cubic"
        assert ResamplingMethod.AVERAGE.value == "average"

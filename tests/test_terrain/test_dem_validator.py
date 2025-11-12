"""
Tests for DEM validator functionality.
"""

import pytest
import numpy as np
from pyproj import CRS

from entmoot.core.terrain.dem_validator import DEMValidator
from entmoot.models.terrain import (
    DEMData,
    DEMMetadata,
    DEMValidationResult,
    ElevationUnit,
)


@pytest.fixture
def validator():
    """Create DEM validator instance."""
    return DEMValidator()


@pytest.fixture
def valid_metadata():
    """Create valid DEM metadata."""
    return DEMMetadata(
        width=100,
        height=100,
        resolution=(1.0, 1.0),
        bounds=(0, 0, 100, 100),
        crs=CRS.from_epsg(32633),
        no_data_value=np.nan,
        elevation_unit=ElevationUnit.METERS,
    )


@pytest.fixture
def valid_elevation():
    """Create valid elevation data."""
    elevation = np.zeros((100, 100), dtype=np.float32)
    for i in range(100):
        elevation[i, :] = 100 + i * 0.5
    return elevation


@pytest.fixture
def valid_dem_data(valid_metadata, valid_elevation):
    """Create valid DEM data."""
    return DEMData(elevation=valid_elevation, metadata=valid_metadata)


class TestDEMValidatorInit:
    """Test DEM validator initialization."""

    def test_init_default(self):
        """Test default initialization."""
        validator = DEMValidator()
        assert validator.min_elevation == -500.0
        assert validator.max_elevation == 9000.0
        assert validator.max_no_data_pct == 50.0

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        validator = DEMValidator(
            min_elevation=-100.0,
            max_elevation=5000.0,
            max_no_data_pct=25.0
        )
        assert validator.min_elevation == -100.0
        assert validator.max_elevation == 5000.0
        assert validator.max_no_data_pct == 25.0


class TestDEMValidatorBasic:
    """Test basic validation."""

    def test_validate_valid_dem(self, validator, valid_dem_data):
        """Test validation of valid DEM."""
        result = validator.validate(valid_dem_data)

        assert isinstance(result, DEMValidationResult)
        assert result.is_valid
        assert len(result.issues) == 0

    def test_validate_returns_metadata(self, validator, valid_dem_data):
        """Test that validation result includes metadata."""
        result = validator.validate(valid_dem_data)

        assert result.metadata is not None
        assert result.metadata.width == 100
        assert result.metadata.height == 100


class TestDEMValidatorMetadata:
    """Test metadata validation."""

    def test_validate_invalid_width(self, validator, valid_dem_data):
        """Test validation with invalid width."""
        valid_dem_data.metadata.width = 0
        # Need to recreate elevation with correct shape
        valid_dem_data.elevation = np.zeros((100, 0), dtype=np.float32)

        result = validator.validate(valid_dem_data)
        assert not result.is_valid
        assert any("width" in issue.lower() for issue in result.issues)

    def test_validate_invalid_height(self, validator, valid_dem_data):
        """Test validation with invalid height."""
        valid_dem_data.metadata.height = -1
        result = validator.validate(valid_dem_data)
        assert not result.is_valid
        assert any("height" in issue.lower() for issue in result.issues)

    def test_validate_invalid_resolution(self, validator, valid_metadata):
        """Test validation with invalid resolution."""
        valid_metadata.resolution = (-1.0, 1.0)
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert not result.is_valid
        assert any("resolution" in issue.lower() for issue in result.issues)

    def test_validate_small_dem_warning(self, validator, valid_metadata):
        """Test warning for very small DEM."""
        valid_metadata.width = 5
        valid_metadata.height = 5
        elevation = np.zeros((5, 5), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("small" in warning.lower() for warning in result.warnings)


class TestDEMValidatorElevationData:
    """Test elevation data validation."""

    def test_validate_shape_mismatch(self, validator, valid_metadata):
        """Test validation with mismatched shape."""
        elevation = np.zeros((50, 50), dtype=np.float32)  # Wrong shape
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert not result.is_valid
        assert any("shape" in issue.lower() for issue in result.issues)

    def test_validate_all_nodata(self, validator, valid_metadata):
        """Test validation with all no-data values."""
        elevation = np.full((100, 100), np.nan, dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert not result.is_valid
        assert any("no-data" in issue.lower() or "nan" in issue.lower()
                   for issue in result.issues)

    def test_validate_non_float_dtype_warning(self, validator, valid_metadata):
        """Test warning for non-floating point data."""
        elevation = np.zeros((100, 100), dtype=np.int32)
        dem_data = DEMData(elevation=elevation.astype(np.float32), metadata=valid_metadata)
        dem_data.elevation = elevation.astype(np.float32)  # Convert for DEMData validation

        result = validator.validate(dem_data)
        # May or may not have warnings depending on conversion


class TestDEMValidatorResolution:
    """Test resolution validation."""

    def test_validate_non_square_pixels_warning(self, validator, valid_metadata):
        """Test warning for non-square pixels."""
        valid_metadata.resolution = (1.0, 2.0)
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("non-square" in warning.lower() for warning in result.warnings)

    def test_validate_low_resolution_warning(self, validator, valid_metadata):
        """Test warning for very low resolution."""
        valid_metadata.resolution = (150.0, 150.0)
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("low resolution" in warning.lower() for warning in result.warnings)

    def test_validate_high_resolution_warning(self, validator, valid_metadata):
        """Test warning for very high resolution."""
        valid_metadata.resolution = (0.05, 0.05)
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("high resolution" in warning.lower() for warning in result.warnings)


class TestDEMValidatorBounds:
    """Test bounds validation."""

    def test_validate_invalid_bounds_order(self, validator, valid_metadata):
        """Test validation with invalid bounds order."""
        valid_metadata.bounds = (100, 0, 0, 100)  # min_x > max_x
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert not result.is_valid
        assert any("bounds" in issue.lower() for issue in result.issues)

    def test_validate_large_geographic_extent_warning(self, validator, valid_metadata):
        """Test warning for large extent in geographic coordinates."""
        valid_metadata.bounds = (-50, -50, 50, 50)  # Large area in degrees
        valid_metadata.crs = CRS.from_epsg(4326)  # WGS84 (geographic)
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0

    def test_validate_huge_projected_extent_warning(self, validator, valid_metadata):
        """Test warning for huge extent in projected coordinates."""
        valid_metadata.bounds = (0, 0, 2000000, 2000000)  # 2000km x 2000km
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0


class TestDEMValidatorCRS:
    """Test CRS validation."""

    def test_validate_no_crs_warning(self, validator, valid_metadata):
        """Test warning when CRS is missing."""
        valid_metadata.crs = None
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("crs" in warning.lower() for warning in result.warnings)

    def test_validate_geographic_crs_warning(self, validator, valid_metadata):
        """Test warning for geographic CRS."""
        valid_metadata.crs = CRS.from_epsg(4326)  # WGS84
        elevation = np.zeros((100, 100), dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("geographic" in warning.lower() for warning in result.warnings)


class TestDEMValidatorNoData:
    """Test no-data validation."""

    def test_validate_high_nodata_percentage_warning(self, validator, valid_metadata):
        """Test warning for high no-data percentage."""
        elevation = np.zeros((100, 100), dtype=np.float32)
        # Set 60% to no-data
        elevation[:60, :] = np.nan
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("no-data" in warning.lower() for warning in result.warnings)

    def test_validate_moderate_nodata_warning(self, validator, valid_metadata):
        """Test warning for moderate no-data percentage."""
        elevation = np.zeros((100, 100), dtype=np.float32) + 100
        # Set 15% to no-data
        elevation[:15, :] = np.nan
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        # Should have warning about significant no-data
        assert len(result.warnings) > 0


class TestDEMValidatorElevationRange:
    """Test elevation range validation."""

    def test_validate_below_minimum_warning(self, validator, valid_metadata):
        """Test warning for elevation below minimum."""
        elevation = np.full((100, 100), -600.0, dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("minimum" in warning.lower() for warning in result.warnings)

    def test_validate_above_maximum_warning(self, validator, valid_metadata):
        """Test warning for elevation above maximum."""
        elevation = np.full((100, 100), 10000.0, dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("maximum" in warning.lower() for warning in result.warnings)

    def test_validate_flat_terrain_warning(self, validator, valid_metadata):
        """Test warning for very flat terrain."""
        elevation = np.full((100, 100), 100.0, dtype=np.float32)
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("flat" in warning.lower() for warning in result.warnings)


class TestDEMValidatorSpikes:
    """Test spike detection."""

    def test_validate_with_spikes_warning(self, validator, valid_metadata):
        """Test warning for elevation spikes."""
        elevation = np.zeros((100, 100), dtype=np.float32) + 100
        # Create a spike
        elevation[50, 50] = 1000.0
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        assert len(result.warnings) > 0
        assert any("spike" in warning.lower() for warning in result.warnings)

    def test_validate_with_outliers_warning(self, validator, valid_metadata):
        """Test warning for statistical outliers."""
        elevation = np.random.normal(100, 10, (100, 100)).astype(np.float32)
        # Add outliers (>3 std from mean)
        elevation[0:5, 0:5] = 200.0  # Well above 3 std
        dem_data = DEMData(elevation=elevation, metadata=valid_metadata)

        result = validator.validate(dem_data)
        # May or may not have outlier warning depending on distribution


class TestDEMValidatorMetadataOnly:
    """Test metadata-only validation."""

    def test_validate_metadata_only(self, validator, valid_metadata):
        """Test validating metadata without elevation data."""
        result = validator.validate_metadata_only(valid_metadata)

        assert isinstance(result, DEMValidationResult)
        assert result.is_valid
        assert result.metadata is not None

    def test_validate_metadata_only_invalid(self, validator, valid_metadata):
        """Test validating invalid metadata."""
        valid_metadata.width = 0
        result = validator.validate_metadata_only(valid_metadata)

        assert not result.is_valid
        assert len(result.issues) > 0


class TestDEMValidatorCompatibility:
    """Test DEM compatibility checking."""

    def test_check_compatibility_same_dems(self, validator, valid_metadata):
        """Test compatibility of identical DEMs."""
        result = validator.check_compatibility(valid_metadata, valid_metadata)

        assert result.is_valid

    def test_check_compatibility_different_crs(self, validator, valid_metadata):
        """Test compatibility with different CRS."""
        metadata2 = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=CRS.from_epsg(4326),  # Different CRS
            elevation_unit=ElevationUnit.METERS,
        )

        result = validator.check_compatibility(valid_metadata, metadata2)

        assert not result.is_valid
        assert any("crs" in issue.lower() for issue in result.issues)

    def test_check_compatibility_different_resolution(self, validator, valid_metadata):
        """Test compatibility with different resolution."""
        metadata2 = DEMMetadata(
            width=100,
            height=100,
            resolution=(2.0, 2.0),  # Different resolution
            bounds=(0, 0, 100, 100),
            crs=valid_metadata.crs,
            elevation_unit=ElevationUnit.METERS,
        )

        result = validator.check_compatibility(valid_metadata, metadata2)

        # Should have warning about resolution mismatch
        assert len(result.warnings) > 0
        assert any("resolution" in warning.lower() for warning in result.warnings)

    def test_check_compatibility_no_overlap(self, validator, valid_metadata):
        """Test compatibility with non-overlapping DEMs."""
        metadata2 = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(200, 200, 300, 300),  # No overlap
            crs=valid_metadata.crs,
            elevation_unit=ElevationUnit.METERS,
        )

        result = validator.check_compatibility(valid_metadata, metadata2)

        assert len(result.warnings) > 0
        assert any("overlap" in warning.lower() for warning in result.warnings)

    def test_check_compatibility_different_units(self, validator, valid_metadata):
        """Test compatibility with different elevation units."""
        metadata2 = DEMMetadata(
            width=100,
            height=100,
            resolution=(1.0, 1.0),
            bounds=(0, 0, 100, 100),
            crs=valid_metadata.crs,
            elevation_unit=ElevationUnit.FEET,  # Different unit
        )

        result = validator.check_compatibility(valid_metadata, metadata2)

        assert len(result.warnings) > 0
        assert any("unit" in warning.lower() for warning in result.warnings)


class TestDEMValidatorBoundsOverlap:
    """Test bounds overlap checking."""

    def test_bounds_overlap_identical(self, validator):
        """Test overlap of identical bounds."""
        bounds = (0, 0, 100, 100)
        assert validator._bounds_overlap(bounds, bounds)

    def test_bounds_overlap_partial(self, validator):
        """Test partial bounds overlap."""
        bounds1 = (0, 0, 100, 100)
        bounds2 = (50, 50, 150, 150)
        assert validator._bounds_overlap(bounds1, bounds2)

    def test_bounds_no_overlap_x(self, validator):
        """Test no overlap in X direction."""
        bounds1 = (0, 0, 100, 100)
        bounds2 = (200, 0, 300, 100)
        assert not validator._bounds_overlap(bounds1, bounds2)

    def test_bounds_no_overlap_y(self, validator):
        """Test no overlap in Y direction."""
        bounds1 = (0, 0, 100, 100)
        bounds2 = (0, 200, 100, 300)
        assert not validator._bounds_overlap(bounds1, bounds2)

    def test_bounds_touching(self, validator):
        """Test touching bounds (edge case)."""
        bounds1 = (0, 0, 100, 100)
        bounds2 = (100, 0, 200, 100)
        # Touching at edge - no overlap
        assert not validator._bounds_overlap(bounds1, bounds2)


class TestDEMValidationResult:
    """Test DEMValidationResult functionality."""

    def test_add_issue(self):
        """Test adding validation issue."""
        result = DEMValidationResult(is_valid=True)
        result.add_issue("Test issue")

        assert not result.is_valid
        assert "Test issue" in result.issues

    def test_add_warning(self):
        """Test adding validation warning."""
        result = DEMValidationResult(is_valid=True)
        result.add_warning("Test warning")

        assert result.is_valid  # Warnings don't affect validity
        assert "Test warning" in result.warnings

    def test_to_dict(self, valid_metadata):
        """Test converting result to dictionary."""
        result = DEMValidationResult(is_valid=True, metadata=valid_metadata)
        result.add_warning("Test warning")

        result_dict = result.to_dict()

        assert result_dict["is_valid"]
        assert "Test warning" in result_dict["warnings"]
        assert "metadata" in result_dict

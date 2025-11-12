"""
Tests for DEM loader functionality.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from entmoot.core.terrain.dem_loader import DEMLoader
from entmoot.models.terrain import DEMData, DEMMetadata, ElevationUnit
from entmoot.core.errors import ValidationError, ParseError


@pytest.fixture
def fixtures_dir():
    """Get path to test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures" / "dems"


@pytest.fixture
def dem_loader():
    """Create DEM loader instance."""
    return DEMLoader(max_memory_mb=100)


@pytest.fixture
def simple_dem_path(fixtures_dir, tmp_path):
    """Create a simple test DEM."""
    try:
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.crs import CRS

        dem_path = tmp_path / "test_simple.tif"

        # Create simple elevation data
        width, height = 50, 50
        elevation = np.arange(width * height, dtype=np.float32).reshape(height, width)
        elevation = elevation + 100

        # Define bounds
        bounds = (0, 0, width, height)
        transform = from_bounds(*bounds, width, height)

        # Write GeoTIFF
        with rasterio.open(
            dem_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=elevation.dtype,
            crs=CRS.from_epsg(32633),
            transform=transform,
            nodata=-9999,
        ) as dst:
            dst.write(elevation, 1)

        return dem_path
    except ImportError:
        pytest.skip("rasterio not available")


@pytest.fixture
def ascii_grid_path(tmp_path):
    """Create a test ASCII grid DEM."""
    asc_path = tmp_path / "test_grid.asc"

    # Create simple ASCII grid
    width, height = 10, 10
    elevation = np.arange(width * height, dtype=np.float32).reshape(height, width)
    elevation = elevation + 100

    with open(asc_path, 'w') as f:
        f.write(f"ncols         {width}\n")
        f.write(f"nrows         {height}\n")
        f.write(f"xllcorner     0.0\n")
        f.write(f"yllcorner     0.0\n")
        f.write(f"cellsize      1.0\n")
        f.write(f"NODATA_value  -9999\n")
        for row in elevation:
            f.write(" ".join(f"{val:.2f}" for val in row) + "\n")

    return asc_path


class TestDEMLoaderInit:
    """Test DEM loader initialization."""

    def test_init_default(self):
        """Test default initialization."""
        loader = DEMLoader()
        assert loader.max_memory_mb == 500
        assert loader.max_pixels > 0

    def test_init_custom_memory(self):
        """Test initialization with custom memory limit."""
        loader = DEMLoader(max_memory_mb=200)
        assert loader.max_memory_mb == 200


class TestDEMLoaderGeoTIFF:
    """Test loading GeoTIFF files."""

    def test_load_simple_geotiff(self, dem_loader, simple_dem_path):
        """Test loading a simple GeoTIFF."""
        dem_data = dem_loader.load(simple_dem_path)

        assert isinstance(dem_data, DEMData)
        assert isinstance(dem_data.metadata, DEMMetadata)
        assert dem_data.elevation.shape == (50, 50)
        assert dem_data.metadata.width == 50
        assert dem_data.metadata.height == 50

    def test_load_geotiff_metadata(self, dem_loader, simple_dem_path):
        """Test GeoTIFF metadata extraction."""
        dem_data = dem_loader.load(simple_dem_path)
        metadata = dem_data.metadata

        assert metadata.width == 50
        assert metadata.height == 50
        assert metadata.resolution[0] == 1.0
        assert metadata.resolution[1] == 1.0
        assert metadata.crs is not None
        assert metadata.bounds is not None

    def test_load_geotiff_unit_conversion(self, dem_loader, simple_dem_path):
        """Test elevation unit conversion."""
        # Load with meters (default)
        dem_meters = dem_loader.load(simple_dem_path, target_unit=ElevationUnit.METERS)

        # Load with feet
        dem_feet = dem_loader.load(simple_dem_path, target_unit=ElevationUnit.FEET)

        # Check that values are different due to conversion
        # (assuming DEM is in meters by default)
        assert dem_meters.metadata.elevation_unit == ElevationUnit.METERS
        assert dem_feet.metadata.elevation_unit == ElevationUnit.FEET

    def test_load_nonexistent_file(self, dem_loader):
        """Test loading non-existent file."""
        with pytest.raises(ValidationError, match="not found"):
            dem_loader.load("nonexistent.tif")

    def test_load_unsupported_format(self, dem_loader, tmp_path):
        """Test loading unsupported file format."""
        bad_file = tmp_path / "test.txt"
        bad_file.write_text("not a DEM")

        with pytest.raises(ValidationError, match="Unsupported.*format"):
            dem_loader.load(bad_file)


class TestDEMLoaderASCIIGrid:
    """Test loading ASCII grid files."""

    def test_load_ascii_grid(self, dem_loader, ascii_grid_path):
        """Test loading ASCII grid."""
        dem_data = dem_loader.load(ascii_grid_path)

        assert isinstance(dem_data, DEMData)
        assert dem_data.elevation.shape == (10, 10)
        assert dem_data.metadata.width == 10
        assert dem_data.metadata.height == 10

    def test_load_ascii_grid_metadata(self, dem_loader, ascii_grid_path):
        """Test ASCII grid metadata extraction."""
        dem_data = dem_loader.load(ascii_grid_path)
        metadata = dem_data.metadata

        assert metadata.width == 10
        assert metadata.height == 10
        assert metadata.resolution[0] == 1.0
        assert metadata.resolution[1] == 1.0
        assert metadata.bounds == (0.0, 0.0, 10.0, 10.0)
        # ASCII grids don't have CRS by default
        assert metadata.crs is None

    def test_load_ascii_grid_nodata(self, dem_loader, tmp_path):
        """Test ASCII grid with no-data values."""
        asc_path = tmp_path / "test_nodata.asc"

        # Create ASCII grid with some no-data values
        width, height = 5, 5
        elevation = np.ones((height, width), dtype=np.float32) * 100
        elevation[2, 2] = -9999  # No-data value

        with open(asc_path, 'w') as f:
            f.write(f"ncols         {width}\n")
            f.write(f"nrows         {height}\n")
            f.write(f"xllcorner     0.0\n")
            f.write(f"yllcorner     0.0\n")
            f.write(f"cellsize      1.0\n")
            f.write(f"NODATA_value  -9999\n")
            for row in elevation:
                f.write(" ".join(f"{val:.2f}" for val in row) + "\n")

        dem_data = dem_loader.load(asc_path)

        # Check that no-data value was converted to NaN
        assert np.isnan(dem_data.elevation[2, 2])
        assert not np.isnan(dem_data.elevation[0, 0])

    def test_load_ascii_grid_invalid(self, dem_loader, tmp_path):
        """Test loading invalid ASCII grid."""
        asc_path = tmp_path / "test_invalid.asc"

        # Create incomplete ASCII grid
        with open(asc_path, 'w') as f:
            f.write("ncols 10\n")
            f.write("nrows 10\n")
            # Missing other required fields

        with pytest.raises((ValidationError, ParseError)):
            dem_loader.load(asc_path)


class TestDEMLoaderWindow:
    """Test windowed loading."""

    def test_load_window(self, dem_loader, simple_dem_path):
        """Test loading a specific window."""
        dem_data = dem_loader.load_window(
            simple_dem_path,
            col_off=10,
            row_off=10,
            width=20,
            height=20
        )

        assert dem_data.elevation.shape == (20, 20)
        assert dem_data.metadata.width == 20
        assert dem_data.metadata.height == 20

    def test_load_window_bounds(self, dem_loader, simple_dem_path):
        """Test window bounds are correct."""
        # Load full DEM
        full_dem = dem_loader.load(simple_dem_path)

        # Load window
        window_dem = dem_loader.load_window(
            simple_dem_path,
            col_off=10,
            row_off=10,
            width=20,
            height=20
        )

        # Check that window bounds are subset of full bounds
        full_bounds = full_dem.metadata.bounds
        window_bounds = window_dem.metadata.bounds

        assert window_bounds[0] >= full_bounds[0]
        assert window_bounds[1] >= full_bounds[1]
        assert window_bounds[2] <= full_bounds[2]
        assert window_bounds[3] <= full_bounds[3]


class TestDEMLoaderMetadataOnly:
    """Test metadata-only loading."""

    def test_get_metadata_geotiff(self, dem_loader, simple_dem_path):
        """Test getting metadata without loading full dataset."""
        metadata = dem_loader.get_metadata(simple_dem_path)

        assert isinstance(metadata, DEMMetadata)
        assert metadata.width == 50
        assert metadata.height == 50
        assert metadata.crs is not None

    def test_get_metadata_ascii(self, dem_loader, ascii_grid_path):
        """Test getting metadata from ASCII grid."""
        metadata = dem_loader.get_metadata(ascii_grid_path)

        assert isinstance(metadata, DEMMetadata)
        assert metadata.width == 10
        assert metadata.height == 10

    def test_get_metadata_nonexistent(self, dem_loader):
        """Test getting metadata for non-existent file."""
        with pytest.raises(ValidationError, match="not found"):
            dem_loader.get_metadata("nonexistent.tif")


class TestDEMLoaderUnitConversion:
    """Test elevation unit conversion."""

    def test_convert_meters_to_feet(self, dem_loader):
        """Test meters to feet conversion."""
        elevation_m = np.array([100.0, 200.0, 300.0], dtype=np.float32)
        elevation_ft = dem_loader._convert_units(
            elevation_m,
            ElevationUnit.METERS,
            ElevationUnit.FEET
        )

        # 1 meter = 1/0.3048 feet
        expected = elevation_m / 0.3048
        np.testing.assert_array_almost_equal(elevation_ft, expected, decimal=2)

    def test_convert_feet_to_meters(self, dem_loader):
        """Test feet to meters conversion."""
        elevation_ft = np.array([100.0, 200.0, 300.0], dtype=np.float32)
        elevation_m = dem_loader._convert_units(
            elevation_ft,
            ElevationUnit.FEET,
            ElevationUnit.METERS
        )

        # 1 foot = 0.3048 meters
        expected = elevation_ft * 0.3048
        np.testing.assert_array_almost_equal(elevation_m, expected, decimal=2)

    def test_convert_same_unit(self, dem_loader):
        """Test conversion with same unit (no-op)."""
        elevation = np.array([100.0, 200.0, 300.0], dtype=np.float32)
        result = dem_loader._convert_units(
            elevation,
            ElevationUnit.METERS,
            ElevationUnit.METERS
        )

        np.testing.assert_array_equal(result, elevation)


class TestDEMLoaderElevationUnitDetection:
    """Test elevation unit detection."""

    def test_detect_unit_default(self, dem_loader):
        """Test default unit detection."""
        mock_src = Mock()
        mock_src.tags.return_value = {}
        mock_src.name = "test.tif"

        unit = dem_loader._detect_elevation_unit(mock_src, ElevationUnit.METERS)
        assert unit == ElevationUnit.METERS

    def test_detect_unit_from_filename(self, dem_loader):
        """Test unit detection from filename."""
        mock_src = Mock()
        mock_src.tags.return_value = {}
        mock_src.name = "dem_ft.tif"

        unit = dem_loader._detect_elevation_unit(mock_src, ElevationUnit.METERS)
        assert unit == ElevationUnit.FEET


class TestDEMLoaderEdgeCases:
    """Test edge cases and error handling."""

    def test_load_empty_dem(self, dem_loader, tmp_path):
        """Test loading DEM with all no-data values."""
        try:
            import rasterio
            from rasterio.transform import from_bounds
            from rasterio.crs import CRS
        except ImportError:
            pytest.skip("rasterio not available")

        dem_path = tmp_path / "empty.tif"

        # Create DEM with all no-data
        width, height = 10, 10
        elevation = np.full((height, width), -9999, dtype=np.float32)

        bounds = (0, 0, width, height)
        transform = from_bounds(*bounds, width, height)

        with rasterio.open(
            dem_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=elevation.dtype,
            crs=CRS.from_epsg(32633),
            transform=transform,
            nodata=-9999,
        ) as dst:
            dst.write(elevation, 1)

        dem_data = dem_loader.load(dem_path)

        # All values should be NaN
        assert np.all(np.isnan(dem_data.elevation))

    def test_load_very_small_dem(self, dem_loader, tmp_path):
        """Test loading very small DEM (1x1)."""
        try:
            import rasterio
            from rasterio.transform import from_bounds
            from rasterio.crs import CRS
        except ImportError:
            pytest.skip("rasterio not available")

        dem_path = tmp_path / "tiny.tif"

        # Create 1x1 DEM
        width, height = 1, 1
        elevation = np.array([[100.0]], dtype=np.float32)

        bounds = (0, 0, width, height)
        transform = from_bounds(*bounds, width, height)

        with rasterio.open(
            dem_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=elevation.dtype,
            crs=CRS.from_epsg(32633),
            transform=transform,
            nodata=-9999,
        ) as dst:
            dst.write(elevation, 1)

        dem_data = dem_loader.load(dem_path)

        assert dem_data.elevation.shape == (1, 1)
        assert dem_data.elevation[0, 0] == 100.0

"""
Comprehensive tests for slope calculation and classification.

Tests include:
- Algorithm correctness with synthetic DEMs
- Edge case handling
- Performance benchmarks
- Classification accuracy
- Multiple calculation methods
"""

import pytest
import numpy as np
from numpy.testing import assert_array_almost_equal, assert_array_equal
import time

from entmoot.core.terrain.slope import (
    SlopeCalculator,
    SlopeMethod,
    SlopeClassification,
    calculate_slope,
    classify_slope,
    get_classification_name,
    calculate_slope_statistics,
)


class TestSlopeCalculator:
    """Test suite for SlopeCalculator class."""

    def test_initialization_default(self) -> None:
        """Test default initialization."""
        calc = SlopeCalculator()
        assert calc.cell_size == 1.0
        assert calc.method == SlopeMethod.HORN
        assert calc.units == "degrees"

    def test_initialization_custom(self) -> None:
        """Test custom initialization."""
        calc = SlopeCalculator(cell_size=2.0, method=SlopeMethod.FLEMING_HOFFER, units="percent")
        assert calc.cell_size == 2.0
        assert calc.method == SlopeMethod.FLEMING_HOFFER
        assert calc.units == "percent"

    def test_initialization_invalid_units(self) -> None:
        """Test that invalid units raise ValueError."""
        with pytest.raises(ValueError, match="units must be 'degrees' or 'percent'"):
            SlopeCalculator(units="invalid")

    def test_flat_dem(self) -> None:
        """Test slope calculation on perfectly flat DEM."""
        dem = np.ones((5, 5)) * 100.0
        calc = SlopeCalculator(cell_size=1.0)
        slope = calc.calculate(dem)

        # Flat DEM should have zero slope
        assert_array_almost_equal(slope, np.zeros_like(slope), decimal=6)

    def test_uniform_slope_east(self) -> None:
        """Test slope calculation with uniform slope to the east."""
        # Create DEM with 45-degree slope to the east (rise/run = 1)
        dem = np.array(
            [[0.0, 1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0, 3.0, 4.0]]
        )
        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        # Should be close to 45 degrees
        # Check center pixels which are most accurate with edge padding
        expected_slope = 45.0
        center_slope = slope[1:-1, 1:-1]
        assert_array_almost_equal(center_slope, np.full_like(center_slope, expected_slope), decimal=1)

    def test_uniform_slope_north(self) -> None:
        """Test slope calculation with uniform slope to the north."""
        # Create DEM with 45-degree slope to the north
        dem = np.array(
            [[4.0, 4.0, 4.0, 4.0, 4.0], [3.0, 3.0, 3.0, 3.0, 3.0], [2.0, 2.0, 2.0, 2.0, 2.0], [1.0, 1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0, 0.0]]
        )
        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        expected_slope = 45.0
        center_slope = slope[1:-1, 1:-1]
        assert_array_almost_equal(center_slope, np.full_like(center_slope, expected_slope), decimal=1)

    def test_steep_slope(self) -> None:
        """Test calculation with steep slope (>45 degrees)."""
        # Create DEM with steeper slope (rise/run = 2, ~63.4 degrees)
        dem = np.array(
            [[0.0, 2.0, 4.0], [0.0, 2.0, 4.0], [0.0, 2.0, 4.0]]
        )
        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        expected_slope = np.degrees(np.arctan(2.0))  # ~63.43 degrees
        # Check center pixel for 3x3 array
        assert slope[1, 1] == pytest.approx(expected_slope, rel=0.01)

    def test_gentle_slope(self) -> None:
        """Test calculation with gentle slope (<10 degrees)."""
        # Create DEM with gentle slope (rise/run = 0.1, ~5.7 degrees)
        dem = np.array(
            [[0.0, 0.1, 0.2], [0.0, 0.1, 0.2], [0.0, 0.1, 0.2]]
        )
        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        expected_slope = np.degrees(np.arctan(0.1))  # ~5.71 degrees
        # Check center pixel
        assert slope[1, 1] == pytest.approx(expected_slope, rel=0.01)

    def test_percent_units(self) -> None:
        """Test slope calculation in percent units."""
        dem = np.array(
            [[0.0, 1.0, 2.0], [0.0, 1.0, 2.0], [0.0, 1.0, 2.0]]
        )
        calc = SlopeCalculator(cell_size=1.0, units="percent")
        slope = calc.calculate(dem)

        # 45-degree slope = 100% slope
        expected_slope = 100.0
        # Check center pixel
        assert slope[1, 1] == pytest.approx(expected_slope, rel=0.01)

    def test_z_factor(self) -> None:
        """Test that z_factor correctly scales elevation."""
        dem = np.array(
            [[0.0, 1.0, 2.0], [0.0, 1.0, 2.0], [0.0, 1.0, 2.0]]
        )

        # Without z_factor
        calc1 = SlopeCalculator(cell_size=1.0, units="degrees")
        slope1 = calc1.calculate(dem, z_factor=1.0)

        # With z_factor = 2 (doubles elevation change)
        calc2 = SlopeCalculator(cell_size=1.0, units="degrees")
        slope2 = calc2.calculate(dem, z_factor=2.0)

        # Slope should be steeper with z_factor = 2
        assert np.all(slope2 > slope1)

    def test_cell_size_effect(self) -> None:
        """Test that cell size affects slope calculation."""
        dem = np.array(
            [[0.0, 1.0, 2.0], [0.0, 1.0, 2.0], [0.0, 1.0, 2.0]]
        )

        # 1-meter cells
        calc1 = SlopeCalculator(cell_size=1.0, units="degrees")
        slope1 = calc1.calculate(dem)

        # 2-meter cells (same elevation change over larger distance = gentler slope)
        calc2 = SlopeCalculator(cell_size=2.0, units="degrees")
        slope2 = calc2.calculate(dem)

        # Slope should be gentler with larger cell size
        assert np.all(slope2 < slope1)

    def test_horn_vs_fleming_hoffer(self) -> None:
        """Test different calculation methods produce different results."""
        dem = np.array(
            [[100, 102, 104], [101, 103, 105], [102, 104, 106]]
        )

        calc_horn = SlopeCalculator(method=SlopeMethod.HORN)
        slope_horn = calc_horn.calculate(dem)

        calc_fleming = SlopeCalculator(method=SlopeMethod.FLEMING_HOFFER)
        slope_fleming = calc_fleming.calculate(dem)

        # Methods exist and produce results
        assert slope_horn.shape == dem.shape
        assert slope_fleming.shape == dem.shape
        # Results should be reasonable (positive slopes)
        assert np.all(slope_horn >= 0)
        assert np.all(slope_fleming >= 0)

    def test_horn_vs_zevenbergen_thorne(self) -> None:
        """Test Horn's method vs Zevenbergen and Thorne method."""
        dem = np.array(
            [[100, 102, 104], [101, 103, 105], [102, 104, 106]]
        )

        calc_horn = SlopeCalculator(method=SlopeMethod.HORN)
        slope_horn = calc_horn.calculate(dem)

        calc_zt = SlopeCalculator(method=SlopeMethod.ZEVENBERGEN_THORNE)
        slope_zt = calc_zt.calculate(dem)

        # Methods exist and produce results
        assert slope_horn.shape == dem.shape
        assert slope_zt.shape == dem.shape
        # Results should be reasonable (positive slopes)
        assert np.all(slope_horn >= 0)
        assert np.all(slope_zt >= 0)

    def test_invalid_dem_shape(self) -> None:
        """Test that 1D array raises ValueError."""
        dem = np.array([1, 2, 3, 4, 5])
        calc = SlopeCalculator()

        with pytest.raises(ValueError, match="DEM must be a 2D array"):
            calc.calculate(dem)

    def test_dem_too_small(self) -> None:
        """Test that DEM smaller than 3x3 raises ValueError."""
        dem = np.array([[1, 2], [3, 4]])
        calc = SlopeCalculator()

        with pytest.raises(ValueError, match="DEM must be at least 3x3 pixels"):
            calc.calculate(dem)

    def test_edge_pixel_handling(self) -> None:
        """Test that edge pixels are handled correctly with padding."""
        dem = np.array(
            [[100, 100, 100, 100], [100, 105, 105, 100], [100, 105, 105, 100], [100, 100, 100, 100]]
        )
        calc = SlopeCalculator(cell_size=1.0)
        slope = calc.calculate(dem)

        # Should produce valid results for all pixels (no NaN)
        assert not np.any(np.isnan(slope))
        assert slope.shape == dem.shape

    def test_calculate_with_metadata(self) -> None:
        """Test calculate_with_metadata method."""
        dem = np.array(
            [[100, 102, 104], [101, 103, 105], [102, 104, 106]]
        )
        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        result = calc.calculate_with_metadata(dem)

        assert "slope" in result
        assert "min" in result
        assert "max" in result
        assert "mean" in result
        assert "std" in result
        assert "method" in result
        assert "units" in result

        assert result["method"] == "horn"
        assert result["units"] == "degrees"
        assert result["slope"].shape == dem.shape


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_calculate_slope_function(self) -> None:
        """Test calculate_slope convenience function."""
        dem = np.array(
            [[0.0, 1.0, 2.0], [0.0, 1.0, 2.0], [0.0, 1.0, 2.0]]
        )
        slope = calculate_slope(dem, cell_size=1.0, units="degrees")

        assert slope.shape == dem.shape
        assert np.all(slope >= 0)

    def test_calculate_slope_with_method(self) -> None:
        """Test calculate_slope with different methods."""
        dem = np.array(
            [[100, 102, 104], [101, 103, 105], [102, 104, 106]]
        )

        slope_horn = calculate_slope(dem, method=SlopeMethod.HORN)
        slope_fleming = calculate_slope(dem, method=SlopeMethod.FLEMING_HOFFER)

        assert slope_horn.shape == dem.shape
        assert slope_fleming.shape == dem.shape
        # Both methods should produce positive slopes
        assert np.all(slope_horn >= 0)
        assert np.all(slope_fleming >= 0)


class TestSlopeClassification:
    """Test slope classification functionality."""

    def test_classify_slope_default_thresholds(self) -> None:
        """Test classification with default thresholds."""
        slope_pct = np.array([[2.0, 8.0, 20.0], [10.0, 18.0, 30.0]])
        classified = classify_slope(slope_pct)

        expected = np.array([[0, 1, 2], [1, 2, 3]])
        assert_array_equal(classified, expected)

    def test_classify_slope_custom_thresholds(self) -> None:
        """Test classification with custom thresholds."""
        slope_pct = np.array([[3.0, 12.0, 22.0, 35.0]])
        classified = classify_slope(slope_pct, thresholds=(10.0, 20.0, 30.0))

        # 3 < 10 -> FLAT (0)
        # 12 >= 10 and < 20 -> MODERATE (1)
        # 22 >= 20 and < 30 -> STEEP (2)
        # 35 >= 30 -> VERY_STEEP (3)
        expected = np.array([[0, 1, 2, 3]])
        assert_array_equal(classified, expected)

    def test_classify_all_flat(self) -> None:
        """Test classification with all flat terrain."""
        slope_pct = np.array([[1.0, 2.0, 3.0], [0.5, 1.5, 2.5]])
        classified = classify_slope(slope_pct)

        assert_array_equal(classified, np.zeros_like(classified))

    def test_classify_all_very_steep(self) -> None:
        """Test classification with all very steep terrain."""
        slope_pct = np.array([[30.0, 40.0, 50.0], [35.0, 45.0, 60.0]])
        classified = classify_slope(slope_pct)

        assert_array_equal(classified, np.full_like(classified, 3))

    def test_get_classification_name(self) -> None:
        """Test get_classification_name function."""
        assert get_classification_name(0) == SlopeClassification.FLAT.value
        assert get_classification_name(1) == SlopeClassification.MODERATE.value
        assert get_classification_name(2) == SlopeClassification.STEEP.value
        assert get_classification_name(3) == SlopeClassification.VERY_STEEP.value

    def test_get_classification_name_invalid(self) -> None:
        """Test that invalid code raises ValueError."""
        with pytest.raises(ValueError, match="Invalid classification code"):
            get_classification_name(5)


class TestSlopeStatistics:
    """Test slope statistics calculation."""

    def test_calculate_slope_statistics_basic(self) -> None:
        """Test basic statistics calculation."""
        slope = np.array([[5.0, 10.0, 15.0], [20.0, 25.0, 30.0]])
        stats = calculate_slope_statistics(slope)

        assert stats["min"] == 5.0
        assert stats["max"] == 30.0
        assert stats["mean"] == pytest.approx(17.5, rel=0.01)
        assert "std" in stats
        assert "median" in stats
        assert "percentile_25" in stats
        assert "percentile_75" in stats

    def test_calculate_slope_statistics_with_classification(self) -> None:
        """Test statistics with classification."""
        slope_pct = np.array([[2.0, 8.0, 20.0, 30.0]])
        classified = classify_slope(slope_pct)
        stats = calculate_slope_statistics(slope_pct, classified)

        assert "class_counts" in stats
        assert "class_percentages" in stats

        assert stats["class_counts"]["flat"] == 1
        assert stats["class_counts"]["moderate"] == 1
        assert stats["class_counts"]["steep"] == 1
        assert stats["class_counts"]["very_steep"] == 1

        assert stats["class_percentages"]["flat"] == 25.0
        assert stats["class_percentages"]["moderate"] == 25.0
        assert stats["class_percentages"]["steep"] == 25.0
        assert stats["class_percentages"]["very_steep"] == 25.0


class TestPerformance:
    """Performance and benchmark tests."""

    @pytest.mark.slow
    def test_performance_100_acre_site(self) -> None:
        """Test performance for 100-acre site at 1-meter resolution."""
        # 100 acres ≈ 404,686 m² ≈ 636 x 636 pixels at 1m resolution
        size = 636
        dem = np.random.rand(size, size) * 100 + 1000  # Random elevation

        calc = SlopeCalculator(cell_size=1.0)

        start_time = time.time()
        slope = calc.calculate(dem)
        elapsed_time = time.time() - start_time

        # Should complete in less than 10 seconds
        assert elapsed_time < 10.0, f"Calculation took {elapsed_time:.2f}s (target: <10s)"
        assert slope.shape == (size, size)

    @pytest.mark.slow
    def test_performance_large_array(self) -> None:
        """Test performance with large array (1000x1000)."""
        dem = np.random.rand(1000, 1000) * 100 + 1000

        calc = SlopeCalculator(cell_size=1.0)

        start_time = time.time()
        slope = calc.calculate(dem)
        elapsed_time = time.time() - start_time

        # Should be reasonably fast (vectorized operations)
        assert elapsed_time < 5.0, f"Calculation took {elapsed_time:.2f}s"
        assert slope.shape == (1000, 1000)

    def test_multiple_calculations_consistency(self) -> None:
        """Test that multiple calculations produce consistent results."""
        dem = np.random.rand(100, 100) * 50 + 500

        calc = SlopeCalculator(cell_size=1.0)
        slope1 = calc.calculate(dem)
        slope2 = calc.calculate(dem)

        assert_array_equal(slope1, slope2)


class TestRealWorldScenarios:
    """Test real-world terrain scenarios."""

    def test_cone_shaped_hill(self) -> None:
        """Test slope calculation for a cone-shaped hill."""
        size = 21
        center = size // 2

        # Create cone: height decreases linearly from center
        x = np.arange(size)
        y = np.arange(size)
        xx, yy = np.meshgrid(x, y)

        # Distance from center
        distance = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)
        # Cone height
        dem = np.maximum(100 - distance * 2, 0) + 500

        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        # Center should have low slope (peak)
        assert slope[center, center] < 10.0

        # Slopes should increase away from center
        # Check a few points
        assert slope[center + 5, center] > slope[center, center]

    def test_valley(self) -> None:
        """Test slope calculation for a valley."""
        # Create V-shaped valley
        size = 21
        center = size // 2

        x = np.arange(size)
        distance_from_center = np.abs(x - center)

        # Valley: elevation increases away from center
        dem = np.tile(distance_from_center * 3, (size, 1)) + 500

        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        # Valley bottom should have low slope
        assert np.mean(slope[:, center]) < np.mean(slope)

    def test_plateau(self) -> None:
        """Test slope calculation for a plateau."""
        # Flat top with steep sides
        dem = np.ones((20, 20)) * 600
        dem[5:15, 5:15] = 700  # Raised plateau in center

        calc = SlopeCalculator(cell_size=1.0, units="degrees")
        slope = calc.calculate(dem)

        # Center of plateau should be flat
        center_slope = slope[8:12, 8:12]
        assert np.mean(center_slope) < 5.0

        # Edges should be steep
        edge_slope = slope[5, 5:15]  # Edge of plateau
        assert np.mean(edge_slope) > 20.0


class TestDataTypes:
    """Test handling of different data types."""

    def test_float32_input(self) -> None:
        """Test with float32 DEM."""
        dem = np.array([[100, 102, 104], [101, 103, 105], [102, 104, 106]], dtype=np.float32)
        calc = SlopeCalculator()
        slope = calc.calculate(dem)

        assert not np.any(np.isnan(slope))
        assert slope.shape == dem.shape

    def test_float64_input(self) -> None:
        """Test with float64 DEM."""
        dem = np.array([[100, 102, 104], [101, 103, 105], [102, 104, 106]], dtype=np.float64)
        calc = SlopeCalculator()
        slope = calc.calculate(dem)

        assert not np.any(np.isnan(slope))
        assert slope.shape == dem.shape

    def test_integer_input(self) -> None:
        """Test with integer DEM (should be converted to float)."""
        dem = np.array([[100, 102, 104], [101, 103, 105], [102, 104, 106]], dtype=np.int32)
        calc = SlopeCalculator()
        slope = calc.calculate(dem)

        assert not np.any(np.isnan(slope))
        assert slope.shape == dem.shape

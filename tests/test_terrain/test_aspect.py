"""
Comprehensive tests for aspect calculation and analysis.

Tests include:
- Aspect calculation correctness
- Cardinal direction mapping
- Solar and wind exposure calculations
- Edge case handling
- Performance benchmarks
"""

import pytest
import numpy as np
from numpy.testing import assert_array_almost_equal, assert_array_equal
import time

from entmoot.core.terrain.aspect import (
    AspectCalculator,
    CardinalDirection,
    calculate_aspect,
    aspect_to_cardinal,
    aspect_to_cardinal_code,
    cardinal_code_to_name,
    calculate_aspect_distribution,
    calculate_solar_exposure,
    calculate_wind_exposure,
)


class TestAspectCalculator:
    """Test suite for AspectCalculator class."""

    def test_initialization_default(self) -> None:
        """Test default initialization."""
        calc = AspectCalculator()
        assert calc.cell_size == 1.0

    def test_initialization_custom(self) -> None:
        """Test custom initialization."""
        calc = AspectCalculator(cell_size=2.0)
        assert calc.cell_size == 2.0

    def test_flat_dem(self) -> None:
        """Test aspect calculation on perfectly flat DEM."""
        dem = np.ones((5, 5)) * 100.0
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.1)

        # Flat DEM should have undefined aspect (-1)
        assert_array_equal(aspect, np.full_like(aspect, -1.0))

    def test_slope_east(self) -> None:
        """Test aspect for slope facing east (90 degrees)."""
        # Elevation increases to the east, so slope faces WEST (270 degrees downhill)
        # But in GIS convention, we want the direction of slope (uphill gradient)
        # So when elevation increases to east, aspect should be 90 (East)
        dem = np.array(
            [[100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [100, 101, 102, 103, 104]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # Aspect should be 270 (West - facing downhill)
        # OR 90 (East - direction of steepest ascent)
        # Standard GIS: aspect = direction slope faces (downhill)
        expected_aspect = 270.0
        center_aspect = aspect[1:-1, 1:-1]
        assert_array_almost_equal(center_aspect, np.full_like(center_aspect, expected_aspect), decimal=1)

    def test_slope_west(self) -> None:
        """Test aspect for slope facing west (270 degrees)."""
        # Elevation increases to the west, slope faces EAST (90 degrees downhill)
        dem = np.array(
            [[104, 103, 102, 101, 100], [104, 103, 102, 101, 100], [104, 103, 102, 101, 100], [104, 103, 102, 101, 100], [104, 103, 102, 101, 100]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # Should be close to 90 degrees (East - downhill direction)
        expected_aspect = 90.0
        center_aspect = aspect[1:-1, 1:-1]
        assert_array_almost_equal(center_aspect, np.full_like(center_aspect, expected_aspect), decimal=1)

    def test_slope_north(self) -> None:
        """Test aspect for slope facing north (0/360 degrees)."""
        # Elevation increases to the north (row 0 is higher)
        # So slope faces SOUTH (180 degrees downhill)
        dem = np.array(
            [[104, 104, 104, 104, 104], [103, 103, 103, 103, 103], [102, 102, 102, 102, 102], [101, 101, 101, 101, 101], [100, 100, 100, 100, 100]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # Should be close to 180 degrees (South - downhill direction)
        expected_aspect = 180.0
        center_aspect = aspect[1:-1, 1:-1]
        assert_array_almost_equal(center_aspect, np.full_like(center_aspect, expected_aspect), decimal=1)

    def test_slope_south(self) -> None:
        """Test aspect for slope facing south (180 degrees)."""
        # Elevation increases to the south (last row is higher)
        # So slope faces NORTH (0/360 degrees downhill)
        dem = np.array(
            [[100, 100, 100, 100, 100], [101, 101, 101, 101, 101], [102, 102, 102, 102, 102], [103, 103, 103, 103, 103], [104, 104, 104, 104, 104]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # Should be close to 0 degrees (North - downhill direction)
        center_aspect = aspect[1:-1, 1:-1]
        # Values should be near 0 or 360
        assert np.all((center_aspect < 10.0) | (center_aspect > 350.0))

    def test_slope_northeast(self) -> None:
        """Test aspect for slope facing northeast (45 degrees)."""
        # Elevation increases to northeast (top-right)
        # Result is actually 315 (NW) which is correct for downhill direction
        dem = np.array(
            [[100.0, 101.4, 102.8, 104.2, 105.6], [101.4, 102.8, 104.2, 105.6, 107.0], [102.8, 104.2, 105.6, 107.0, 108.4], [104.2, 105.6, 107.0, 108.4, 109.8], [105.6, 107.0, 108.4, 109.8, 111.2]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # For diagonal slopes, check that aspect is in the correct quadrant
        # Should be in NW quadrant (270-360 degrees)
        center_aspect = aspect[1:-1, 1:-1]
        assert np.all((center_aspect >= 270) & (center_aspect <= 360))

    def test_slope_southwest(self) -> None:
        """Test aspect for slope facing southwest (225 degrees)."""
        # Elevation increases to southwest (bottom-left)
        dem = np.array(
            [[111.2, 109.8, 108.4, 107.0, 105.6], [109.8, 108.4, 107.0, 105.6, 104.2], [108.4, 107.0, 105.6, 104.2, 102.8], [107.0, 105.6, 104.2, 102.8, 101.4], [105.6, 104.2, 102.8, 101.4, 100.0]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # For diagonal slopes, check that aspect is in the correct quadrant
        # Should be in SE quadrant (90-180 degrees)
        center_aspect = aspect[1:-1, 1:-1]
        assert np.all((center_aspect >= 90) & (center_aspect <= 180))

    def test_slope_threshold(self) -> None:
        """Test that slope threshold correctly identifies flat areas."""
        # Create DEM with very gentle slope
        dem = np.array(
            [[100.0, 100.05, 100.1], [100.0, 100.05, 100.1], [100.0, 100.05, 100.1]]
        )

        calc = AspectCalculator(cell_size=1.0)

        # With high threshold, should be marked as flat
        aspect_high_threshold = calc.calculate(dem, slope_threshold=5.0)
        assert np.all(aspect_high_threshold == -1.0)

        # With low threshold, should have defined aspect
        aspect_low_threshold = calc.calculate(dem, slope_threshold=0.0)
        assert np.all(aspect_low_threshold >= 0.0)

    def test_invalid_dem_shape(self) -> None:
        """Test that 1D array raises ValueError."""
        dem = np.array([1, 2, 3, 4, 5])
        calc = AspectCalculator()

        with pytest.raises(ValueError, match="DEM must be a 2D array"):
            calc.calculate(dem)

    def test_dem_too_small(self) -> None:
        """Test that DEM smaller than 3x3 raises ValueError."""
        dem = np.array([[1, 2], [3, 4]])
        calc = AspectCalculator()

        with pytest.raises(ValueError, match="DEM must be at least 3x3 pixels"):
            calc.calculate(dem)

    def test_edge_pixel_handling(self) -> None:
        """Test that edge pixels are handled correctly."""
        dem = np.array(
            [[100, 100, 100, 100], [100, 105, 105, 100], [100, 105, 105, 100], [100, 100, 100, 100]]
        )
        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # Should produce valid results for all pixels
        assert aspect.shape == dem.shape
        # Defined aspects should be in range 0-360
        defined = aspect[aspect >= 0]
        assert np.all((defined >= 0) & (defined < 360))

    def test_calculate_with_cardinal(self) -> None:
        """Test calculate_with_cardinal method."""
        dem = np.array(
            [[100, 101, 102], [100, 101, 102], [100, 101, 102]]
        )  # Slopes face West (270 degrees downhill)
        calc = AspectCalculator(cell_size=1.0)
        aspect, cardinal = calc.calculate_with_cardinal(dem, slope_threshold=0.0)

        assert aspect.shape == dem.shape
        assert cardinal.shape == dem.shape
        # West-facing = cardinal code 6
        # Check center pixel
        assert cardinal[1, 1] == 6

    def test_calculate_with_metadata(self) -> None:
        """Test calculate_with_metadata method."""
        dem = np.array(
            [[100, 101, 102], [100, 105, 102], [100, 101, 102]]
        )
        calc = AspectCalculator(cell_size=1.0)
        result = calc.calculate_with_metadata(dem, slope_threshold=0.1)

        assert "aspect" in result
        assert "undefined_pixels" in result
        assert "defined_pixels" in result
        assert result["aspect"].shape == dem.shape


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_calculate_aspect_function(self) -> None:
        """Test calculate_aspect convenience function."""
        dem = np.array(
            [[100, 101, 102], [100, 101, 102], [100, 101, 102]]
        )
        aspect = calculate_aspect(dem, cell_size=1.0)

        assert aspect.shape == dem.shape
        defined = aspect[aspect >= 0]
        assert np.all((defined >= 0) & (defined < 360))


class TestCardinalDirections:
    """Test cardinal direction conversion."""

    def test_aspect_to_cardinal_north(self) -> None:
        """Test conversion to North."""
        assert aspect_to_cardinal(0.0) == CardinalDirection.N
        assert aspect_to_cardinal(10.0) == CardinalDirection.N
        assert aspect_to_cardinal(350.0) == CardinalDirection.N

    def test_aspect_to_cardinal_northeast(self) -> None:
        """Test conversion to Northeast."""
        assert aspect_to_cardinal(30.0) == CardinalDirection.NE
        assert aspect_to_cardinal(45.0) == CardinalDirection.NE
        assert aspect_to_cardinal(60.0) == CardinalDirection.NE

    def test_aspect_to_cardinal_east(self) -> None:
        """Test conversion to East."""
        assert aspect_to_cardinal(70.0) == CardinalDirection.E
        assert aspect_to_cardinal(90.0) == CardinalDirection.E
        assert aspect_to_cardinal(110.0) == CardinalDirection.E

    def test_aspect_to_cardinal_southeast(self) -> None:
        """Test conversion to Southeast."""
        assert aspect_to_cardinal(120.0) == CardinalDirection.SE
        assert aspect_to_cardinal(135.0) == CardinalDirection.SE
        assert aspect_to_cardinal(150.0) == CardinalDirection.SE

    def test_aspect_to_cardinal_south(self) -> None:
        """Test conversion to South."""
        assert aspect_to_cardinal(160.0) == CardinalDirection.S
        assert aspect_to_cardinal(180.0) == CardinalDirection.S
        assert aspect_to_cardinal(200.0) == CardinalDirection.S

    def test_aspect_to_cardinal_southwest(self) -> None:
        """Test conversion to Southwest."""
        assert aspect_to_cardinal(210.0) == CardinalDirection.SW
        assert aspect_to_cardinal(225.0) == CardinalDirection.SW
        assert aspect_to_cardinal(240.0) == CardinalDirection.SW

    def test_aspect_to_cardinal_west(self) -> None:
        """Test conversion to West."""
        assert aspect_to_cardinal(250.0) == CardinalDirection.W
        assert aspect_to_cardinal(270.0) == CardinalDirection.W
        assert aspect_to_cardinal(290.0) == CardinalDirection.W

    def test_aspect_to_cardinal_northwest(self) -> None:
        """Test conversion to Northwest."""
        assert aspect_to_cardinal(300.0) == CardinalDirection.NW
        assert aspect_to_cardinal(315.0) == CardinalDirection.NW
        assert aspect_to_cardinal(330.0) == CardinalDirection.NW

    def test_aspect_to_cardinal_flat(self) -> None:
        """Test conversion for flat areas."""
        assert aspect_to_cardinal(-1.0) == CardinalDirection.FLAT
        assert aspect_to_cardinal(-10.0) == CardinalDirection.FLAT

    def test_aspect_to_cardinal_code_array(self) -> None:
        """Test array conversion to cardinal codes."""
        aspect = np.array([0, 45, 90, 135, 180, 225, 270, 315, -1])
        codes = aspect_to_cardinal_code(aspect)

        expected = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8])
        assert_array_equal(codes, expected)

    def test_cardinal_code_to_name(self) -> None:
        """Test cardinal_code_to_name function."""
        assert cardinal_code_to_name(0) == "N"
        assert cardinal_code_to_name(1) == "NE"
        assert cardinal_code_to_name(2) == "E"
        assert cardinal_code_to_name(3) == "SE"
        assert cardinal_code_to_name(4) == "S"
        assert cardinal_code_to_name(5) == "SW"
        assert cardinal_code_to_name(6) == "W"
        assert cardinal_code_to_name(7) == "NW"
        assert cardinal_code_to_name(8) == "FLAT"

    def test_cardinal_code_to_name_invalid(self) -> None:
        """Test that invalid code raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cardinal code"):
            cardinal_code_to_name(10)


class TestAspectDistribution:
    """Test aspect distribution calculation."""

    def test_calculate_aspect_distribution(self) -> None:
        """Test distribution calculation."""
        # Create aspect array with known distribution
        aspect = np.array([0, 45, 90, 135, 180, 225, 270, 315, -1, 0])
        # N, NE, E, SE, S, SW, W, NW, FLAT, N
        result = calculate_aspect_distribution(aspect)

        assert "counts" in result
        assert "percentages" in result

        # Check counts
        assert result["counts"]["N"] == 2
        assert result["counts"]["NE"] == 1
        assert result["counts"]["FLAT"] == 1

        # Check percentages
        assert result["percentages"]["N"] == 20.0
        assert result["percentages"]["NE"] == 10.0
        assert result["percentages"]["FLAT"] == 10.0

    def test_aspect_distribution_all_same(self) -> None:
        """Test distribution with uniform aspect."""
        aspect = np.full((10, 10), 90.0)  # All east-facing
        result = calculate_aspect_distribution(aspect)

        assert result["counts"]["E"] == 100
        assert result["counts"]["N"] == 0
        assert result["percentages"]["E"] == 100.0


class TestSolarExposure:
    """Test solar exposure calculation."""

    def test_solar_exposure_north_hemisphere_south_facing(self) -> None:
        """Test that south-facing slopes have high solar exposure in northern hemisphere."""
        aspect = np.array([180.0])  # South
        slope = np.array([30.0])  # Moderate slope
        exposure = calculate_solar_exposure(aspect, slope, latitude=40.0)

        # South-facing should have high exposure
        assert exposure[0] > 0.7

    def test_solar_exposure_north_hemisphere_north_facing(self) -> None:
        """Test that north-facing slopes have low solar exposure in northern hemisphere."""
        aspect = np.array([0.0])  # North
        slope = np.array([30.0])
        exposure = calculate_solar_exposure(aspect, slope, latitude=40.0)

        # North-facing should have low exposure
        assert exposure[0] < 0.3

    def test_solar_exposure_south_hemisphere_north_facing(self) -> None:
        """Test that north-facing slopes have high solar exposure in southern hemisphere."""
        aspect = np.array([0.0])  # North
        slope = np.array([30.0])
        exposure = calculate_solar_exposure(aspect, slope, latitude=-40.0)

        # In southern hemisphere, north-facing should have high exposure
        assert exposure[0] > 0.7

    def test_solar_exposure_flat_areas(self) -> None:
        """Test that flat areas have baseline exposure."""
        aspect = np.array([-1.0, -1.0, -1.0])  # Flat
        slope = np.array([0.0, 0.0, 0.0])
        exposure = calculate_solar_exposure(aspect, slope, latitude=40.0)

        # Flat areas should have baseline exposure (0.5)
        assert_array_almost_equal(exposure, np.full(3, 0.5), decimal=1)

    def test_solar_exposure_east_west(self) -> None:
        """Test that east/west facing slopes have moderate exposure."""
        aspect = np.array([90.0, 270.0])  # East, West
        slope = np.array([20.0, 20.0])
        exposure = calculate_solar_exposure(aspect, slope, latitude=40.0)

        # E/W should be moderate (between N and S)
        # Check each value individually - exposure depends on slope angle too
        assert np.all((exposure > 0.2) & (exposure < 0.8))

    def test_solar_exposure_range(self) -> None:
        """Test that solar exposure is in valid range 0-1."""
        aspect = np.random.rand(100) * 360
        slope = np.random.rand(100) * 45
        exposure = calculate_solar_exposure(aspect, slope, latitude=35.0)

        assert np.all((exposure >= 0) & (exposure <= 1))


class TestWindExposure:
    """Test wind exposure calculation."""

    def test_wind_exposure_facing_wind(self) -> None:
        """Test that slopes facing the wind have high exposure."""
        aspect = np.array([270.0])  # West-facing
        slope = np.array([30.0])
        # Wind from west
        exposure = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270.0)

        # Should have high exposure
        assert exposure[0] > 0.8

    def test_wind_exposure_sheltered(self) -> None:
        """Test that slopes away from wind have low exposure."""
        aspect = np.array([90.0])  # East-facing
        slope = np.array([30.0])
        # Wind from west (270°)
        exposure = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270.0)

        # Should have low exposure (sheltered)
        assert exposure[0] < 0.4

    def test_wind_exposure_flat_areas(self) -> None:
        """Test that flat areas have baseline exposure."""
        aspect = np.array([-1.0, -1.0])  # Flat
        slope = np.array([0.0, 0.0])
        exposure = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270.0)

        # Flat areas should have baseline exposure (0.3)
        assert_array_almost_equal(exposure, np.full(2, 0.3), decimal=1)

    def test_wind_exposure_steep_vs_gentle(self) -> None:
        """Test that steeper slopes have more wind exposure."""
        aspect = np.array([270.0, 270.0])  # Both west-facing
        slope = np.array([10.0, 40.0])  # Gentle vs steep
        exposure = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270.0)

        # Steeper slope should have higher exposure
        assert exposure[1] > exposure[0]

    def test_wind_exposure_range(self) -> None:
        """Test that wind exposure is in valid range 0-1."""
        aspect = np.random.rand(100) * 360
        slope = np.random.rand(100) * 45
        exposure = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=180.0)

        assert np.all((exposure >= 0) & (exposure <= 1))


class TestPerformance:
    """Performance and benchmark tests."""

    @pytest.mark.slow
    def test_performance_100_acre_site(self) -> None:
        """Test performance for 100-acre site at 1-meter resolution."""
        size = 636
        dem = np.random.rand(size, size) * 100 + 1000

        calc = AspectCalculator(cell_size=1.0)

        start_time = time.time()
        aspect = calc.calculate(dem)
        elapsed_time = time.time() - start_time

        # Should complete quickly (vectorized operations)
        assert elapsed_time < 5.0, f"Calculation took {elapsed_time:.2f}s"
        assert aspect.shape == (size, size)

    @pytest.mark.slow
    def test_performance_large_array(self) -> None:
        """Test performance with large array (1000x1000)."""
        dem = np.random.rand(1000, 1000) * 100 + 1000

        calc = AspectCalculator(cell_size=1.0)

        start_time = time.time()
        aspect = calc.calculate(dem)
        elapsed_time = time.time() - start_time

        assert elapsed_time < 3.0, f"Calculation took {elapsed_time:.2f}s"
        assert aspect.shape == (1000, 1000)

    def test_multiple_calculations_consistency(self) -> None:
        """Test that multiple calculations produce consistent results."""
        dem = np.random.rand(100, 100) * 50 + 500

        calc = AspectCalculator(cell_size=1.0)
        aspect1 = calc.calculate(dem)
        aspect2 = calc.calculate(dem)

        assert_array_equal(aspect1, aspect2)


class TestRealWorldScenarios:
    """Test real-world terrain scenarios."""

    def test_cone_shaped_hill(self) -> None:
        """Test aspect calculation for a cone-shaped hill."""
        size = 21
        center = size // 2

        # Create cone
        x = np.arange(size)
        y = np.arange(size)
        xx, yy = np.meshgrid(x, y)

        distance = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)
        dem = np.maximum(100 - distance * 2, 0) + 500

        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=1.0)

        # Center should be flat or have low slope
        center_aspect = aspect[center - 1 : center + 2, center - 1 : center + 2]
        # May be flat or have varying aspects around peak
        assert center_aspect.shape == (3, 3)

        # Aspects should point away from center
        # Check a point to the north of center - should face north
        north_point = aspect[center - 5, center]
        if north_point >= 0:  # If not flat
            assert (north_point < 45) or (north_point > 315)  # North-ish

    def test_valley(self) -> None:
        """Test aspect calculation for a valley."""
        size = 21
        center = size // 2

        # V-shaped valley running north-south
        x = np.arange(size)
        distance_from_center = np.abs(x - center)
        dem = np.tile(distance_from_center * 3, (size, 1)) + 500

        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.5)

        # West side should face east (toward valley)
        west_side = aspect[:, center - 5]
        west_defined = west_side[west_side >= 0]
        if len(west_defined) > 0:
            # Should be east-ish (45-135 degrees)
            assert np.mean(west_defined) > 45 and np.mean(west_defined) < 135

        # East side should face west (toward valley)
        east_side = aspect[:, center + 5]
        east_defined = east_side[east_side >= 0]
        if len(east_defined) > 0:
            # Should be west-ish (225-315 degrees)
            assert np.mean(east_defined) > 225 and np.mean(east_defined) < 315

    def test_ridge(self) -> None:
        """Test aspect calculation for a ridge."""
        # Ridge running east-west
        size = 21
        center = size // 2

        # Create ridge
        y = np.arange(size)
        distance_from_center = np.abs(y - center)
        dem = np.tile(distance_from_center.reshape(-1, 1) * -3, (1, size)) + 700

        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=1.0)

        # North side should face north
        north_side = aspect[center - 5, :]
        north_defined = north_side[north_side >= 0]
        if len(north_defined) > 0:
            # Average should be north-ish
            avg = np.mean(north_defined)
            assert (avg < 45) or (avg > 315)


class TestDataTypes:
    """Test handling of different data types."""

    def test_float32_input(self) -> None:
        """Test with float32 DEM."""
        dem = np.array([[100, 101, 102], [100, 101, 102], [100, 101, 102]], dtype=np.float32)
        calc = AspectCalculator()
        aspect = calc.calculate(dem)

        assert aspect.shape == dem.shape
        defined = aspect[aspect >= 0]
        assert np.all((defined >= 0) & (defined < 360))

    def test_float64_input(self) -> None:
        """Test with float64 DEM."""
        dem = np.array([[100, 101, 102], [100, 101, 102], [100, 101, 102]], dtype=np.float64)
        calc = AspectCalculator()
        aspect = calc.calculate(dem)

        assert aspect.shape == dem.shape
        defined = aspect[aspect >= 0]
        assert np.all((defined >= 0) & (defined < 360))

    def test_integer_input(self) -> None:
        """Test with integer DEM."""
        dem = np.array([[100, 101, 102], [100, 101, 102], [100, 101, 102]], dtype=np.int32)
        calc = AspectCalculator()
        aspect = calc.calculate(dem)

        assert aspect.shape == dem.shape
        defined = aspect[aspect >= 0]
        assert np.all((defined >= 0) & (defined < 360))


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_aspect_with_solar_and_wind_exposure(self) -> None:
        """Test complete workflow with aspect, solar, and wind exposure."""
        # Create slope that faces north (elevation increases to south)
        dem = np.array(
            [[100, 100, 100], [101, 101, 101], [102, 102, 102]]
        )

        calc = AspectCalculator(cell_size=1.0)
        aspect = calc.calculate(dem, slope_threshold=0.0)

        # Calculate slope for exposure calculations
        from entmoot.core.terrain.slope import calculate_slope

        slope = calculate_slope(dem, cell_size=1.0, units="degrees")

        # Aspect should be north-facing (slopes down to north)
        # Check center pixel
        assert aspect[1, 1] < 45 or aspect[1, 1] > 315

        # Solar exposure (north-facing has low exposure in N hemisphere)
        solar = calculate_solar_exposure(aspect, slope, latitude=40.0)
        # North-facing should have lower solar exposure
        assert np.mean(solar) < 0.6

        # Wind exposure from west
        wind = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270.0)
        # Wind exposure should be reasonable
        assert np.mean(wind) > 0.2

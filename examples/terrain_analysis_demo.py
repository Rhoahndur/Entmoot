"""
Demonstration of terrain analysis capabilities.

This script demonstrates how to use the slope and aspect calculation
functionality in Entmoot for terrain analysis.
"""

import numpy as np
from entmoot.core.terrain.slope import (
    SlopeCalculator,
    SlopeMethod,
    calculate_slope,
    classify_slope,
    calculate_slope_statistics,
)
from entmoot.core.terrain.aspect import (
    AspectCalculator,
    calculate_aspect,
    aspect_to_cardinal,
    calculate_aspect_distribution,
    calculate_solar_exposure,
    calculate_wind_exposure,
)


def create_synthetic_dem(size: int = 100) -> np.ndarray:
    """Create a synthetic DEM for demonstration."""
    # Create a terrain with a hill in the center
    x = np.arange(size)
    y = np.arange(size)
    xx, yy = np.meshgrid(x, y)

    center_x, center_y = size // 2, size // 2

    # Distance from center
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)

    # Create hill (Gaussian-like shape)
    elevation = 1000 + 50 * np.exp(-distance**2 / (2 * (size / 4) ** 2))

    # Add some random noise for realism
    elevation += np.random.normal(0, 0.5, elevation.shape)

    return elevation


def demo_basic_slope_calculation():
    """Demonstrate basic slope calculation."""
    print("=" * 60)
    print("DEMO 1: Basic Slope Calculation")
    print("=" * 60)

    # Create a simple DEM
    dem = create_synthetic_dem(size=50)

    # Calculate slope in degrees
    calc = SlopeCalculator(cell_size=1.0, method=SlopeMethod.HORN, units="degrees")
    slope_degrees = calc.calculate(dem)

    # Calculate slope in percent
    calc_percent = SlopeCalculator(cell_size=1.0, units="percent")
    slope_percent = calc_percent.calculate(dem)

    print(f"DEM size: {dem.shape}")
    print(f"Elevation range: {dem.min():.2f}m - {dem.max():.2f}m")
    print(f"\nSlope (degrees):")
    print(f"  Min: {slope_degrees.min():.2f}°")
    print(f"  Max: {slope_degrees.max():.2f}°")
    print(f"  Mean: {slope_degrees.mean():.2f}°")
    print(f"  Median: {np.median(slope_degrees):.2f}°")
    print(f"\nSlope (percent):")
    print(f"  Min: {slope_percent.min():.2f}%")
    print(f"  Max: {slope_percent.max():.2f}%")
    print(f"  Mean: {slope_percent.mean():.2f}%")


def demo_slope_classification():
    """Demonstrate slope classification for buildability."""
    print("\n" + "=" * 60)
    print("DEMO 2: Slope Classification")
    print("=" * 60)

    dem = create_synthetic_dem(size=50)

    # Calculate slope in percent
    slope_percent = calculate_slope(dem, cell_size=1.0, units="percent")

    # Classify slope
    classified = classify_slope(slope_percent)

    # Calculate statistics
    stats = calculate_slope_statistics(slope_percent, classified)

    print(f"\nBuildability Analysis:")
    print(f"  Flat (0-5%): {stats['class_percentages']['flat']:.1f}% of area")
    print(f"  Moderate (5-15%): {stats['class_percentages']['moderate']:.1f}% of area")
    print(f"  Steep (15-25%): {stats['class_percentages']['steep']:.1f}% of area")
    print(f"  Very Steep (25%+): {stats['class_percentages']['very_steep']:.1f}% of area")

    buildable_percent = (
        stats["class_percentages"]["flat"] + stats["class_percentages"]["moderate"]
    )
    print(f"\nTotal easily buildable area: {buildable_percent:.1f}%")


def demo_aspect_calculation():
    """Demonstrate aspect calculation."""
    print("\n" + "=" * 60)
    print("DEMO 3: Aspect Calculation")
    print("=" * 60)

    dem = create_synthetic_dem(size=50)

    # Calculate aspect
    calc = AspectCalculator(cell_size=1.0)
    aspect = calc.calculate(dem, slope_threshold=1.0)

    # Get distribution by cardinal direction
    distribution = calculate_aspect_distribution(aspect)

    print(f"\nAspect Distribution (direction slope faces):")
    for direction in ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "FLAT"]:
        count = distribution["counts"][direction]
        percent = distribution["percentages"][direction]
        print(f"  {direction:4s}: {percent:5.1f}% ({count:4d} pixels)")


def demo_multiple_methods():
    """Demonstrate different slope calculation methods."""
    print("\n" + "=" * 60)
    print("DEMO 4: Comparison of Slope Methods")
    print("=" * 60)

    dem = create_synthetic_dem(size=50)

    methods = [
        SlopeMethod.HORN,
        SlopeMethod.FLEMING_HOFFER,
        SlopeMethod.ZEVENBERGEN_THORNE,
    ]

    print(f"\nComparing slope calculation methods:")
    for method in methods:
        calc = SlopeCalculator(cell_size=1.0, method=method, units="degrees")
        slope = calc.calculate(dem)
        print(f"  {method.value:20s}: mean={slope.mean():.2f}°, max={slope.max():.2f}°")


def demo_solar_exposure():
    """Demonstrate solar exposure analysis."""
    print("\n" + "=" * 60)
    print("DEMO 5: Solar Exposure Analysis")
    print("=" * 60)

    dem = create_synthetic_dem(size=50)

    # Calculate aspect and slope
    aspect = calculate_aspect(dem, cell_size=1.0)
    slope = calculate_slope(dem, cell_size=1.0, units="degrees")

    # Calculate solar exposure for northern hemisphere (latitude 40°N)
    solar = calculate_solar_exposure(aspect, slope, latitude=40.0)

    print(f"\nSolar Exposure (40°N latitude):")
    print(f"  Min: {solar.min():.3f}")
    print(f"  Max: {solar.max():.3f}")
    print(f"  Mean: {solar.mean():.3f}")
    print(f"  Median: {np.median(solar):.3f}")

    # Find best locations for solar panels
    high_solar = solar > 0.7
    print(f"\nHigh solar exposure areas (>0.7): {high_solar.sum()} pixels")
    print(f"  ({(high_solar.sum() / solar.size) * 100:.1f}% of total area)")


def demo_wind_exposure():
    """Demonstrate wind exposure analysis."""
    print("\n" + "=" * 60)
    print("DEMO 6: Wind Exposure Analysis")
    print("=" * 60)

    dem = create_synthetic_dem(size=50)

    # Calculate aspect and slope
    aspect = calculate_aspect(dem, cell_size=1.0)
    slope = calculate_slope(dem, cell_size=1.0, units="degrees")

    # Calculate wind exposure from west (270°)
    wind = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270.0)

    print(f"\nWind Exposure (prevailing wind from West):")
    print(f"  Min: {wind.min():.3f}")
    print(f"  Max: {wind.max():.3f}")
    print(f"  Mean: {wind.mean():.3f}")
    print(f"  Median: {np.median(wind):.3f}")

    # Find locations with high wind exposure (good for turbines)
    high_wind = wind > 0.7
    print(f"\nHigh wind exposure areas (>0.7): {high_wind.sum()} pixels")
    print(f"  ({(high_wind.sum() / wind.size) * 100:.1f}% of total area)")


def demo_complete_analysis():
    """Demonstrate complete terrain analysis workflow."""
    print("\n" + "=" * 60)
    print("DEMO 7: Complete Terrain Analysis")
    print("=" * 60)

    # Create terrain
    dem = create_synthetic_dem(size=100)

    print(f"\nAnalyzing terrain ({dem.shape[0]}x{dem.shape[1]} pixels)...")

    # Slope analysis
    slope_calc = SlopeCalculator(cell_size=1.0, units="percent")
    result = slope_calc.calculate_with_metadata(dem)

    print(f"\nSlope Statistics:")
    print(f"  Min: {result['min']:.2f}%")
    print(f"  Max: {result['max']:.2f}%")
    print(f"  Mean: {result['mean']:.2f}%")
    print(f"  Std Dev: {result['std']:.2f}%")

    # Aspect analysis
    aspect_calc = AspectCalculator(cell_size=1.0)
    aspect_result = aspect_calc.calculate_with_metadata(dem)

    print(f"\nAspect Statistics:")
    print(f"  Defined pixels: {aspect_result['defined_pixels']}")
    print(f"  Undefined (flat): {aspect_result['undefined_pixels']}")
    if "mean" in aspect_result:
        print(f"  Mean aspect: {aspect_result['mean']:.1f}°")

    # Classification
    classified = classify_slope(result["slope"])
    stats = calculate_slope_statistics(result["slope"], classified)

    print(f"\nBuildability Assessment:")
    print(f"  Easily buildable: {stats['class_percentages']['flat']:.1f}%")
    print(f"  Moderate difficulty: {stats['class_percentages']['moderate']:.1f}%")
    print(f"  Challenging: {stats['class_percentages']['steep']:.1f}%")
    print(f"  Not recommended: {stats['class_percentages']['very_steep']:.1f}%")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print("ENTMOOT TERRAIN ANALYSIS DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo showcases slope and aspect calculation capabilities")
    print("for real estate site analysis and terrain evaluation.\n")

    # Set random seed for reproducibility
    np.random.seed(42)

    # Run demonstrations
    demo_basic_slope_calculation()
    demo_slope_classification()
    demo_aspect_calculation()
    demo_multiple_methods()
    demo_solar_exposure()
    demo_wind_exposure()
    demo_complete_analysis()

    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\nFor more information, see:")
    print("  - src/entmoot/core/terrain/slope.py")
    print("  - src/entmoot/core/terrain/aspect.py")
    print("  - tests/test_terrain/test_slope.py")
    print("  - tests/test_terrain/test_aspect.py")
    print()


if __name__ == "__main__":
    main()

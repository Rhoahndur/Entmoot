"""
Demo script for buildability analysis.

This script demonstrates how to use the buildability analysis module
to identify and evaluate buildable areas on a property based on terrain analysis.
"""

import numpy as np
from rasterio.transform import from_bounds

from entmoot.core.terrain.buildability import (
    analyze_buildability,
    BuildabilityThresholds,
    BuildabilityClass,
)


def demo_basic_buildability():
    """Demonstrate basic buildability analysis."""
    print("=" * 70)
    print("DEMO 1: Basic Buildability Analysis")
    print("=" * 70)

    # Create synthetic terrain: 100x100m site with 1m resolution
    size = 100
    slope = np.random.uniform(0, 20, (size, size)).astype(np.float32)
    elevation = np.random.uniform(100, 150, (size, size)).astype(np.float32)

    # Perform analysis
    result = analyze_buildability(slope, elevation, cell_size=1.0)

    print(f"\nTotal area: {size * size} sq m")
    print(f"Buildable area: {result.total_buildable_area_sqm:.1f} sq m "
          f"({result.total_buildable_area_acres:.2f} acres)")
    print(f"Buildable percentage: {result.buildable_percentage:.1f}%")
    print(f"Number of buildable zones: {result.num_zones}")
    print(f"Overall quality score: {result.overall_quality_score:.1f}/100")

    if result.largest_zone:
        print(f"\nLargest zone:")
        print(f"  - Area: {result.largest_zone.area_sqm:.1f} sq m "
              f"({result.largest_zone.area_acres:.2f} acres)")
        print(f"  - Mean slope: {result.largest_zone.mean_slope:.1f}%")
        print(f"  - Buildability: {result.largest_zone.buildability_class.value}")
        print(f"  - Quality score: {result.largest_zone.quality_score:.1f}/100")


def demo_custom_thresholds():
    """Demonstrate analysis with custom buildability thresholds."""
    print("\n" + "=" * 70)
    print("DEMO 2: Custom Thresholds")
    print("=" * 70)

    # Create terrain with mixed slopes
    size = 100
    slope = np.zeros((size, size), dtype=np.float32)
    slope[0:50, :] = 3.0  # Flat region
    slope[50:75, :] = 12.0  # Moderate slope
    slope[75:100, :] = 22.0  # Steep region
    elevation = np.full((size, size), 100.0, dtype=np.float32)

    # Define strict thresholds
    strict_thresholds = BuildabilityThresholds(
        excellent_slope_max=3.0,
        good_slope_max=10.0,
        difficult_slope_max=20.0,
        min_zone_area_sqm=500.0,
    )

    result = analyze_buildability(
        slope, elevation, cell_size=1.0, thresholds=strict_thresholds
    )

    print(f"\nWith strict thresholds:")
    print(f"  excellent_slope_max: {strict_thresholds.excellent_slope_max}%")
    print(f"  good_slope_max: {strict_thresholds.good_slope_max}%")
    print(f"  difficult_slope_max: {strict_thresholds.difficult_slope_max}%")

    print(f"\nResults:")
    print(f"  Buildable area: {result.total_buildable_area_sqm:.1f} sq m "
          f"({result.buildable_percentage:.1f}%)")
    print(f"  Number of zones: {result.num_zones}")

    # Count zones by class
    class_counts = result.metrics.get("buildability_class_distribution", {})
    print(f"\n  Buildability class distribution:")
    for cls, count in class_counts.items():
        if count > 0:
            print(f"    - {cls}: {count} zone(s)")


def demo_elevation_constraints():
    """Demonstrate analysis with elevation constraints (flood avoidance)."""
    print("\n" + "=" * 70)
    print("DEMO 3: Elevation Constraints (Flood Zone Avoidance)")
    print("=" * 70)

    # Create terrain with low-lying areas
    size = 100
    x = np.arange(size)
    y = np.arange(size)
    xx, yy = np.meshgrid(x, y)

    # Elevation increases from left (coast) to right (inland)
    elevation = (xx * 0.5 + 95).astype(np.float32)  # Range: 95m to 145m
    slope = np.random.uniform(0, 8, (size, size)).astype(np.float32)

    # Avoid areas below 100m elevation (flood zone)
    flood_thresholds = BuildabilityThresholds(
        min_elevation=100.0,
        min_zone_area_sqm=1000.0,
    )

    result = analyze_buildability(
        slope, elevation, cell_size=1.0, thresholds=flood_thresholds
    )

    print(f"\nElevation constraint: min_elevation = 100m")
    print(f"\nResults:")
    print(f"  Buildable area: {result.total_buildable_area_sqm:.1f} sq m "
          f"({result.buildable_percentage:.1f}%)")
    print(f"  Number of zones: {result.num_zones}")

    if result.largest_zone:
        print(f"\nLargest buildable zone:")
        print(f"  - Area: {result.largest_zone.area_sqm:.1f} sq m")
        print(f"  - Elevation range: {result.largest_zone.min_elevation:.1f}m - "
              f"{result.largest_zone.max_elevation:.1f}m")
        print(f"  - Mean elevation: {result.largest_zone.mean_elevation:.1f}m")


def demo_with_transform():
    """Demonstrate analysis with georeferenced coordinates."""
    print("\n" + "=" * 70)
    print("DEMO 4: Georeferenced Analysis")
    print("=" * 70)

    # Create terrain data
    size = 50
    slope = np.random.uniform(0, 15, (size, size)).astype(np.float32)
    elevation = np.random.uniform(100, 150, (size, size)).astype(np.float32)

    # Create transform for real-world coordinates
    # Property bounds: 0-500m east, 0-500m north, 10m resolution
    transform = from_bounds(0, 0, 500, 500, size, size)

    result = analyze_buildability(slope, elevation, cell_size=10.0, transform=transform)

    print(f"\nProperty bounds: 0-500m x 0-500m")
    print(f"Resolution: 10m")
    print(f"\nResults:")
    print(f"  Total buildable: {result.total_buildable_area_sqm:.1f} sq m "
          f"({result.total_buildable_area_acres:.2f} acres)")
    print(f"  Number of zones: {result.num_zones}")

    if result.largest_zone:
        cx, cy = result.largest_zone.centroid
        print(f"\nLargest zone centroid (georeferenced):")
        print(f"  - Easting: {cx:.1f}m")
        print(f"  - Northing: {cy:.1f}m")
        print(f"  - Geometry type: {result.largest_zone.geometry.geom_type}")


def demo_quality_scoring():
    """Demonstrate quality scoring for different site conditions."""
    print("\n" + "=" * 70)
    print("DEMO 5: Quality Scoring Comparison")
    print("=" * 70)

    scenarios = [
        ("Excellent flat site", np.full((100, 100), 2.0, dtype=np.float32)),
        ("Moderate sloped site", np.full((100, 100), 10.0, dtype=np.float32)),
        ("Difficult steep site", np.full((100, 100), 22.0, dtype=np.float32)),
    ]

    elevation = np.full((100, 100), 100.0, dtype=np.float32)

    print("\nComparing different site conditions:\n")

    for name, slope in scenarios:
        result = analyze_buildability(slope, elevation, cell_size=1.0)

        print(f"{name}:")
        print(f"  - Mean slope: {np.mean(slope):.1f}%")
        print(f"  - Buildable: {result.buildable_percentage:.1f}%")
        print(f"  - Quality score: {result.overall_quality_score:.1f}/100")
        if result.largest_zone:
            print(f"  - Classification: {result.largest_zone.buildability_class.value}")
        print()


if __name__ == "__main__":
    print("\nBuildability Analysis Demonstrations")
    print("=" * 70)

    demo_basic_buildability()
    demo_custom_thresholds()
    demo_elevation_constraints()
    demo_with_transform()
    demo_quality_scoring()

    print("\n" + "=" * 70)
    print("Demos complete!")
    print("=" * 70)

#!/usr/bin/env python3
"""
Demo script showing how to use the Property Boundary Extraction service.

This example demonstrates:
1. Parsing a KML file
2. Extracting property boundaries
3. Accessing boundary metrics and metadata
4. Exporting to GeoJSON
"""

from pathlib import Path

from entmoot.core.boundaries import extract_boundaries_from_kml
from entmoot.core.parsers.kml_parser import parse_kml_file
from entmoot.models.boundary import BoundarySource


def main():
    """Run boundary extraction demo."""
    print("=" * 70)
    print("Property Boundary Extraction Demo")
    print("=" * 70)

    # Example 1: Parse KML and extract boundaries with auto-detection
    print("\n1. Auto-detecting boundaries from KML...")
    print("-" * 70)

    # In a real scenario, you would have a KML file path
    # For this demo, we'll show the API usage

    # parsed_kml = parse_kml_file("path/to/property.kml")
    # result = extract_boundaries_from_kml(parsed_kml)

    # Example 2: Extract with specific strategy
    print("\n2. Using specific identification strategy...")
    print("-" * 70)

    # result = extract_boundaries_from_kml(
    #     parsed_kml,
    #     strategy=BoundarySource.NAME_PATTERN
    # )

    # Example 3: Process results
    print("\n3. Processing extracted boundaries...")
    print("-" * 70)

    # Pseudo-code showing result processing:
    """
    if result.success:
        print(f"✓ Successfully extracted {len(result.boundaries)} boundaries")
        print(f"  Strategy used: {result.extraction_strategy}")
        print(f"  Total placemarks: {result.total_placemarks}")
        print(f"  Total polygons: {result.total_polygons}")

        for i, boundary in enumerate(result.boundaries, 1):
            print(f"\nBoundary {i}:")
            print(f"  Name: {boundary.metadata.name}")
            print(f"  Description: {boundary.metadata.description}")
            print(f"  Area: {boundary.metrics.area_acres:.2f} acres")
            print(f"  Perimeter: {boundary.metrics.perimeter_ft:.2f} feet")
            print(f"  Centroid: ({boundary.metrics.centroid_lon:.6f}, "
                  f"{boundary.metrics.centroid_lat:.6f})")
            print(f"  Valid: {boundary.is_valid}")
            print(f"  Has holes: {boundary.metrics.has_holes}")

            if boundary.is_multi_parcel:
                print(f"  Multi-parcel property with {len(boundary.sub_parcels)} parcels")
                for parcel in boundary.sub_parcels:
                    print(f"    - {parcel.parcel_id}: {parcel.area_acres:.2f} acres")

            # Export to GeoJSON
            geojson = boundary.to_geojson()
            print(f"  GeoJSON: {geojson['type']} with {len(geojson['properties'])} properties")

    else:
        print("✗ Boundary extraction failed")
        for error in result.errors:
            print(f"  Error: {error}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")
    """

    # Example 4: Different use cases
    print("\n4. Common use cases...")
    print("-" * 70)

    print("\nUse Case A: Extract from uploaded KMZ file")
    print("  1. Parse KMZ file using KMZParser")
    print("  2. Extract KML content")
    print("  3. Parse KML to get placemarks")
    print("  4. Extract boundaries with auto-detection")

    print("\nUse Case B: Validate property boundaries")
    print("  1. Extract boundaries from KML")
    print("  2. Check boundary.is_valid for each result")
    print("  3. Review boundary.validation_issues for problems")
    print("  4. Use auto_repair=True to fix common issues")

    print("\nUse Case C: Calculate property metrics")
    print("  1. Extract boundaries")
    print("  2. Access boundary.metrics for area, perimeter")
    print("  3. Get centroid and bounding box")
    print("  4. Export to GeoJSON for mapping")

    print("\nUse Case D: Handle multi-parcel properties")
    print("  1. Extract boundaries")
    print("  2. Check boundary.is_multi_parcel")
    print("  3. Iterate through boundary.sub_parcels")
    print("  4. Calculate aggregate metrics")

    # Example 5: Configuration options
    print("\n5. Configuration options...")
    print("-" * 70)

    print("\nAvailable strategies:")
    for source in BoundarySource:
        print(f"  - {source.value}")

    print("\nExtraction options:")
    print("  - auto_repair: Automatically fix invalid geometries (default: True)")
    print("  - min_area_sqm: Minimum area threshold (default: 1.0)")
    print("  - strategy: Specific identification strategy (default: auto-detect)")

    print("\n" + "=" * 70)
    print("Demo complete! See the test files for working examples.")
    print("=" * 70)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Example: FEMA Floodplain Data Query

This script demonstrates how to use the FEMA NFHL integration to:
1. Query floodplain data for a specific location
2. Check if a property is in a flood zone
3. Convert floodplain data to regulatory constraints
4. Display flood zone information

Run:
    python examples/fema_floodplain_example.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from entmoot.integrations.fema import FEMAClient
from entmoot.integrations.fema.client import FEMAClientConfig
from entmoot.models.regulatory import RegulatoryConstraint


async def query_floodplain_example():
    """Example: Query floodplain data for a location."""
    print("=" * 60)
    print("FEMA Floodplain Data Query Example")
    print("=" * 60)

    # Example location: Mountain View, CA (near Google campus)
    longitude = -122.084
    latitude = 37.422

    print(f"\nQuerying FEMA NFHL for location:")
    print(f"  Longitude: {longitude}")
    print(f"  Latitude: {latitude}")

    # Create client with custom config
    config = FEMAClientConfig(
        timeout=10.0,
        max_retries=3,
        cache_enabled=True,
        cache_ttl=2592000,  # 30 days
    )

    async with FEMAClient(config) as client:
        # Query by point
        print("\n[1] Querying by point...")
        result = await client.query_by_point(longitude, latitude)

        print("\n" + "=" * 60)
        print("FLOODPLAIN QUERY RESULTS")
        print("=" * 60)

        # Display basic information
        print(f"\nLocation: ({result.location_lon}, {result.location_lat})")
        print(f"Data Source: {result.data_source.value}")
        print(f"Query Date: {result.query_date}")
        print(f"Cache Hit: {result.cache_hit}")

        # Check flood hazard status
        print(f"\n{'FLOOD HAZARD STATUS':^60}")
        print("-" * 60)
        print(f"In SFHA (Special Flood Hazard Area): {result.in_sfha}")
        print(f"Flood Insurance Required: {result.insurance_required}")

        if result.highest_risk_zone:
            print(f"Highest Risk Zone: {result.highest_risk_zone.value}")

        # Display flood zones
        print(f"\n{'FLOOD ZONES FOUND':^60}")
        print("-" * 60)
        if result.zones:
            print(f"Total Zones: {len(result.zones)}")

            # Zone summary
            summary = result.get_zone_summary()
            print("\nZone Type Summary:")
            for zone_type, count in summary.items():
                print(f"  - {zone_type}: {count}")

            # Maximum BFE
            max_bfe = result.get_max_bfe()
            if max_bfe:
                print(f"\nMaximum Base Flood Elevation: {max_bfe:.2f} feet")

            # Detailed zone information
            print("\nDetailed Zone Information:")
            for i, zone in enumerate(result.zones, 1):
                print(f"\n  Zone {i}:")
                print(f"    Type: {zone.zone_type.value}")
                if zone.zone_subtype:
                    print(f"    Subtype: {zone.zone_subtype}")
                if zone.base_flood_elevation:
                    print(f"    BFE: {zone.base_flood_elevation:.2f} feet")
                if zone.vertical_datum:
                    print(f"    Vertical Datum: {zone.vertical_datum}")
                print(f"    Floodway: {zone.floodway}")
                print(f"    Coastal Zone: {zone.coastal_zone}")
                if zone.effective_date:
                    print(f"    Effective Date: {zone.effective_date.strftime('%Y-%m-%d')}")
                if zone.source_citation:
                    print(f"    Source: {zone.source_citation}")

                # Check risk level
                if zone.is_high_risk():
                    print("    ⚠️  HIGH RISK - Flood insurance required")
        else:
            print("No flood zones found at this location")
            print("✓ Location appears to be outside of mapped flood hazards")

        # Convert to regulatory constraint
        print(f"\n{'REGULATORY CONSTRAINT':^60}")
        print("-" * 60)

        constraint = RegulatoryConstraint.from_floodplain_data(result)
        if constraint:
            print(f"Type: {constraint.constraint_type}")
            print(f"Severity: {constraint.severity.upper()}")
            print(f"Description: {constraint.description}")
            print(f"Affects Development: {constraint.affects_development}")
            print(f"Requires Permit: {constraint.requires_permit}")
            print(f"Mitigation Possible: {constraint.mitigation_possible}")

            # Display metadata
            if constraint.metadata:
                print("\nMetadata:")
                for key, value in constraint.metadata.items():
                    if key != "zone_summary":
                        print(f"  - {key}: {value}")
        else:
            print("No regulatory constraints identified")
            print("✓ Property development not restricted by floodplain")

        # Cache statistics
        print(f"\n{'CACHE STATISTICS':^60}")
        print("-" * 60)
        cache_stats = client.get_cache_stats()
        print(f"Cache Enabled: {cache_stats['enabled']}")
        print(f"Cache Entries: {cache_stats['entries']}")
        print(f"TTL: {cache_stats['ttl_seconds'] / 86400:.0f} days")

        # Query by bounding box example
        print(f"\n{'BOUNDING BOX QUERY EXAMPLE':^60}")
        print("-" * 60)
        print("\n[2] Querying by bounding box...")

        bbox_result = await client.query_by_bbox(
            min_lon=longitude - 0.005,
            min_lat=latitude - 0.005,
            max_lon=longitude + 0.005,
            max_lat=latitude + 0.005,
        )

        print(f"\nBounding Box: ({bbox_result.bbox_min_lon:.4f}, {bbox_result.bbox_min_lat:.4f}) to "
              f"({bbox_result.bbox_max_lon:.4f}, {bbox_result.bbox_max_lat:.4f})")
        print(f"Zones Found: {len(bbox_result.zones)}")

        if bbox_result.zones:
            summary = bbox_result.get_zone_summary()
            print("\nZone Types in Area:")
            for zone_type, count in summary.items():
                print(f"  - {zone_type}: {count}")

    print("\n" + "=" * 60)
    print("Example Complete")
    print("=" * 60)


async def multiple_locations_example():
    """Example: Query multiple locations efficiently."""
    print("\n\n" + "=" * 60)
    print("MULTIPLE LOCATIONS EXAMPLE")
    print("=" * 60)

    # Sample locations (different flood risk areas)
    locations = [
        (-122.084, 37.422, "Mountain View, CA"),
        (-90.071, 29.951, "New Orleans, LA"),
        (-80.191, 25.761, "Miami, FL"),
    ]

    async with FEMAClient() as client:
        for lon, lat, name in locations:
            print(f"\n{name}:")
            result = await client.query_by_point(lon, lat)

            if result.in_sfha:
                print(f"  ⚠️  SFHA: Yes - Zone {result.highest_risk_zone.value}")
                max_bfe = result.get_max_bfe()
                if max_bfe:
                    print(f"  Max BFE: {max_bfe:.2f} feet")
            else:
                print("  ✓ SFHA: No")

            print(f"  Zones: {len(result.zones)}")


def main():
    """Run examples."""
    print("\nFEMA NFHL Integration Examples")
    print("Note: These examples make real API calls to FEMA's servers\n")

    try:
        # Run main example
        asyncio.run(query_floodplain_example())

        # Run multiple locations example
        # asyncio.run(multiple_locations_example())

    except KeyboardInterrupt:
        print("\n\nExample interrupted by user")
    except Exception as e:
        print(f"\n\nError running example: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

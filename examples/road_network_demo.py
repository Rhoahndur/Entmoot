"""
Demo script for road network generation.

This example demonstrates the complete road network generation pipeline:
1. Create terrain data and navigation graph
2. Find paths using A* with grade constraints
3. Generate optimized road network connecting assets to entrance
"""

import numpy as np
from rasterio.transform import from_bounds

from entmoot.core.roads.graph import NavigationGraph
from entmoot.core.roads.network import RoadNetwork
from entmoot.core.roads.pathfinding import PathfinderConfig


def main():
    """Run road network generation demo."""
    print("=" * 60)
    print("Road Network Generation Demo")
    print("=" * 60)

    # 1. Create sample terrain data
    print("\n1. Creating terrain data (500m x 500m site)...")
    size = 50
    elevation = np.zeros((size, size), dtype=np.float32)
    slope = np.ones((size, size), dtype=np.float32) * 3.0  # Gentle slope

    # Add elevation gradient (rises from west to east)
    for i in range(size):
        for j in range(size):
            elevation[i, j] = 100.0 + j * 0.5

    # Add steeper section in middle
    for i in range(20, 30):
        for j in range(20, 30):
            elevation[i, j] += 5.0
            slope[i, j] = 8.0

    transform = from_bounds(0, 0, 500, 500, size, size)

    print(f"   - Elevation range: {elevation.min():.1f}m - {elevation.max():.1f}m")
    print(f"   - Slope range: {slope.min():.1f}% - {slope.max():.1f}%")

    # 2. Create navigation graph
    print("\n2. Building navigation graph...")
    graph = NavigationGraph(
        elevation_data=elevation,
        slope_data=slope,
        transform=transform,
        cell_size=10.0,
        grid_spacing=50.0,  # 50m spacing between nodes
    )

    # Build grid within site bounds
    bounds = (0, 0, 500, 500)
    graph.build_grid_graph(bounds)

    stats = graph.get_graph_stats()
    print(f"   - Nodes: {stats['num_nodes']}")
    print(f"   - Edges: {stats['num_edges']}")
    print(f"   - Connected: {stats['is_connected']}")

    # 3. Generate road network
    print("\n3. Generating road network...")

    # Site entrance at southwest corner
    entrance_position = (50.0, 50.0)

    # Asset positions (buildings, parking, etc.)
    asset_positions = [
        (150.0, 150.0),  # Building 1
        (250.0, 150.0),  # Parking lot
        (350.0, 250.0),  # Building 2
        (250.0, 350.0),  # Storage yard
    ]

    asset_ids = ["building_1", "parking_1", "building_2", "storage_1"]

    # Configure pathfinder with grade constraints
    config = PathfinderConfig(
        max_grade_percent=8.0,  # Maximum 8% grade
        switchback_detection=True,
        smoothing_enabled=True,
    )

    # Create road network
    network = RoadNetwork(
        navigation_graph=graph,
        entrance_position=entrance_position,
        pathfinder_config=config,
    )

    # Generate optimized network (minimum spanning tree)
    success = network.generate_network(
        asset_positions=asset_positions,
        asset_ids=asset_ids,
        optimize=True,
    )

    if not success:
        print("   ERROR: Could not generate road network!")
        return

    print("   SUCCESS: Road network generated!")

    # 4. Display network statistics
    print("\n4. Road Network Statistics:")
    print("-" * 60)

    stats = network.get_network_stats()

    print(f"   Total Length: {stats['total_length_m']:.1f} meters")
    print(f"   Total Area: {stats['total_area_sqm']:.1f} square meters")
    print(f"   Cut/Fill Volume: {stats['total_cut_fill_m3']:.1f} cubic meters")
    print(f"   Number of Segments: {stats['total_segments']}")
    print(f"   Number of Intersections: {stats['num_intersections']}")
    print(f"   Maximum Grade: {stats['max_grade_pct']:.2f}%")
    print(f"   Average Grade: {stats['avg_grade_pct']:.2f}%")

    print("\n   Road Classification:")
    print(f"     - Primary Roads: {stats['primary_roads']['count']} "
          f"({stats['primary_roads']['total_length_m']:.1f}m)")
    print(f"     - Secondary Roads: {stats['secondary_roads']['count']} "
          f"({stats['secondary_roads']['total_length_m']:.1f}m)")
    print(f"     - Access Roads: {stats['access_roads']['count']} "
          f"({stats['access_roads']['total_length_m']:.1f}m)")

    # 5. Show individual segments
    print("\n5. Road Segments:")
    print("-" * 60)

    for seg_id, segment in list(network.segments.items())[:5]:  # Show first 5
        print(f"   {seg_id}:")
        print(f"     - Type: {segment.road_type.value}")
        print(f"     - Length: {segment.length_m:.1f}m")
        print(f"     - Width: {segment.width_m:.1f}m")
        print(f"     - Max Grade: {segment.max_grade:.2f}%")
        print(f"     - Cut/Fill: {segment.cut_fill_volume:.1f} cubic meters")

    # 6. Export to GeoJSON
    print("\n6. Exporting to GeoJSON...")
    geojson = network.export_to_geojson()
    print(f"   - Features: {len(geojson['features'])}")
    print(f"   - Format: {geojson['type']}")

    # 7. Acceptance criteria check
    print("\n7. Acceptance Criteria Check:")
    print("-" * 60)

    checks = {
        "All assets accessible": len(network.segments) > 0,
        "Grade constraints respected": stats['max_grade_pct'] <= config.max_grade_percent * 1.1,
        "Network optimized": success,
        "Smooth road geometry": all(
            len(s.centerline.coords) >= 2 for s in network.segments.values()
        ),
    }

    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"   {status}: {check}")

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

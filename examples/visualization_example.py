"""
Example usage of Entmoot visualization modules.

This example demonstrates how to use the 2D and 3D map renderers
to create professional visualizations of site data.
"""

import numpy as np
from shapely.geometry import Polygon, LineString, Point

from entmoot.core.visualization import (
    Map2DRenderer,
    MapConfig,
    StyleConfig,
    LayerType,
    OutputFormat,
    Map3DRenderer,
    Map3DConfig,
    CameraPreset,
    OutputFormat3D,
)


def example_2d_map():
    """Create a simple 2D map with multiple layers."""
    print("Creating 2D map...")

    # Create sample geometries
    boundary = Polygon([
        (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
    ])

    buildings = [
        Polygon([(10, 10), (30, 10), (30, 30), (10, 30), (10, 10)]),
        Polygon([(50, 50), (70, 50), (70, 70), (50, 70), (50, 70)]),
    ]

    roads = [
        LineString([(0, 50), (50, 50), (50, 100)]),
        LineString([(50, 50), (100, 50)]),
    ]

    constraint = Polygon([
        (20, 60), (40, 60), (40, 80), (20, 80), (20, 60)
    ])

    # Configure map
    config = MapConfig(
        title="Site Layout - 2D View",
        width=12,
        height=10,
        dpi=300,
        show_legend=True,
        show_scale=True,
        show_north_arrow=True,
        show_grid=True,
    )

    # Create renderer
    renderer = Map2DRenderer(config)

    # Add layers
    renderer.add_layer(
        name="boundary",
        geometries=[boundary],
        layer_type=LayerType.BOUNDARIES,
        label="Property Boundary",
    )

    renderer.add_layer(
        name="constraints",
        geometries=[constraint],
        layer_type=LayerType.CONSTRAINTS,
        label="Wetland Constraint",
    )

    renderer.add_layer(
        name="buildings",
        geometries=buildings,
        layer_type=LayerType.ASSETS,
        label="Buildings",
        style=StyleConfig(
            color="#8b4513",
            edge_color="#654321",
            alpha=0.8,
        ),
    )

    renderer.add_layer(
        name="roads",
        geometries=roads,
        layer_type=LayerType.ROADS,
        label="Roads",
        style=StyleConfig(
            color="#ffcc00",
            line_width=3.0,
        ),
    )

    # Render and export
    fig = renderer.render()
    output_path = renderer.export("output/site_2d_map.png", format=OutputFormat.PNG)
    print(f"2D map exported to: {output_path}")

    # Also export as SVG
    svg_path = renderer.export("output/site_2d_map.svg", format=OutputFormat.SVG)
    print(f"2D map (SVG) exported to: {svg_path}")

    renderer.close()


def example_3d_map():
    """Create a 3D terrain visualization."""
    print("Creating 3D map...")

    # Create sample terrain (50x50 grid)
    x = np.linspace(0, 100, 50)
    y = np.linspace(0, 100, 50)
    X, Y = np.meshgrid(x, y)
    Z = 10 + 5 * np.sin(X / 20) * np.cos(Y / 20)  # Simple terrain

    # Create sample geometries
    buildings = [
        Polygon([(20, 20), (30, 20), (30, 30), (20, 30), (20, 20)]),
        Polygon([(60, 60), (75, 60), (75, 75), (60, 75), (60, 75)]),
    ]

    roads = [
        LineString([(0, 50), (50, 50), (50, 100)]),
        LineString([(50, 50), (100, 50)]),
    ]

    # Configure map
    config = Map3DConfig(
        title="Site Layout - 3D View",
        width=1200,
        height=800,
        show_axes=True,
        show_grid=True,
        dem_resolution=50,  # Downsample if needed
    )

    # Set camera to isometric view
    config.camera.preset = CameraPreset.ISOMETRIC

    # Create renderer
    renderer = Map3DRenderer(config)

    # Set terrain
    renderer.set_terrain(X, Y, Z)

    # Add buildings with extrusion
    for i, building in enumerate(buildings):
        renderer.add_asset(
            building,
            height=15.0,
            name=f"Building {i+1}",
        )

    # Add roads draped on terrain
    for i, road in enumerate(roads):
        renderer.add_road(
            road,
            width=5.0,
            name=f"Road {i+1}",
            color="#ffcc00",
        )

    # Render and export
    fig = renderer.render()
    output_path = renderer.export("output/site_3d_map.html", format=OutputFormat3D.HTML)
    print(f"3D map exported to: {output_path}")

    # Also get HTML string for embedding
    html_string = renderer.export_html_string()
    print(f"3D map HTML length: {len(html_string)} characters")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Entmoot Visualization Examples")
    print("=" * 60)
    print()

    example_2d_map()
    print()
    example_3d_map()
    print()
    print("=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

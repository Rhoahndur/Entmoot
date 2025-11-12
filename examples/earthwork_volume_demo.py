"""
Earthwork Volume Calculation Demo

Demonstrates the complete earthwork analysis workflow:
1. Load existing terrain (pre-grading)
2. Define grading zones (post-grading)
3. Calculate cut/fill volumes
4. Estimate costs
5. Generate visualizations
"""

import numpy as np
from pathlib import Path

from entmoot.core.earthwork import PreGradingModel, PostGradingModel, VolumeCalculator
from entmoot.models.terrain import DEMData, DEMMetadata, ElevationUnit
from entmoot.models.earthwork import SoilType, SoilProperties, CostDatabase
from pyproj import CRS

try:
    from shapely.geometry import Polygon, LineString
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("Warning: Shapely not available. Grading zone demo will be limited.")


def create_sample_terrain():
    """Create a sample sloped terrain for demonstration."""
    print("\n=== Creating Sample Terrain ===")

    # Create metadata
    metadata = DEMMetadata(
        width=200,
        height=200,
        resolution=(1.0, 1.0),  # 1 meter resolution
        bounds=(0.0, 0.0, 200.0, 200.0),
        crs=CRS.from_epsg(32610),  # UTM Zone 10N
        no_data_value=np.nan,
        elevation_unit=ElevationUnit.FEET,
        transform=(1.0, 0.0, 0.0, 0.0, -1.0, 200.0),
    )

    # Create terrain with gentle slope (10 ft over 200 meters)
    elevation = np.zeros((200, 200), dtype=np.float32)
    for i in range(200):
        elevation[i, :] = 100.0 + (i / 200.0) * 10.0  # Slopes from 100 to 110 ft

    # Add some natural variation
    np.random.seed(42)
    noise = np.random.normal(0, 0.5, (200, 200))
    elevation += noise

    dem_data = DEMData(elevation=elevation, metadata=metadata)

    print(f"  Created terrain: {metadata.width}x{metadata.height}")
    print(f"  Elevation range: {np.min(elevation):.1f} - {np.max(elevation):.1f} ft")

    return dem_data


def demonstrate_pre_grading(dem_data):
    """Demonstrate pre-grading model."""
    print("\n=== Pre-Grading Analysis ===")

    # Create pre-grading model
    pre_model = PreGradingModel(dem_data)

    # Get statistics
    stats = pre_model.get_statistics()
    print(f"  Min elevation: {stats['min_elevation']:.2f} ft")
    print(f"  Max elevation: {stats['max_elevation']:.2f} ft")
    print(f"  Mean elevation: {stats['mean_elevation']:.2f} ft")
    print(f"  Surface area: {stats['surface_area_sf']:,.0f} sq ft")

    # Get elevation profile
    distance, elevation = pre_model.get_elevation_profile(
        start=(10.0, 10.0),
        end=(190.0, 190.0),
        num_points=100
    )
    print(f"  Created elevation profile with {len(distance)} points")
    print(f"  Profile length: {distance[-1]:.1f} ft")

    return pre_model


def demonstrate_post_grading(dem_data):
    """Demonstrate post-grading model with zones."""
    print("\n=== Post-Grading Design ===")

    if not SHAPELY_AVAILABLE:
        print("  Shapely not available - creating simple grading")
        post_model = PostGradingModel(dem_data.metadata, base_elevation=dem_data.elevation)
        elevation = post_model.generate_grading()
        # Simple modification - flatten center area
        elevation[80:120, 80:120] = 105.0
        post_model.elevation = elevation
        return post_model

    # Create post-grading model
    post_model = PostGradingModel(dem_data.metadata, base_elevation=dem_data.elevation)

    # Add building pad at elevation 105 ft
    building_pad = Polygon([
        (80, 80), (120, 80), (120, 120), (80, 120)
    ])
    post_model.add_building_pad(
        geometry=building_pad,
        target_elevation=105.0,
        transition_slope=3.0,  # 3:1 slope
        priority=10
    )
    print("  Added building pad: 40x40 meters at 105 ft")

    # Add road corridor
    road_centerline = LineString([
        (50, 100), (150, 100)
    ])
    post_model.add_road_corridor(
        centerline=road_centerline,
        width=24.0,  # 24 ft wide
        crown_height=0.5,  # 0.5 ft crown
        cross_slope=2.0,  # 2% cross-slope
        priority=8
    )
    print("  Added road corridor: 100 meters long, 24 ft wide")

    # Generate grading
    elevation = post_model.generate_grading()

    stats = post_model.get_statistics()
    print(f"  Graded {stats['graded_cells']} cells")
    print(f"  {stats['num_zones']} grading zones applied")

    return post_model


def calculate_volumes(pre_model, post_model):
    """Calculate earthwork volumes."""
    print("\n=== Volume Calculation ===")

    # Define soil properties (clay)
    soil_props = SoilProperties.get_default(SoilType.CLAY)
    print(f"  Soil type: {soil_props.soil_type.value}")
    print(f"  Shrink factor: {soil_props.shrink_factor}")
    print(f"  Swell factor: {soil_props.swell_factor}")

    # Create calculator
    calculator = VolumeCalculator(
        pre_elevation=pre_model.elevation,
        post_elevation=post_model.elevation,
        metadata=pre_model.metadata,
        soil_properties=soil_props,
    )

    # Calculate volumes
    volume_result = calculator.calculate_volumes(apply_shrink_swell=True)

    print(f"\n  Cut volume: {volume_result.cut_volume_cy:,.0f} CY")
    print(f"  Fill volume: {volume_result.fill_volume_cy:,.0f} CY")
    print(f"  Net volume: {volume_result.net_volume_cy:,.0f} CY")
    print(f"  Balanced volume: {volume_result.balanced_volume_cy:,.0f} CY")
    print(f"  Import required: {volume_result.import_volume_cy:,.0f} CY")
    print(f"  Export required: {volume_result.export_volume_cy:,.0f} CY")
    print(f"\n  Cut area: {volume_result.cut_area_sf:,.0f} sq ft")
    print(f"  Fill area: {volume_result.fill_area_sf:,.0f} sq ft")
    print(f"  Average cut depth: {volume_result.average_cut_depth_ft:.2f} ft")
    print(f"  Average fill depth: {volume_result.average_fill_depth_ft:.2f} ft")

    return calculator, volume_result


def estimate_costs(calculator, volume_result):
    """Estimate earthwork costs."""
    print("\n=== Cost Estimation ===")

    # Define cost database
    cost_db = CostDatabase(
        excavation_cost_cy=5.00,
        fill_cost_cy=8.00,
        haul_cost_cy_mile=2.50,
        import_cost_cy=25.00,
        export_cost_cy=15.00,
        compaction_cost_cy=3.50,
    )

    print("  Cost rates (per CY):")
    print(f"    Excavation: ${cost_db.excavation_cost_cy:.2f}")
    print(f"    Fill: ${cost_db.fill_cost_cy:.2f}")
    print(f"    Haul: ${cost_db.haul_cost_cy_mile:.2f}/mile")
    print(f"    Import: ${cost_db.import_cost_cy:.2f}")
    print(f"    Export: ${cost_db.export_cost_cy:.2f}")

    # Update calculator cost database
    calculator.cost_database = cost_db

    # Calculate costs
    cost_result = calculator.calculate_costs(
        volume_result,
        average_haul_distance_miles=0.25  # 1/4 mile average haul
    )

    print("\n  Cost breakdown:")
    print(f"    Excavation: ${cost_result.excavation_cost:,.2f}")
    print(f"    Fill placement: ${cost_result.fill_cost:,.2f}")
    print(f"    Haul: ${cost_result.haul_cost:,.2f}")
    print(f"    Import: ${cost_result.import_cost:,.2f}")
    print(f"    Export: ${cost_result.export_cost:,.2f}")
    print(f"    Compaction: ${cost_result.compaction_cost:,.2f}")
    print(f"\n  TOTAL COST: ${cost_result.total_cost:,.2f}")

    return cost_result


def analyze_balancing(calculator):
    """Analyze earthwork balancing."""
    print("\n=== Earthwork Balancing ===")

    balancing = calculator.calculate_balancing()

    print(f"  Is balanced: {balancing.is_balanced}")
    print(f"  Balance ratio: {balancing.balance_ratio:.2f}")
    print(f"  Optimal haul distance: {balancing.optimal_haul_distance:.2f} miles")

    print("\n  Recommendations:")
    for i, rec in enumerate(balancing.recommendations, 1):
        print(f"    {i}. {rec}")

    return balancing


def generate_visualizations(calculator):
    """Generate visualizations."""
    print("\n=== Generating Visualizations ===")

    output_dir = Path("output/earthwork")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate GeoTIFF heatmap
    try:
        geotiff_path = output_dir / "cut_fill_heatmap.tif"
        calculator.generate_heatmap(str(geotiff_path), format="geotiff")
        print(f"  GeoTIFF heatmap: {geotiff_path}")
    except ImportError as e:
        print(f"  GeoTIFF export skipped: {e}")

    # Generate PNG heatmap
    try:
        png_path = output_dir / "cut_fill_heatmap.png"
        calculator.generate_heatmap(
            str(png_path),
            format="png",
            color_range=(-5.0, 5.0)  # -5 to +5 feet
        )
        print(f"  PNG heatmap: {png_path}")
    except ImportError as e:
        print(f"  PNG export skipped: {e}")

    # Generate cross-section
    section = calculator.generate_cross_section(
        start=(50.0, 50.0),
        end=(150.0, 150.0),
        num_points=100
    )
    print(f"\n  Cross-section generated:")
    print(f"    Length: {section.distance[-1]:.1f} ft")
    print(f"    Volume: {section.section_volume_cy:.0f} CY")
    print(f"    Max cut: {np.nanmax(section.cut_fill):.2f} ft")
    print(f"    Max fill: {np.nanmin(section.cut_fill):.2f} ft")


def main():
    """Run the earthwork demo."""
    print("=" * 70)
    print("EARTHWORK VOLUME CALCULATION DEMO")
    print("=" * 70)

    # Create sample terrain
    dem_data = create_sample_terrain()

    # Pre-grading analysis
    pre_model = demonstrate_pre_grading(dem_data)

    # Post-grading design
    post_model = demonstrate_post_grading(dem_data)

    # Calculate volumes
    calculator, volume_result = calculate_volumes(pre_model, post_model)

    # Estimate costs
    cost_result = estimate_costs(calculator, volume_result)

    # Analyze balancing
    balancing = analyze_balancing(calculator)

    # Generate visualizations
    generate_visualizations(calculator)

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)

    # Summary
    print("\nSUMMARY:")
    print(f"  Total earthwork: {volume_result.cut_volume_cy + volume_result.fill_volume_cy:,.0f} CY")
    print(f"  Estimated cost: ${cost_result.total_cost:,.2f}")
    print(f"  Balance status: {'BALANCED' if balancing.is_balanced else 'UNBALANCED'}")

    if volume_result.import_volume_cy > 0:
        print(f"  Import required: {volume_result.import_volume_cy:,.0f} CY")
    if volume_result.export_volume_cy > 0:
        print(f"  Export required: {volume_result.export_volume_cy:,.0f} CY")


if __name__ == "__main__":
    main()

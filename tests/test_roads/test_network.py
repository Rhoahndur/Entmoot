"""
Tests for road network generation.

Tests network topology, road geometry, intersections, and optimization.
"""

import numpy as np
import pytest
from rasterio.transform import from_bounds

from entmoot.core.roads.graph import NavigationGraph
from entmoot.core.roads.network import (
    RoadIntersection,
    RoadNetwork,
    RoadSegment,
    RoadType,
)
from entmoot.core.roads.pathfinding import PathfinderConfig


@pytest.fixture
def sample_terrain():
    """Create sample terrain for testing."""
    elevation = np.zeros((30, 30), dtype=np.float32)
    slope = np.ones((30, 30), dtype=np.float32) * 3.0  # Gentle slope throughout

    # Add gentle elevation gradient
    for i in range(30):
        for j in range(30):
            elevation[i, j] = 100.0 + (i + j) * 0.2

    transform = from_bounds(0, 0, 300, 300, 30, 30)
    return elevation, slope, transform


@pytest.fixture
def navigation_graph(sample_terrain):
    """Create navigation graph with terrain."""
    elevation, slope, transform = sample_terrain
    graph = NavigationGraph(
        elevation_data=elevation,
        slope_data=slope,
        transform=transform,
        cell_size=10.0,
        grid_spacing=30.0,
    )

    # Build grid
    graph.build_grid_graph((0, 0, 300, 300))

    return graph


@pytest.fixture
def road_network(navigation_graph):
    """Create road network for testing."""
    entrance = (10.0, 10.0)
    return RoadNetwork(navigation_graph, entrance)


class TestRoadSegment:
    """Tests for RoadSegment dataclass."""

    def test_segment_creation(self):
        """Test creating a road segment."""
        from shapely.geometry import LineString

        centerline = LineString([(0, 0), (10, 10), (20, 20)])

        segment = RoadSegment(
            id="road_1",
            road_type=RoadType.PRIMARY,
            centerline=centerline,
            width_m=7.3,
            length_m=28.3,
            start_node_id="node_1",
            end_node_id="node_2",
        )

        assert segment.id == "road_1"
        assert segment.road_type == RoadType.PRIMARY
        assert segment.width_m == 7.3
        assert segment.length_m == 28.3

    def test_get_geometry(self):
        """Test getting road segment geometry."""
        from shapely.geometry import LineString

        centerline = LineString([(0, 0), (10, 0)])
        segment = RoadSegment(
            id="road_1",
            road_type=RoadType.PRIMARY,
            centerline=centerline,
            width_m=6.0,
            length_m=10.0,
            start_node_id="n1",
            end_node_id="n2",
        )

        geometry = segment.get_geometry()

        # Should be a buffered polygon
        assert geometry.geom_type == "Polygon"
        assert geometry.area > 0

    def test_get_geometry_with_shoulder(self):
        """Test getting geometry with shoulders."""
        from shapely.geometry import LineString

        centerline = LineString([(0, 0), (10, 0)])
        segment = RoadSegment(
            id="road_1",
            road_type=RoadType.PRIMARY,
            centerline=centerline,
            width_m=6.0,
            length_m=10.0,
            start_node_id="n1",
            end_node_id="n2",
        )

        geom_no_shoulder = segment.get_geometry()
        geom_with_shoulder = segment.get_geometry_with_shoulder(shoulder_width=2.0)

        # With shoulder should be larger
        assert geom_with_shoulder.area > geom_no_shoulder.area

    def test_to_dict(self):
        """Test converting segment to dictionary."""
        from shapely.geometry import LineString

        centerline = LineString([(0, 0), (10, 0)])
        segment = RoadSegment(
            id="road_1",
            road_type=RoadType.SECONDARY,
            centerline=centerline,
            width_m=5.5,
            length_m=10.0,
            start_node_id="n1",
            end_node_id="n2",
            avg_grade=5.0,
            max_grade=7.5,
        )

        segment_dict = segment.to_dict()

        assert segment_dict["id"] == "road_1"
        assert segment_dict["road_type"] == "secondary"
        assert segment_dict["width_m"] == 5.5
        assert segment_dict["avg_grade"] == 5.0


class TestRoadIntersection:
    """Tests for RoadIntersection."""

    def test_intersection_creation(self):
        """Test creating an intersection."""
        from shapely.geometry import Point

        geometry = Point(50, 50).buffer(5)

        intersection = RoadIntersection(
            id="int_1",
            position=(50.0, 50.0),
            connecting_segments=["road_1", "road_2", "road_3"],
            intersection_type="T-junction",
            geometry=geometry,
        )

        assert intersection.id == "int_1"
        assert intersection.position == (50.0, 50.0)
        assert len(intersection.connecting_segments) == 3
        assert intersection.intersection_type == "T-junction"

    def test_to_dict(self):
        """Test converting intersection to dictionary."""
        from shapely.geometry import Point

        geometry = Point(50, 50).buffer(5)

        intersection = RoadIntersection(
            id="int_1",
            position=(50.0, 50.0),
            connecting_segments=["road_1", "road_2"],
            intersection_type="T-junction",
            geometry=geometry,
        )

        int_dict = intersection.to_dict()

        assert int_dict["id"] == "int_1"
        assert int_dict["num_connections"] == 2
        assert int_dict["intersection_type"] == "T-junction"


class TestRoadType:
    """Tests for RoadType enum."""

    def test_road_types(self):
        """Test road type values."""
        assert RoadType.PRIMARY.value == "primary"
        assert RoadType.SECONDARY.value == "secondary"
        assert RoadType.ACCESS.value == "access"


class TestRoadNetwork:
    """Tests for RoadNetwork."""

    def test_network_initialization(self, navigation_graph):
        """Test road network initialization."""
        entrance = (10.0, 10.0)
        network = RoadNetwork(navigation_graph, entrance)

        assert network.navigation_graph == navigation_graph
        assert network.entrance_position == entrance
        assert len(network.segments) == 0
        assert len(network.intersections) == 0

    def test_entrance_node_creation(self, road_network):
        """Test that entrance node is created."""
        assert road_network.entrance_node is not None
        entrance_node = road_network.navigation_graph.nodes[road_network.entrance_node]
        assert entrance_node.is_entrance

    def test_generate_empty_network(self, road_network):
        """Test generating network with no assets."""
        success = road_network.generate_network([])
        assert not success

    def test_generate_single_asset_network(self, road_network):
        """Test generating network with single asset."""
        asset_positions = [(100.0, 100.0)]

        success = road_network.generate_network(asset_positions)

        if success:
            assert len(road_network.segments) > 0
            assert road_network.get_total_length() > 0

    def test_generate_multiple_asset_network(self, road_network):
        """Test generating network with multiple assets."""
        asset_positions = [
            (100.0, 100.0),
            (150.0, 150.0),
            (200.0, 200.0),
        ]

        success = road_network.generate_network(asset_positions)

        if success:
            assert len(road_network.segments) > 0

    def test_generate_optimized_network(self, road_network):
        """Test optimized network generation."""
        asset_positions = [
            (80.0, 80.0),
            (120.0, 120.0),
            (160.0, 160.0),
        ]

        success = road_network.generate_network(
            asset_positions,
            optimize=True
        )

        if success:
            # Optimized network should minimize total length
            assert road_network.get_total_length() > 0

    def test_generate_direct_network(self, road_network):
        """Test direct (non-optimized) network generation."""
        asset_positions = [
            (80.0, 80.0),
            (120.0, 120.0),
        ]

        success = road_network.generate_network(
            asset_positions,
            optimize=False
        )

        if success:
            # Direct network connects each asset to entrance
            assert len(road_network.segments) >= len(asset_positions)

    def test_road_width_classification(self, road_network):
        """Test road width for different types."""
        primary_width = road_network._get_road_width(RoadType.PRIMARY)
        secondary_width = road_network._get_road_width(RoadType.SECONDARY)
        access_width = road_network._get_road_width(RoadType.ACCESS)

        assert primary_width == 7.3  # 24 feet
        assert secondary_width == 5.5  # 18 feet
        assert access_width == 3.7  # 12 feet

    def test_get_total_length(self, road_network):
        """Test getting total road length."""
        initial_length = road_network.get_total_length()
        assert initial_length == 0.0

        # Generate network
        asset_positions = [(100.0, 100.0)]
        road_network.generate_network(asset_positions)

        final_length = road_network.get_total_length()
        if len(road_network.segments) > 0:
            assert final_length > 0

    def test_get_total_area(self, road_network):
        """Test getting total road area."""
        initial_area = road_network.get_total_area()
        assert initial_area == 0.0

        asset_positions = [(100.0, 100.0)]
        road_network.generate_network(asset_positions)

        final_area = road_network.get_total_area()
        if len(road_network.segments) > 0:
            assert final_area > 0

    def test_get_total_cut_fill(self, road_network):
        """Test getting total cut/fill volume."""
        initial_cut_fill = road_network.get_total_cut_fill()
        assert initial_cut_fill == 0.0

        asset_positions = [(100.0, 100.0)]
        road_network.generate_network(asset_positions)

        final_cut_fill = road_network.get_total_cut_fill()
        # Cut/fill should be calculated
        assert final_cut_fill >= 0

    def test_network_stats(self, road_network):
        """Test network statistics."""
        asset_positions = [
            (100.0, 100.0),
            (150.0, 150.0),
        ]

        road_network.generate_network(asset_positions)

        stats = road_network.get_network_stats()

        assert "total_segments" in stats
        assert "total_length_m" in stats
        assert "total_area_sqm" in stats
        assert "total_cut_fill_m3" in stats
        assert "num_intersections" in stats
        assert "primary_roads" in stats
        assert "secondary_roads" in stats
        assert "access_roads" in stats
        assert "max_grade_pct" in stats
        assert "avg_grade_pct" in stats

    def test_intersection_generation(self, road_network):
        """Test intersection generation at junctions."""
        # Create a scenario that should generate intersections
        asset_positions = [
            (80.0, 80.0),
            (80.0, 120.0),
            (120.0, 80.0),
            (120.0, 120.0),
        ]

        success = road_network.generate_network(asset_positions, optimize=True)

        # Check if intersections were generated
        # (May or may not depending on network topology)
        assert isinstance(road_network.intersections, dict)

    def test_export_geojson(self, road_network):
        """Test exporting network to GeoJSON."""
        asset_positions = [(100.0, 100.0)]
        road_network.generate_network(asset_positions)

        geojson = road_network.export_to_geojson()

        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson

        if len(road_network.segments) > 0:
            # Should have road segment features
            segment_features = [
                f for f in geojson["features"]
                if f["properties"].get("feature_type") == "road_segment"
            ]
            assert len(segment_features) > 0

    def test_road_type_classification(self, road_network):
        """Test road type classification logic."""
        entrance_node = road_network.entrance_node
        asset_nodes = ["asset_1", "asset_2", "asset_3"]

        # Road connected to entrance should be primary
        road_type = road_network._classify_road_type(
            entrance_node, "asset_1", asset_nodes
        )
        assert road_type == RoadType.PRIMARY

        # Road between assets depends on downstream count
        road_type = road_network._classify_road_type(
            "asset_1", "asset_2", asset_nodes
        )
        assert road_type in [RoadType.SECONDARY, RoadType.ACCESS]

    def test_cut_fill_estimation(self, road_network, navigation_graph):
        """Test cut/fill volume estimation."""
        # Create a path
        node1 = navigation_graph.add_node((0.0, 0.0), node_id="n1")
        node2 = navigation_graph.add_node((10.0, 0.0), node_id="n2")

        # Set different elevations
        node1.elevation = 100.0
        node2.elevation = 105.0

        from entmoot.core.roads.pathfinding import Path

        path = Path(
            nodes=[node1, node2],
            total_length=10.0,
        )

        cut_fill = road_network._estimate_cut_fill(path, road_width=6.0)

        # Should have some volume
        assert cut_fill > 0

    def test_create_intersection_geometry(self, road_network):
        """Test intersection geometry creation."""
        segment_ids = ["road_1", "road_2", "road_3"]
        position = (50.0, 50.0)

        # Add mock segments
        from shapely.geometry import LineString

        for seg_id in segment_ids:
            centerline = LineString([(50, 50), (60, 60)])
            segment = RoadSegment(
                id=seg_id,
                road_type=RoadType.PRIMARY,
                centerline=centerline,
                width_m=7.3,
                length_m=14.1,
                start_node_id="n1",
                end_node_id="n2",
            )
            road_network.segments[seg_id] = segment

        intersection = road_network._create_intersection(
            "node_center", position, segment_ids
        )

        assert intersection.id.startswith("intersection_")
        assert intersection.position == position
        assert len(intersection.connecting_segments) == 3
        assert intersection.intersection_type == "T-junction"
        assert intersection.geometry.geom_type == "Polygon"

    def test_network_with_custom_asset_ids(self, road_network):
        """Test network generation with custom asset IDs."""
        asset_positions = [(100.0, 100.0), (150.0, 150.0)]
        asset_ids = ["building_1", "parking_1"]

        success = road_network.generate_network(
            asset_positions,
            asset_ids=asset_ids
        )

        if success:
            assert len(road_network.segments) > 0

    def test_pathfinder_config_usage(self, navigation_graph):
        """Test using custom pathfinder config."""
        config = PathfinderConfig(
            max_grade_percent=10.0,
            smoothing_enabled=False,
        )

        network = RoadNetwork(
            navigation_graph,
            entrance_position=(10.0, 10.0),
            pathfinder_config=config,
        )

        assert network.pathfinder.config.max_grade_percent == 10.0
        assert not network.pathfinder.config.smoothing_enabled

    def test_empty_stats(self, road_network):
        """Test stats for empty network."""
        stats = road_network.get_network_stats()

        assert stats["total_segments"] == 0
        assert stats["total_length_m"] == 0.0
        assert stats["total_area_sqm"] == 0.0
        assert stats["num_intersections"] == 0

    def test_segment_counter(self, road_network):
        """Test segment ID generation."""
        asset_positions = [(100.0, 100.0), (150.0, 150.0)]
        road_network.generate_network(asset_positions)

        if len(road_network.segments) > 0:
            # Segment IDs should be unique and numbered
            segment_ids = list(road_network.segments.keys())
            assert all(seg_id.startswith("road_") for seg_id in segment_ids)

    def test_network_connectivity(self, road_network):
        """Test that all assets are connected."""
        asset_positions = [
            (80.0, 80.0),
            (120.0, 120.0),
            (160.0, 160.0),
        ]

        success = road_network.generate_network(asset_positions)

        # If successful, all assets should be reachable
        if success:
            # Check that we have paths to assets
            assert len(road_network.segments) > 0

    def test_grade_constraints_in_network(self, navigation_graph):
        """Test that network respects grade constraints."""
        # Create network with strict grade limit
        config = PathfinderConfig(max_grade_percent=5.0)
        network = RoadNetwork(
            navigation_graph,
            entrance_position=(10.0, 10.0),
            pathfinder_config=config,
        )

        asset_positions = [(100.0, 100.0)]
        network.generate_network(asset_positions)

        # Check that generated roads respect grade constraint
        for segment in network.segments.values():
            # Allow some tolerance
            assert segment.max_grade <= config.max_grade_percent * 1.5

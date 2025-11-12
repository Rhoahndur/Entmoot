"""
Tests for terrain-based navigation graph.

Tests graph creation, node/edge management, and terrain sampling.
"""

import numpy as np
import pytest
from rasterio.transform import from_bounds

from entmoot.core.roads.graph import GraphNode, NavigationGraph


@pytest.fixture
def sample_terrain():
    """Create sample terrain data for testing."""
    # Create 10x10 grid
    elevation = np.array(
        [
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        ],
        dtype=np.float32,
    )

    # Slope increases from left to right
    slope = np.array(
        [
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
        ],
        dtype=np.float32,
    )

    # Create transform for 10m cells, covering 0-100m in x and y
    transform = from_bounds(0, 0, 100, 100, 10, 10)

    return elevation, slope, transform


@pytest.fixture
def navigation_graph(sample_terrain):
    """Create a navigation graph for testing."""
    elevation, slope, transform = sample_terrain
    return NavigationGraph(
        elevation_data=elevation,
        slope_data=slope,
        transform=transform,
        cell_size=10.0,
        grid_spacing=25.0,
    )


class TestGraphNode:
    """Tests for GraphNode dataclass."""

    def test_node_creation(self):
        """Test creating a graph node."""
        node = GraphNode(
            id="node_1",
            position=(100.0, 200.0),
            elevation=150.0,
            slope_pct=5.0,
        )

        assert node.id == "node_1"
        assert node.position == (100.0, 200.0)
        assert node.elevation == 150.0
        assert node.slope_pct == 5.0
        assert not node.is_asset
        assert not node.is_entrance

    def test_node_with_flags(self):
        """Test node with asset/entrance flags."""
        node = GraphNode(
            id="entrance",
            position=(0.0, 0.0),
            elevation=100.0,
            is_entrance=True,
        )

        assert node.is_entrance
        assert not node.is_asset

    def test_node_equality(self):
        """Test node equality based on ID."""
        node1 = GraphNode(id="node_1", position=(0, 0), elevation=100)
        node2 = GraphNode(id="node_1", position=(10, 10), elevation=110)
        node3 = GraphNode(id="node_2", position=(0, 0), elevation=100)

        assert node1 == node2  # Same ID
        assert node1 != node3  # Different ID

    def test_node_hashable(self):
        """Test that nodes are hashable."""
        node1 = GraphNode(id="node_1", position=(0, 0), elevation=100)
        node2 = GraphNode(id="node_2", position=(10, 10), elevation=110)

        node_set = {node1, node2}
        assert len(node_set) == 2


class TestNavigationGraph:
    """Tests for NavigationGraph."""

    def test_graph_initialization(self, sample_terrain):
        """Test graph initialization."""
        elevation, slope, transform = sample_terrain
        graph = NavigationGraph(
            elevation_data=elevation,
            slope_data=slope,
            transform=transform,
            cell_size=10.0,
        )

        assert graph.elevation_data.shape == (10, 10)
        assert graph.slope_data.shape == (10, 10)
        assert graph.cell_size == 10.0

    def test_weight_validation(self, sample_terrain):
        """Test that weights must sum to 1.0."""
        elevation, slope, transform = sample_terrain

        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            NavigationGraph(
                elevation_data=elevation,
                slope_data=slope,
                transform=transform,
                cell_size=10.0,
                slope_weight=0.5,
                length_weight=0.3,
                cut_fill_weight=0.1,  # Sum = 0.9
            )

    def test_add_node(self, navigation_graph):
        """Test adding nodes to graph."""
        node = navigation_graph.add_node(position=(50.0, 50.0))

        assert node.id in navigation_graph.nodes
        assert node.id in navigation_graph.graph.nodes
        assert node.position == (50.0, 50.0)

    def test_add_custom_node(self, navigation_graph):
        """Test adding node with custom ID."""
        node = navigation_graph.add_node(
            position=(25.0, 25.0),
            node_id="custom_node",
            is_asset=True,
        )

        assert node.id == "custom_node"
        assert node.is_asset
        assert "custom_node" in navigation_graph.nodes

    def test_add_edge(self, navigation_graph):
        """Test adding edges between nodes."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))

        navigation_graph.add_edge(node1.id, node2.id)

        assert navigation_graph.graph.has_edge(node1.id, node2.id)

    def test_add_edge_invalid_nodes(self, navigation_graph):
        """Test adding edge with invalid nodes."""
        with pytest.raises(ValueError, match="Both nodes must exist"):
            navigation_graph.add_edge("invalid1", "invalid2")

    def test_get_neighbors(self, navigation_graph):
        """Test getting neighboring nodes."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))
        node3 = navigation_graph.add_node((30.0, 30.0))

        navigation_graph.add_edge(node1.id, node2.id)
        navigation_graph.add_edge(node1.id, node3.id)

        neighbors = navigation_graph.get_neighbors(node1.id)
        assert len(neighbors) == 2
        assert node2 in neighbors
        assert node3 in neighbors

    def test_get_edge_weight(self, navigation_graph):
        """Test getting edge weights."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))

        navigation_graph.add_edge(node1.id, node2.id)

        weight = navigation_graph.get_edge_weight(node1.id, node2.id)
        assert weight > 0  # Should have positive weight

    def test_get_edge_weight_invalid(self, navigation_graph):
        """Test getting weight for non-existent edge."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))

        with pytest.raises(ValueError, match="No edge between"):
            navigation_graph.get_edge_weight(node1.id, node2.id)

    def test_build_grid_graph(self, navigation_graph):
        """Test building grid-based graph."""
        bounds = (0.0, 0.0, 100.0, 100.0)
        navigation_graph.build_grid_graph(bounds)

        stats = navigation_graph.get_graph_stats()
        assert stats["num_nodes"] > 0
        assert stats["num_edges"] > 0

    def test_add_strategic_node(self, navigation_graph):
        """Test adding strategic nodes."""
        # Build base graph
        bounds = (0.0, 0.0, 100.0, 100.0)
        navigation_graph.build_grid_graph(bounds)

        initial_nodes = len(navigation_graph.nodes)

        # Add strategic node
        node = navigation_graph.add_strategic_node(
            position=(50.0, 50.0),
            node_id="asset_1",
            is_asset=True,
        )

        assert len(navigation_graph.nodes) == initial_nodes + 1
        assert node.is_asset

    def test_find_nearest_node(self, navigation_graph):
        """Test finding nearest node."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((50.0, 50.0))
        node3 = navigation_graph.add_node((90.0, 90.0))

        # Find nearest to (12, 12) - should be node1
        nearest = navigation_graph.find_nearest_node((12.0, 12.0))
        assert nearest == node1

        # Find nearest to (88, 88) - should be node3
        nearest = navigation_graph.find_nearest_node((88.0, 88.0))
        assert nearest == node3

    def test_find_nearest_node_empty_graph(self, navigation_graph):
        """Test finding nearest node in empty graph."""
        nearest = navigation_graph.find_nearest_node((50.0, 50.0))
        assert nearest is None

    def test_sample_elevation(self, navigation_graph):
        """Test elevation sampling."""
        # Add node and check it samples elevation
        node = navigation_graph.add_node((50.0, 50.0))
        assert node.elevation > 0

    def test_sample_slope(self, navigation_graph):
        """Test slope sampling."""
        # Add node and check it samples slope
        node = navigation_graph.add_node((50.0, 50.0))
        assert node.slope_pct > 0

    def test_edge_weight_calculation(self, navigation_graph):
        """Test edge weight incorporates terrain factors."""
        # Add two nodes at different elevations/slopes
        node1 = navigation_graph.add_node((10.0, 10.0))  # Lower elevation, gentle slope
        node2 = navigation_graph.add_node((80.0, 80.0))  # Higher elevation, steep slope

        navigation_graph.add_edge(node1.id, node2.id)

        weight = navigation_graph.get_edge_weight(node1.id, node2.id)

        # Weight should account for length, slope, and elevation change
        assert weight > 0

    def test_graph_stats(self, navigation_graph):
        """Test graph statistics."""
        # Build a small graph
        node1 = navigation_graph.add_node((10.0, 10.0), is_entrance=True)
        node2 = navigation_graph.add_node((20.0, 20.0), is_asset=True)
        node3 = navigation_graph.add_node((30.0, 30.0), is_asset=True)

        navigation_graph.add_edge(node1.id, node2.id)
        navigation_graph.add_edge(node1.id, node3.id)

        stats = navigation_graph.get_graph_stats()

        assert stats["num_nodes"] == 3
        assert stats["num_edges"] == 2
        assert stats["entrance_nodes"] == 1
        assert stats["asset_nodes"] == 2
        assert stats["is_connected"]

    def test_export_geojson(self, navigation_graph):
        """Test exporting graph to GeoJSON."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))
        navigation_graph.add_edge(node1.id, node2.id)

        geojson = navigation_graph.export_to_geojson()

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 2  # At least nodes
        assert any(f["properties"]["type"] == "node" for f in geojson["features"])
        assert any(f["properties"]["type"] == "edge" for f in geojson["features"])

    def test_edge_weight_factors(self, navigation_graph):
        """Test that edge weights incorporate all factors."""
        # Create nodes with controlled terrain
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 10.0))  # Same y, 10m apart

        navigation_graph.add_edge(node1.id, node2.id)
        weight = navigation_graph.get_edge_weight(node1.id, node2.id)

        # Weight should be influenced by configured weights
        assert weight > 0
        assert navigation_graph.slope_weight > 0
        assert navigation_graph.length_weight > 0
        assert navigation_graph.cut_fill_weight > 0

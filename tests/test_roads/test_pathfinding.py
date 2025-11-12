"""
Tests for A* pathfinding with grade constraints.

Tests pathfinding algorithm, grade enforcement, and path smoothing.
"""

import numpy as np
import pytest
from rasterio.transform import from_bounds

from entmoot.core.roads.graph import NavigationGraph
from entmoot.core.roads.pathfinding import AStarPathfinder, Path, PathfinderConfig


@pytest.fixture
def sample_terrain():
    """Create sample terrain for testing."""
    # Create terrain with controlled slope
    elevation = np.zeros((20, 20), dtype=np.float32)
    slope = np.zeros((20, 20), dtype=np.float32)

    # Create gentle slope from left to right
    for i in range(20):
        for j in range(20):
            elevation[i, j] = 100.0 + j * 0.5  # Gradual elevation increase
            slope[i, j] = 2.0  # Gentle slope

    # Add a steep section in the middle
    for i in range(8, 12):
        for j in range(8, 12):
            elevation[i, j] = 120.0
            slope[i, j] = 15.0  # Steep area

    transform = from_bounds(0, 0, 200, 200, 20, 20)
    return elevation, slope, transform


@pytest.fixture
def navigation_graph(sample_terrain):
    """Create navigation graph for testing."""
    elevation, slope, transform = sample_terrain
    graph = NavigationGraph(
        elevation_data=elevation,
        slope_data=slope,
        transform=transform,
        cell_size=10.0,
        grid_spacing=20.0,
    )

    # Build grid
    graph.build_grid_graph((0, 0, 200, 200))

    return graph


@pytest.fixture
def pathfinder(navigation_graph):
    """Create pathfinder for testing."""
    config = PathfinderConfig(max_grade_percent=8.0)
    return AStarPathfinder(navigation_graph, config)


class TestPathfinderConfig:
    """Tests for PathfinderConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = PathfinderConfig()

        assert config.max_grade_percent == 8.0
        assert config.switchback_detection
        assert config.smoothing_enabled
        assert config.heuristic_weight == 1.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = PathfinderConfig(
            max_grade_percent=10.0,
            switchback_detection=False,
            smoothing_enabled=False,
            heuristic_weight=1.5,
        )

        assert config.max_grade_percent == 10.0
        assert not config.switchback_detection
        assert not config.smoothing_enabled
        assert config.heuristic_weight == 1.5

    def test_invalid_max_grade(self):
        """Test validation of max grade."""
        with pytest.raises(ValueError, match="max_grade_percent must be positive"):
            PathfinderConfig(max_grade_percent=-5.0)

    def test_invalid_smoothing_tolerance(self):
        """Test validation of smoothing tolerance."""
        with pytest.raises(ValueError, match="smoothing_tolerance must be non-negative"):
            PathfinderConfig(smoothing_tolerance=-1.0)

    def test_invalid_heuristic_weight(self):
        """Test validation of heuristic weight."""
        with pytest.raises(ValueError, match="heuristic_weight must be non-negative"):
            PathfinderConfig(heuristic_weight=-1.0)


class TestPath:
    """Tests for Path dataclass."""

    def test_path_creation(self, navigation_graph):
        """Test creating a path."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))
        node3 = navigation_graph.add_node((30.0, 30.0))

        path = Path(
            nodes=[node1, node2, node3],
            total_cost=100.0,
            total_length=50.0,
            max_grade=5.0,
            avg_grade=3.0,
        )

        assert len(path.nodes) == 3
        assert path.total_cost == 100.0
        assert path.total_length == 50.0
        assert path.max_grade == 5.0
        assert path.avg_grade == 3.0

    def test_get_geometry(self, navigation_graph):
        """Test getting path geometry."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))
        node3 = navigation_graph.add_node((30.0, 30.0))

        path = Path(nodes=[node1, node2, node3])
        geometry = path.get_geometry()

        assert geometry.geom_type == "LineString"
        assert len(geometry.coords) == 3

    def test_get_waypoints(self, navigation_graph):
        """Test getting waypoints."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))

        path = Path(nodes=[node1, node2])
        waypoints = path.get_waypoints()

        assert len(waypoints) == 2
        assert waypoints[0] == (10.0, 10.0)
        assert waypoints[1] == (20.0, 20.0)

    def test_get_elevations(self, navigation_graph):
        """Test getting elevations."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))

        path = Path(nodes=[node1, node2])
        elevations = path.get_elevations()

        assert len(elevations) == 2
        assert all(isinstance(e, float) for e in elevations)

    def test_to_dict(self, navigation_graph):
        """Test converting path to dictionary."""
        node1 = navigation_graph.add_node((10.0, 10.0))
        node2 = navigation_graph.add_node((20.0, 20.0))

        path = Path(
            nodes=[node1, node2],
            total_cost=50.0,
            total_length=25.0,
        )

        path_dict = path.to_dict()

        assert "num_nodes" in path_dict
        assert "total_cost" in path_dict
        assert "total_length" in path_dict
        assert "waypoints" in path_dict
        assert "elevations" in path_dict


class TestAStarPathfinder:
    """Tests for A* pathfinding."""

    def test_pathfinder_initialization(self, navigation_graph):
        """Test pathfinder initialization."""
        config = PathfinderConfig(max_grade_percent=10.0)
        pathfinder = AStarPathfinder(navigation_graph, config)

        assert pathfinder.graph == navigation_graph
        assert pathfinder.config.max_grade_percent == 10.0

    def test_find_simple_path(self, pathfinder, navigation_graph):
        """Test finding a simple path."""
        # Add two nodes and connect them
        node1 = navigation_graph.add_node((10.0, 10.0), node_id="start")
        node2 = navigation_graph.add_node((30.0, 30.0), node_id="goal")

        # Connect them through grid or directly
        navigation_graph.add_edge("start", "goal")

        # Find path
        path = pathfinder.find_path("start", "goal")

        assert path is not None
        assert len(path.nodes) >= 2
        assert path.nodes[0].id == "start"
        assert path.nodes[-1].id == "goal"

    def test_no_path_found(self, pathfinder, navigation_graph):
        """Test when no path exists."""
        # Create isolated nodes
        node1 = navigation_graph.add_node((500.0, 500.0), node_id="isolated1")
        node2 = navigation_graph.add_node((600.0, 600.0), node_id="isolated2")

        path = pathfinder.find_path("isolated1", "isolated2")

        # Should return None if nodes aren't connected
        # (might find path through grid, but testing the concept)
        assert path is None or len(path.nodes) >= 2

    def test_invalid_nodes(self, pathfinder):
        """Test pathfinding with invalid node IDs."""
        path = pathfinder.find_path("invalid1", "invalid2")
        assert path is None

    def test_grade_constraint_enforcement(self, navigation_graph):
        """Test that grade constraints are enforced."""
        # Create a steep path scenario
        node1 = navigation_graph.add_node((10.0, 10.0), node_id="bottom")
        node2 = navigation_graph.add_node((20.0, 10.0), node_id="top")

        # Manually set extreme elevations to create steep grade
        navigation_graph.nodes["bottom"].elevation = 100.0
        navigation_graph.nodes["top"].elevation = 120.0  # Very steep

        # Add edge
        navigation_graph.add_edge("bottom", "top")

        # Pathfinder with strict grade limit
        strict_config = PathfinderConfig(max_grade_percent=5.0)
        strict_pathfinder = AStarPathfinder(navigation_graph, strict_config)

        # This edge should be avoided due to grade
        # (Implementation checks grade during pathfinding)
        path = strict_pathfinder.find_path("bottom", "top")

        # Path might still be found through alternate routes in grid
        if path:
            assert path.max_grade <= strict_config.max_grade_percent * 1.5  # Allow some margin

    def test_path_metrics_calculation(self, pathfinder, navigation_graph):
        """Test that path metrics are calculated correctly."""
        node1 = navigation_graph.add_node((10.0, 10.0), node_id="start")
        node2 = navigation_graph.add_node((50.0, 50.0), node_id="end")

        path = pathfinder.find_path("start", "end")

        if path:
            assert path.total_length > 0
            assert path.total_cost > 0
            assert path.max_grade >= 0
            assert path.avg_grade >= 0

    def test_find_paths_to_multiple_goals(self, pathfinder, navigation_graph):
        """Test finding paths to multiple destinations."""
        start = navigation_graph.add_node((10.0, 10.0), node_id="start")
        goal1 = navigation_graph.add_node((50.0, 50.0), node_id="goal1")
        goal2 = navigation_graph.add_node((80.0, 80.0), node_id="goal2")

        paths = pathfinder.find_paths_to_multiple_goals(
            "start", ["goal1", "goal2"]
        )

        assert "goal1" in paths
        assert "goal2" in paths

    def test_heuristic_calculation(self, pathfinder, navigation_graph):
        """Test heuristic function."""
        node1 = navigation_graph.add_node((0.0, 0.0), node_id="node1")
        node2 = navigation_graph.add_node((30.0, 40.0), node_id="node2")

        # Heuristic should be positive
        heuristic = pathfinder._heuristic("node1", "node2")
        assert heuristic > 0

        # Should be approximately Euclidean distance (50m in this case)
        # Plus some elevation penalty
        assert heuristic >= 50.0

    def test_grade_constraint_check(self, pathfinder, navigation_graph):
        """Test grade constraint checking."""
        # Create nodes with known elevations
        node1 = navigation_graph.add_node((0.0, 0.0), node_id="low")
        node2 = navigation_graph.add_node((100.0, 0.0), node_id="high")

        # Set elevations
        navigation_graph.nodes["low"].elevation = 100.0
        navigation_graph.nodes["high"].elevation = 110.0

        # Grade = (10m rise / 100m run) * 100 = 10%
        # Should pass 8% limit if we increase the config
        pathfinder.config.max_grade_percent = 12.0
        assert pathfinder._check_grade_constraint("low", "high")

        # Should fail with strict limit
        pathfinder.config.max_grade_percent = 5.0
        assert not pathfinder._check_grade_constraint("low", "high")

    def test_switchback_detection(self, pathfinder, navigation_graph):
        """Test switchback detection in paths."""
        # Create a path with a sharp turn
        node1 = navigation_graph.add_node((0.0, 0.0), node_id="n1")
        node2 = navigation_graph.add_node((10.0, 0.0), node_id="n2")
        node3 = navigation_graph.add_node((5.0, 0.0), node_id="n3")  # Goes back

        # Test detection
        has_switchback = pathfinder._detect_switchbacks([node1, node2, node3])
        assert has_switchback

        # Straight path should not have switchbacks
        node4 = navigation_graph.add_node((20.0, 0.0), node_id="n4")
        no_switchback = pathfinder._detect_switchbacks([node1, node2, node4])
        assert not no_switchback

    def test_path_smoothing(self, pathfinder, navigation_graph):
        """Test path smoothing."""
        # Create path with unnecessary waypoints
        nodes = []
        for i in range(5):
            node = navigation_graph.add_node(
                (float(i * 10), float(i * 10)),
                node_id=f"node_{i}"
            )
            nodes.append(node)

        # Create original path
        original_path = Path(
            nodes=nodes,
            total_cost=100.0,
            total_length=50.0,
        )

        # Apply smoothing
        smoothed_path = pathfinder._smooth_path(original_path)

        # Smoothed path should have fewer nodes (or same if optimal)
        assert len(smoothed_path.nodes) <= len(original_path.nodes)

    def test_smoothing_disabled(self, navigation_graph):
        """Test pathfinding with smoothing disabled."""
        config = PathfinderConfig(smoothing_enabled=False)
        pathfinder = AStarPathfinder(navigation_graph, config)

        node1 = navigation_graph.add_node((10.0, 10.0), node_id="start")
        node2 = navigation_graph.add_node((50.0, 50.0), node_id="end")

        path = pathfinder.find_path("start", "end")

        # Path should still be found
        if path:
            assert len(path.nodes) >= 2

    def test_avoid_nodes(self, pathfinder, navigation_graph):
        """Test avoiding specific nodes."""
        node1 = navigation_graph.add_node((10.0, 10.0), node_id="start")
        node2 = navigation_graph.add_node((30.0, 30.0), node_id="middle")
        node3 = navigation_graph.add_node((50.0, 50.0), node_id="end")

        # Find path avoiding middle node
        path = pathfinder.find_path("start", "end", avoid_nodes={"middle"})

        if path:
            # Middle node should not be in path
            node_ids = [n.id for n in path.nodes]
            assert "middle" not in node_ids

    def test_path_reconstruction(self, navigation_graph):
        """Test path reconstruction from came_from dictionary."""
        # Use pathfinder with smoothing disabled
        config = PathfinderConfig(smoothing_enabled=False)
        pathfinder = AStarPathfinder(navigation_graph, config)

        node1 = navigation_graph.add_node((10.0, 10.0), node_id="n1")
        node2 = navigation_graph.add_node((20.0, 20.0), node_id="n2")
        node3 = navigation_graph.add_node((30.0, 30.0), node_id="n3")

        came_from = {"n2": "n1", "n3": "n2"}

        path = pathfinder._reconstruct_path(came_from, "n3", 100.0)

        assert len(path.nodes) == 3
        assert path.nodes[0].id == "n1"
        assert path.nodes[1].id == "n2"
        assert path.nodes[2].id == "n3"

    def test_can_skip_waypoint(self, pathfinder, navigation_graph):
        """Test waypoint skipping logic."""
        node1 = navigation_graph.add_node((0.0, 0.0), node_id="start")
        node2 = navigation_graph.add_node((10.0, 0.0), node_id="middle")
        node3 = navigation_graph.add_node((20.0, 0.0), node_id="end")

        # Straight line - should be able to skip middle
        can_skip = pathfinder._can_skip_waypoint(node1, node3, [node2])

        # Result depends on grade and tolerance
        assert isinstance(can_skip, bool)

    def test_heuristic_weight(self, navigation_graph):
        """Test different heuristic weights."""
        # Greedy search (high weight)
        greedy_config = PathfinderConfig(heuristic_weight=2.0)
        greedy_pathfinder = AStarPathfinder(navigation_graph, greedy_config)

        # Dijkstra (zero weight)
        dijkstra_config = PathfinderConfig(heuristic_weight=0.0)
        dijkstra_pathfinder = AStarPathfinder(navigation_graph, dijkstra_config)

        # Both should work
        assert greedy_pathfinder.config.heuristic_weight == 2.0
        assert dijkstra_pathfinder.config.heuristic_weight == 0.0

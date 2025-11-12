"""
A* pathfinding with terrain-aware grade constraints.

This module implements A* pathfinding optimized for road planning, including:
- Maximum grade enforcement
- Switchback detection
- Path smoothing
- Multi-destination routing
"""

import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from shapely.geometry import LineString

from entmoot.core.roads.graph import GraphNode, NavigationGraph


@dataclass
class PathfinderConfig:
    """
    Configuration for A* pathfinding.

    Attributes:
        max_grade_percent: Maximum allowable grade (default: 8%)
        switchback_detection: Enable switchback detection
        smoothing_enabled: Enable path smoothing
        smoothing_tolerance: Tolerance for path smoothing (meters)
        heuristic_weight: Weight for heuristic (1.0 = A*, higher = greedier)
    """

    max_grade_percent: float = 8.0
    switchback_detection: bool = True
    smoothing_enabled: bool = True
    smoothing_tolerance: float = 2.0
    heuristic_weight: float = 1.0

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_grade_percent <= 0:
            raise ValueError("max_grade_percent must be positive")
        if self.smoothing_tolerance < 0:
            raise ValueError("smoothing_tolerance must be non-negative")
        if self.heuristic_weight < 0:
            raise ValueError("heuristic_weight must be non-negative")


@dataclass
class Path:
    """
    Represents a path through the navigation graph.

    Attributes:
        nodes: Ordered list of nodes in path
        total_cost: Total path cost
        total_length: Total path length in meters
        max_grade: Maximum grade along path (%)
        avg_grade: Average grade along path (%)
        has_switchbacks: Whether path contains switchbacks
        metadata: Additional path metadata
    """

    nodes: List[GraphNode]
    total_cost: float = 0.0
    total_length: float = 0.0
    max_grade: float = 0.0
    avg_grade: float = 0.0
    has_switchbacks: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_geometry(self) -> LineString:
        """
        Get path as Shapely LineString.

        Returns:
            LineString geometry
        """
        if not self.nodes:
            return LineString()

        coords = [node.position for node in self.nodes]
        return LineString(coords)

    def get_waypoints(self) -> List[Tuple[float, float]]:
        """
        Get list of waypoint coordinates.

        Returns:
            List of (x, y) tuples
        """
        return [node.position for node in self.nodes]

    def get_elevations(self) -> List[float]:
        """
        Get elevations along path.

        Returns:
            List of elevation values
        """
        return [node.elevation for node in self.nodes]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert path to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "num_nodes": len(self.nodes),
            "total_cost": float(self.total_cost),
            "total_length": float(self.total_length),
            "max_grade": float(self.max_grade),
            "avg_grade": float(self.avg_grade),
            "has_switchbacks": bool(self.has_switchbacks),
            "waypoints": self.get_waypoints(),
            "elevations": self.get_elevations(),
            "metadata": self.metadata,
        }


class AStarPathfinder:
    """
    A* pathfinding with terrain-aware constraints for road planning.

    This implementation includes grade constraints, switchback detection,
    and path smoothing optimized for generating drivable roads.
    """

    def __init__(self, graph: NavigationGraph, config: Optional[PathfinderConfig] = None):
        """
        Initialize the pathfinder.

        Args:
            graph: Navigation graph to search
            config: Pathfinder configuration (uses defaults if not provided)
        """
        self.graph = graph
        self.config = config or PathfinderConfig()

    def find_path(
        self, start_node_id: str, goal_node_id: str, avoid_nodes: Optional[Set[str]] = None
    ) -> Optional[Path]:
        """
        Find optimal path between two nodes using A* algorithm.

        Args:
            start_node_id: Starting node ID
            goal_node_id: Goal node ID
            avoid_nodes: Optional set of node IDs to avoid

        Returns:
            Path object if found, None otherwise
        """
        if start_node_id not in self.graph.nodes or goal_node_id not in self.graph.nodes:
            return None

        avoid_nodes = avoid_nodes or set()

        # A* data structures
        open_set: List[Tuple[float, str]] = []  # (f_score, node_id)
        heapq.heappush(open_set, (0.0, start_node_id))

        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {start_node_id: 0.0}
        f_score: Dict[str, float] = {start_node_id: self._heuristic(start_node_id, goal_node_id)}

        closed_set: Set[str] = set()

        while open_set:
            _, current_id = heapq.heappop(open_set)

            # Skip if already processed
            if current_id in closed_set:
                continue

            # Goal reached
            if current_id == goal_node_id:
                return self._reconstruct_path(came_from, current_id, g_score[current_id])

            closed_set.add(current_id)

            # Explore neighbors
            for neighbor in self.graph.get_neighbors(current_id):
                neighbor_id = neighbor.id

                # Skip avoided nodes
                if neighbor_id in avoid_nodes:
                    continue

                # Skip if already processed
                if neighbor_id in closed_set:
                    continue

                # Check grade constraint
                if not self._check_grade_constraint(current_id, neighbor_id):
                    continue

                # Calculate tentative g_score
                edge_weight = self.graph.get_edge_weight(current_id, neighbor_id)
                tentative_g = g_score[current_id] + edge_weight

                # Check if this path is better
                if neighbor_id not in g_score or tentative_g < g_score[neighbor_id]:
                    came_from[neighbor_id] = current_id
                    g_score[neighbor_id] = tentative_g
                    f = tentative_g + self.config.heuristic_weight * self._heuristic(
                        neighbor_id, goal_node_id
                    )
                    f_score[neighbor_id] = f
                    heapq.heappush(open_set, (f, neighbor_id))

        # No path found
        return None

    def find_paths_to_multiple_goals(
        self, start_node_id: str, goal_node_ids: List[str]
    ) -> Dict[str, Optional[Path]]:
        """
        Find paths from start to multiple goal nodes.

        Args:
            start_node_id: Starting node ID
            goal_node_ids: List of goal node IDs

        Returns:
            Dictionary mapping goal_node_id to Path (or None if no path found)
        """
        paths: Dict[str, Optional[Path]] = {}

        for goal_id in goal_node_ids:
            paths[goal_id] = self.find_path(start_node_id, goal_id)

        return paths

    def _heuristic(self, node1_id: str, node2_id: str) -> float:
        """
        Heuristic function for A* (Euclidean distance).

        Args:
            node1_id: First node ID
            node2_id: Second node ID

        Returns:
            Estimated cost from node1 to node2
        """
        node1 = self.graph.nodes[node1_id]
        node2 = self.graph.nodes[node2_id]

        x1, y1 = node1.position
        x2, y2 = node2.position

        # Euclidean distance
        distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # Factor in elevation change for better heuristic
        elevation_change = abs(node2.elevation - node1.elevation)
        elevation_penalty = elevation_change * 0.5

        return distance + elevation_penalty

    def _check_grade_constraint(self, node1_id: str, node2_id: str) -> bool:
        """
        Check if edge between nodes satisfies grade constraint.

        Args:
            node1_id: First node ID
            node2_id: Second node ID

        Returns:
            True if grade is acceptable
        """
        node1 = self.graph.nodes[node1_id]
        node2 = self.graph.nodes[node2_id]

        # Calculate grade
        x1, y1 = node1.position
        x2, y2 = node2.position
        horizontal_distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        if horizontal_distance < 0.1:  # Avoid division by zero
            return True

        elevation_change = abs(node2.elevation - node1.elevation)
        grade_percent = (elevation_change / horizontal_distance) * 100.0

        return grade_percent <= self.config.max_grade_percent

    def _reconstruct_path(
        self, came_from: Dict[str, str], current_id: str, total_cost: float
    ) -> Path:
        """
        Reconstruct path from A* came_from dictionary.

        Args:
            came_from: Dictionary mapping node_id to previous node_id
            current_id: Goal node ID
            total_cost: Total path cost

        Returns:
            Path object
        """
        # Build path
        path_ids = [current_id]
        while current_id in came_from:
            current_id = came_from[current_id]
            path_ids.append(current_id)

        path_ids.reverse()
        nodes = [self.graph.nodes[nid] for nid in path_ids]

        # Calculate path metrics
        total_length = 0.0
        grades = []

        for i in range(len(nodes) - 1):
            node1 = nodes[i]
            node2 = nodes[i + 1]

            x1, y1 = node1.position
            x2, y2 = node2.position
            segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            total_length += segment_length

            # Calculate grade
            elevation_change = abs(node2.elevation - node1.elevation)
            if segment_length > 0.1:
                grade = (elevation_change / segment_length) * 100.0
                grades.append(grade)

        max_grade = max(grades) if grades else 0.0
        avg_grade = np.mean(grades) if grades else 0.0

        # Detect switchbacks
        has_switchbacks = self._detect_switchbacks(nodes) if self.config.switchback_detection else False

        # Create path
        path = Path(
            nodes=nodes,
            total_cost=total_cost,
            total_length=total_length,
            max_grade=max_grade,
            avg_grade=avg_grade,
            has_switchbacks=has_switchbacks,
        )

        # Apply smoothing if enabled
        if self.config.smoothing_enabled:
            path = self._smooth_path(path)

        return path

    def _detect_switchbacks(self, nodes: List[GraphNode]) -> bool:
        """
        Detect if path contains switchbacks (hairpin turns).

        Args:
            nodes: List of nodes in path

        Returns:
            True if switchbacks detected
        """
        if len(nodes) < 3:
            return False

        # Check for sharp direction changes
        for i in range(len(nodes) - 2):
            p1 = nodes[i].position
            p2 = nodes[i + 1].position
            p3 = nodes[i + 2].position

            # Calculate vectors
            v1 = (p2[0] - p1[0], p2[1] - p1[1])
            v2 = (p3[0] - p2[0], p3[1] - p2[1])

            # Calculate angle between vectors
            dot_product = v1[0] * v2[0] + v1[1] * v2[1]
            mag1 = np.sqrt(v1[0] ** 2 + v1[1] ** 2)
            mag2 = np.sqrt(v2[0] ** 2 + v2[1] ** 2)

            if mag1 > 0.1 and mag2 > 0.1:
                cos_angle = dot_product / (mag1 * mag2)
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                angle_deg = np.degrees(np.arccos(cos_angle))

                # Switchback if angle > 135 degrees
                if angle_deg > 135.0:
                    return True

        return False

    def _smooth_path(self, path: Path) -> Path:
        """
        Smooth path by removing unnecessary waypoints.

        Uses Douglas-Peucker-like algorithm to simplify path while
        maintaining terrain constraints.

        Args:
            path: Original path

        Returns:
            Smoothed path
        """
        if len(path.nodes) <= 2:
            return path

        # Keep start and end
        smoothed_nodes = [path.nodes[0]]

        # Iterate through intermediate nodes
        i = 0
        while i < len(path.nodes) - 1:
            current = path.nodes[i]
            next_idx = i + 1

            # Try to skip ahead as far as possible
            while next_idx < len(path.nodes) - 1:
                candidate = path.nodes[next_idx + 1]

                # Check if we can go directly from current to candidate
                if self._can_skip_waypoint(current, candidate, path.nodes[i + 1 : next_idx + 1]):
                    next_idx += 1
                else:
                    break

            # Add the furthest reachable node
            smoothed_nodes.append(path.nodes[next_idx])
            i = next_idx

        # Recalculate metrics
        total_length = 0.0
        grades = []

        for i in range(len(smoothed_nodes) - 1):
            node1 = smoothed_nodes[i]
            node2 = smoothed_nodes[i + 1]

            x1, y1 = node1.position
            x2, y2 = node2.position
            segment_length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            total_length += segment_length

            elevation_change = abs(node2.elevation - node1.elevation)
            if segment_length > 0.1:
                grade = (elevation_change / segment_length) * 100.0
                grades.append(grade)

        max_grade = max(grades) if grades else 0.0
        avg_grade = np.mean(grades) if grades else 0.0

        return Path(
            nodes=smoothed_nodes,
            total_cost=path.total_cost,
            total_length=total_length,
            max_grade=max_grade,
            avg_grade=avg_grade,
            has_switchbacks=path.has_switchbacks,
            metadata=path.metadata,
        )

    def _can_skip_waypoint(
        self, start: GraphNode, end: GraphNode, skipped: List[GraphNode]
    ) -> bool:
        """
        Check if we can skip intermediate waypoints.

        Args:
            start: Start node
            end: End node
            skipped: List of nodes being skipped

        Returns:
            True if skipping is valid
        """
        # Check grade constraint on direct segment
        x1, y1 = start.position
        x2, y2 = end.position
        horizontal_distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        if horizontal_distance < 0.1:
            return True

        elevation_change = abs(end.elevation - start.elevation)
        grade_percent = (elevation_change / horizontal_distance) * 100.0

        if grade_percent > self.config.max_grade_percent:
            return False

        # Check that direct line doesn't deviate too much from original path
        if not skipped:
            return True

        # Calculate maximum perpendicular distance
        line = LineString([start.position, end.position])
        max_deviation = 0.0

        for node in skipped:
            from shapely.geometry import Point as ShapelyPoint

            point = ShapelyPoint(node.position)
            deviation = point.distance(line)
            max_deviation = max(max_deviation, deviation)

        return max_deviation <= self.config.smoothing_tolerance

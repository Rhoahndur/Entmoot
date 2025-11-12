"""
Terrain-based navigation graph for road planning.

This module creates a navigation graph from terrain data where nodes represent
potential road waypoints and edges represent possible road segments. Edge weights
are calculated based on terrain cost factors like slope, length, and cut/fill.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, Point as ShapelyPoint

try:
    import networkx as nx
except ImportError:
    raise ImportError(
        "NetworkX is required for road network generation. "
        "Install it with: pip install networkx"
    )


@dataclass
class GraphNode:
    """
    Represents a node in the navigation graph.

    Attributes:
        id: Unique node identifier
        position: (x, y) coordinates in project CRS
        elevation: Elevation at this point in meters
        slope_pct: Average slope percentage at this location
        is_asset: Whether this node is at an asset location
        is_entrance: Whether this node is the site entrance
        metadata: Additional node metadata
    """

    id: str
    position: Tuple[float, float]
    elevation: float
    slope_pct: float = 0.0
    is_asset: bool = False
    is_entrance: bool = False
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize metadata if None."""
        if self.metadata is None:
            self.metadata = {}

    def __hash__(self) -> int:
        """Make node hashable for use in sets and dicts."""
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        """Compare nodes by ID."""
        if not isinstance(other, GraphNode):
            return False
        return self.id == other.id


class NavigationGraph:
    """
    Creates and manages a terrain-aware navigation graph for road planning.

    The graph represents potential road routes with nodes at strategic locations
    and edges weighted by construction cost factors.
    """

    def __init__(
        self,
        elevation_data: NDArray[np.floating[Any]],
        slope_data: NDArray[np.floating[Any]],
        transform: Any,
        cell_size: float,
        grid_spacing: float = 25.0,
        slope_weight: float = 0.4,
        length_weight: float = 0.3,
        cut_fill_weight: float = 0.3,
    ):
        """
        Initialize the navigation graph.

        Args:
            elevation_data: 2D array of elevation values
            slope_data: 2D array of slope percentages
            transform: Affine transform for coordinate conversion
            cell_size: DEM cell size in meters
            grid_spacing: Spacing between grid nodes in meters (default: 25m)
            slope_weight: Weight for slope cost factor (0-1)
            length_weight: Weight for length cost factor (0-1)
            cut_fill_weight: Weight for cut/fill cost factor (0-1)
        """
        self.elevation_data = elevation_data
        self.slope_data = slope_data
        self.transform = transform
        self.cell_size = cell_size
        self.grid_spacing = grid_spacing

        # Validate weights
        total_weight = slope_weight + length_weight + cut_fill_weight
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total_weight}")

        self.slope_weight = slope_weight
        self.length_weight = length_weight
        self.cut_fill_weight = cut_fill_weight

        # Initialize graph
        self.graph: nx.Graph = nx.Graph()
        self.nodes: Dict[str, GraphNode] = {}
        self._node_counter = 0

    def add_node(
        self,
        position: Tuple[float, float],
        is_asset: bool = False,
        is_entrance: bool = False,
        node_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GraphNode:
        """
        Add a node to the navigation graph.

        Args:
            position: (x, y) coordinates in project CRS
            is_asset: Whether this is an asset location
            is_entrance: Whether this is the site entrance
            node_id: Optional custom node ID
            metadata: Optional node metadata

        Returns:
            GraphNode instance
        """
        # Generate ID if not provided
        if node_id is None:
            node_id = f"node_{self._node_counter}"
            self._node_counter += 1

        # Sample elevation and slope at position
        elevation = self._sample_elevation(position)
        slope_pct = self._sample_slope(position)

        # Create node
        node = GraphNode(
            id=node_id,
            position=position,
            elevation=elevation,
            slope_pct=slope_pct,
            is_asset=is_asset,
            is_entrance=is_entrance,
            metadata=metadata or {},
        )

        # Add to graph
        self.nodes[node_id] = node
        self.graph.add_node(node_id, node=node)

        return node

    def add_edge(self, node1_id: str, node2_id: str) -> None:
        """
        Add an edge between two nodes with calculated weight.

        Args:
            node1_id: First node ID
            node2_id: Second node ID

        Raises:
            ValueError: If either node doesn't exist
        """
        if node1_id not in self.nodes or node2_id not in self.nodes:
            raise ValueError("Both nodes must exist in graph")

        node1 = self.nodes[node1_id]
        node2 = self.nodes[node2_id]

        # Calculate edge weight (cost)
        weight = self._calculate_edge_weight(node1, node2)

        # Add edge
        self.graph.add_edge(node1_id, node2_id, weight=weight)

    def build_grid_graph(
        self,
        bounds: Tuple[float, float, float, float],
        excluded_zones: Optional[List[Any]] = None,
    ) -> None:
        """
        Build a grid-based navigation graph within bounds.

        Args:
            bounds: (min_x, min_y, max_x, max_y) bounding box
            excluded_zones: Optional list of Shapely polygons to exclude
        """
        min_x, min_y, max_x, max_y = bounds

        # Create grid nodes
        x_coords = np.arange(min_x, max_x, self.grid_spacing)
        y_coords = np.arange(min_y, max_y, self.grid_spacing)

        grid_nodes: List[GraphNode] = []

        for x in x_coords:
            for y in y_coords:
                position = (float(x), float(y))

                # Check if in excluded zone
                if excluded_zones:
                    point = ShapelyPoint(position)
                    if any(zone.contains(point) for zone in excluded_zones):
                        continue

                # Check if valid terrain
                slope_pct = self._sample_slope(position)
                if slope_pct > 100.0:  # Skip extreme slopes
                    continue

                # Add node
                node = self.add_node(position)
                grid_nodes.append(node)

        # Connect adjacent nodes
        for i, node1 in enumerate(grid_nodes):
            x1, y1 = node1.position
            for node2 in grid_nodes[i + 1 :]:
                x2, y2 = node2.position
                distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                # Connect if within reasonable distance (1.5x grid spacing)
                if distance <= self.grid_spacing * 1.5:
                    self.add_edge(node1.id, node2.id)

    def add_strategic_node(
        self,
        position: Tuple[float, float],
        connect_to_nearby: bool = True,
        connection_radius: float = 50.0,
        node_id: Optional[str] = None,
        is_asset: bool = False,
        is_entrance: bool = False,
    ) -> GraphNode:
        """
        Add a strategic node (asset, entrance, waypoint) and connect to graph.

        Args:
            position: (x, y) coordinates
            connect_to_nearby: Whether to connect to nearby nodes
            connection_radius: Radius to search for connections (meters)
            node_id: Optional custom node ID
            is_asset: Whether this is an asset location
            is_entrance: Whether this is the site entrance

        Returns:
            GraphNode instance
        """
        # Add node
        node = self.add_node(
            position=position,
            is_asset=is_asset,
            is_entrance=is_entrance,
            node_id=node_id,
        )

        # Connect to nearby nodes
        if connect_to_nearby:
            x, y = position
            for other_node in self.nodes.values():
                if other_node.id == node.id:
                    continue

                x2, y2 = other_node.position
                distance = np.sqrt((x2 - x) ** 2 + (y2 - y) ** 2)

                if distance <= connection_radius:
                    self.add_edge(node.id, other_node.id)

        return node

    def get_neighbors(self, node_id: str) -> List[GraphNode]:
        """
        Get neighboring nodes.

        Args:
            node_id: Node ID

        Returns:
            List of neighboring GraphNode objects
        """
        if node_id not in self.graph:
            return []

        neighbor_ids = self.graph.neighbors(node_id)
        return [self.nodes[nid] for nid in neighbor_ids]

    def get_edge_weight(self, node1_id: str, node2_id: str) -> float:
        """
        Get edge weight between two nodes.

        Args:
            node1_id: First node ID
            node2_id: Second node ID

        Returns:
            Edge weight (cost)

        Raises:
            ValueError: If edge doesn't exist
        """
        if not self.graph.has_edge(node1_id, node2_id):
            raise ValueError(f"No edge between {node1_id} and {node2_id}")

        return self.graph[node1_id][node2_id]["weight"]

    def _sample_elevation(self, position: Tuple[float, float]) -> float:
        """
        Sample elevation at a given position.

        Args:
            position: (x, y) coordinates

        Returns:
            Elevation in meters
        """
        # Convert world coordinates to raster indices
        x, y = position
        row, col = ~self.transform * (x, y)
        row, col = int(row), int(col)

        # Check bounds
        if (
            row < 0
            or row >= self.elevation_data.shape[0]
            or col < 0
            or col >= self.elevation_data.shape[1]
        ):
            return 0.0

        return float(self.elevation_data[row, col])

    def _sample_slope(self, position: Tuple[float, float]) -> float:
        """
        Sample slope percentage at a given position.

        Args:
            position: (x, y) coordinates

        Returns:
            Slope percentage
        """
        # Convert world coordinates to raster indices
        x, y = position
        row, col = ~self.transform * (x, y)
        row, col = int(row), int(col)

        # Check bounds
        if (
            row < 0
            or row >= self.slope_data.shape[0]
            or col < 0
            or col >= self.slope_data.shape[1]
        ):
            return 0.0

        return float(self.slope_data[row, col])

    def _calculate_edge_weight(self, node1: GraphNode, node2: GraphNode) -> float:
        """
        Calculate edge weight based on terrain factors.

        Weight combines:
        - Slope cost: Steeper = higher cost
        - Length cost: Longer = higher cost
        - Cut/fill cost: Elevation change = higher cost

        Args:
            node1: First node
            node2: Second node

        Returns:
            Edge weight (cost), normalized to typical 0-100 range
        """
        x1, y1 = node1.position
        x2, y2 = node2.position

        # 1. Length cost
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        length_cost = length  # Direct proportion

        # 2. Slope cost
        # Use average slope along segment
        avg_slope = (node1.slope_pct + node2.slope_pct) / 2.0

        # Exponential penalty for steep slopes
        if avg_slope > 25.0:
            slope_cost = length * 10.0  # Very expensive
        elif avg_slope > 15.0:
            slope_cost = length * 3.0
        elif avg_slope > 8.0:
            slope_cost = length * 1.5
        else:
            slope_cost = length * 0.5

        # 3. Cut/fill cost
        elevation_change = abs(node2.elevation - node1.elevation)

        # Cost proportional to volume of earthwork
        # Assume road width of 6m for cost calculation
        road_width = 6.0
        cut_fill_volume = elevation_change * road_width * length
        cut_fill_cost = cut_fill_volume * 0.01  # Scale factor

        # Combine costs with weights
        total_cost = (
            self.length_weight * length_cost
            + self.slope_weight * slope_cost
            + self.cut_fill_weight * cut_fill_cost
        )

        return total_cost

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the navigation graph.

        Returns:
            Dictionary with graph statistics
        """
        if len(self.graph.nodes) == 0:
            return {
                "num_nodes": 0,
                "num_edges": 0,
                "is_connected": False,
                "num_components": 0,
                "avg_degree": 0.0,
            }

        return {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "is_connected": nx.is_connected(self.graph),
            "num_components": nx.number_connected_components(self.graph),
            "avg_degree": sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes()
            if self.graph.number_of_nodes() > 0
            else 0.0,
            "asset_nodes": sum(1 for n in self.nodes.values() if n.is_asset),
            "entrance_nodes": sum(1 for n in self.nodes.values() if n.is_entrance),
        }

    def find_nearest_node(self, position: Tuple[float, float]) -> Optional[GraphNode]:
        """
        Find the nearest node to a given position.

        Args:
            position: (x, y) coordinates

        Returns:
            Nearest GraphNode or None if graph is empty
        """
        if not self.nodes:
            return None

        x, y = position
        min_dist = float("inf")
        nearest_node = None

        for node in self.nodes.values():
            x2, y2 = node.position
            dist = np.sqrt((x2 - x) ** 2 + (y2 - y) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest_node = node

        return nearest_node

    def export_to_geojson(self) -> Dict[str, Any]:
        """
        Export graph to GeoJSON format.

        Returns:
            GeoJSON FeatureCollection
        """
        features = []

        # Export nodes
        for node in self.nodes.values():
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [node.position[0], node.position[1]]},
                    "properties": {
                        "id": node.id,
                        "elevation": node.elevation,
                        "slope_pct": node.slope_pct,
                        "is_asset": node.is_asset,
                        "is_entrance": node.is_entrance,
                        "type": "node",
                    },
                }
            )

        # Export edges
        for edge in self.graph.edges():
            node1 = self.nodes[edge[0]]
            node2 = self.nodes[edge[1]]
            weight = self.graph[edge[0]][edge[1]]["weight"]

            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [node1.position[0], node1.position[1]],
                            [node2.position[0], node2.position[1]],
                        ],
                    },
                    "properties": {
                        "from": edge[0],
                        "to": edge[1],
                        "weight": weight,
                        "type": "edge",
                    },
                }
            )

        return {"type": "FeatureCollection", "features": features}

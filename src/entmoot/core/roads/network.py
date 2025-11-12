"""
Road network generation and geometry.

This module generates complete road networks connecting all assets,
including road topology, geometry, intersections, and cut/fill calculations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import LineString, Point as ShapelyPoint, Polygon as ShapelyPolygon
from shapely.geometry import MultiLineString, box
from shapely.ops import unary_union

try:
    import networkx as nx
except ImportError:
    raise ImportError(
        "NetworkX is required for road network generation. "
        "Install it with: pip install networkx"
    )

from entmoot.core.roads.graph import NavigationGraph
from entmoot.core.roads.pathfinding import AStarPathfinder, Path, PathfinderConfig


class RoadType(str, Enum):
    """Road classification types."""

    PRIMARY = "primary"  # Main access roads: 24ft (7.3m) width
    SECONDARY = "secondary"  # Secondary roads: 18ft (5.5m) width
    ACCESS = "access"  # Access roads/driveways: 12ft (3.7m) width


@dataclass
class RoadSegment:
    """
    Represents a road segment in the network.

    Attributes:
        id: Unique segment identifier
        road_type: Classification of road
        centerline: Shapely LineString of road centerline
        width_m: Road width in meters
        length_m: Segment length in meters
        start_node_id: Starting node ID
        end_node_id: Ending node ID
        cut_fill_volume: Estimated cut/fill volume (cubic meters)
        avg_grade: Average grade along segment (%)
        max_grade: Maximum grade along segment (%)
        metadata: Additional segment metadata
    """

    id: str
    road_type: RoadType
    centerline: LineString
    width_m: float
    length_m: float
    start_node_id: str
    end_node_id: str
    cut_fill_volume: float = 0.0
    avg_grade: float = 0.0
    max_grade: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_geometry(self) -> ShapelyPolygon:
        """
        Get road segment as buffered polygon.

        Returns:
            Shapely Polygon representing road surface
        """
        return self.centerline.buffer(self.width_m / 2.0)

    def get_geometry_with_shoulder(self, shoulder_width: float = 1.0) -> ShapelyPolygon:
        """
        Get road segment with shoulders.

        Args:
            shoulder_width: Shoulder width on each side (meters)

        Returns:
            Shapely Polygon including shoulders
        """
        total_width = self.width_m + 2 * shoulder_width
        return self.centerline.buffer(total_width / 2.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert segment to dictionary."""
        return {
            "id": self.id,
            "road_type": self.road_type.value,
            "width_m": float(self.width_m),
            "length_m": float(self.length_m),
            "cut_fill_volume": float(self.cut_fill_volume),
            "avg_grade": float(self.avg_grade),
            "max_grade": float(self.max_grade),
            "start_node": self.start_node_id,
            "end_node": self.end_node_id,
            "metadata": self.metadata,
        }


@dataclass
class RoadIntersection:
    """
    Represents a road intersection.

    Attributes:
        id: Unique intersection identifier
        position: (x, y) coordinates
        connecting_segments: List of segment IDs meeting at intersection
        intersection_type: Type (T-junction, cross, etc.)
        geometry: Shapely Polygon of intersection area
    """

    id: str
    position: Tuple[float, float]
    connecting_segments: List[str]
    intersection_type: str
    geometry: ShapelyPolygon

    def to_dict(self) -> Dict[str, Any]:
        """Convert intersection to dictionary."""
        return {
            "id": self.id,
            "position": self.position,
            "connecting_segments": self.connecting_segments,
            "intersection_type": self.intersection_type,
            "num_connections": len(self.connecting_segments),
        }


class RoadNetwork:
    """
    Generates and manages complete road networks for site layouts.

    Connects all assets to the site entrance with optimized routing,
    proper road geometry, and intersection handling.
    """

    def __init__(
        self,
        navigation_graph: NavigationGraph,
        entrance_position: Tuple[float, float],
        pathfinder_config: Optional[PathfinderConfig] = None,
    ):
        """
        Initialize road network generator.

        Args:
            navigation_graph: Navigation graph for pathfinding
            entrance_position: (x, y) coordinates of site entrance
            pathfinder_config: Pathfinder configuration
        """
        self.navigation_graph = navigation_graph
        self.entrance_position = entrance_position
        self.pathfinder_config = pathfinder_config or PathfinderConfig()

        # Initialize pathfinder
        self.pathfinder = AStarPathfinder(navigation_graph, self.pathfinder_config)

        # Network data
        self.segments: Dict[str, RoadSegment] = {}
        self.intersections: Dict[str, RoadIntersection] = {}
        self._segment_counter = 0
        self._intersection_counter = 0

        # Add entrance node to graph if not exists
        self.entrance_node = self._ensure_entrance_node()

    def generate_network(
        self,
        asset_positions: List[Tuple[float, float]],
        asset_ids: Optional[List[str]] = None,
        optimize: bool = True,
    ) -> bool:
        """
        Generate road network connecting entrance to all assets.

        Args:
            asset_positions: List of (x, y) asset positions
            asset_ids: Optional list of asset IDs (for labeling)
            optimize: Whether to optimize network topology

        Returns:
            True if network generated successfully
        """
        if not asset_positions:
            return False

        # Add asset nodes to graph
        asset_node_ids = []
        for i, position in enumerate(asset_positions):
            asset_id = asset_ids[i] if asset_ids and i < len(asset_ids) else f"asset_{i}"

            # Find or add node
            existing_node = self.navigation_graph.find_nearest_node(position)
            if (
                existing_node
                and np.linalg.norm(np.array(existing_node.position) - np.array(position)) < 1.0
            ):
                node_id = existing_node.id
            else:
                node = self.navigation_graph.add_strategic_node(
                    position=position, node_id=asset_id, is_asset=True
                )
                node_id = node.id

            asset_node_ids.append(node_id)

        # Generate routes
        if optimize:
            # Use minimum spanning tree approach
            success = self._generate_optimized_network(asset_node_ids)
        else:
            # Direct routes from entrance to each asset
            success = self._generate_direct_network(asset_node_ids)

        if not success:
            return False

        # Generate intersections
        self._generate_intersections()

        return True

    def _ensure_entrance_node(self) -> str:
        """
        Ensure entrance node exists in navigation graph.

        Returns:
            Entrance node ID
        """
        # Check if entrance node already exists
        for node in self.navigation_graph.nodes.values():
            if node.is_entrance:
                return node.id

        # Add entrance node
        node = self.navigation_graph.add_strategic_node(
            position=self.entrance_position, is_entrance=True, node_id="entrance"
        )
        return node.id

    def _generate_direct_network(self, asset_node_ids: List[str]) -> bool:
        """
        Generate direct routes from entrance to each asset.

        Args:
            asset_node_ids: List of asset node IDs

        Returns:
            True if all routes found
        """
        success = True

        for asset_id in asset_node_ids:
            path = self.pathfinder.find_path(self.entrance_node, asset_id)

            if path is None:
                success = False
                continue

            # Create road segment from path
            self._create_segment_from_path(path, RoadType.ACCESS)

        return success

    def _generate_optimized_network(self, asset_node_ids: List[str]) -> bool:
        """
        Generate optimized network using minimum spanning tree.

        Args:
            asset_node_ids: List of asset node IDs

        Returns:
            True if network generated
        """
        # Build complete graph of paths
        all_nodes = [self.entrance_node] + asset_node_ids
        path_graph = nx.Graph()

        # Find paths between all pairs
        for i, node1 in enumerate(all_nodes):
            for node2 in all_nodes[i + 1 :]:
                path = self.pathfinder.find_path(node1, node2)
                if path:
                    # Add edge with path length as weight
                    path_graph.add_edge(node1, node2, weight=path.total_length, path=path)

        # Check if graph is connected
        if not nx.is_connected(path_graph):
            return False

        # Find minimum spanning tree
        mst = nx.minimum_spanning_tree(path_graph)

        # Create road segments from MST edges
        for edge in mst.edges(data=True):
            node1, node2, data = edge
            path = data["path"]

            # Classify road type based on proximity to entrance
            road_type = self._classify_road_type(node1, node2, asset_node_ids)

            # Create segment
            self._create_segment_from_path(path, road_type)

        return True

    def _classify_road_type(
        self, node1: str, node2: str, asset_node_ids: List[str]
    ) -> RoadType:
        """
        Classify road type based on network position.

        Args:
            node1: First node ID
            node2: Second node ID
            asset_node_ids: List of asset node IDs

        Returns:
            RoadType classification
        """
        # Primary roads connect to entrance
        if node1 == self.entrance_node or node2 == self.entrance_node:
            return RoadType.PRIMARY

        # Count downstream connections
        # For simplicity, use asset count heuristic
        # More downstream assets = higher classification
        if len(asset_node_ids) > 5:
            return RoadType.SECONDARY
        else:
            return RoadType.ACCESS

    def _create_segment_from_path(self, path: Path, road_type: RoadType) -> RoadSegment:
        """
        Create road segment from path.

        Args:
            path: Path object
            road_type: Road classification

        Returns:
            RoadSegment object
        """
        # Generate segment ID
        segment_id = f"road_{self._segment_counter}"
        self._segment_counter += 1

        # Get centerline
        centerline = path.get_geometry()

        # Determine width based on road type
        width_m = self._get_road_width(road_type)

        # Calculate cut/fill
        cut_fill_volume = self._estimate_cut_fill(path, width_m)

        # Create segment
        segment = RoadSegment(
            id=segment_id,
            road_type=road_type,
            centerline=centerline,
            width_m=width_m,
            length_m=path.total_length,
            start_node_id=path.nodes[0].id,
            end_node_id=path.nodes[-1].id,
            cut_fill_volume=cut_fill_volume,
            avg_grade=path.avg_grade,
            max_grade=path.max_grade,
        )

        self.segments[segment_id] = segment
        return segment

    def _get_road_width(self, road_type: RoadType) -> float:
        """
        Get standard road width for road type.

        Args:
            road_type: Road classification

        Returns:
            Width in meters
        """
        widths = {
            RoadType.PRIMARY: 7.3,  # 24 feet
            RoadType.SECONDARY: 5.5,  # 18 feet
            RoadType.ACCESS: 3.7,  # 12 feet
        }
        return widths[road_type]

    def _estimate_cut_fill(self, path: Path, road_width: float) -> float:
        """
        Estimate cut/fill volume for road segment.

        Args:
            path: Path object
            road_width: Road width in meters

        Returns:
            Estimated volume in cubic meters
        """
        total_volume = 0.0

        for i in range(len(path.nodes) - 1):
            node1 = path.nodes[i]
            node2 = path.nodes[i + 1]

            # Calculate segment length
            x1, y1 = node1.position
            x2, y2 = node2.position
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

            # Average elevation change
            avg_cut_depth = abs(node2.elevation - node1.elevation) / 2.0

            # Volume = length × width × depth
            segment_volume = length * road_width * avg_cut_depth
            total_volume += segment_volume

        return total_volume

    def _generate_intersections(self) -> None:
        """Generate intersection geometry for road junctions."""
        # Build map of nodes to segments
        node_segments: Dict[str, List[str]] = {}

        for segment_id, segment in self.segments.items():
            # Add to start node
            if segment.start_node_id not in node_segments:
                node_segments[segment.start_node_id] = []
            node_segments[segment.start_node_id].append(segment_id)

            # Add to end node
            if segment.end_node_id not in node_segments:
                node_segments[segment.end_node_id] = []
            node_segments[segment.end_node_id].append(segment_id)

        # Create intersections where 3+ segments meet
        for node_id, segment_ids in node_segments.items():
            if len(segment_ids) >= 3:
                node = self.navigation_graph.nodes[node_id]
                intersection = self._create_intersection(node_id, node.position, segment_ids)
                self.intersections[intersection.id] = intersection

    def _create_intersection(
        self, node_id: str, position: Tuple[float, float], segment_ids: List[str]
    ) -> RoadIntersection:
        """
        Create intersection geometry.

        Args:
            node_id: Node ID at intersection
            position: (x, y) coordinates
            segment_ids: List of connecting segment IDs

        Returns:
            RoadIntersection object
        """
        intersection_id = f"intersection_{self._intersection_counter}"
        self._intersection_counter += 1

        # Determine intersection type
        num_connections = len(segment_ids)
        if num_connections == 3:
            intersection_type = "T-junction"
        elif num_connections == 4:
            intersection_type = "cross"
        else:
            intersection_type = f"{num_connections}-way"

        # Create intersection geometry (circular for simplicity)
        # Use maximum road width of connecting segments
        max_width = max(self.segments[sid].width_m for sid in segment_ids)
        radius = max_width * 1.5  # 1.5x for turning radius

        # Create circular geometry
        center = ShapelyPoint(position)
        geometry = center.buffer(radius)

        return RoadIntersection(
            id=intersection_id,
            position=position,
            connecting_segments=segment_ids,
            intersection_type=intersection_type,
            geometry=geometry,
        )

    def get_total_length(self) -> float:
        """
        Get total road network length.

        Returns:
            Total length in meters
        """
        return sum(segment.length_m for segment in self.segments.values())

    def get_total_area(self) -> float:
        """
        Get total road surface area.

        Returns:
            Total area in square meters
        """
        total_area = 0.0

        for segment in self.segments.values():
            total_area += segment.length_m * segment.width_m

        return total_area

    def get_total_cut_fill(self) -> float:
        """
        Get total estimated cut/fill volume.

        Returns:
            Total volume in cubic meters
        """
        return sum(segment.cut_fill_volume for segment in self.segments.values())

    def get_network_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive network statistics.

        Returns:
            Dictionary with network statistics
        """
        segments_by_type = {
            RoadType.PRIMARY: [],
            RoadType.SECONDARY: [],
            RoadType.ACCESS: [],
        }

        for segment in self.segments.values():
            segments_by_type[segment.road_type].append(segment)

        return {
            "total_segments": len(self.segments),
            "total_length_m": self.get_total_length(),
            "total_area_sqm": self.get_total_area(),
            "total_cut_fill_m3": self.get_total_cut_fill(),
            "num_intersections": len(self.intersections),
            "primary_roads": {
                "count": len(segments_by_type[RoadType.PRIMARY]),
                "total_length_m": sum(s.length_m for s in segments_by_type[RoadType.PRIMARY]),
            },
            "secondary_roads": {
                "count": len(segments_by_type[RoadType.SECONDARY]),
                "total_length_m": sum(s.length_m for s in segments_by_type[RoadType.SECONDARY]),
            },
            "access_roads": {
                "count": len(segments_by_type[RoadType.ACCESS]),
                "total_length_m": sum(s.length_m for s in segments_by_type[RoadType.ACCESS]),
            },
            "max_grade_pct": max((s.max_grade for s in self.segments.values()), default=0.0),
            "avg_grade_pct": np.mean([s.avg_grade for s in self.segments.values()])
            if self.segments
            else 0.0,
        }

    def export_to_geojson(self) -> Dict[str, Any]:
        """
        Export road network to GeoJSON format.

        Returns:
            GeoJSON FeatureCollection
        """
        features = []

        # Export segments
        for segment in self.segments.values():
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": list(segment.centerline.coords),
                    },
                    "properties": {
                        **segment.to_dict(),
                        "feature_type": "road_segment",
                    },
                }
            )

        # Export intersections
        for intersection in self.intersections.values():
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [intersection.position[0], intersection.position[1]],
                    },
                    "properties": {
                        **intersection.to_dict(),
                        "feature_type": "intersection",
                    },
                }
            )

        return {"type": "FeatureCollection", "features": features}

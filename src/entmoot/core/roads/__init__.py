"""
Road network generation for site layout planning.

This module provides terrain-aware road network generation, including:
- Navigation graph creation from terrain data
- A* pathfinding with grade constraints
- Road network optimization and geometry generation
"""

from entmoot.core.roads.graph import NavigationGraph, GraphNode
from entmoot.core.roads.pathfinding import AStarPathfinder, Path, PathfinderConfig
from entmoot.core.roads.network import (
    RoadNetwork,
    RoadSegment,
    RoadType,
    RoadIntersection,
)

__all__ = [
    "NavigationGraph",
    "GraphNode",
    "AStarPathfinder",
    "Path",
    "PathfinderConfig",
    "RoadNetwork",
    "RoadSegment",
    "RoadType",
    "RoadIntersection",
]

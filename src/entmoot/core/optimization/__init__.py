"""
Optimization module for AI-driven asset placement.

This module provides genetic algorithm-based optimization for placing
assets on a property while respecting constraints and optimizing objectives.
"""

from entmoot.core.optimization.problem import (
    ObjectiveWeights,
    OptimizationConstraints,
    OptimizationObjective,
    PlacementSolution,
)

__all__ = [
    "OptimizationObjective",
    "ObjectiveWeights",
    "OptimizationConstraints",
    "PlacementSolution",
]

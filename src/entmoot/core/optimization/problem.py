"""
Optimization problem definition for asset placement.

This module defines the optimization objectives, constraints, and solution
representation for the asset placement problem.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon, LineString
from shapely.ops import unary_union

from entmoot.models.assets import Asset
from entmoot.models.constraints import Constraint


class ObjectiveType(str, Enum):
    """Types of optimization objectives."""

    MINIMIZE_CUT_FILL = "minimize_cut_fill"
    MAXIMIZE_ACCESSIBILITY = "maximize_accessibility"
    MINIMIZE_ROAD_LENGTH = "minimize_road_length"
    MAXIMIZE_COMPACTNESS = "maximize_compactness"
    MINIMIZE_SLOPE_VARIANCE = "minimize_slope_variance"


@dataclass
class ObjectiveWeights:
    """
    Configurable weights for multi-objective optimization.

    Weights should sum to 1.0 for normalized scoring.

    Attributes:
        cut_fill_weight: Weight for cut/fill minimization (0-1)
        accessibility_weight: Weight for accessibility maximization (0-1)
        road_length_weight: Weight for road length minimization (0-1)
        compactness_weight: Weight for layout compactness (0-1)
        slope_variance_weight: Weight for slope variance minimization (0-1)
    """

    cut_fill_weight: float = 0.3
    accessibility_weight: float = 0.25
    road_length_weight: float = 0.25
    compactness_weight: float = 0.1
    slope_variance_weight: float = 0.1

    def __post_init__(self) -> None:
        """Validate weights."""
        total = (
            self.cut_fill_weight
            + self.accessibility_weight
            + self.road_length_weight
            + self.compactness_weight
            + self.slope_variance_weight
        )
        if not (0.99 <= total <= 1.01):  # Allow small floating point error
            raise ValueError(f"Objective weights must sum to 1.0, got {total}")

        # Check all weights are non-negative
        if any(
            w < 0
            for w in [
                self.cut_fill_weight,
                self.accessibility_weight,
                self.road_length_weight,
                self.compactness_weight,
                self.slope_variance_weight,
            ]
        ):
            raise ValueError("All weights must be non-negative")


@dataclass
class OptimizationConstraints:
    """
    Constraints for asset placement optimization.

    Attributes:
        site_boundary: Property boundary polygon
        buildable_zones: List of buildable area polygons
        exclusion_zones: List of exclusion zone polygons
        regulatory_constraints: List of regulatory constraints
        min_setback_m: Global minimum setback from property line
        min_asset_spacing_m: Global minimum spacing between assets
        max_site_coverage_percent: Maximum percentage of site that can be covered
        require_road_access: Whether all assets must have road access
        max_total_road_length_m: Maximum total road length allowed
    """

    site_boundary: ShapelyPolygon
    buildable_zones: List[ShapelyPolygon] = field(default_factory=list)
    exclusion_zones: List[ShapelyPolygon] = field(default_factory=list)
    regulatory_constraints: List[Constraint] = field(default_factory=list)
    min_setback_m: float = 7.62  # 25 feet
    min_asset_spacing_m: float = 3.0  # 10 feet
    max_site_coverage_percent: float = 40.0
    require_road_access: bool = True
    max_total_road_length_m: float = 1000.0

    def __post_init__(self) -> None:
        """Validate constraints."""
        if not self.site_boundary.is_valid:
            raise ValueError("Site boundary must be a valid polygon")

        if self.min_setback_m < 0:
            raise ValueError("Minimum setback must be non-negative")

        if not (0 < self.max_site_coverage_percent <= 100):
            raise ValueError("Max site coverage must be between 0 and 100%")

    def get_buildable_area(self) -> ShapelyPolygon:
        """
        Get the effective buildable area after applying constraints.

        Returns:
            Shapely Polygon of buildable area
        """
        # Start with site boundary
        buildable = self.site_boundary

        # Apply setback
        if self.min_setback_m > 0:
            buildable = buildable.buffer(-self.min_setback_m)
            if buildable.is_empty:
                return ShapelyPolygon()

        # Intersect with buildable zones if specified
        if self.buildable_zones:
            buildable_union = unary_union(self.buildable_zones)
            buildable = buildable.intersection(buildable_union)

        # Subtract exclusion zones
        if self.exclusion_zones:
            exclusion_union = unary_union(self.exclusion_zones)
            buildable = buildable.difference(exclusion_union)

        # Subtract regulatory constraints
        for constraint in self.regulatory_constraints:
            constraint_geom = constraint.get_geometry()
            buildable = buildable.difference(constraint_geom)

        return buildable if isinstance(buildable, ShapelyPolygon) else ShapelyPolygon()

    def is_position_valid(self, asset: Asset, position: Tuple[float, float]) -> bool:
        """
        Check if an asset position satisfies constraints.

        Args:
            asset: Asset to check
            position: (x, y) position to test

        Returns:
            True if position is valid
        """
        # Temporarily set position
        original_pos = asset.position
        asset.set_position(position[0], position[1])

        try:
            asset_geom = asset.get_geometry()

            # Check if within site boundary
            if not self.site_boundary.contains(asset_geom):
                return False

            # Check setback
            setback_geom = asset.get_setback_geometry()
            if not self.site_boundary.contains(setback_geom):
                return False

            # Check if in buildable zones
            if self.buildable_zones:
                in_buildable = any(zone.contains(asset_geom) for zone in self.buildable_zones)
                if not in_buildable:
                    return False

            # Check exclusion zones
            for exclusion in self.exclusion_zones:
                if asset_geom.intersects(exclusion):
                    return False

            # Check regulatory constraints
            for constraint in self.regulatory_constraints:
                if asset_geom.intersects(constraint.get_geometry()):
                    return False

            return True

        finally:
            # Restore original position
            asset.set_position(original_pos[0], original_pos[1])


@dataclass
class PlacementSolution:
    """
    Represents a solution to the asset placement problem.

    Attributes:
        assets: List of assets with their positions
        fitness: Overall fitness score (higher = better)
        objectives: Individual objective scores
        constraint_violations: Number of constraint violations
        is_valid: Whether solution satisfies all hard constraints
        metadata: Additional solution metadata
    """

    assets: List[Asset]
    fitness: float = 0.0
    objectives: Dict[str, float] = field(default_factory=dict)
    constraint_violations: int = 0
    is_valid: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "PlacementSolution":
        """
        Create a deep copy of the solution.

        Returns:
            New PlacementSolution instance
        """
        # Copy assets (Pydantic models are immutable, so model_copy is safe)
        assets_copy = [asset.model_copy(deep=True) for asset in self.assets]

        return PlacementSolution(
            assets=assets_copy,
            fitness=self.fitness,
            objectives=self.objectives.copy(),
            constraint_violations=self.constraint_violations,
            is_valid=self.is_valid,
            metadata=self.metadata.copy(),
        )

    def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        """
        Get an asset by ID.

        Args:
            asset_id: Asset ID to find

        Returns:
            Asset if found, None otherwise
        """
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        return None

    def get_total_area_sqm(self) -> float:
        """
        Get total area covered by all assets.

        Returns:
            Total area in square meters
        """
        return sum(asset.area_sqm for asset in self.assets)

    def get_coverage_percent(self, site_area_sqm: float) -> float:
        """
        Get percentage of site covered by assets.

        Args:
            site_area_sqm: Total site area

        Returns:
            Coverage percentage
        """
        if site_area_sqm <= 0:
            return 0.0
        return (self.get_total_area_sqm() / site_area_sqm) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert solution to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "fitness": float(self.fitness),
            "objectives": {k: float(v) for k, v in self.objectives.items()},
            "constraint_violations": int(self.constraint_violations),
            "is_valid": bool(self.is_valid),
            "total_area_sqm": float(self.get_total_area_sqm()),
            "num_assets": len(self.assets),
            "assets": [
                {
                    "id": asset.id,
                    "name": asset.name,
                    "type": asset.asset_type.value,
                    "position": asset.position,
                    "rotation": asset.rotation,
                    "area_sqm": asset.area_sqm,
                }
                for asset in self.assets
            ],
            "metadata": self.metadata,
        }


class OptimizationObjective:
    """
    Multi-objective optimization evaluator for asset placement.

    This class evaluates solutions against multiple objectives and combines
    them into a single fitness score using configurable weights.
    """

    def __init__(
        self,
        constraints: OptimizationConstraints,
        weights: Optional[ObjectiveWeights] = None,
        elevation_data: Optional[NDArray[np.floating[Any]]] = None,
        slope_data: Optional[NDArray[np.floating[Any]]] = None,
        transform: Optional[Any] = None,
        road_entry_point: Optional[Tuple[float, float]] = None,
    ):
        """
        Initialize optimization objectives.

        Args:
            constraints: Optimization constraints
            weights: Objective weights (uses defaults if not provided)
            elevation_data: DEM elevation data
            slope_data: Slope percentage data
            transform: Rasterio affine transform
            road_entry_point: (x, y) point where road enters site
        """
        self.constraints = constraints
        self.weights = weights or ObjectiveWeights()
        self.elevation_data = elevation_data
        self.slope_data = slope_data
        self.transform = transform
        self.road_entry_point = road_entry_point or (0.0, 0.0)

    def evaluate(self, solution: PlacementSolution) -> float:
        """
        Evaluate a solution and compute fitness score.

        Args:
            solution: Solution to evaluate

        Returns:
            Fitness score (higher = better)
        """
        # Check constraint violations
        violations = self._count_constraint_violations(solution)
        solution.constraint_violations = violations

        # If solution has violations, penalize VERY heavily
        # Use exponential penalty to strongly discourage violations
        if violations > 0:
            solution.is_valid = False
            # Exponential penalty: much worse for multiple violations
            solution.fitness = -10000.0 * (violations ** 1.5)
            return solution.fitness

        solution.is_valid = True

        # Evaluate individual objectives
        objectives = {}

        # 1. Cut/Fill minimization (0-100, higher = better)
        if self.elevation_data is not None and self.weights.cut_fill_weight > 0:
            objectives["cut_fill"] = self._evaluate_cut_fill(solution)

        # 2. Accessibility maximization (0-100, higher = better)
        if self.weights.accessibility_weight > 0:
            objectives["accessibility"] = self._evaluate_accessibility(solution)

        # 3. Road length minimization (0-100, higher = better)
        if self.weights.road_length_weight > 0:
            objectives["road_length"] = self._evaluate_road_length(solution)

        # 4. Compactness maximization (0-100, higher = better)
        if self.weights.compactness_weight > 0:
            objectives["compactness"] = self._evaluate_compactness(solution)

        # 5. Slope variance minimization (0-100, higher = better)
        if self.slope_data is not None and self.weights.slope_variance_weight > 0:
            objectives["slope_variance"] = self._evaluate_slope_variance(solution)

        solution.objectives = objectives

        # Compute weighted fitness
        fitness = (
            objectives.get("cut_fill", 0.0) * self.weights.cut_fill_weight
            + objectives.get("accessibility", 0.0) * self.weights.accessibility_weight
            + objectives.get("road_length", 0.0) * self.weights.road_length_weight
            + objectives.get("compactness", 0.0) * self.weights.compactness_weight
            + objectives.get("slope_variance", 0.0) * self.weights.slope_variance_weight
        )

        solution.fitness = fitness
        return fitness

    def _count_constraint_violations(self, solution: PlacementSolution) -> int:
        """Count constraint violations in a solution."""
        violations = 0

        # Check asset overlaps
        for i, asset1 in enumerate(solution.assets):
            geom1 = asset1.get_geometry()

            # Check if asset is within site boundary
            if not self.constraints.site_boundary.contains(geom1):
                violations += 1

            # Check against other assets
            for j, asset2 in enumerate(solution.assets[i + 1 :], start=i + 1):
                geom2 = asset2.get_geometry()

                # Check overlap
                if geom1.intersects(geom2):
                    violations += 1

                # Check spacing
                spacing1 = asset1.get_spacing_geometry()
                if spacing1.intersects(geom2):
                    violations += 1

            # Check exclusion zones
            for exclusion in self.constraints.exclusion_zones:
                if geom1.intersects(exclusion):
                    violations += 1

        # Check site coverage
        site_area = self.constraints.site_boundary.area
        coverage_pct = solution.get_coverage_percent(site_area)
        if coverage_pct > self.constraints.max_site_coverage_percent:
            violations += 1

        return violations

    def _evaluate_cut_fill(self, solution: PlacementSolution) -> float:
        """
        Evaluate cut/fill objective (minimize earthwork).

        Returns:
            Score 0-100 (higher = better, less cut/fill needed)
        """
        if self.elevation_data is None:
            return 50.0  # Neutral score if no elevation data

        total_variance = 0.0
        for asset in solution.assets:
            # Get elevation at asset location
            x, y = asset.position
            # Sample elevation (simplified - would need proper raster sampling)
            # For now, use a heuristic based on position variance
            total_variance += abs(x % 100) + abs(y % 100)

        # Normalize to 0-100 (lower variance = higher score)
        max_variance = len(solution.assets) * 200
        score = 100.0 * (1.0 - min(total_variance / max_variance, 1.0)) if max_variance > 0 else 100.0
        return score

    def _evaluate_accessibility(self, solution: PlacementSolution) -> float:
        """
        Evaluate accessibility (maximize access to assets).

        Returns:
            Score 0-100 (higher = better accessibility)
        """
        if not solution.assets:
            return 0.0

        # Calculate average distance from centroid
        centroid = self.constraints.site_boundary.centroid
        total_distance = 0.0

        for asset in solution.assets:
            asset_point = ShapelyPoint(asset.position)
            distance = asset_point.distance(centroid)
            total_distance += distance

        avg_distance = total_distance / len(solution.assets)

        # Normalize: closer to center = higher score
        # Assume typical site radius ~200m
        typical_radius = 200.0
        score = 100.0 * (1.0 - min(avg_distance / typical_radius, 1.0))
        return max(score, 0.0)

    def _evaluate_road_length(self, solution: PlacementSolution) -> float:
        """
        Evaluate road length (minimize total road length needed).

        Returns:
            Score 0-100 (higher = better, shorter roads)
        """
        if not solution.assets:
            return 100.0

        # Calculate total road length needed (simplified MST approach)
        # Connect all assets to road entry point
        total_length = 0.0
        entry = ShapelyPoint(self.road_entry_point)

        for asset in solution.assets:
            asset_point = ShapelyPoint(asset.position)
            distance = asset_point.distance(entry)
            total_length += distance

        # Normalize to 0-100
        max_allowed = self.constraints.max_total_road_length_m
        score = 100.0 * (1.0 - min(total_length / max_allowed, 1.0)) if max_allowed > 0 else 100.0
        return max(score, 0.0)

    def _evaluate_compactness(self, solution: PlacementSolution) -> float:
        """
        Evaluate compactness (maximize layout compactness).

        Returns:
            Score 0-100 (higher = better, more compact)
        """
        if len(solution.assets) < 2:
            return 100.0

        # Calculate bounding box of all assets
        all_points = []
        for asset in solution.assets:
            geom = asset.get_geometry()
            all_points.extend(geom.exterior.coords)

        if not all_points:
            return 0.0

        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]

        bbox_width = max(xs) - min(xs)
        bbox_height = max(ys) - min(ys)
        bbox_area = bbox_width * bbox_height

        if bbox_area == 0:
            return 100.0

        # Calculate actual coverage area
        actual_area = solution.get_total_area_sqm()

        # Compactness ratio (higher = more compact)
        compactness_ratio = actual_area / bbox_area if bbox_area > 0 else 0.0
        score = compactness_ratio * 100.0
        return min(score, 100.0)

    def _evaluate_slope_variance(self, solution: PlacementSolution) -> float:
        """
        Evaluate slope variance (minimize variance in slopes at asset locations).

        Returns:
            Score 0-100 (higher = better, less variance)
        """
        if self.slope_data is None or not solution.assets:
            return 50.0  # Neutral score

        # Simplified: would need proper raster sampling
        # For now, use heuristic based on position clustering
        positions = [asset.position for asset in solution.assets]
        if len(positions) < 2:
            return 100.0

        # Calculate variance in positions as proxy for slope variance
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]

        variance = np.var(xs) + np.var(ys)

        # Normalize: lower variance = higher score
        max_variance = 10000.0  # Typical
        score = 100.0 * (1.0 - min(variance / max_variance, 1.0))
        return max(score, 0.0)

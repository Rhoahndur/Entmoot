"""
Constraint collection and spatial indexing.

This module provides the ConstraintCollection class for managing multiple constraints
with spatial indexing for efficient queries.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from pydantic import BaseModel, Field
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree
from shapely import wkt

from entmoot.models.constraints import (
    Constraint,
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
)


class ConstraintStatistics(BaseModel):
    """
    Statistics about a constraint collection.

    Attributes:
        total_constraints: Total number of constraints
        by_type: Count by constraint type
        by_severity: Count by severity
        by_priority: Count by priority
        total_constrained_area_sqm: Total constrained area
        total_constrained_area_acres: Total constrained area in acres
        constraint_coverage_percent: Percentage of site covered by constraints
        overlapping_constraints: Number of overlapping constraint pairs
        blocking_constraints: Number of blocking constraints
    """

    total_constraints: int = Field(default=0, description="Total constraint count")
    by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by type"
    )
    by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by severity"
    )
    by_priority: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by priority"
    )
    total_constrained_area_sqm: float = Field(
        default=0.0,
        description="Total area under constraint (union)"
    )
    total_constrained_area_acres: float = Field(
        default=0.0,
        description="Total area under constraint in acres"
    )
    constraint_coverage_percent: float = Field(
        default=0.0,
        description="Percentage of site covered",
        ge=0,
        le=100
    )
    overlapping_constraints: int = Field(
        default=0,
        description="Number of overlapping constraint pairs"
    )
    blocking_constraints: int = Field(
        default=0,
        description="Number of blocking constraints"
    )


class ConstraintCollection:
    """
    Collection of constraints with spatial indexing and query capabilities.

    Provides efficient spatial queries using R-tree indexing and supports
    various operations on constraint collections.
    """

    def __init__(self, site_boundary_wkt: Optional[str] = None):
        """
        Initialize constraint collection.

        Args:
            site_boundary_wkt: WKT of site boundary for coverage calculations
        """
        self._constraints: Dict[str, Constraint] = {}
        self._spatial_index: Optional[STRtree] = None
        self._index_dirty: bool = False
        self._site_boundary_wkt = site_boundary_wkt

    def add_constraint(self, constraint: Constraint) -> None:
        """
        Add a constraint to the collection.

        Args:
            constraint: Constraint to add

        Raises:
            ValueError: If constraint with same ID already exists
        """
        if constraint.id in self._constraints:
            raise ValueError(f"Constraint with ID '{constraint.id}' already exists")

        self._constraints[constraint.id] = constraint
        self._index_dirty = True

    def add_constraints(self, constraints: List[Constraint]) -> None:
        """
        Add multiple constraints to the collection.

        Args:
            constraints: List of constraints to add
        """
        for constraint in constraints:
            self.add_constraint(constraint)

    def remove_constraint(self, constraint_id: str) -> Optional[Constraint]:
        """
        Remove a constraint from the collection.

        Args:
            constraint_id: ID of constraint to remove

        Returns:
            Removed constraint, or None if not found
        """
        constraint = self._constraints.pop(constraint_id, None)
        if constraint:
            self._index_dirty = True
        return constraint

    def get_constraint(self, constraint_id: str) -> Optional[Constraint]:
        """
        Get a constraint by ID.

        Args:
            constraint_id: ID of constraint to retrieve

        Returns:
            Constraint if found, None otherwise
        """
        return self._constraints.get(constraint_id)

    def get_all_constraints(self) -> List[Constraint]:
        """Get all constraints in the collection."""
        return list(self._constraints.values())

    def count(self) -> int:
        """Get total number of constraints."""
        return len(self._constraints)

    def clear(self) -> None:
        """Remove all constraints from the collection."""
        self._constraints.clear()
        self._spatial_index = None
        self._index_dirty = False

    def _rebuild_spatial_index(self) -> None:
        """Rebuild the spatial index from current constraints."""
        if not self._constraints:
            self._spatial_index = None
            self._index_dirty = False
            return

        geometries = []
        for constraint in self._constraints.values():
            try:
                geom = constraint.get_geometry()
                geometries.append(geom)
            except Exception:
                # Skip constraints with invalid geometries
                continue

        if geometries:
            self._spatial_index = STRtree(geometries)
        else:
            self._spatial_index = None

        self._index_dirty = False

    def query_by_location(
        self,
        geometry: BaseGeometry,
        predicate: str = "intersects"
    ) -> List[Constraint]:
        """
        Query constraints by spatial relationship to a geometry.

        Args:
            geometry: Query geometry
            predicate: Spatial predicate (intersects, contains, within)

        Returns:
            List of constraints matching the spatial query
        """
        if self._index_dirty or self._spatial_index is None:
            self._rebuild_spatial_index()

        if not self._spatial_index:
            return []

        # Use spatial index to find candidates
        indices = self._spatial_index.query(geometry, predicate=predicate)

        # Map back to constraints
        geometries_list = list(self._spatial_index.geometries)
        matching_constraints = []

        for idx in indices:
            candidate_geom = geometries_list[idx]
            # Find constraint with matching geometry
            for constraint in self._constraints.values():
                try:
                    if constraint.get_geometry().equals(candidate_geom):
                        matching_constraints.append(constraint)
                        break
                except Exception:
                    continue

        return matching_constraints

    def query_by_point(self, point: ShapelyPoint) -> List[Constraint]:
        """
        Query constraints that contain a point.

        Args:
            point: Query point

        Returns:
            List of constraints containing the point
        """
        # Use intersects first to get candidates, then filter for contains
        candidates = self.query_by_location(point, predicate="intersects")
        return [c for c in candidates if c.contains(point)]

    def query_by_type(
        self,
        constraint_types: List[ConstraintType]
    ) -> List[Constraint]:
        """
        Query constraints by type.

        Args:
            constraint_types: List of constraint types to match

        Returns:
            List of constraints matching any of the types
        """
        type_set = set(constraint_types)
        return [
            c for c in self._constraints.values()
            if c.constraint_type in type_set
        ]

    def query_by_severity(
        self,
        severities: List[ConstraintSeverity]
    ) -> List[Constraint]:
        """
        Query constraints by severity.

        Args:
            severities: List of severities to match

        Returns:
            List of constraints matching any of the severities
        """
        severity_set = set(severities)
        return [
            c for c in self._constraints.values()
            if c.severity in severity_set
        ]

    def query_by_priority(
        self,
        priorities: List[ConstraintPriority]
    ) -> List[Constraint]:
        """
        Query constraints by priority.

        Args:
            priorities: List of priorities to match

        Returns:
            List of constraints matching any of the priorities
        """
        priority_set = set(priorities)
        return [
            c for c in self._constraints.values()
            if c.priority in priority_set
        ]

    def get_blocking_constraints(self) -> List[Constraint]:
        """Get all blocking severity constraints."""
        return self.query_by_severity([ConstraintSeverity.BLOCKING])

    def get_critical_constraints(self) -> List[Constraint]:
        """Get all critical priority constraints."""
        return self.query_by_priority([ConstraintPriority.CRITICAL])

    def find_overlapping_constraints(
        self,
        constraint_id: Optional[str] = None
    ) -> List[Tuple[Constraint, Constraint]]:
        """
        Find pairs of overlapping constraints.

        Args:
            constraint_id: If provided, only find overlaps with this constraint

        Returns:
            List of tuples of overlapping constraint pairs
        """
        overlaps = []

        if constraint_id:
            # Find overlaps with specific constraint
            constraint = self.get_constraint(constraint_id)
            if not constraint:
                return []

            geom = constraint.get_geometry()
            candidates = self.query_by_location(geom, predicate="intersects")

            for candidate in candidates:
                if candidate.id != constraint_id:
                    overlaps.append((constraint, candidate))
        else:
            # Find all overlaps
            constraints = list(self._constraints.values())
            for i, c1 in enumerate(constraints):
                geom1 = c1.get_geometry()
                for c2 in constraints[i + 1:]:
                    geom2 = c2.get_geometry()
                    if geom1.intersects(geom2):
                        overlaps.append((c1, c2))

        return overlaps

    def calculate_statistics(self) -> ConstraintStatistics:
        """
        Calculate statistics about the constraint collection.

        Returns:
            ConstraintStatistics object
        """
        stats = ConstraintStatistics()
        stats.total_constraints = len(self._constraints)

        # Count by type
        type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        blocking_count = 0

        for constraint in self._constraints.values():
            type_counts[constraint.constraint_type] += 1
            severity_counts[constraint.severity] += 1
            priority_counts[constraint.priority] += 1

            if constraint.severity == ConstraintSeverity.BLOCKING:
                blocking_count += 1

        stats.by_type = dict(type_counts)
        stats.by_severity = dict(severity_counts)
        stats.by_priority = dict(priority_counts)
        stats.blocking_constraints = blocking_count

        # Calculate total constrained area (union of all geometries)
        if self._constraints:
            from shapely.ops import unary_union

            geometries = []
            for constraint in self._constraints.values():
                try:
                    geometries.append(constraint.get_geometry())
                except Exception:
                    continue

            if geometries:
                union = unary_union(geometries)
                stats.total_constrained_area_sqm = union.area
                stats.total_constrained_area_acres = union.area * 0.000247105

                # Calculate coverage percentage if site boundary provided
                if self._site_boundary_wkt:
                    try:
                        site_geom = wkt.loads(self._site_boundary_wkt)
                        site_area = site_geom.area
                        if site_area > 0:
                            coverage = (union.area / site_area) * 100
                            stats.constraint_coverage_percent = min(coverage, 100.0)
                    except Exception:
                        pass

        # Count overlaps
        stats.overlapping_constraints = len(self.find_overlapping_constraints())

        return stats

    def get_unconstrained_area(self) -> Optional[BaseGeometry]:
        """
        Calculate the unconstrained area (site boundary minus constraints).

        Returns:
            Shapely geometry of unconstrained area, or None if no site boundary
        """
        if not self._site_boundary_wkt:
            return None

        try:
            from shapely.ops import unary_union

            site_geom = wkt.loads(self._site_boundary_wkt)

            # Get union of all blocking constraints
            blocking = self.get_blocking_constraints()
            if not blocking:
                return site_geom

            blocking_geoms = [c.get_geometry() for c in blocking]
            constrained_union = unary_union(blocking_geoms)

            # Subtract from site
            unconstrained = site_geom.difference(constrained_union)
            return unconstrained

        except Exception:
            return None

    def validate_all(self) -> Dict[str, List[str]]:
        """
        Validate all constraints in the collection.

        Returns:
            Dictionary mapping constraint ID to list of validation errors
        """
        validation_results = {}

        for constraint_id, constraint in self._constraints.items():
            is_valid, errors = constraint.validate_constraint()
            if not is_valid:
                validation_results[constraint_id] = errors

        return validation_results

    def resolve_conflicts(
        self,
        point: ShapelyPoint
    ) -> Optional[Constraint]:
        """
        Resolve conflicts when multiple constraints apply to a point.

        Uses priority system to determine which constraint takes precedence.

        Args:
            point: Point to check

        Returns:
            Highest priority constraint at that point, or None
        """
        constraints_at_point = self.query_by_point(point)

        if not constraints_at_point:
            return None

        # Priority order: CRITICAL > HIGH > MEDIUM > LOW
        priority_order = {
            ConstraintPriority.CRITICAL: 0,
            ConstraintPriority.HIGH: 1,
            ConstraintPriority.MEDIUM: 2,
            ConstraintPriority.LOW: 3,
        }

        # Sort by priority, then by severity
        severity_order = {
            ConstraintSeverity.BLOCKING: 0,
            ConstraintSeverity.WARNING: 1,
            ConstraintSeverity.PREFERENCE: 2,
        }

        constraints_at_point.sort(
            key=lambda c: (
                priority_order.get(c.priority, 999),
                severity_order.get(c.severity, 999)
            )
        )

        return constraints_at_point[0]

    def to_geojson(self) -> Dict[str, Any]:
        """
        Export all constraints as GeoJSON FeatureCollection.

        Returns:
            GeoJSON FeatureCollection dictionary
        """
        features = []

        for constraint in self._constraints.values():
            try:
                features.append(constraint.to_geojson())
            except Exception:
                # Skip constraints that can't be serialized
                continue

        return {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "total_constraints": len(features),
                "statistics": self.calculate_statistics().model_dump(),
            },
        }

    def export_summary(self) -> Dict[str, Any]:
        """
        Export summary information about the collection.

        Returns:
            Dictionary with collection summary
        """
        stats = self.calculate_statistics()

        return {
            "total_constraints": stats.total_constraints,
            "statistics": stats.model_dump(),
            "constraints": [
                {
                    "id": c.id,
                    "name": c.name,
                    "type": c.constraint_type,
                    "severity": c.severity,
                    "priority": c.priority,
                    "area_sqm": c.get_area_sqm(),
                    "area_acres": c.get_area_acres(),
                }
                for c in self._constraints.values()
            ],
        }

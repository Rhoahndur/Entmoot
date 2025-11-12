"""
Constraint aggregation engine.

This module provides functionality for combining and aggregating multiple constraints
into composite constraint maps and calculating aggregate statistics.
"""

from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely import wkt

from entmoot.models.constraints import (
    Constraint,
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
)


class AggregationMode(str, Enum):
    """Mode for aggregating constraints."""

    UNION = "union"  # Union of all constraint geometries
    INTERSECTION = "intersection"  # Intersection of all constraints
    MOST_RESTRICTIVE = "most_restrictive"  # Keep most restrictive at each point


class ConstraintAggregator:
    """Engine for aggregating multiple constraints."""

    @staticmethod
    def aggregate_geometries(
        constraints: List[Constraint],
        mode: AggregationMode = AggregationMode.UNION
    ) -> Optional[BaseGeometry]:
        """
        Aggregate constraint geometries.

        Args:
            constraints: List of constraints to aggregate
            mode: Aggregation mode

        Returns:
            Aggregated geometry, or None if no valid geometries
        """
        if not constraints:
            return None

        geometries = []
        for constraint in constraints:
            try:
                geometries.append(constraint.get_geometry())
            except Exception:
                continue

        if not geometries:
            return None

        if mode == AggregationMode.UNION:
            return unary_union(geometries)
        elif mode == AggregationMode.INTERSECTION:
            result = geometries[0]
            for geom in geometries[1:]:
                result = result.intersection(geom)
            return result
        else:  # MOST_RESTRICTIVE - for now same as union
            return unary_union(geometries)

    @staticmethod
    def create_composite_constraint_map(
        constraints: List[Constraint],
        filter_severity: Optional[List[ConstraintSeverity]] = None,
        filter_types: Optional[List[ConstraintType]] = None
    ) -> Optional[BaseGeometry]:
        """
        Create a composite constraint map from multiple constraints.

        Args:
            constraints: List of constraints
            filter_severity: Only include these severities (None = all)
            filter_types: Only include these types (None = all)

        Returns:
            Union geometry of all matching constraints
        """
        # Filter constraints
        filtered = constraints

        if filter_severity:
            severity_set = set(filter_severity)
            filtered = [c for c in filtered if c.severity in severity_set]

        if filter_types:
            type_set = set(filter_types)
            filtered = [c for c in filtered if c.constraint_type in type_set]

        # Aggregate
        return ConstraintAggregator.aggregate_geometries(
            filtered,
            mode=AggregationMode.UNION
        )

    @staticmethod
    def calculate_available_area(
        site_boundary: BaseGeometry,
        constraints: List[Constraint],
        only_blocking: bool = True
    ) -> Tuple[BaseGeometry, float, float]:
        """
        Calculate the available (unconstrained) area on a site.

        Args:
            site_boundary: Site boundary geometry
            constraints: List of constraints
            only_blocking: If True, only consider blocking constraints

        Returns:
            Tuple of (available_geometry, area_sqm, area_acres)
        """
        # Filter to blocking constraints if requested
        if only_blocking:
            constraints = [
                c for c in constraints
                if c.severity == ConstraintSeverity.BLOCKING
            ]

        if not constraints:
            area_sqm = site_boundary.area
            return (site_boundary, area_sqm, area_sqm * 0.000247105)

        # Create composite constraint map
        constrained_area = ConstraintAggregator.create_composite_constraint_map(
            constraints
        )

        if constrained_area is None or constrained_area.is_empty:
            area_sqm = site_boundary.area
            return (site_boundary, area_sqm, area_sqm * 0.000247105)

        # Calculate available area
        available = site_boundary.difference(constrained_area)
        area_sqm = available.area
        area_acres = area_sqm * 0.000247105

        return (available, area_sqm, area_acres)

    @staticmethod
    def calculate_constraint_coverage(
        site_boundary: BaseGeometry,
        constraints: List[Constraint],
        by_type: bool = False,
        by_severity: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate constraint coverage statistics.

        Args:
            site_boundary: Site boundary geometry
            constraints: List of constraints
            by_type: Include breakdown by constraint type
            by_severity: Include breakdown by severity

        Returns:
            Dictionary with coverage statistics
        """
        site_area = site_boundary.area

        stats = {
            "site_area_sqm": site_area,
            "site_area_acres": site_area * 0.000247105,
            "total_constraints": len(constraints),
        }

        # Calculate total constrained area
        all_constrained = ConstraintAggregator.create_composite_constraint_map(
            constraints
        )

        if all_constrained and not all_constrained.is_empty:
            constrained_area = all_constrained.intersection(site_boundary).area
            stats["constrained_area_sqm"] = constrained_area
            stats["constrained_area_acres"] = constrained_area * 0.000247105
            stats["coverage_percent"] = (constrained_area / site_area * 100) if site_area > 0 else 0
        else:
            stats["constrained_area_sqm"] = 0.0
            stats["constrained_area_acres"] = 0.0
            stats["coverage_percent"] = 0.0

        # Calculate available area
        available_geom, available_sqm, available_acres = (
            ConstraintAggregator.calculate_available_area(
                site_boundary, constraints, only_blocking=True
            )
        )

        stats["available_area_sqm"] = available_sqm
        stats["available_area_acres"] = available_acres
        stats["available_percent"] = (available_sqm / site_area * 100) if site_area > 0 else 0

        # Breakdown by type
        if by_type:
            type_coverage = {}
            constraint_types = set(c.constraint_type for c in constraints)

            for ctype in constraint_types:
                type_constraints = [c for c in constraints if c.constraint_type == ctype]
                type_geom = ConstraintAggregator.create_composite_constraint_map(
                    type_constraints
                )

                if type_geom and not type_geom.is_empty:
                    type_area = type_geom.intersection(site_boundary).area
                    type_coverage[ctype] = {
                        "area_sqm": type_area,
                        "area_acres": type_area * 0.000247105,
                        "coverage_percent": (type_area / site_area * 100) if site_area > 0 else 0,
                        "count": len(type_constraints),
                    }

            stats["by_type"] = type_coverage

        # Breakdown by severity
        if by_severity:
            severity_coverage = {}
            severities = set(c.severity for c in constraints)

            for severity in severities:
                severity_constraints = [c for c in constraints if c.severity == severity]
                severity_geom = ConstraintAggregator.create_composite_constraint_map(
                    severity_constraints
                )

                if severity_geom and not severity_geom.is_empty:
                    sev_area = severity_geom.intersection(site_boundary).area
                    severity_coverage[severity] = {
                        "area_sqm": sev_area,
                        "area_acres": sev_area * 0.000247105,
                        "coverage_percent": (sev_area / site_area * 100) if site_area > 0 else 0,
                        "count": len(severity_constraints),
                    }

            stats["by_severity"] = severity_coverage

        return stats

    @staticmethod
    def identify_overlapping_constraints(
        constraints: List[Constraint],
        min_overlap_sqm: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Identify pairs of overlapping constraints.

        Args:
            constraints: List of constraints to check
            min_overlap_sqm: Minimum overlap area to report (square meters)

        Returns:
            List of overlap reports
        """
        overlaps = []

        for i, c1 in enumerate(constraints):
            geom1 = c1.get_geometry()

            for c2 in constraints[i + 1:]:
                geom2 = c2.get_geometry()

                if geom1.intersects(geom2):
                    intersection = geom1.intersection(geom2)
                    overlap_area = intersection.area

                    if overlap_area >= min_overlap_sqm:
                        overlaps.append({
                            "constraint_1_id": c1.id,
                            "constraint_1_name": c1.name,
                            "constraint_1_type": c1.constraint_type,
                            "constraint_1_severity": c1.severity,
                            "constraint_2_id": c2.id,
                            "constraint_2_name": c2.name,
                            "constraint_2_type": c2.constraint_type,
                            "constraint_2_severity": c2.severity,
                            "overlap_area_sqm": overlap_area,
                            "overlap_area_acres": overlap_area * 0.000247105,
                            "overlap_geometry_wkt": intersection.wkt,
                        })

        return overlaps

    @staticmethod
    def generate_constraint_summary(
        site_boundary: BaseGeometry,
        constraints: List[Constraint]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of constraints.

        Args:
            site_boundary: Site boundary geometry
            constraints: List of constraints

        Returns:
            Comprehensive summary dictionary
        """
        summary = {
            "site": {
                "area_sqm": site_boundary.area,
                "area_acres": site_boundary.area * 0.000247105,
            },
            "constraints": {
                "total": len(constraints),
                "by_type": {},
                "by_severity": {},
                "by_priority": {},
            },
            "coverage": {},
            "overlaps": [],
        }

        # Count by type, severity, priority
        from collections import defaultdict

        type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        priority_counts = defaultdict(int)

        for c in constraints:
            type_counts[c.constraint_type] += 1
            severity_counts[c.severity] += 1
            priority_counts[c.priority] += 1

        summary["constraints"]["by_type"] = dict(type_counts)
        summary["constraints"]["by_severity"] = dict(severity_counts)
        summary["constraints"]["by_priority"] = dict(priority_counts)

        # Calculate coverage
        coverage = ConstraintAggregator.calculate_constraint_coverage(
            site_boundary,
            constraints,
            by_type=True,
            by_severity=True
        )
        summary["coverage"] = coverage

        # Find overlaps
        overlaps = ConstraintAggregator.identify_overlapping_constraints(
            constraints,
            min_overlap_sqm=1.0
        )
        summary["overlaps"] = {
            "count": len(overlaps),
            "details": overlaps[:10],  # Limit to first 10 for summary
        }

        return summary

    @staticmethod
    def export_constraint_layers(
        constraints: List[Constraint],
        by_type: bool = True,
        by_severity: bool = True
    ) -> Dict[str, Any]:
        """
        Export constraints organized into layers for visualization.

        Args:
            constraints: List of constraints
            by_type: Create layers by constraint type
            by_severity: Create layers by severity

        Returns:
            Dictionary with layer information
        """
        layers = {}

        if by_type:
            layers["by_type"] = {}
            constraint_types = set(c.constraint_type for c in constraints)

            for ctype in constraint_types:
                type_constraints = [c for c in constraints if c.constraint_type == ctype]
                type_geom = ConstraintAggregator.create_composite_constraint_map(
                    type_constraints
                )

                if type_geom and not type_geom.is_empty:
                    layers["by_type"][ctype] = {
                        "geometry_wkt": type_geom.wkt,
                        "constraint_ids": [c.id for c in type_constraints],
                        "count": len(type_constraints),
                    }

        if by_severity:
            layers["by_severity"] = {}
            severities = set(c.severity for c in constraints)

            for severity in severities:
                sev_constraints = [c for c in constraints if c.severity == severity]
                sev_geom = ConstraintAggregator.create_composite_constraint_map(
                    sev_constraints
                )

                if sev_geom and not sev_geom.is_empty:
                    layers["by_severity"][severity] = {
                        "geometry_wkt": sev_geom.wkt,
                        "constraint_ids": [c.id for c in sev_constraints],
                        "count": len(sev_constraints),
                    }

        return layers

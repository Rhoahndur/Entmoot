"""
Constraint validation utilities.

This module provides validation functions for constraints and constraint collections.
"""

from typing import Dict, List, Tuple
from shapely.geometry.base import BaseGeometry
from shapely import wkt

from entmoot.models.constraints import Constraint, ConstraintSeverity


class ConstraintValidator:
    """Validator for constraints and constraint collections."""

    @staticmethod
    def validate_geometry(geometry_wkt: str) -> Tuple[bool, List[str]]:
        """
        Validate a geometry WKT string.

        Args:
            geometry_wkt: WKT string to validate

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        try:
            geom = wkt.loads(geometry_wkt)
        except Exception as e:
            errors.append(f"Failed to parse WKT: {str(e)}")
            return (False, errors)

        # Check if geometry is valid
        if not geom.is_valid:
            errors.append(f"Invalid geometry: {geom.is_valid_reason}")

        # Check if geometry is empty
        if geom.is_empty:
            errors.append("Geometry is empty")

        # Check if geometry has area (for polygon constraints)
        if hasattr(geom, 'area') and geom.area == 0:
            errors.append("Geometry has zero area")

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_spatial_relationships(
        constraint: Constraint,
        site_boundary: BaseGeometry
    ) -> Tuple[bool, List[str]]:
        """
        Validate spatial relationships between constraint and site.

        Args:
            constraint: Constraint to validate
            site_boundary: Site boundary geometry

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        try:
            constraint_geom = constraint.get_geometry()
        except Exception as e:
            errors.append(f"Failed to load constraint geometry: {str(e)}")
            return (False, errors)

        # Check if constraint is within or intersects site
        if not constraint_geom.intersects(site_boundary):
            errors.append("Constraint does not intersect site boundary")

        # Warn if constraint extends significantly beyond site
        if not site_boundary.contains(constraint_geom):
            constraint_area = constraint_geom.area
            intersection_area = constraint_geom.intersection(site_boundary).area

            if constraint_area > 0:
                overlap_percent = (intersection_area / constraint_area) * 100
                if overlap_percent < 50:
                    errors.append(
                        f"Constraint extends significantly beyond site "
                        f"(only {overlap_percent:.1f}% overlap)"
                    )

        return (len(errors) == 0, errors)

    @staticmethod
    def check_contradictions(
        constraints: List[Constraint]
    ) -> List[Dict[str, any]]:
        """
        Check for contradictory constraints.

        Args:
            constraints: List of constraints to check

        Returns:
            List of contradiction reports
        """
        contradictions = []

        # Check for overlapping blocking constraints that might be contradictory
        for i, c1 in enumerate(constraints):
            if c1.severity != ConstraintSeverity.BLOCKING:
                continue

            geom1 = c1.get_geometry()

            for c2 in constraints[i + 1:]:
                if c2.severity != ConstraintSeverity.BLOCKING:
                    continue

                geom2 = c2.get_geometry()

                # If two blocking constraints overlap significantly,
                # check if they're contradictory
                if geom1.intersects(geom2):
                    intersection = geom1.intersection(geom2)
                    overlap_area = intersection.area

                    # If overlap is significant
                    min_area = min(geom1.area, geom2.area)
                    if min_area > 0 and (overlap_area / min_area) > 0.1:
                        contradictions.append({
                            "constraint_1_id": c1.id,
                            "constraint_1_name": c1.name,
                            "constraint_2_id": c2.id,
                            "constraint_2_name": c2.name,
                            "overlap_area_sqm": overlap_area,
                            "overlap_percent": (overlap_area / min_area) * 100,
                            "issue": "Overlapping blocking constraints"
                        })

        return contradictions

    @staticmethod
    def verify_coverage(
        constraints: List[Constraint],
        site_boundary: BaseGeometry
    ) -> Tuple[bool, List[str]]:
        """
        Verify that constraint coverage doesn't exceed 100% unreasonably.

        Args:
            constraints: List of constraints
            site_boundary: Site boundary geometry

        Returns:
            Tuple of (is_valid, list of warnings)
        """
        warnings = []

        from shapely.ops import unary_union

        # Get blocking constraints
        blocking_constraints = [
            c for c in constraints
            if c.severity == ConstraintSeverity.BLOCKING
        ]

        if not blocking_constraints:
            return (True, [])

        # Calculate union of all blocking constraints
        blocking_geoms = [c.get_geometry() for c in blocking_constraints]
        blocking_union = unary_union(blocking_geoms)

        # Calculate coverage
        site_area = site_boundary.area
        if site_area == 0:
            warnings.append("Site boundary has zero area")
            return (False, warnings)

        constrained_area = blocking_union.intersection(site_boundary).area
        coverage_percent = (constrained_area / site_area) * 100

        # Warn if coverage is very high
        if coverage_percent > 95:
            warnings.append(
                f"Blocking constraints cover {coverage_percent:.1f}% of site - "
                "very little developable area remaining"
            )
        elif coverage_percent > 100:
            # This can happen due to overlaps
            warnings.append(
                f"Blocking constraints coverage is {coverage_percent:.1f}% - "
                "exceeds site area due to overlaps"
            )

        return (True, warnings)

    @staticmethod
    def validate_constraint_logic(constraint: Constraint) -> Tuple[bool, List[str]]:
        """
        Validate the internal logic of a constraint.

        Args:
            constraint: Constraint to validate

        Returns:
            Tuple of (is_valid, list of errors)
        """
        # Use the constraint's own validation method
        return constraint.validate_constraint()

    @classmethod
    def validate_collection(
        cls,
        constraints: List[Constraint],
        site_boundary: BaseGeometry
    ) -> Dict[str, any]:
        """
        Perform comprehensive validation of a constraint collection.

        Args:
            constraints: List of constraints to validate
            site_boundary: Site boundary geometry

        Returns:
            Dictionary with validation results
        """
        results = {
            "is_valid": True,
            "constraint_errors": {},
            "spatial_errors": {},
            "contradictions": [],
            "coverage_warnings": [],
        }

        # Validate each constraint individually
        for constraint in constraints:
            # Validate constraint logic
            is_valid, errors = cls.validate_constraint_logic(constraint)
            if not is_valid:
                results["constraint_errors"][constraint.id] = errors
                results["is_valid"] = False

            # Validate spatial relationships
            is_valid, errors = cls.validate_spatial_relationships(
                constraint, site_boundary
            )
            if not is_valid:
                results["spatial_errors"][constraint.id] = errors
                results["is_valid"] = False

        # Check for contradictions
        contradictions = cls.check_contradictions(constraints)
        if contradictions:
            results["contradictions"] = contradictions
            # Contradictions are warnings, not necessarily invalid

        # Verify coverage
        is_valid, warnings = cls.verify_coverage(constraints, site_boundary)
        if warnings:
            results["coverage_warnings"] = warnings

        return results

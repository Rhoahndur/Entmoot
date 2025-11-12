"""
Tests for constraint collection and aggregation.

Tests ConstraintCollection, ConstraintValidator, and ConstraintAggregator.
"""

import pytest
from shapely.geometry import Polygon, Point, box

from entmoot.models.constraints import (
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
    SetbackConstraint,
    ExclusionZoneConstraint,
    RegulatoryConstraint as RegulatoryConstraintV2,
    UserDefinedConstraint,
)
from entmoot.core.constraints import (
    ConstraintCollection,
    ConstraintStatistics,
    ConstraintValidator,
    ConstraintAggregator,
)
from entmoot.core.constraints.aggregator import AggregationMode


class TestConstraintCollection:
    """Test ConstraintCollection class."""

    @pytest.fixture
    def site_boundary(self):
        """Create a site boundary polygon."""
        return Polygon([
            (0, 0), (200, 0), (200, 200), (0, 200), (0, 0)
        ])

    @pytest.fixture
    def sample_constraints(self):
        """Create sample constraints for testing."""
        constraints = []

        # Setback constraint
        poly1 = box(0, 0, 50, 200)
        constraints.append(SetbackConstraint(
            id="setback_001",
            name="Property Line Setback",
            constraint_type=ConstraintType.PROPERTY_LINE,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.HIGH,
            geometry_wkt=poly1.wkt,
            setback_distance_m=7.62,
        ))

        # Exclusion zone
        poly2 = box(50, 50, 100, 100)
        constraints.append(ExclusionZoneConstraint(
            id="exclusion_001",
            name="Wetland",
            constraint_type=ConstraintType.WETLAND,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.CRITICAL,
            geometry_wkt=poly2.wkt,
            reason="Protected wetland",
            is_permanent=True,
        ))

        # User preference
        poly3 = box(150, 150, 200, 200)
        constraints.append(UserDefinedConstraint(
            id="custom_001",
            name="View Preservation",
            constraint_type=ConstraintType.CUSTOM,
            severity=ConstraintSeverity.PREFERENCE,
            priority=ConstraintPriority.LOW,
            geometry_wkt=poly3.wkt,
            rule_description="Preserve view",
        ))

        return constraints

    def test_create_collection(self, site_boundary):
        """Test creating a constraint collection."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        assert collection is not None
        assert collection.count() == 0

    def test_add_constraint(self, site_boundary, sample_constraints):
        """Test adding a constraint to collection."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        constraint = sample_constraints[0]

        collection.add_constraint(constraint)
        assert collection.count() == 1

        retrieved = collection.get_constraint(constraint.id)
        assert retrieved is not None
        assert retrieved.id == constraint.id

    def test_add_duplicate_constraint_raises_error(self, site_boundary, sample_constraints):
        """Test that adding duplicate constraint raises error."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        constraint = sample_constraints[0]

        collection.add_constraint(constraint)

        with pytest.raises(ValueError, match="already exists"):
            collection.add_constraint(constraint)

    def test_add_multiple_constraints(self, site_boundary, sample_constraints):
        """Test adding multiple constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        assert collection.count() == len(sample_constraints)

    def test_remove_constraint(self, site_boundary, sample_constraints):
        """Test removing a constraint."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        constraint_id = sample_constraints[0].id
        removed = collection.remove_constraint(constraint_id)

        assert removed is not None
        assert removed.id == constraint_id
        assert collection.count() == len(sample_constraints) - 1
        assert collection.get_constraint(constraint_id) is None

    def test_remove_nonexistent_constraint(self, site_boundary):
        """Test removing non-existent constraint returns None."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        removed = collection.remove_constraint("nonexistent")
        assert removed is None

    def test_get_all_constraints(self, site_boundary, sample_constraints):
        """Test getting all constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        all_constraints = collection.get_all_constraints()
        assert len(all_constraints) == len(sample_constraints)

    def test_clear_collection(self, site_boundary, sample_constraints):
        """Test clearing all constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        collection.clear()
        assert collection.count() == 0

    def test_query_by_type(self, site_boundary, sample_constraints):
        """Test querying constraints by type."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        wetland_constraints = collection.query_by_type([ConstraintType.WETLAND])
        assert len(wetland_constraints) == 1
        assert wetland_constraints[0].constraint_type == ConstraintType.WETLAND

    def test_query_by_severity(self, site_boundary, sample_constraints):
        """Test querying constraints by severity."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        blocking = collection.query_by_severity([ConstraintSeverity.BLOCKING])
        assert len(blocking) == 2  # setback and exclusion zone

    def test_query_by_priority(self, site_boundary, sample_constraints):
        """Test querying constraints by priority."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        critical = collection.query_by_priority([ConstraintPriority.CRITICAL])
        assert len(critical) == 1
        assert critical[0].priority == ConstraintPriority.CRITICAL

    def test_get_blocking_constraints(self, site_boundary, sample_constraints):
        """Test getting blocking constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        blocking = collection.get_blocking_constraints()
        assert len(blocking) == 2
        assert all(c.severity == ConstraintSeverity.BLOCKING for c in blocking)

    def test_get_critical_constraints(self, site_boundary, sample_constraints):
        """Test getting critical constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        critical = collection.get_critical_constraints()
        assert len(critical) == 1
        assert critical[0].priority == ConstraintPriority.CRITICAL

    def test_query_by_location(self, site_boundary, sample_constraints):
        """Test spatial query by location."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        # Query with polygon that intersects wetland
        query_geom = box(75, 75, 125, 125)
        results = collection.query_by_location(query_geom, predicate="intersects")

        assert len(results) >= 1
        # Should find at least the wetland constraint

    def test_query_by_point(self, site_boundary, sample_constraints):
        """Test query by point."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        # Point in setback area
        point = Point(25, 100)
        results = collection.query_by_point(point)

        assert len(results) >= 1

    def test_find_overlapping_constraints(self, site_boundary):
        """Test finding overlapping constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)

        # Create overlapping constraints
        poly1 = box(0, 0, 100, 100)
        poly2 = box(50, 50, 150, 150)  # Overlaps with poly1

        c1 = SetbackConstraint(
            id="overlap_1",
            name="Constraint 1",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=poly1.wkt,
            setback_distance_m=10.0,
        )

        c2 = SetbackConstraint(
            id="overlap_2",
            name="Constraint 2",
            constraint_type=ConstraintType.ROAD,
            geometry_wkt=poly2.wkt,
            setback_distance_m=10.0,
        )

        collection.add_constraints([c1, c2])

        overlaps = collection.find_overlapping_constraints()
        assert len(overlaps) >= 1
        assert overlaps[0][0].id in ["overlap_1", "overlap_2"]
        assert overlaps[0][1].id in ["overlap_1", "overlap_2"]

    def test_resolve_conflicts(self, site_boundary, sample_constraints):
        """Test conflict resolution."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        # Point in wetland (critical constraint)
        point = Point(75, 75)
        winning_constraint = collection.resolve_conflicts(point)

        assert winning_constraint is not None
        assert winning_constraint.priority == ConstraintPriority.CRITICAL

    def test_calculate_statistics(self, site_boundary, sample_constraints):
        """Test calculating collection statistics."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        stats = collection.calculate_statistics()

        assert isinstance(stats, ConstraintStatistics)
        assert stats.total_constraints == len(sample_constraints)
        assert stats.blocking_constraints == 2
        assert stats.total_constrained_area_sqm > 0
        assert stats.constraint_coverage_percent > 0

    def test_get_unconstrained_area(self, site_boundary, sample_constraints):
        """Test calculating unconstrained area."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        unconstrained = collection.get_unconstrained_area()

        assert unconstrained is not None
        assert unconstrained.is_valid
        assert unconstrained.area > 0
        assert unconstrained.area < site_boundary.area

    def test_validate_all(self, site_boundary, sample_constraints):
        """Test validating all constraints."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        validation_results = collection.validate_all()

        assert isinstance(validation_results, dict)
        # May or may not have errors depending on constraints

    def test_to_geojson(self, site_boundary, sample_constraints):
        """Test exporting collection to GeoJSON."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        geojson = collection.to_geojson()

        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson
        assert len(geojson["features"]) == len(sample_constraints)
        assert "properties" in geojson

    def test_export_summary(self, site_boundary, sample_constraints):
        """Test exporting collection summary."""
        collection = ConstraintCollection(site_boundary_wkt=site_boundary.wkt)
        collection.add_constraints(sample_constraints)

        summary = collection.export_summary()

        assert "total_constraints" in summary
        assert "statistics" in summary
        assert "constraints" in summary
        assert len(summary["constraints"]) == len(sample_constraints)


class TestConstraintValidator:
    """Test ConstraintValidator class."""

    @pytest.fixture
    def site_boundary(self):
        """Create a site boundary."""
        return Polygon([
            (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
        ])

    def test_validate_geometry_valid(self):
        """Test validating valid geometry."""
        poly = box(0, 0, 10, 10)
        is_valid, errors = ConstraintValidator.validate_geometry(poly.wkt)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_geometry_invalid_wkt(self):
        """Test validating invalid WKT."""
        is_valid, errors = ConstraintValidator.validate_geometry("INVALID WKT")

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_spatial_relationships(self, site_boundary):
        """Test validating spatial relationships."""
        # Constraint within site
        poly = box(10, 10, 50, 50)
        constraint = SetbackConstraint(
            id="test_001",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=poly.wkt,
            setback_distance_m=10.0,
        )

        is_valid, errors = ConstraintValidator.validate_spatial_relationships(
            constraint, site_boundary
        )

        assert is_valid is True

    def test_validate_spatial_relationships_outside_site(self, site_boundary):
        """Test constraint completely outside site."""
        # Constraint outside site
        poly = box(200, 200, 300, 300)
        constraint = SetbackConstraint(
            id="test_002",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=poly.wkt,
            setback_distance_m=10.0,
        )

        is_valid, errors = ConstraintValidator.validate_spatial_relationships(
            constraint, site_boundary
        )

        assert is_valid is False
        assert len(errors) > 0

    def test_check_contradictions(self):
        """Test checking for contradictory constraints."""
        # Two overlapping blocking constraints
        poly1 = box(0, 0, 50, 50)
        poly2 = box(25, 25, 75, 75)

        c1 = ExclusionZoneConstraint(
            id="c1",
            name="Constraint 1",
            constraint_type=ConstraintType.WETLAND,
            severity=ConstraintSeverity.BLOCKING,
            geometry_wkt=poly1.wkt,
            reason="Test",
            is_permanent=True,
        )

        c2 = ExclusionZoneConstraint(
            id="c2",
            name="Constraint 2",
            constraint_type=ConstraintType.FLOODPLAIN,
            severity=ConstraintSeverity.BLOCKING,
            geometry_wkt=poly2.wkt,
            reason="Test",
            is_permanent=True,
        )

        contradictions = ConstraintValidator.check_contradictions([c1, c2])

        assert len(contradictions) >= 1
        assert "overlap" in contradictions[0]["issue"].lower()

    def test_verify_coverage(self, site_boundary):
        """Test verifying constraint coverage."""
        # Create constraint covering most of site (>95%)
        poly = box(0, 0, 98, 98)  # Covers 96% of 100x100 site
        constraint = ExclusionZoneConstraint(
            id="large",
            name="Large Constraint",
            constraint_type=ConstraintType.FLOODPLAIN,
            severity=ConstraintSeverity.BLOCKING,
            geometry_wkt=poly.wkt,
            reason="Test",
            is_permanent=True,
        )

        is_valid, warnings = ConstraintValidator.verify_coverage(
            [constraint], site_boundary
        )

        assert is_valid is True
        assert len(warnings) > 0  # Should warn about high coverage (>95%)

    def test_validate_collection(self, site_boundary):
        """Test comprehensive collection validation."""
        poly = box(10, 10, 50, 50)
        constraint = SetbackConstraint(
            id="test",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=poly.wkt,
            setback_distance_m=10.0,
        )

        results = ConstraintValidator.validate_collection(
            [constraint], site_boundary
        )

        assert "is_valid" in results
        assert "constraint_errors" in results
        assert "spatial_errors" in results
        assert "contradictions" in results


class TestConstraintAggregator:
    """Test ConstraintAggregator class."""

    @pytest.fixture
    def site_boundary(self):
        """Create a site boundary."""
        return Polygon([
            (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
        ])

    @pytest.fixture
    def sample_constraints(self):
        """Create sample constraints."""
        constraints = []

        poly1 = box(0, 0, 40, 40)
        constraints.append(SetbackConstraint(
            id="c1",
            name="Constraint 1",
            constraint_type=ConstraintType.PROPERTY_LINE,
            severity=ConstraintSeverity.BLOCKING,
            geometry_wkt=poly1.wkt,
            setback_distance_m=10.0,
        ))

        poly2 = box(30, 30, 70, 70)
        constraints.append(SetbackConstraint(
            id="c2",
            name="Constraint 2",
            constraint_type=ConstraintType.ROAD,
            severity=ConstraintSeverity.BLOCKING,
            geometry_wkt=poly2.wkt,
            setback_distance_m=10.0,
        ))

        return constraints

    def test_aggregate_geometries_union(self, sample_constraints):
        """Test aggregating geometries with union."""
        result = ConstraintAggregator.aggregate_geometries(
            sample_constraints, mode=AggregationMode.UNION
        )

        assert result is not None
        assert result.is_valid
        assert result.area > 0

    def test_aggregate_geometries_intersection(self, sample_constraints):
        """Test aggregating geometries with intersection."""
        result = ConstraintAggregator.aggregate_geometries(
            sample_constraints, mode=AggregationMode.INTERSECTION
        )

        assert result is not None
        assert result.is_valid

    def test_aggregate_empty_list(self):
        """Test aggregating empty constraint list."""
        result = ConstraintAggregator.aggregate_geometries([])
        assert result is None

    def test_create_composite_constraint_map(self, sample_constraints):
        """Test creating composite constraint map."""
        result = ConstraintAggregator.create_composite_constraint_map(
            sample_constraints
        )

        assert result is not None
        assert result.is_valid
        assert result.area > 0

    def test_create_composite_map_with_filter(self, sample_constraints):
        """Test creating composite map with severity filter."""
        result = ConstraintAggregator.create_composite_constraint_map(
            sample_constraints,
            filter_severity=[ConstraintSeverity.BLOCKING]
        )

        assert result is not None

    def test_calculate_available_area(self, site_boundary, sample_constraints):
        """Test calculating available area."""
        available_geom, area_sqm, area_acres = (
            ConstraintAggregator.calculate_available_area(
                site_boundary, sample_constraints
            )
        )

        assert available_geom is not None
        assert available_geom.is_valid
        assert area_sqm > 0
        assert area_acres > 0
        assert area_sqm < site_boundary.area

    def test_calculate_constraint_coverage(self, site_boundary, sample_constraints):
        """Test calculating constraint coverage."""
        stats = ConstraintAggregator.calculate_constraint_coverage(
            site_boundary, sample_constraints
        )

        assert "site_area_sqm" in stats
        assert "constrained_area_sqm" in stats
        assert "available_area_sqm" in stats
        assert "coverage_percent" in stats
        assert stats["coverage_percent"] > 0
        assert stats["coverage_percent"] <= 100

    def test_calculate_coverage_with_breakdown(self, site_boundary, sample_constraints):
        """Test coverage calculation with type/severity breakdown."""
        stats = ConstraintAggregator.calculate_constraint_coverage(
            site_boundary, sample_constraints, by_type=True, by_severity=True
        )

        assert "by_type" in stats
        assert "by_severity" in stats

    def test_identify_overlapping_constraints(self, sample_constraints):
        """Test identifying overlapping constraints."""
        overlaps = ConstraintAggregator.identify_overlapping_constraints(
            sample_constraints
        )

        assert len(overlaps) >= 1
        assert "overlap_area_sqm" in overlaps[0]
        assert overlaps[0]["overlap_area_sqm"] > 0

    def test_generate_constraint_summary(self, site_boundary, sample_constraints):
        """Test generating comprehensive constraint summary."""
        summary = ConstraintAggregator.generate_constraint_summary(
            site_boundary, sample_constraints
        )

        assert "site" in summary
        assert "constraints" in summary
        assert "coverage" in summary
        assert "overlaps" in summary

    def test_export_constraint_layers(self, sample_constraints):
        """Test exporting constraint layers."""
        layers = ConstraintAggregator.export_constraint_layers(
            sample_constraints, by_type=True, by_severity=True
        )

        assert "by_type" in layers
        assert "by_severity" in layers

    def test_export_layers_by_type_only(self, sample_constraints):
        """Test exporting layers by type only."""
        layers = ConstraintAggregator.export_constraint_layers(
            sample_constraints, by_type=True, by_severity=False
        )

        assert "by_type" in layers
        assert "by_severity" not in layers

"""
Tests for collision detection and constraint validation.

Tests cover:
- Bounding box collision detection
- Precise polygon intersection
- Spacing enforcement
- Constraint validation
- Spatial indexing performance
"""

import pytest
from datetime import datetime
from shapely.geometry import Polygon, Point, box

from entmoot.models.asset import AssetType, PlacedAsset, get_required_spacing
from entmoot.core.optimization.collision import (
    CollisionDetector,
    Violation,
    ViolationType,
    ValidationResult,
)


# Fixtures

@pytest.fixture
def simple_building():
    """Create a simple rectangular building."""
    # 10m x 10m building at origin
    geom = box(0, 0, 10, 10)
    return PlacedAsset(
        id="building_1",
        name="Building 1",
        asset_type=AssetType.BUILDING,
        geometry_wkt=geom.wkt,
    )


@pytest.fixture
def another_building():
    """Create another building for collision tests."""
    # 10m x 10m building with 40m spacing (no collision or spacing violation)
    geom = box(50, 0, 60, 10)
    return PlacedAsset(
        id="building_2",
        name="Building 2",
        asset_type=AssetType.BUILDING,
        geometry_wkt=geom.wkt,
    )


@pytest.fixture
def overlapping_building():
    """Create a building that overlaps with the first building."""
    # 10m x 10m building partially overlapping
    geom = box(5, 5, 15, 15)
    return PlacedAsset(
        id="building_3",
        name="Building 3",
        asset_type=AssetType.BUILDING,
        geometry_wkt=geom.wkt,
    )


@pytest.fixture
def equipment_yard():
    """Create an equipment yard."""
    geom = box(50, 50, 70, 70)
    return PlacedAsset(
        id="yard_1",
        name="Equipment Yard 1",
        asset_type=AssetType.EQUIPMENT_YARD,
        geometry_wkt=geom.wkt,
    )


@pytest.fixture
def site_boundary():
    """Create a site boundary polygon."""
    # 100m x 100m site
    return box(0, 0, 100, 100)


@pytest.fixture
def exclusion_zone():
    """Create an exclusion zone."""
    # Small exclusion zone in corner
    return box(90, 90, 100, 100)


@pytest.fixture
def buildable_area():
    """Create a buildable area with setbacks."""
    # Buildable area with 10m setbacks
    return box(10, 10, 90, 90)


@pytest.fixture
def collision_detector():
    """Create a fresh collision detector."""
    return CollisionDetector()


# Bounding Box Tests

class TestBoundingBoxCollision:
    """Tests for bounding box collision detection."""

    def test_no_collision(self, collision_detector, simple_building, another_building):
        """Test bounding boxes that don't overlap."""
        result = collision_detector.check_bounding_box_collision(
            simple_building, another_building
        )
        assert result is False

    def test_collision(self, collision_detector, simple_building, overlapping_building):
        """Test bounding boxes that do overlap."""
        result = collision_detector.check_bounding_box_collision(
            simple_building, overlapping_building
        )
        assert result is True

    def test_adjacent_no_collision(self, collision_detector, simple_building):
        """Test adjacent bounding boxes (touching but not overlapping)."""
        # Building exactly adjacent (touching edge)
        adjacent_geom = box(10, 0, 20, 10)
        adjacent_building = PlacedAsset(
            id="building_adjacent",
            name="Adjacent Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=adjacent_geom.wkt,
        )
        result = collision_detector.check_bounding_box_collision(
            simple_building, adjacent_building
        )
        # Adjacent boxes should not be considered colliding
        assert result is False


# Precise Collision Tests

class TestPreciseCollision:
    """Tests for precise polygon-polygon collision detection."""

    def test_no_intersection(self, collision_detector, simple_building, another_building):
        """Test polygons that don't intersect."""
        result = collision_detector.check_precise_collision(
            simple_building, another_building
        )
        assert result is False

    def test_intersection(self, collision_detector, simple_building, overlapping_building):
        """Test polygons that do intersect."""
        result = collision_detector.check_precise_collision(
            simple_building, overlapping_building
        )
        assert result is True

    def test_complete_overlap(self, collision_detector, simple_building):
        """Test one polygon completely inside another."""
        # Small building inside the first building
        small_geom = box(2, 2, 5, 5)
        small_building = PlacedAsset(
            id="building_small",
            name="Small Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=small_geom.wkt,
        )
        result = collision_detector.check_precise_collision(
            simple_building, small_building
        )
        assert result is True

    def test_complex_polygon_intersection(self, collision_detector):
        """Test intersection with complex polygon shapes."""
        # L-shaped building
        l_shape = Polygon([
            (0, 0), (10, 0), (10, 5), (5, 5),
            (5, 10), (0, 10), (0, 0)
        ])
        l_building = PlacedAsset(
            id="l_building",
            name="L-Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=l_shape.wkt,
        )

        # Rectangle that intersects the L
        rect_geom = box(3, 3, 7, 7)
        rect_building = PlacedAsset(
            id="rect_building",
            name="Rect Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=rect_geom.wkt,
        )

        result = collision_detector.check_precise_collision(
            l_building, rect_building
        )
        assert result is True


# Spacing Tests

class TestSpacingEnforcement:
    """Tests for minimum spacing enforcement."""

    def test_get_required_spacing_building_to_building(self):
        """Test default building-to-building spacing."""
        spacing = get_required_spacing(AssetType.BUILDING, AssetType.BUILDING)
        assert spacing == 30.0

    def test_get_required_spacing_building_to_road(self):
        """Test building-to-road spacing."""
        spacing = get_required_spacing(AssetType.BUILDING, AssetType.ROAD)
        assert spacing == 10.0

    def test_get_required_spacing_yard_to_yard(self):
        """Test equipment yard to equipment yard spacing."""
        spacing = get_required_spacing(
            AssetType.EQUIPMENT_YARD, AssetType.EQUIPMENT_YARD
        )
        assert spacing == 20.0

    def test_check_spacing_sufficient(self, collision_detector, simple_building):
        """Test spacing check when spacing is sufficient."""
        # Building 50m away (more than 30m requirement)
        far_geom = box(50, 0, 60, 10)
        far_building = PlacedAsset(
            id="far_building",
            name="Far Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=far_geom.wkt,
        )

        is_valid, actual, required = collision_detector.check_spacing(
            simple_building, far_building
        )

        assert is_valid is True
        assert actual >= required
        assert required == 30.0

    def test_check_spacing_insufficient(self, collision_detector, simple_building):
        """Test spacing check when spacing is insufficient."""
        # Building only 15m away (less than 30m requirement)
        close_geom = box(25, 0, 35, 10)
        close_building = PlacedAsset(
            id="close_building",
            name="Close Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=close_geom.wkt,
        )

        is_valid, actual, required = collision_detector.check_spacing(
            simple_building, close_building
        )

        assert is_valid is False
        assert actual < required
        assert required == 30.0
        assert actual == pytest.approx(15.0, abs=0.1)

    def test_custom_spacing_rules(self, collision_detector, simple_building):
        """Test custom spacing rules override defaults."""
        # Custom rule: buildings need 50m spacing
        custom_rules = {
            (AssetType.BUILDING, AssetType.BUILDING): 50.0
        }
        detector = CollisionDetector(spacing_rules=custom_rules)

        # Building 40m away
        medium_geom = box(50, 0, 60, 10)
        medium_building = PlacedAsset(
            id="medium_building",
            name="Medium Distance Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=medium_geom.wkt,
        )

        is_valid, actual, required = detector.check_spacing(
            simple_building, medium_building
        )

        assert is_valid is False  # 40m < 50m
        assert required == 50.0

    def test_asset_specific_min_spacing(self, collision_detector):
        """Test asset-specific minimum spacing overrides type rules."""
        # Building with custom 60m spacing requirement
        building1 = PlacedAsset(
            id="building_special",
            name="Special Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(0, 0, 10, 10).wkt,
            min_spacing_m=60.0,
        )

        building2 = PlacedAsset(
            id="building_normal",
            name="Normal Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(50, 0, 60, 10).wkt,
        )

        is_valid, actual, required = collision_detector.check_spacing(
            building1, building2
        )

        assert is_valid is False
        assert required == 60.0  # Asset-specific spacing is used


# Collision Detection Tests

class TestCollisionDetection:
    """Tests for full collision detection."""

    def test_no_collisions(self, collision_detector, simple_building, another_building):
        """Test detecting no collisions when assets are far apart."""
        collision_detector.add_asset(another_building)

        violations = collision_detector.check_collisions(simple_building)

        assert len(violations) == 0

    def test_detect_overlap_collision(
        self, collision_detector, simple_building, overlapping_building
    ):
        """Test detecting direct overlap collision."""
        collision_detector.add_asset(simple_building)

        violations = collision_detector.check_collisions(overlapping_building)

        assert len(violations) == 1
        assert violations[0].violation_type == ViolationType.COLLISION
        assert violations[0].asset_id == overlapping_building.id
        assert violations[0].conflicting_asset_id == simple_building.id

    def test_detect_spacing_violation(self, collision_detector, simple_building):
        """Test detecting spacing violations."""
        collision_detector.add_asset(simple_building)

        # Building 20m away (violates 30m rule)
        close_geom = box(30, 0, 40, 10)
        close_building = PlacedAsset(
            id="close_building",
            name="Close Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=close_geom.wkt,
        )

        violations = collision_detector.check_collisions(close_building)

        assert len(violations) == 1
        assert violations[0].violation_type == ViolationType.SPACING_VIOLATION
        assert violations[0].required_distance_m == 30.0
        assert violations[0].distance_m < 30.0

    def test_multiple_violations(self, collision_detector):
        """Test detecting multiple violations."""
        # Add two buildings
        building1 = PlacedAsset(
            id="building_1",
            name="Building 1",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(0, 0, 10, 10).wkt,
        )
        building2 = PlacedAsset(
            id="building_2",
            name="Building 2",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(25, 0, 35, 10).wkt,
        )

        collision_detector.add_asset(building1)
        collision_detector.add_asset(building2)

        # New building violates spacing with both
        middle_building = PlacedAsset(
            id="middle_building",
            name="Middle Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(12, 0, 22, 10).wkt,
        )

        violations = collision_detector.check_collisions(middle_building)

        assert len(violations) == 2
        assert all(v.violation_type == ViolationType.SPACING_VIOLATION for v in violations)

    def test_exclude_assets_from_check(self, collision_detector, simple_building):
        """Test excluding specific assets from collision check."""
        collision_detector.add_asset(simple_building)

        close_building = PlacedAsset(
            id="close_building",
            name="Close Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(15, 0, 25, 10).wkt,
        )

        # Check with exclusion
        violations = collision_detector.check_collisions(
            close_building,
            exclude_ids={simple_building.id}
        )

        assert len(violations) == 0


# Constraint Validation Tests

class TestConstraintValidation:
    """Tests for constraint validation."""

    def test_validate_within_boundary(
        self, collision_detector, simple_building, site_boundary
    ):
        """Test asset within site boundary passes validation."""
        result = collision_detector.validate_placement(
            simple_building,
            site_boundary=site_boundary
        )

        assert result.is_valid is True
        assert len(result.violations) == 0

    def test_validate_outside_boundary(
        self, collision_detector, site_boundary
    ):
        """Test asset outside site boundary fails validation."""
        # Building completely outside boundary
        outside_building = PlacedAsset(
            id="outside_building",
            name="Outside Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(110, 110, 120, 120).wkt,
        )

        result = collision_detector.validate_placement(
            outside_building,
            site_boundary=site_boundary
        )

        assert result.is_valid is False
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == ViolationType.OUT_OF_BOUNDS

    def test_validate_partially_outside_boundary(
        self, collision_detector, site_boundary
    ):
        """Test asset partially outside boundary."""
        # Building partially outside
        partial_building = PlacedAsset(
            id="partial_building",
            name="Partial Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(95, 95, 105, 105).wkt,
        )

        result = collision_detector.validate_placement(
            partial_building,
            site_boundary=site_boundary
        )

        assert result.is_valid is False
        assert any(
            v.violation_type == ViolationType.OUT_OF_BOUNDS
            for v in result.violations
        )

    def test_validate_exclusion_zone(
        self, collision_detector, site_boundary, exclusion_zone
    ):
        """Test asset in exclusion zone fails validation."""
        # Building in exclusion zone
        excluded_building = PlacedAsset(
            id="excluded_building",
            name="Excluded Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(91, 91, 95, 95).wkt,
        )

        result = collision_detector.validate_placement(
            excluded_building,
            site_boundary=site_boundary,
            exclusion_zones=[exclusion_zone]
        )

        assert result.is_valid is False
        assert any(
            v.violation_type == ViolationType.EXCLUSION_ZONE
            for v in result.violations
        )

    def test_validate_buildable_area(
        self, collision_detector, site_boundary, buildable_area
    ):
        """Test asset must be in buildable area."""
        # Building outside buildable area but inside site
        setback_violation = PlacedAsset(
            id="setback_building",
            name="Setback Violation Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(2, 2, 8, 8).wkt,
        )

        result = collision_detector.validate_placement(
            setback_violation,
            site_boundary=site_boundary,
            buildable_area=buildable_area
        )

        assert result.is_valid is False
        assert any(
            v.violation_type == ViolationType.SETBACK_VIOLATION
            for v in result.violations
        )

    def test_validate_multiple_constraints(
        self, collision_detector, site_boundary, exclusion_zone, buildable_area
    ):
        """Test validation with multiple constraint types."""
        collision_detector.add_asset(
            PlacedAsset(
                id="existing_building",
                name="Existing Building",
                asset_type=AssetType.BUILDING,
                geometry_wkt=box(20, 20, 30, 30).wkt,
            )
        )

        # Building that violates spacing
        problem_building = PlacedAsset(
            id="problem_building",
            name="Problem Building",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(35, 20, 45, 30).wkt,
        )

        result = collision_detector.validate_placement(
            problem_building,
            site_boundary=site_boundary,
            exclusion_zones=[exclusion_zone],
            buildable_area=buildable_area
        )

        # Should have spacing violation
        assert result.is_valid is False
        assert any(
            v.violation_type == ViolationType.SPACING_VIOLATION
            for v in result.violations
        )


# Spatial Indexing Tests

class TestSpatialIndexing:
    """Tests for spatial index functionality."""

    def test_spatial_index_creation(self, collision_detector, simple_building):
        """Test spatial index is created when needed."""
        collision_detector.add_asset(simple_building)
        assert collision_detector._needs_rebuild is True

        # Trigger index rebuild
        collision_detector._rebuild_index()

        assert collision_detector._needs_rebuild is False
        assert collision_detector.spatial_index is not None

    def test_find_potential_collisions(self, collision_detector):
        """Test finding potential collisions with spatial index."""
        # Add several buildings
        for i in range(5):
            building = PlacedAsset(
                id=f"building_{i}",
                name=f"Building {i}",
                asset_type=AssetType.BUILDING,
                geometry_wkt=box(i * 20, 0, i * 20 + 10, 10).wkt,
            )
            collision_detector.add_asset(building)

        # Test asset near building 2
        test_asset = PlacedAsset(
            id="test_asset",
            name="Test Asset",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(45, 0, 55, 10).wkt,
        )

        candidates = collision_detector.find_potential_collisions(test_asset)

        # Should find nearby buildings
        assert len(candidates) > 0
        assert len(candidates) <= 5

    def test_spatial_index_performance(self, collision_detector):
        """Test spatial index performance with many assets."""
        # Add many assets
        for i in range(100):
            x = (i % 10) * 20
            y = (i // 10) * 20
            asset = PlacedAsset(
                id=f"asset_{i}",
                name=f"Asset {i}",
                asset_type=AssetType.BUILDING,
                geometry_wkt=box(x, y, x + 10, y + 10).wkt,
            )
            collision_detector.add_asset(asset)

        # Test query performance
        test_asset = PlacedAsset(
            id="test_asset",
            name="Test Asset",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(105, 105, 115, 115).wkt,
        )

        # Should complete quickly even with 100 assets
        import time
        start = time.time()
        candidates = collision_detector.find_potential_collisions(test_asset)
        elapsed = time.time() - start

        # Should be very fast (under 0.1 seconds)
        assert elapsed < 0.1


# Multiple Asset Validation Tests

class TestMultipleAssetValidation:
    """Tests for validating multiple assets."""

    def test_validate_multiple_placements(
        self, collision_detector, site_boundary
    ):
        """Test validating multiple assets at once."""
        assets = [
            PlacedAsset(
                id=f"building_{i}",
                name=f"Building {i}",
                asset_type=AssetType.BUILDING,
                geometry_wkt=box(i * 40, 0, i * 40 + 10, 10).wkt,
            )
            for i in range(3)
        ]

        results = collision_detector.validate_multiple_placements(
            assets,
            site_boundary=site_boundary
        )

        assert len(results) == 3
        assert all(isinstance(r, ValidationResult) for r in results.values())

    def test_check_all_spacing_violations(self, collision_detector):
        """Test checking all assets for spacing violations."""
        # Add buildings that violate spacing with each other
        building1 = PlacedAsset(
            id="building_1",
            name="Building 1",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(0, 0, 10, 10).wkt,
        )
        building2 = PlacedAsset(
            id="building_2",
            name="Building 2",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(20, 0, 30, 10).wkt,  # Only 10m away
        )

        collision_detector.add_asset(building1)
        collision_detector.add_asset(building2)

        violations = collision_detector.check_minimum_spacing_violations()

        assert len(violations) > 0
        assert all(
            v.violation_type == ViolationType.SPACING_VIOLATION
            for v in violations
        )


# Clearance Zone Tests

class TestClearanceZones:
    """Tests for clearance zone functionality."""

    def test_get_clearance_zone(self, collision_detector, simple_building):
        """Test getting clearance zone around asset."""
        clearance = collision_detector.get_clearance_zone(simple_building, 15.0)

        # Clearance should be larger than original
        original_area = simple_building.get_area_sqm()
        clearance_area = clearance.area

        assert clearance_area > original_area

    def test_clearance_zone_validation(self, collision_detector):
        """Test validation with clearance zones."""
        building1 = PlacedAsset(
            id="building_1",
            name="Building 1",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(0, 0, 10, 10).wkt,
        )

        # Get clearance zone
        clearance = collision_detector.get_clearance_zone(building1, 30.0)

        # Building in clearance zone
        building2 = PlacedAsset(
            id="building_2",
            name="Building 2",
            asset_type=AssetType.BUILDING,
            geometry_wkt=box(25, 0, 35, 10).wkt,
        )

        # Should intersect clearance zone
        assert clearance.intersects(building2.get_geometry())


# Edge Cases

class TestEdgeCases:
    """Tests for edge cases and corner scenarios."""

    def test_empty_detector(self, collision_detector, simple_building):
        """Test collision detection with no existing assets."""
        violations = collision_detector.check_collisions(simple_building)
        assert len(violations) == 0

    def test_clear_detector(self, collision_detector, simple_building):
        """Test clearing all assets from detector."""
        collision_detector.add_asset(simple_building)
        assert len(collision_detector.assets) == 1

        collision_detector.clear()
        assert len(collision_detector.assets) == 0
        assert collision_detector.spatial_index is None

    def test_remove_asset(self, collision_detector, simple_building, another_building):
        """Test removing an asset."""
        collision_detector.add_asset(simple_building)
        collision_detector.add_asset(another_building)
        assert len(collision_detector.assets) == 2

        collision_detector.remove_asset(simple_building.id)
        assert len(collision_detector.assets) == 1
        assert simple_building.id not in collision_detector.assets

    def test_zero_area_geometry(self, collision_detector):
        """Test handling zero-area geometries."""
        # Point geometry (zero area)
        point_asset = PlacedAsset(
            id="point_asset",
            name="Point Asset",
            asset_type=AssetType.UTILITY,
            geometry_wkt=Point(5, 5).wkt,
        )

        area = point_asset.get_area_sqm()
        assert area == 0.0

    def test_validation_result_to_dict(self):
        """Test converting validation result to dictionary."""
        violation = Violation(
            violation_type=ViolationType.COLLISION,
            asset_id="test_asset",
            description="Test collision",
            severity="blocking",
        )

        result = ValidationResult(
            is_valid=False,
            violations=[violation],
            warnings=["Test warning"]
        )

        result_dict = result.to_dict()

        assert result_dict["is_valid"] is False
        assert len(result_dict["violations"]) == 1
        assert len(result_dict["warnings"]) == 1
        assert result_dict["violations"][0]["violation_type"] == "collision"

"""
Tests for constraint models.

Tests the Constraint base class and all derived constraint types including:
- SetbackConstraint
- ExclusionZoneConstraint
- RegulatoryConstraint
- UserDefinedConstraint
"""

import pytest
from datetime import datetime, timedelta
from shapely.geometry import Polygon, Point, LineString
from shapely import wkt as shapely_wkt

from entmoot.models.constraints import (
    Constraint,
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
    SetbackConstraint,
    ExclusionZoneConstraint,
    RegulatoryConstraint as RegulatoryConstraintV2,
    UserDefinedConstraint,
    STANDARD_SETBACKS,
    create_standard_setback,
)


class TestConstraintType:
    """Test ConstraintType enum."""

    def test_constraint_types_exist(self):
        """Test all required constraint types exist."""
        assert ConstraintType.PROPERTY_LINE
        assert ConstraintType.ROAD
        assert ConstraintType.WATER_FEATURE
        assert ConstraintType.WETLAND
        assert ConstraintType.FLOODPLAIN
        assert ConstraintType.UTILITY
        assert ConstraintType.NEIGHBOR
        assert ConstraintType.STEEP_SLOPE
        assert ConstraintType.ARCHAEOLOGICAL
        assert ConstraintType.CUSTOM


class TestConstraintSeverity:
    """Test ConstraintSeverity enum."""

    def test_severity_levels(self):
        """Test all severity levels exist."""
        assert ConstraintSeverity.BLOCKING
        assert ConstraintSeverity.WARNING
        assert ConstraintSeverity.PREFERENCE


class TestConstraintPriority:
    """Test ConstraintPriority enum."""

    def test_priority_levels(self):
        """Test all priority levels exist."""
        assert ConstraintPriority.CRITICAL
        assert ConstraintPriority.HIGH
        assert ConstraintPriority.MEDIUM
        assert ConstraintPriority.LOW


class TestSetbackConstraint:
    """Test SetbackConstraint class."""

    @pytest.fixture
    def property_line(self):
        """Create a simple property line."""
        return LineString([
            (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
        ])

    @pytest.fixture
    def setback_polygon(self):
        """Create a setback polygon."""
        # 10m buffer around property line
        return Polygon([
            (-10, -10), (110, -10), (110, 110), (-10, 110), (-10, -10)
        ])

    def test_create_setback_constraint(self, setback_polygon):
        """Test creating a valid setback constraint."""
        constraint = SetbackConstraint(
            id="setback_001",
            name="Property Line Setback",
            description="25 foot setback from property line",
            constraint_type=ConstraintType.PROPERTY_LINE,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.HIGH,
            geometry_wkt=setback_polygon.wkt,
            setback_distance_m=7.62,
        )

        assert constraint.id == "setback_001"
        assert constraint.name == "Property Line Setback"
        assert constraint.constraint_type == ConstraintType.PROPERTY_LINE
        assert constraint.setback_distance_m == 7.62
        assert constraint.severity == ConstraintSeverity.BLOCKING

    def test_setback_with_source_feature(self, property_line, setback_polygon):
        """Test setback constraint with source feature."""
        constraint = SetbackConstraint(
            id="setback_002",
            name="Road Setback",
            constraint_type=ConstraintType.ROAD,
            geometry_wkt=setback_polygon.wkt,
            source_feature_wkt=property_line.wkt,
            setback_distance_m=15.24,
        )

        assert constraint.source_feature_wkt is not None
        assert constraint.setback_distance_m == 15.24

    def test_setback_validation(self, setback_polygon):
        """Test setback constraint validation."""
        constraint = SetbackConstraint(
            id="setback_003",
            name="Test Setback",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=setback_polygon.wkt,
            setback_distance_m=7.62,
        )

        is_valid, errors = constraint.validate_constraint()
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_excessive_setback_warning(self, setback_polygon):
        """Test warning for excessive setback distance."""
        constraint = SetbackConstraint(
            id="setback_004",
            name="Excessive Setback",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=setback_polygon.wkt,
            setback_distance_m=1500.0,  # Excessive
        )

        is_valid, errors = constraint.validate_constraint()
        assert len(errors) > 0
        assert any("exceeds" in error.lower() for error in errors)

    def test_invalid_geometry_raises_error(self):
        """Test that invalid geometry WKT raises validation error."""
        with pytest.raises(ValueError, match="Invalid geometry WKT"):
            SetbackConstraint(
                id="setback_bad",
                name="Bad Geometry",
                constraint_type=ConstraintType.PROPERTY_LINE,
                geometry_wkt="INVALID WKT STRING",
                setback_distance_m=10.0,
            )


class TestExclusionZoneConstraint:
    """Test ExclusionZoneConstraint class."""

    @pytest.fixture
    def wetland_polygon(self):
        """Create a wetland polygon."""
        return Polygon([
            (10, 10), (50, 10), (50, 50), (10, 50), (10, 10)
        ])

    def test_create_exclusion_zone(self, wetland_polygon):
        """Test creating an exclusion zone."""
        constraint = ExclusionZoneConstraint(
            id="exclusion_001",
            name="Wetland Exclusion",
            description="Protected wetland area",
            constraint_type=ConstraintType.WETLAND,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.CRITICAL,
            geometry_wkt=wetland_polygon.wkt,
            reason="Federally protected wetland",
            is_permanent=True,
        )

        assert constraint.id == "exclusion_001"
        assert constraint.reason == "Federally protected wetland"
        assert constraint.is_permanent is True
        assert constraint.expiration_date is None

    def test_temporary_exclusion_zone(self, wetland_polygon):
        """Test temporary exclusion zone with expiration."""
        expiration = datetime.utcnow() + timedelta(days=365)

        constraint = ExclusionZoneConstraint(
            id="exclusion_002",
            name="Temporary Exclusion",
            constraint_type=ConstraintType.ARCHAEOLOGICAL,
            geometry_wkt=wetland_polygon.wkt,
            reason="Archaeological survey in progress",
            is_permanent=False,
            expiration_date=expiration,
        )

        assert constraint.is_permanent is False
        assert constraint.expiration_date is not None
        assert constraint.expiration_date > datetime.utcnow()

    def test_permanent_cannot_have_expiration(self, wetland_polygon):
        """Test that permanent exclusions cannot have expiration dates."""
        expiration = datetime.utcnow() + timedelta(days=365)

        with pytest.raises(ValueError, match="Permanent exclusions cannot have expiration"):
            ExclusionZoneConstraint(
                id="exclusion_bad",
                name="Bad Exclusion",
                constraint_type=ConstraintType.WETLAND,
                geometry_wkt=wetland_polygon.wkt,
                reason="Test",
                is_permanent=True,
                expiration_date=expiration,
            )

    def test_temporary_requires_expiration(self, wetland_polygon):
        """Test that temporary exclusions must have expiration dates."""
        with pytest.raises(ValueError, match="Temporary exclusions must have expiration"):
            ExclusionZoneConstraint(
                id="exclusion_bad2",
                name="Bad Temporary",
                constraint_type=ConstraintType.ARCHAEOLOGICAL,
                geometry_wkt=wetland_polygon.wkt,
                reason="Test",
                is_permanent=False,
                expiration_date=None,
            )

    def test_exclusion_zone_validation(self, wetland_polygon):
        """Test exclusion zone validation."""
        constraint = ExclusionZoneConstraint(
            id="exclusion_003",
            name="Floodplain",
            constraint_type=ConstraintType.FLOODPLAIN,
            geometry_wkt=wetland_polygon.wkt,
            reason="100-year floodplain",
            is_permanent=True,
        )

        is_valid, errors = constraint.validate_constraint()
        # Should warn about missing regulatory reference
        assert len(errors) > 0


class TestRegulatoryConstraint:
    """Test RegulatoryConstraint class."""

    @pytest.fixture
    def floodplain_polygon(self):
        """Create a floodplain polygon."""
        return Polygon([
            (0, 0), (100, 0), (100, 50), (0, 50), (0, 0)
        ])

    def test_create_regulatory_constraint(self, floodplain_polygon):
        """Test creating a regulatory constraint."""
        constraint = RegulatoryConstraintV2(
            id="reg_001",
            name="100-Year Floodplain",
            description="FEMA designated floodplain",
            constraint_type=ConstraintType.FLOODPLAIN,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.CRITICAL,
            geometry_wkt=floodplain_polygon.wkt,
            regulation_name="National Flood Insurance Program",
            regulation_code="44 CFR 60",
            authority="Federal (FEMA)",
            compliance_requirement="No habitable structures",
            data_source="FEMA NFHL",
            verification_url="https://msc.fema.gov",
        )

        assert constraint.regulation_name == "National Flood Insurance Program"
        assert constraint.regulation_code == "44 CFR 60"
        assert constraint.authority == "Federal (FEMA)"
        assert constraint.priority == ConstraintPriority.CRITICAL

    def test_regulatory_constraint_validation(self, floodplain_polygon):
        """Test regulatory constraint validation."""
        constraint = RegulatoryConstraintV2(
            id="reg_002",
            name="Zoning Setback",
            constraint_type=ConstraintType.ZONING,
            geometry_wkt=floodplain_polygon.wkt,
            regulation_name="Local Zoning Code",
            authority="Local",
            compliance_requirement="Minimum setback",
            data_source="City Planning Department",
        )

        is_valid, errors = constraint.validate_constraint()
        assert isinstance(is_valid, bool)

    def test_regulatory_low_priority_warning(self, floodplain_polygon):
        """Test warning for low priority regulatory constraint."""
        constraint = RegulatoryConstraintV2(
            id="reg_003",
            name="Low Priority Reg",
            constraint_type=ConstraintType.ZONING,
            priority=ConstraintPriority.LOW,
            geometry_wkt=floodplain_polygon.wkt,
            regulation_name="Test",
            authority="Local",
            compliance_requirement="Test",
        )

        is_valid, errors = constraint.validate_constraint()
        assert any("LOW priority" in error for error in errors)

    def test_old_verification_warning(self, floodplain_polygon):
        """Test warning for old verification date."""
        old_date = datetime.utcnow() - timedelta(days=400)

        constraint = RegulatoryConstraintV2(
            id="reg_004",
            name="Old Regulation",
            constraint_type=ConstraintType.FLOODPLAIN,
            geometry_wkt=floodplain_polygon.wkt,
            regulation_name="Test",
            authority="Federal",
            compliance_requirement="Test",
            verification_date=old_date,
        )

        is_valid, errors = constraint.validate_constraint()
        assert any("days old" in error for error in errors)


class TestUserDefinedConstraint:
    """Test UserDefinedConstraint class."""

    @pytest.fixture
    def custom_polygon(self):
        """Create a custom constraint polygon."""
        return Polygon([
            (20, 20), (80, 20), (80, 80), (20, 80), (20, 20)
        ])

    def test_create_user_defined_constraint(self, custom_polygon):
        """Test creating a user-defined constraint."""
        constraint = UserDefinedConstraint(
            id="custom_001",
            name="View Corridor",
            description="Preserve mountain view",
            constraint_type=ConstraintType.CUSTOM,
            severity=ConstraintSeverity.PREFERENCE,
            priority=ConstraintPriority.LOW,
            geometry_wkt=custom_polygon.wkt,
            rule_description="Maintain clear view corridor to mountains",
            parameters={"max_height_ft": 15, "view_azimuth": 270},
            can_override=True,
        )

        assert constraint.rule_description == "Maintain clear view corridor to mountains"
        assert constraint.parameters["max_height_ft"] == 15
        assert constraint.can_override is True

    def test_user_constraint_validation(self, custom_polygon):
        """Test user-defined constraint validation."""
        constraint = UserDefinedConstraint(
            id="custom_002",
            name="Custom Rule",
            constraint_type=ConstraintType.CUSTOM,
            geometry_wkt=custom_polygon.wkt,
            rule_description="Custom development rule",
            can_override=True,
        )

        is_valid, errors = constraint.validate_constraint()
        assert isinstance(is_valid, bool)

    def test_user_constraint_without_rule_fails(self, custom_polygon):
        """Test that user constraint without rule description fails validation."""
        # Pydantic will validate min_length at creation
        with pytest.raises(ValueError):
            constraint = UserDefinedConstraint(
                id="custom_bad",
                name="No Rule",
                constraint_type=ConstraintType.CUSTOM,
                geometry_wkt=custom_polygon.wkt,
                rule_description="",  # Empty rule - should fail Pydantic validation
            )


class TestConstraintGeometry:
    """Test constraint geometry operations."""

    @pytest.fixture
    def test_polygon(self):
        """Create a test polygon."""
        return Polygon([
            (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
        ])

    def test_get_geometry(self, test_polygon):
        """Test getting Shapely geometry from WKT."""
        constraint = SetbackConstraint(
            id="test_001",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=test_polygon.wkt,
            setback_distance_m=10.0,
        )

        geom = constraint.get_geometry()
        assert geom is not None
        assert geom.is_valid
        assert geom.geom_type == "Polygon"

    def test_get_area_sqm(self, test_polygon):
        """Test calculating area in square meters."""
        constraint = SetbackConstraint(
            id="test_002",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=test_polygon.wkt,
            setback_distance_m=10.0,
        )

        area = constraint.get_area_sqm()
        assert area > 0
        assert area == pytest.approx(10000.0, rel=0.01)

    def test_get_area_acres(self, test_polygon):
        """Test calculating area in acres."""
        constraint = SetbackConstraint(
            id="test_003",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=test_polygon.wkt,
            setback_distance_m=10.0,
        )

        area_acres = constraint.get_area_acres()
        assert area_acres > 0
        # 10000 sqm ≈ 2.47 acres
        assert area_acres == pytest.approx(2.47, rel=0.01)

    def test_intersects(self, test_polygon):
        """Test intersection check."""
        constraint = SetbackConstraint(
            id="test_004",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=test_polygon.wkt,
            setback_distance_m=10.0,
        )

        # Point inside
        point_inside = Polygon([(25, 25), (75, 25), (75, 75), (25, 75), (25, 25)])
        assert constraint.intersects(point_inside)

        # Point outside
        point_outside = Polygon([(200, 200), (300, 200), (300, 300), (200, 300), (200, 200)])
        assert not constraint.intersects(point_outside)

    def test_contains_point(self, test_polygon):
        """Test point containment."""
        constraint = SetbackConstraint(
            id="test_005",
            name="Test",
            constraint_type=ConstraintType.PROPERTY_LINE,
            geometry_wkt=test_polygon.wkt,
            setback_distance_m=10.0,
        )

        # Point inside
        point_inside = Point(50, 50)
        assert constraint.contains(point_inside)

        # Point outside
        point_outside = Point(200, 200)
        assert not constraint.contains(point_outside)


class TestConstraintGeoJSON:
    """Test GeoJSON export."""

    @pytest.fixture
    def test_polygon(self):
        """Create a test polygon."""
        return Polygon([
            (0, 0), (10, 0), (10, 10), (0, 10), (0, 0)
        ])

    def test_to_geojson(self, test_polygon):
        """Test exporting constraint to GeoJSON."""
        constraint = SetbackConstraint(
            id="geojson_001",
            name="Test Setback",
            description="Test description",
            constraint_type=ConstraintType.PROPERTY_LINE,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.HIGH,
            geometry_wkt=test_polygon.wkt,
            setback_distance_m=7.62,
        )

        geojson = constraint.to_geojson()

        assert geojson["type"] == "Feature"
        assert "geometry" in geojson
        assert "properties" in geojson
        assert geojson["properties"]["id"] == "geojson_001"
        assert geojson["properties"]["name"] == "Test Setback"
        assert geojson["properties"]["constraint_type"] == ConstraintType.PROPERTY_LINE


class TestStandardSetbacks:
    """Test standard setback distances and creation."""

    def test_standard_setbacks_exist(self):
        """Test that standard setbacks are defined."""
        assert ConstraintType.PROPERTY_LINE in STANDARD_SETBACKS
        assert ConstraintType.ROAD in STANDARD_SETBACKS
        assert ConstraintType.WATER_FEATURE in STANDARD_SETBACKS
        assert ConstraintType.WETLAND in STANDARD_SETBACKS

    def test_create_standard_setback(self):
        """Test creating a standard setback constraint."""
        property_line = LineString([
            (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
        ])

        constraint = create_standard_setback(
            constraint_id="std_001",
            constraint_type=ConstraintType.PROPERTY_LINE,
            source_geometry=property_line,
        )

        assert constraint.id == "std_001"
        assert constraint.constraint_type == ConstraintType.PROPERTY_LINE
        assert constraint.setback_distance_m == STANDARD_SETBACKS[ConstraintType.PROPERTY_LINE]
        assert constraint.source_feature_wkt is not None

    def test_create_standard_setback_with_override(self):
        """Test creating standard setback with distance override."""
        property_line = LineString([
            (0, 0), (100, 0)
        ])

        constraint = create_standard_setback(
            constraint_id="std_002",
            constraint_type=ConstraintType.ROAD,
            source_geometry=property_line,
            distance_override=20.0,
        )

        assert constraint.setback_distance_m == 20.0
        assert constraint.setback_distance_m != STANDARD_SETBACKS[ConstraintType.ROAD]

    def test_create_standard_setback_custom_name(self):
        """Test creating standard setback with custom name."""
        line = LineString([(0, 0), (100, 0)])

        constraint = create_standard_setback(
            constraint_id="std_003",
            constraint_type=ConstraintType.UTILITY,
            source_geometry=line,
            name="Custom Utility Setback",
        )

        assert constraint.name == "Custom Utility Setback"

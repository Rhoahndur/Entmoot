"""
Tests for buffer generation engine.

Tests all buffer creation functionality including:
- Basic buffer operations
- Property line setbacks
- Road setbacks with different classifications
- Water feature setbacks
- Utility corridor setbacks
- Buffer validation and simplification
- Edge cases and error handling
"""

import pytest
from shapely.geometry import (
    Point,
    LineString,
    Polygon,
    MultiPoint,
    MultiLineString,
    MultiPolygon,
)
from shapely.validation import make_valid

from entmoot.core.constraints.buffers import (
    BufferGenerator,
    BufferConfig,
    BufferStyle,
    RoadType,
    WaterFeatureType,
    PROPERTY_LINE_SETBACK,
    ROAD_SETBACK,
    WATER_FEATURE_SETBACK,
    UTILITY_SETBACK,
    create_buffer_from_config,
)
from entmoot.models.constraints import (
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
    SetbackConstraint,
    RegulatoryConstraint,
)


class TestBufferConfig:
    """Test BufferConfig configuration class."""

    def test_create_basic_config(self):
        """Test creating basic buffer configuration."""
        config = BufferConfig(distance_m=10.0)

        assert config.distance_m == 10.0
        assert config.style == BufferStyle.ROUND
        assert config.simplify_tolerance == 0.0
        assert config.resolution == 16

    def test_config_with_style(self):
        """Test buffer config with different styles."""
        config_round = BufferConfig(distance_m=10.0, style=BufferStyle.ROUND)
        assert config_round.cap_style == 1

        config_flat = BufferConfig(distance_m=10.0, style=BufferStyle.FLAT)
        assert config_flat.cap_style == 2

        config_square = BufferConfig(distance_m=10.0, style=BufferStyle.SQUARE)
        assert config_square.cap_style == 3

    def test_config_with_simplification(self):
        """Test buffer config with simplification."""
        config = BufferConfig(
            distance_m=10.0,
            simplify_tolerance=0.5
        )

        assert config.simplify_tolerance == 0.5

    def test_invalid_distance_raises_error(self):
        """Test that negative or zero distance raises error."""
        with pytest.raises(ValueError, match="Buffer distance must be positive"):
            BufferConfig(distance_m=0.0)

        with pytest.raises(ValueError, match="Buffer distance must be positive"):
            BufferConfig(distance_m=-10.0)

    def test_negative_tolerance_normalized(self):
        """Test that negative tolerance is normalized to 0."""
        config = BufferConfig(distance_m=10.0, simplify_tolerance=-1.0)
        assert config.simplify_tolerance == 0.0


class TestBufferGenerator:
    """Test BufferGenerator main class."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def simple_line(self):
        """Create a simple line for testing."""
        return LineString([(0, 0), (100, 0)])

    @pytest.fixture
    def simple_polygon(self):
        """Create a simple polygon for testing."""
        return Polygon([
            (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
        ])

    @pytest.fixture
    def property_boundary(self):
        """Create a property boundary polygon."""
        return Polygon([
            (0, 0), (200, 0), (200, 200), (0, 200), (0, 0)
        ])

    def test_create_basic_buffer(self, generator, simple_line):
        """Test creating a basic buffer around a line."""
        config = BufferConfig(distance_m=10.0)
        buffer = generator.create_buffer(simple_line, config)

        assert buffer is not None
        assert buffer.is_valid
        assert buffer.area > 0
        # Buffer should contain the original line
        assert buffer.contains(simple_line)

    def test_create_buffer_around_polygon(self, generator, simple_polygon):
        """Test creating a buffer around a polygon."""
        config = BufferConfig(distance_m=10.0)
        buffer = generator.create_buffer(simple_polygon, config)

        assert buffer.is_valid
        assert buffer.contains(simple_polygon)
        # Buffered polygon should be larger
        assert buffer.area > simple_polygon.area

    def test_inward_buffer(self, generator, simple_polygon):
        """Test creating an inward (negative) buffer."""
        config = BufferConfig(distance_m=5.0)
        buffer = generator.create_buffer(simple_polygon, config, inward=True)

        assert buffer.is_valid
        # Inward buffer should be smaller
        assert buffer.area < simple_polygon.area
        # Original polygon should contain the buffer
        assert simple_polygon.contains(buffer)

    def test_buffer_with_flat_caps(self, generator, simple_line):
        """Test buffer with flat end caps."""
        config = BufferConfig(
            distance_m=10.0,
            style=BufferStyle.FLAT
        )
        buffer = generator.create_buffer(simple_line, config)

        assert buffer.is_valid
        assert config.cap_style == 2  # Flat caps

    def test_buffer_with_square_caps(self, generator, simple_line):
        """Test buffer with square end caps."""
        config = BufferConfig(
            distance_m=10.0,
            style=BufferStyle.SQUARE
        )
        buffer = generator.create_buffer(simple_line, config)

        assert buffer.is_valid
        assert config.cap_style == 3  # Square caps

    def test_buffer_simplification(self, generator, simple_polygon):
        """Test buffer geometry simplification."""
        config_no_simplify = BufferConfig(distance_m=10.0, simplify_tolerance=0.0)
        buffer_complex = generator.create_buffer(simple_polygon, config_no_simplify)

        config_simplify = BufferConfig(distance_m=10.0, simplify_tolerance=2.0)
        buffer_simple = generator.create_buffer(simple_polygon, config_simplify)

        assert buffer_simple.is_valid
        # Simplified version should have fewer vertices
        if hasattr(buffer_complex, 'exterior') and hasattr(buffer_simple, 'exterior'):
            assert len(buffer_simple.exterior.coords) <= len(buffer_complex.exterior.coords)

    def test_auto_repair_invalid_geometry(self, generator):
        """Test automatic repair of invalid geometries."""
        # Create a self-intersecting polygon (bowtie)
        invalid_polygon = Polygon([
            (0, 0), (100, 100), (100, 0), (0, 100), (0, 0)
        ])

        config = BufferConfig(distance_m=5.0)

        # Generator with auto_repair should handle it
        buffer = generator.create_buffer(invalid_polygon, config)
        assert buffer.is_valid

    def test_buffer_validation_enabled(self):
        """Test that validation catches issues."""
        generator = BufferGenerator(auto_validate=True, auto_repair=False)

        # Try to buffer an invalid geometry
        invalid_polygon = Polygon([
            (0, 0), (100, 100), (100, 0), (0, 100), (0, 0)
        ])

        config = BufferConfig(distance_m=5.0)

        # Should raise ValueError due to invalid input
        with pytest.raises(ValueError, match="invalid"):
            generator.create_buffer(invalid_polygon, config)


class TestMultiBuffer:
    """Test multi-geometry buffer operations."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def multiple_lines(self):
        """Create multiple lines for testing."""
        return [
            LineString([(0, 0), (50, 0)]),
            LineString([(60, 0), (100, 0)]),
            LineString([(0, 20), (50, 20)]),
        ]

    def test_create_multi_buffer_merged(self, generator, multiple_lines):
        """Test creating merged buffer from multiple geometries."""
        config = BufferConfig(distance_m=5.0)
        buffer = generator.create_multi_buffer(multiple_lines, config, merge=True)

        assert buffer.is_valid
        # Should be a single geometry (possibly MultiPolygon)
        assert hasattr(buffer, 'area')
        assert buffer.area > 0

    def test_create_multi_buffer_separate(self, generator, multiple_lines):
        """Test creating separate buffers for each geometry."""
        config = BufferConfig(distance_m=5.0)
        buffers = generator.create_multi_buffer(multiple_lines, config, merge=False)

        assert isinstance(buffers, list)
        assert len(buffers) == 3
        for buffer in buffers:
            assert buffer.is_valid

    def test_multi_buffer_with_overlaps(self, generator):
        """Test multi-buffer with overlapping geometries."""
        # Create overlapping lines
        lines = [
            LineString([(0, 0), (100, 0)]),
            LineString([(50, 0), (150, 0)]),
        ]

        config = BufferConfig(distance_m=10.0)
        merged_buffer = generator.create_multi_buffer(lines, config, merge=True)

        assert merged_buffer.is_valid
        # Merged should be a single polygon
        assert merged_buffer.geom_type in ['Polygon', 'MultiPolygon']

    def test_multi_buffer_empty_list_raises_error(self, generator):
        """Test that empty geometry list raises error."""
        config = BufferConfig(distance_m=10.0)

        with pytest.raises(ValueError, match="No geometries provided"):
            generator.create_multi_buffer([], config)


class TestPropertySetback:
    """Test property line setback creation."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def property_boundary(self):
        """Create a property boundary."""
        return Polygon([
            (0, 0), (200, 0), (200, 200), (0, 200), (0, 0)
        ])

    def test_create_default_property_setback(self, generator, property_boundary):
        """Test creating default property setback."""
        constraint = generator.create_property_setback(
            property_boundary=property_boundary,
            constraint_id="prop_001",
        )

        assert isinstance(constraint, SetbackConstraint)
        assert constraint.id == "prop_001"
        assert constraint.constraint_type == ConstraintType.PROPERTY_LINE
        assert constraint.severity == ConstraintSeverity.BLOCKING
        assert constraint.priority == ConstraintPriority.HIGH
        assert constraint.setback_distance_m == PROPERTY_LINE_SETBACK["default"]

    def test_create_front_setback(self, generator, property_boundary):
        """Test creating front property setback."""
        constraint = generator.create_property_setback(
            property_boundary=property_boundary,
            constraint_id="prop_002",
            setback_type="front",
        )

        assert constraint.setback_distance_m == PROPERTY_LINE_SETBACK["front"]
        assert "front" in constraint.name.lower()

    def test_create_side_setback(self, generator, property_boundary):
        """Test creating side property setback."""
        constraint = generator.create_property_setback(
            property_boundary=property_boundary,
            constraint_id="prop_003",
            setback_type="side",
        )

        assert constraint.setback_distance_m == PROPERTY_LINE_SETBACK["side"]

    def test_create_rear_setback(self, generator, property_boundary):
        """Test creating rear property setback."""
        constraint = generator.create_property_setback(
            property_boundary=property_boundary,
            constraint_id="prop_004",
            setback_type="rear",
        )

        assert constraint.setback_distance_m == PROPERTY_LINE_SETBACK["rear"]

    def test_property_setback_with_override(self, generator, property_boundary):
        """Test property setback with custom distance."""
        custom_distance = 15.0

        constraint = generator.create_property_setback(
            property_boundary=property_boundary,
            constraint_id="prop_005",
            setback_distance=custom_distance,
        )

        assert constraint.setback_distance_m == custom_distance

    def test_property_setback_geometry_valid(self, generator, property_boundary):
        """Test that property setback geometry is valid and inward."""
        constraint = generator.create_property_setback(
            property_boundary=property_boundary,
            constraint_id="prop_006",
        )

        buffer_geom = constraint.get_geometry()
        assert buffer_geom.is_valid

        # Inward buffer should be smaller than original
        assert buffer_geom.area < property_boundary.area


class TestRoadSetback:
    """Test road setback creation."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def road_centerline(self):
        """Create a road centerline."""
        return LineString([(0, 0), (100, 0), (150, 50)])

    def test_create_major_road_setback(self, generator, road_centerline):
        """Test creating major road setback."""
        constraint = generator.create_road_setback(
            road_geometry=road_centerline,
            constraint_id="road_001",
            road_type=RoadType.MAJOR,
        )

        assert isinstance(constraint, SetbackConstraint)
        assert constraint.constraint_type == ConstraintType.ROAD
        assert constraint.setback_distance_m == ROAD_SETBACK[RoadType.MAJOR]
        assert "major" in constraint.name.lower()
        assert constraint.metadata["road_type"] == RoadType.MAJOR.value

    def test_create_local_road_setback(self, generator, road_centerline):
        """Test creating local road setback."""
        constraint = generator.create_road_setback(
            road_geometry=road_centerline,
            constraint_id="road_002",
            road_type=RoadType.LOCAL,
        )

        assert constraint.setback_distance_m == ROAD_SETBACK[RoadType.LOCAL]
        assert "local" in constraint.name.lower()

    def test_create_driveway_setback(self, generator, road_centerline):
        """Test creating driveway setback."""
        constraint = generator.create_road_setback(
            road_geometry=road_centerline,
            constraint_id="road_003",
            road_type=RoadType.DRIVEWAY,
        )

        assert constraint.setback_distance_m == ROAD_SETBACK[RoadType.DRIVEWAY]
        assert "driveway" in constraint.name.lower()

    def test_create_collector_road_setback(self, generator, road_centerline):
        """Test creating collector road setback."""
        constraint = generator.create_road_setback(
            road_geometry=road_centerline,
            constraint_id="road_004",
            road_type=RoadType.COLLECTOR,
        )

        assert constraint.setback_distance_m == ROAD_SETBACK[RoadType.COLLECTOR]

    def test_road_setback_with_override(self, generator, road_centerline):
        """Test road setback with custom distance."""
        custom_distance = 25.0

        constraint = generator.create_road_setback(
            road_geometry=road_centerline,
            constraint_id="road_005",
            road_type=RoadType.LOCAL,
            setback_distance=custom_distance,
        )

        assert constraint.setback_distance_m == custom_distance

    def test_road_setback_geometry_valid(self, generator, road_centerline):
        """Test that road setback geometry is valid."""
        constraint = generator.create_road_setback(
            road_geometry=road_centerline,
            constraint_id="road_006",
            road_type=RoadType.LOCAL,
        )

        buffer_geom = constraint.get_geometry()
        assert buffer_geom.is_valid
        assert buffer_geom.contains(road_centerline)


class TestWaterFeatureSetback:
    """Test water feature setback creation."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def stream_line(self):
        """Create a stream centerline."""
        return LineString([
            (0, 0), (50, 10), (100, 5), (150, 20)
        ])

    @pytest.fixture
    def pond_polygon(self):
        """Create a pond polygon."""
        return Polygon([
            (0, 0), (50, 0), (50, 50), (0, 50), (0, 0)
        ])

    def test_create_stream_setback(self, generator, stream_line):
        """Test creating stream setback."""
        constraint = generator.create_water_feature_setback(
            water_geometry=stream_line,
            constraint_id="water_001",
            feature_type=WaterFeatureType.STREAM,
        )

        assert isinstance(constraint, RegulatoryConstraint)
        assert constraint.constraint_type == ConstraintType.WATER_FEATURE
        assert constraint.severity == ConstraintSeverity.BLOCKING
        assert constraint.priority == ConstraintPriority.CRITICAL
        assert constraint.metadata["setback_distance_m"] == WATER_FEATURE_SETBACK[WaterFeatureType.STREAM]
        assert "stream" in constraint.name.lower()

    def test_create_river_setback(self, generator, stream_line):
        """Test creating river setback."""
        constraint = generator.create_water_feature_setback(
            water_geometry=stream_line,
            constraint_id="water_002",
            feature_type=WaterFeatureType.RIVER,
        )

        assert constraint.metadata["setback_distance_m"] == WATER_FEATURE_SETBACK[WaterFeatureType.RIVER]
        assert "river" in constraint.name.lower()

    def test_create_pond_setback(self, generator, pond_polygon):
        """Test creating pond setback."""
        constraint = generator.create_water_feature_setback(
            water_geometry=pond_polygon,
            constraint_id="water_003",
            feature_type=WaterFeatureType.POND,
        )

        assert constraint.metadata["setback_distance_m"] == WATER_FEATURE_SETBACK[WaterFeatureType.POND]
        assert "pond" in constraint.name.lower()

    def test_create_wetland_setback(self, generator, pond_polygon):
        """Test creating wetland setback."""
        constraint = generator.create_water_feature_setback(
            water_geometry=pond_polygon,
            constraint_id="water_004",
            feature_type=WaterFeatureType.WETLAND,
        )

        assert constraint.metadata["setback_distance_m"] == WATER_FEATURE_SETBACK[WaterFeatureType.WETLAND]
        assert "wetland" in constraint.name.lower()

    def test_water_setback_regulatory_info(self, generator, stream_line):
        """Test that water setback has proper regulatory information."""
        constraint = generator.create_water_feature_setback(
            water_geometry=stream_line,
            constraint_id="water_005",
            feature_type=WaterFeatureType.STREAM,
        )

        assert constraint.regulation_name is not None
        assert constraint.authority is not None
        assert "Federal" in constraint.authority or "EPA" in constraint.authority
        assert constraint.compliance_requirement is not None

    def test_water_setback_custom_regulatory_info(self, generator, stream_line):
        """Test water setback with custom regulatory information."""
        custom_reg = {
            "regulation_name": "State Water Protection Act",
            "authority": "State DEP",
            "regulation_code": "State Code 123.45",
            "data_source": "State GIS Database",
        }

        constraint = generator.create_water_feature_setback(
            water_geometry=stream_line,
            constraint_id="water_006",
            feature_type=WaterFeatureType.STREAM,
            regulatory_info=custom_reg,
        )

        assert constraint.regulation_name == "State Water Protection Act"
        assert constraint.authority == "State DEP"
        assert constraint.regulation_code == "State Code 123.45"

    def test_water_setback_with_override(self, generator, stream_line):
        """Test water setback with custom distance."""
        custom_distance = 50.0

        constraint = generator.create_water_feature_setback(
            water_geometry=stream_line,
            constraint_id="water_007",
            feature_type=WaterFeatureType.STREAM,
            setback_distance=custom_distance,
        )

        assert constraint.metadata["setback_distance_m"] == custom_distance


class TestUtilitySetback:
    """Test utility corridor setback creation."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def power_line(self):
        """Create a power line."""
        return LineString([
            (0, 0), (100, 0), (200, 50)
        ])

    def test_create_power_line_setback(self, generator, power_line):
        """Test creating power line setback."""
        constraint = generator.create_utility_setback(
            utility_geometry=power_line,
            constraint_id="util_001",
            utility_type="power_line",
        )

        assert isinstance(constraint, SetbackConstraint)
        assert constraint.constraint_type == ConstraintType.UTILITY
        assert constraint.setback_distance_m == UTILITY_SETBACK["power_line"]
        assert "power line" in constraint.name.lower()
        assert constraint.metadata["utility_type"] == "power_line"

    def test_create_high_voltage_setback(self, generator, power_line):
        """Test creating high voltage line setback."""
        constraint = generator.create_utility_setback(
            utility_geometry=power_line,
            constraint_id="util_002",
            utility_type="high_voltage",
        )

        assert constraint.setback_distance_m == UTILITY_SETBACK["high_voltage"]

    def test_create_pipeline_setback(self, generator, power_line):
        """Test creating pipeline setback."""
        constraint = generator.create_utility_setback(
            utility_geometry=power_line,
            constraint_id="util_003",
            utility_type="pipeline",
        )

        assert constraint.setback_distance_m == UTILITY_SETBACK["pipeline"]

    def test_create_gas_line_setback(self, generator, power_line):
        """Test creating gas line setback."""
        constraint = generator.create_utility_setback(
            utility_geometry=power_line,
            constraint_id="util_004",
            utility_type="gas_line",
        )

        assert constraint.setback_distance_m == UTILITY_SETBACK["gas_line"]

    def test_create_default_utility_setback(self, generator, power_line):
        """Test creating default utility setback."""
        constraint = generator.create_utility_setback(
            utility_geometry=power_line,
            constraint_id="util_005",
            utility_type="unknown_type",
        )

        assert constraint.setback_distance_m == UTILITY_SETBACK["default"]

    def test_utility_setback_with_override(self, generator, power_line):
        """Test utility setback with custom distance."""
        custom_distance = 20.0

        constraint = generator.create_utility_setback(
            utility_geometry=power_line,
            constraint_id="util_006",
            utility_type="power_line",
            setback_distance=custom_distance,
        )

        assert constraint.setback_distance_m == custom_distance


class TestBufferValidation:
    """Test buffer validation functionality."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def simple_line(self):
        """Create a simple line."""
        return LineString([(0, 0), (100, 0)])

    def test_validate_valid_buffer(self, generator, simple_line):
        """Test validating a valid buffer."""
        config = BufferConfig(distance_m=10.0)
        buffer = generator.create_buffer(simple_line, config)

        is_valid, issues = generator.validate_buffer(buffer, simple_line, 10.0)

        assert is_valid
        # May have warnings but should be valid
        for issue in issues:
            assert "invalid" not in issue.lower()
            assert "empty" not in issue.lower()

    def test_validate_empty_buffer(self, generator, simple_line):
        """Test validation catches empty buffers."""
        from shapely.geometry import Polygon

        empty_geom = Polygon()  # Empty polygon

        is_valid, issues = generator.validate_buffer(empty_geom, simple_line, 10.0)

        assert not is_valid
        assert any("empty" in issue.lower() for issue in issues)

    def test_validate_invalid_buffer(self, generator, simple_line):
        """Test validation catches invalid geometry."""
        # Create an invalid polygon
        invalid_polygon = Polygon([
            (0, 0), (10, 10), (10, 0), (0, 10), (0, 0)
        ])

        is_valid, issues = generator.validate_buffer(invalid_polygon, simple_line, 10.0)

        # Should have issues
        assert len(issues) > 0


class TestBufferSimplification:
    """Test buffer simplification."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    @pytest.fixture
    def complex_polygon(self):
        """Create a complex polygon with many vertices."""
        # Create a circle approximation with many points
        import math
        points = []
        for i in range(100):
            angle = 2 * math.pi * i / 100
            x = 50 + 40 * math.cos(angle)
            y = 50 + 40 * math.sin(angle)
            points.append((x, y))
        points.append(points[0])  # Close the ring
        return Polygon(points)

    def test_simplify_buffer(self, generator, complex_polygon):
        """Test simplifying a complex buffer."""
        original_vertices = len(complex_polygon.exterior.coords)

        simplified = generator.simplify_buffer(complex_polygon, tolerance=2.0)

        assert simplified.is_valid
        simplified_vertices = len(simplified.exterior.coords)
        assert simplified_vertices < original_vertices

    def test_simplify_preserves_topology(self, generator, complex_polygon):
        """Test that simplification preserves topology."""
        simplified = generator.simplify_buffer(
            complex_polygon,
            tolerance=1.0,
            preserve_topology=True
        )

        assert simplified.is_valid
        # Simplified geometry should still roughly match original
        assert simplified.area > 0
        # Check overlap is significant
        intersection = complex_polygon.intersection(simplified)
        assert intersection.area > 0.9 * min(complex_polygon.area, simplified.area)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def generator(self):
        """Create a buffer generator instance."""
        return BufferGenerator()

    def test_buffer_very_small_geometry(self, generator):
        """Test buffering very small geometry."""
        tiny_line = LineString([(0, 0), (0.001, 0)])
        config = BufferConfig(distance_m=10.0)

        buffer = generator.create_buffer(tiny_line, config)
        assert buffer.is_valid
        assert buffer.area > 0

    def test_buffer_with_large_distance(self, generator):
        """Test buffer with very large distance."""
        line = LineString([(0, 0), (10, 0)])
        config = BufferConfig(distance_m=1000.0)

        buffer = generator.create_buffer(line, config)
        assert buffer.is_valid
        assert buffer.area > 0

    def test_inward_buffer_larger_than_geometry(self, generator):
        """Test inward buffer that's larger than the geometry."""
        small_polygon = Polygon([
            (0, 0), (10, 0), (10, 10), (0, 10), (0, 0)
        ])

        # Try to create inward buffer larger than polygon
        config = BufferConfig(distance_m=20.0)  # Larger than polygon

        # This might result in empty geometry or very small geometry
        try:
            buffer = generator.create_buffer(small_polygon, config, inward=True)
            # If it succeeds, buffer should be much smaller or empty
            if not buffer.is_empty:
                assert buffer.area < small_polygon.area
        except ValueError:
            # Expected to fail with empty geometry
            pass

    def test_multipart_geometry_buffer(self, generator):
        """Test buffering multipart geometries."""
        multi_line = MultiLineString([
            [(0, 0), (10, 0)],
            [(20, 0), (30, 0)],
            [(0, 20), (10, 20)],
        ])

        config = BufferConfig(distance_m=5.0)
        buffer = generator.create_buffer(multi_line, config)

        assert buffer.is_valid
        assert buffer.area > 0


class TestConvenienceFunction:
    """Test convenience function for buffer creation."""

    def test_create_buffer_from_config(self):
        """Test the convenience function."""
        line = LineString([(0, 0), (100, 0)])

        buffer = create_buffer_from_config(
            geometry=line,
            distance_m=10.0,
            style="round",
        )

        assert buffer.is_valid
        assert buffer.area > 0
        assert buffer.contains(line)

    def test_create_buffer_with_simplification(self):
        """Test convenience function with simplification."""
        line = LineString([(0, 0), (100, 0)])

        buffer = create_buffer_from_config(
            geometry=line,
            distance_m=10.0,
            style="flat",
            simplify_tolerance=1.0,
        )

        assert buffer.is_valid

    def test_create_buffer_invalid_style(self):
        """Test convenience function with invalid style."""
        line = LineString([(0, 0), (100, 0)])

        with pytest.raises(ValueError):
            create_buffer_from_config(
                geometry=line,
                distance_m=10.0,
                style="invalid_style",
            )


class TestStandardDistances:
    """Test standard distance configurations."""

    def test_property_line_setback_defaults(self):
        """Test property line setback standard distances."""
        assert PROPERTY_LINE_SETBACK["default"] > 0
        assert PROPERTY_LINE_SETBACK["front"] > 0
        assert PROPERTY_LINE_SETBACK["side"] > 0
        assert PROPERTY_LINE_SETBACK["rear"] > 0

    def test_road_setback_defaults(self):
        """Test road setback standard distances."""
        assert ROAD_SETBACK[RoadType.MAJOR] > ROAD_SETBACK[RoadType.LOCAL]
        assert ROAD_SETBACK[RoadType.LOCAL] > ROAD_SETBACK[RoadType.DRIVEWAY]
        # Major roads should have largest setback
        assert ROAD_SETBACK[RoadType.MAJOR] == max(ROAD_SETBACK.values())

    def test_water_feature_setback_defaults(self):
        """Test water feature setback standard distances."""
        # Stream setback should be significant (federal requirement)
        assert WATER_FEATURE_SETBACK[WaterFeatureType.STREAM] >= 30.48  # At least 100 feet
        assert WATER_FEATURE_SETBACK[WaterFeatureType.RIVER] > 0
        assert WATER_FEATURE_SETBACK[WaterFeatureType.WETLAND] > 0

    def test_utility_setback_defaults(self):
        """Test utility setback standard distances."""
        assert UTILITY_SETBACK["high_voltage"] > UTILITY_SETBACK["power_line"]
        assert UTILITY_SETBACK["default"] > 0

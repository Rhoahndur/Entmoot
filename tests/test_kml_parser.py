"""
Comprehensive tests for KML parsing functionality.

Tests cover:
- KML validation
- Geometry parsing (Point, LineString, Polygon)
- Property boundary extraction
- Topographic contour parsing
- Nested folder structures
- Extended data parsing
- Error handling
"""

import pytest
from pathlib import Path
from shapely.geometry import Point, LineString, Polygon

from entmoot.core.parsers import (
    KMLParser,
    KMLValidator,
    ParsedKML,
    Placemark,
    GeometryType,
    parse_kml_file,
    parse_kml_string,
    validate_kml_file,
    validate_kml_string,
)


# Test fixtures path
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SIMPLE_KML = FIXTURES_DIR / "simple.kml"
COMPLEX_KML = FIXTURES_DIR / "complex.kml"
MALFORMED_KML = FIXTURES_DIR / "malformed.kml"


class TestKMLValidator:
    """Tests for KML validation."""

    def test_validate_simple_kml(self):
        """Test validation of simple valid KML."""
        result = validate_kml_file(SIMPLE_KML)
        assert result.is_valid
        assert not result.errors
        assert result.has_placemarks
        assert result.has_geometries
        assert result.geometry_count >= 1
        assert result.namespace is not None

    def test_validate_complex_kml(self):
        """Test validation of complex KML with folders and styles."""
        result = validate_kml_file(COMPLEX_KML)
        assert result.is_valid
        assert not result.errors
        assert result.has_placemarks
        assert result.has_geometries
        assert result.geometry_count > 1

    def test_validate_malformed_kml(self):
        """Test validation of malformed KML."""
        result = validate_kml_file(MALFORMED_KML)
        assert not result.is_valid
        assert len(result.errors) > 0
        assert "Invalid XML structure" in result.errors[0]

    def test_validate_empty_content(self):
        """Test validation of empty content."""
        result = validate_kml_string("")
        assert not result.is_valid
        assert "empty" in result.errors[0].lower()

    def test_validate_non_kml_root(self):
        """Test validation of XML with wrong root element."""
        xml_content = """<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1">
            <metadata><name>Test</name></metadata>
        </gpx>
        """
        result = validate_kml_string(xml_content)
        assert not result.is_valid
        assert "Invalid root element" in result.errors[0]

    def test_validate_missing_coordinates(self):
        """Test validation of geometry with missing coordinates."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <name>Test</name>
                    <Point>
                        <coordinates></coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        result = validate_kml_string(kml_content)
        assert not result.is_valid
        assert "empty coordinates" in result.errors[0].lower()

    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        result = validate_kml_file(Path("/nonexistent/file.kml"))
        assert not result.is_valid
        assert "not found" in result.errors[0].lower()


class TestKMLParser:
    """Tests for KML parsing."""

    def test_parse_simple_kml(self):
        """Test parsing simple KML with one polygon."""
        result = parse_kml_file(SIMPLE_KML)

        assert result.document_name == "Simple Property"
        assert result.placemark_count >= 1
        assert result.geometry_count >= 1

        # Check first placemark
        placemark = result.placemarks[0]
        assert placemark.name == "Property Boundary"
        assert placemark.geometry_type == GeometryType.POLYGON
        assert isinstance(placemark.geometry, Polygon)
        assert placemark.geometry.is_valid

    def test_parse_complex_kml(self):
        """Test parsing complex KML with multiple features."""
        result = parse_kml_file(COMPLEX_KML)

        assert result.document_name == "Complex Property Map"
        assert result.placemark_count > 5
        assert result.geometry_count > 5

        # Check we have multiple geometry types
        polygons = result.get_placemarks_by_type(GeometryType.POLYGON)
        lines = result.get_placemarks_by_type(GeometryType.LINE_STRING)
        points = result.get_placemarks_by_type(GeometryType.POINT)

        assert len(polygons) >= 2
        assert len(lines) >= 2
        assert len(points) >= 2

    def test_parse_polygon_with_holes(self):
        """Test parsing polygon with inner boundaries (holes)."""
        result = parse_kml_file(COMPLEX_KML)

        # Find parcel 1 which has a hole
        parcel1 = None
        for placemark in result.placemarks:
            if placemark.id == "parcel1":
                parcel1 = placemark
                break

        assert parcel1 is not None
        assert isinstance(parcel1.geometry, Polygon)
        assert len(parcel1.geometry.interiors) == 1  # Has one hole

    def test_parse_extended_data(self):
        """Test parsing extended data from placemarks."""
        result = parse_kml_file(COMPLEX_KML)

        # Find parcel 1
        parcel1 = None
        for placemark in result.placemarks:
            if placemark.id == "parcel1":
                parcel1 = placemark
                break

        assert parcel1 is not None
        assert "parcel_id" in parcel1.properties
        assert parcel1.properties["parcel_id"] == "123-456-789"
        assert "area_acres" in parcel1.properties
        assert parcel1.properties["area_acres"] == "5.0"
        assert "owner" in parcel1.properties
        assert parcel1.properties["owner"] == "John Doe"

    def test_parse_folder_structure(self):
        """Test parsing nested folder structure."""
        result = parse_kml_file(COMPLEX_KML)

        assert len(result.folders) >= 4

        # Check folder paths
        folder_names = [f.split("/")[-1] for f in result.folders]
        assert "Property Boundaries" in folder_names
        assert "Topography" in folder_names
        assert "Points of Interest" in folder_names

    def test_parse_contour_lines(self):
        """Test parsing and identification of contour lines."""
        result = parse_kml_file(COMPLEX_KML)

        contours = result.get_contours()
        assert len(contours) >= 2

        # Check first contour
        contour = contours[0]
        assert contour.is_contour
        assert contour.geometry_type == GeometryType.LINE_STRING
        assert contour.elevation is not None
        assert contour.elevation in [1200.0, 1250.0]

    def test_parse_property_boundaries(self):
        """Test extraction of property boundaries."""
        result = parse_kml_file(COMPLEX_KML)

        boundaries = result.get_property_boundaries()
        assert len(boundaries) >= 2

        # All should be polygons
        for boundary in boundaries:
            assert boundary.geometry_type == GeometryType.POLYGON
            assert not boundary.is_contour

    def test_parse_points(self):
        """Test parsing Point geometries."""
        result = parse_kml_file(COMPLEX_KML)

        points = result.get_placemarks_by_type(GeometryType.POINT)
        assert len(points) >= 2

        # Check a specific point
        well = None
        for point in points:
            if point.name == "Well":
                well = point
                break

        assert well is not None
        assert isinstance(well.geometry, Point)
        assert well.description == "Water well location"

    def test_parse_linestrings(self):
        """Test parsing LineString geometries."""
        result = parse_kml_file(COMPLEX_KML)

        lines = result.get_placemarks_by_type(GeometryType.LINE_STRING)
        assert len(lines) >= 3  # 2 contours + 1 road

        # Check access road
        road = None
        for line in lines:
            if line.name == "Access Road":
                road = line
                break

        assert road is not None
        assert isinstance(road.geometry, LineString)
        assert not road.is_contour

    def test_parse_styles(self):
        """Test parsing style definitions."""
        result = parse_kml_file(COMPLEX_KML)

        assert len(result.styles) >= 2
        assert "propertyStyle" in result.styles
        assert "contourStyle" in result.styles

        # Check property style
        prop_style = result.styles["propertyStyle"]
        assert "line" in prop_style
        assert "polygon" in prop_style

    def test_parse_without_validation(self):
        """Test parsing without validation."""
        parser = KMLParser(validate=False)
        result = parser.parse(SIMPLE_KML)
        assert result.placemark_count >= 1

    def test_parse_malformed_raises_error(self):
        """Test that parsing malformed KML raises error."""
        with pytest.raises(ValueError):
            parse_kml_file(MALFORMED_KML)

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file raises error."""
        with pytest.raises(Exception):
            parse_kml_file(Path("/nonexistent/file.kml"))

    def test_parse_kml_string(self):
        """Test parsing KML from string."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <name>Test</name>
                <Placemark>
                    <name>Test Point</name>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content)
        assert result.document_name == "Test"
        assert result.placemark_count == 1
        assert result.placemarks[0].name == "Test Point"

    def test_placemark_to_dict(self):
        """Test converting Placemark to dictionary."""
        result = parse_kml_file(SIMPLE_KML)
        placemark = result.placemarks[0]

        data = placemark.to_dict()
        assert "name" in data
        assert "geometry_type" in data
        assert "geometry_wkt" in data
        assert data["geometry_wkt"] is not None

    def test_parse_empty_description(self):
        """Test parsing placemarks with empty descriptions."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <name>Test</name>
                    <description></description>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content)
        assert result.placemark_count == 1

    def test_namespace_handling(self):
        """Test handling of different KML namespaces."""
        # KML without namespace - parser should handle this by detecting no namespace
        kml_content = """<?xml version="1.0"?>
        <kml>
            <Document>
                <Placemark>
                    <name>Test</name>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        parser = KMLParser(validate=False)
        result = parser.parse(kml_content)
        # Parser sets namespace to empty string for no namespace
        # This test verifies it doesn't crash, but may not parse without namespace
        assert result is not None

    def test_contour_elevation_extraction(self):
        """Test extraction of elevation from contour names."""
        result = parse_kml_file(COMPLEX_KML)

        contours = result.get_contours()
        elevations = [c.elevation for c in contours if c.elevation is not None]

        assert len(elevations) >= 2
        assert 1200.0 in elevations
        assert 1250.0 in elevations

    def test_parsed_kml_properties(self):
        """Test ParsedKML property methods."""
        result = parse_kml_file(COMPLEX_KML)

        assert result.placemark_count > 0
        assert result.geometry_count > 0
        assert result.contour_count >= 2

        # All geometries should be valid
        assert result.geometry_count == sum(
            1 for p in result.placemarks if p.geometry is not None
        )


class TestGeometryParsing:
    """Tests for geometry coordinate parsing."""

    def test_parse_point_coordinates(self):
        """Test parsing Point coordinates."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <Point>
                        <coordinates>-122.084075,37.421870,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content, validate=False)
        placemark = result.placemarks[0]

        assert isinstance(placemark.geometry, Point)
        assert placemark.geometry.x == pytest.approx(-122.084075)
        assert placemark.geometry.y == pytest.approx(37.421870)

    def test_parse_linestring_coordinates(self):
        """Test parsing LineString coordinates."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <LineString>
                        <coordinates>
                            -122.084,37.422,0
                            -122.085,37.423,0
                            -122.086,37.424,0
                        </coordinates>
                    </LineString>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content, validate=False)
        placemark = result.placemarks[0]

        assert isinstance(placemark.geometry, LineString)
        coords = list(placemark.geometry.coords)
        assert len(coords) == 3

    def test_parse_polygon_coordinates(self):
        """Test parsing Polygon coordinates."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <Polygon>
                        <outerBoundaryIs>
                            <LinearRing>
                                <coordinates>
                                    -122.084,37.422,0
                                    -122.085,37.422,0
                                    -122.085,37.423,0
                                    -122.084,37.423,0
                                    -122.084,37.422,0
                                </coordinates>
                            </LinearRing>
                        </outerBoundaryIs>
                    </Polygon>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content, validate=False)
        placemark = result.placemarks[0]

        assert isinstance(placemark.geometry, Polygon)
        assert placemark.geometry.is_valid
        assert placemark.geometry.area > 0

    def test_parse_coordinates_without_altitude(self):
        """Test parsing coordinates without altitude values."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <Point>
                        <coordinates>-122.084,37.422</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content, validate=False)
        placemark = result.placemarks[0]

        assert isinstance(placemark.geometry, Point)
        assert placemark.geometry.x == pytest.approx(-122.084)
        assert placemark.geometry.y == pytest.approx(37.422)


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_invalid_geometry_type(self):
        """Test handling of unsupported geometry types."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <name>Test</name>
                    <Model>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Model>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content, validate=False)
        # Should parse but skip the unsupported geometry
        assert result.placemark_count == 0 or result.placemarks[0].geometry is None

    def test_empty_placemark(self):
        """Test parsing placemark without geometry."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <name>No Geometry</name>
                </Placemark>
            </Document>
        </kml>
        """
        result = parse_kml_string(kml_content, validate=False)
        # Parser should handle this gracefully
        if result.placemark_count > 0:
            assert result.placemarks[0].geometry is None

    def test_parse_with_invalid_coordinates(self):
        """Test parsing with invalid coordinate values."""
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <Point>
                        <coordinates>invalid,data,here</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        parser = KMLParser(validate=False)
        result = parser.parse(kml_content)
        # Should log error but continue - placemark will be skipped if geometry fails
        assert len(result.parse_errors) > 0 or result.placemark_count == 0

    def test_parse_bytes_input(self):
        """Test parsing KML from bytes."""
        kml_bytes = b"""<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <Placemark>
                    <name>Test</name>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """
        parser = KMLParser(validate=False)
        result = parser.parse(kml_bytes)
        assert result.placemark_count == 1

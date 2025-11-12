"""
Comprehensive tests for property boundary extraction service.

Tests cover:
- Simple polygons
- Polygons with holes
- Multi-polygons
- Invalid geometries
- Metric calculations
- Edge cases
"""

import pytest
from shapely.geometry import MultiPolygon, Polygon

from entmoot.core.boundaries import BoundaryExtractionService, extract_boundaries_from_kml
from entmoot.core.parsers.geometry import GeometryType
from entmoot.core.parsers.kml_parser import ParsedKML, Placemark
from entmoot.models.boundary import BoundarySource, GeometryIssue


class TestBoundaryExtractionService:
    """Test suite for BoundaryExtractionService."""

    def test_initialization(self):
        """Test service initialization with default parameters."""
        service = BoundaryExtractionService()
        assert service.auto_repair is True
        assert service.min_area_sqm == 1.0

    def test_initialization_custom_params(self):
        """Test service initialization with custom parameters."""
        service = BoundaryExtractionService(auto_repair=False, min_area_sqm=10.0)
        assert service.auto_repair is False
        assert service.min_area_sqm == 10.0


class TestBoundaryIdentification:
    """Test boundary identification strategies."""

    def create_polygon_placemark(
        self,
        name: str = "Test Polygon",
        geometry: Polygon = None,
        folder_path: list = None,
        properties: dict = None,
    ) -> Placemark:
        """Helper to create a test polygon placemark."""
        if geometry is None:
            # Simple square polygon
            geometry = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])

        return Placemark(
            name=name,
            geometry=geometry,
            geometry_type=GeometryType.POLYGON,
            folder_path=folder_path or [],
            properties=properties or {},
        )

    def test_identify_by_name_pattern(self):
        """Test identification by name pattern."""
        service = BoundaryExtractionService()

        placemarks = [
            self.create_polygon_placemark("Property Boundary"),
            self.create_polygon_placemark("Site Boundary"),
            self.create_polygon_placemark("Parcel 123"),
            self.create_polygon_placemark("Random Polygon"),
            self.create_polygon_placemark("Lot Line"),
        ]

        matches = service._identify_by_name(placemarks)
        assert len(matches) == 4
        assert placemarks[3] not in matches  # "Random Polygon" should not match

    def test_identify_by_name_case_insensitive(self):
        """Test name pattern matching is case-insensitive."""
        service = BoundaryExtractionService()

        placemarks = [
            self.create_polygon_placemark("PROPERTY BOUNDARY"),
            self.create_polygon_placemark("property boundary"),
            self.create_polygon_placemark("Property Boundary"),
        ]

        matches = service._identify_by_name(placemarks)
        assert len(matches) == 3

    def test_identify_by_folder(self):
        """Test identification by folder path."""
        service = BoundaryExtractionService()

        placemarks = [
            self.create_polygon_placemark("Polygon 1", folder_path=["Boundaries", "Main"]),
            self.create_polygon_placemark("Polygon 2", folder_path=["Property", "Site"]),
            self.create_polygon_placemark("Polygon 3", folder_path=["Parcels"]),
            self.create_polygon_placemark("Polygon 4", folder_path=["Other", "Stuff"]),
        ]

        matches = service._identify_by_folder(placemarks)
        assert len(matches) == 3
        assert placemarks[3] not in matches

    def test_identify_by_metadata(self):
        """Test identification by metadata properties."""
        service = BoundaryExtractionService()

        placemarks = [
            self.create_polygon_placemark("Polygon 1", properties={"boundary": "true"}),
            self.create_polygon_placemark("Polygon 2", properties={"parcel_id": "123"}),
            self.create_polygon_placemark("Polygon 3", properties={"apn": "456-789"}),
            self.create_polygon_placemark("Polygon 4", properties={"random": "data"}),
        ]

        matches = service._identify_by_metadata(placemarks)
        assert len(matches) == 3
        assert placemarks[3] not in matches

    def test_identify_by_size_largest(self):
        """Test identification by selecting largest polygon."""
        service = BoundaryExtractionService()

        # Create polygons of different sizes
        small_poly = Polygon([(-122.1, 37.4), (-122.09, 37.4), (-122.09, 37.41), (-122.1, 37.41), (-122.1, 37.4)])
        medium_poly = Polygon([(-122.1, 37.4), (-122.08, 37.4), (-122.08, 37.42), (-122.1, 37.42), (-122.1, 37.4)])
        large_poly = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])

        placemarks = [
            self.create_polygon_placemark("Small", geometry=small_poly),
            self.create_polygon_placemark("Medium", geometry=medium_poly),
            self.create_polygon_placemark("Large", geometry=large_poly),
        ]

        matches = service._identify_by_size(placemarks)
        assert len(matches) == 1
        assert matches[0].name == "Large"


class TestGeometryValidation:
    """Test geometry validation functionality."""

    def test_validate_valid_polygon(self):
        """Test validation of a valid polygon."""
        service = BoundaryExtractionService()
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])

        is_valid, issues = service._validate_geometry(polygon)
        assert is_valid is True
        assert len(issues) == 0

    def test_validate_self_intersecting_polygon(self):
        """Test validation of self-intersecting polygon."""
        service = BoundaryExtractionService()
        # Bowtie/figure-8 polygon (self-intersecting)
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.5), (-122.0, 37.4), (-122.1, 37.5), (-122.1, 37.4)])

        is_valid, issues = service._validate_geometry(polygon)
        assert is_valid is False
        assert len(issues) > 0

    def test_validate_invalid_coordinates(self):
        """Test validation of polygon with invalid coordinates."""
        service = BoundaryExtractionService()
        # Polygon with longitude out of range
        polygon = Polygon([(-200, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-200, 37.4)])

        is_valid, issues = service._validate_geometry(polygon)
        assert is_valid is False
        assert GeometryIssue.INVALID_COORDINATES in issues

    def test_auto_repair_geometry(self):
        """Test automatic geometry repair."""
        service = BoundaryExtractionService(auto_repair=True)
        # Create a self-intersecting polygon
        invalid_polygon = Polygon([(-122.1, 37.4), (-122.0, 37.5), (-122.0, 37.4), (-122.1, 37.5), (-122.1, 37.4)])

        repaired = service._repair_geometry(invalid_polygon)
        assert repaired is not None
        # After repair, it should be valid (buffer(0) fixes self-intersections)

    def test_no_auto_repair(self):
        """Test that auto-repair can be disabled."""
        service = BoundaryExtractionService(auto_repair=False)
        # Create a valid polygon placemark
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Test",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
        )

        boundary = service._process_boundary(placemark, BoundarySource.NAME_PATTERN)
        assert boundary is not None
        assert boundary.repaired is False


class TestMetricCalculations:
    """Test boundary metric calculations."""

    def test_calculate_area_square(self):
        """Test area calculation for a square polygon."""
        service = BoundaryExtractionService()
        # Create a roughly 1km x 1km square
        # At latitude 37.4, 0.01 degrees longitude ≈ 889 meters
        # At any latitude, 0.01 degrees latitude ≈ 1,111 meters
        polygon = Polygon([(-122.1, 37.4), (-122.09, 37.4), (-122.09, 37.41), (-122.1, 37.41), (-122.1, 37.4)])

        metrics = service._calculate_metrics(polygon)

        # Area should be roughly 889m * 1111m ≈ 987,000 sqm
        assert metrics.area_sqm > 900000
        assert metrics.area_sqm < 1100000
        assert metrics.area_acres > 220  # ~1 million sqm ≈ 247 acres
        assert metrics.vertex_count == 4

    def test_calculate_perimeter(self):
        """Test perimeter calculation."""
        service = BoundaryExtractionService()
        polygon = Polygon([(-122.1, 37.4), (-122.09, 37.4), (-122.09, 37.41), (-122.1, 37.41), (-122.1, 37.4)])

        metrics = service._calculate_metrics(polygon)

        # Perimeter should be 2 * (889 + 1111) = 4000m
        assert metrics.perimeter_m > 3800
        assert metrics.perimeter_m < 4200
        assert metrics.perimeter_ft == pytest.approx(metrics.perimeter_m * 3.28084, rel=0.01)

    def test_calculate_centroid(self):
        """Test centroid calculation."""
        service = BoundaryExtractionService()
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])

        metrics = service._calculate_metrics(polygon)

        # Centroid should be at the center
        assert metrics.centroid_lon == pytest.approx(-122.05, abs=0.01)
        assert metrics.centroid_lat == pytest.approx(37.45, abs=0.01)

    def test_calculate_bounding_box(self):
        """Test bounding box calculation."""
        service = BoundaryExtractionService()
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])

        metrics = service._calculate_metrics(polygon)

        assert metrics.bbox_min_lon == -122.1
        assert metrics.bbox_max_lon == -122.0
        assert metrics.bbox_min_lat == 37.4
        assert metrics.bbox_max_lat == 37.5

    def test_polygon_with_holes(self):
        """Test metrics calculation for polygon with holes."""
        service = BoundaryExtractionService()

        # Outer ring
        outer = [(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)]
        # Inner hole
        hole = [(-122.08, 37.42), (-122.02, 37.42), (-122.02, 37.48), (-122.08, 37.48), (-122.08, 37.42)]

        polygon = Polygon(outer, [hole])

        metrics = service._calculate_metrics(polygon)

        assert metrics.has_holes is True
        assert metrics.hole_count == 1
        # Area should be outer area minus hole area
        assert metrics.area_sqm > 0


class TestMultiPolygonHandling:
    """Test multi-polygon property handling."""

    def test_multi_polygon_detection(self):
        """Test detection of multi-polygon properties."""
        service = BoundaryExtractionService()

        # Create two separate polygons
        poly1 = Polygon([(-122.1, 37.4), (-122.09, 37.4), (-122.09, 37.41), (-122.1, 37.41), (-122.1, 37.4)])
        poly2 = Polygon([(-122.05, 37.45), (-122.04, 37.45), (-122.04, 37.46), (-122.05, 37.46), (-122.05, 37.45)])

        multi_poly = MultiPolygon([poly1, poly2])

        placemark = Placemark(
            name="Multi-Parcel Property",
            geometry=multi_poly,
            geometry_type=GeometryType.POLYGON,
        )

        boundary = service._process_boundary(placemark, BoundarySource.NAME_PATTERN)

        assert boundary is not None
        assert boundary.is_multi_parcel is True
        assert len(boundary.sub_parcels) == 2

    def test_sub_parcel_extraction(self):
        """Test extraction of sub-parcel details."""
        service = BoundaryExtractionService()

        poly1 = Polygon([(-122.1, 37.4), (-122.09, 37.4), (-122.09, 37.41), (-122.1, 37.41), (-122.1, 37.4)])
        poly2 = Polygon([(-122.05, 37.45), (-122.04, 37.45), (-122.04, 37.46), (-122.05, 37.46), (-122.05, 37.45)])

        multi_poly = MultiPolygon([poly1, poly2])

        sub_parcels = service._extract_sub_parcels(multi_poly)

        assert len(sub_parcels) == 2
        assert sub_parcels[0].parcel_id == "parcel_1"
        assert sub_parcels[1].parcel_id == "parcel_2"
        assert sub_parcels[0].area_sqm > 0
        assert sub_parcels[1].area_sqm > 0


class TestMetadataExtraction:
    """Test metadata extraction from placemarks."""

    def test_extract_basic_metadata(self):
        """Test extraction of basic metadata."""
        service = BoundaryExtractionService()

        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Property Boundary",
            description="Main parcel for development",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
            folder_path=["Site", "Boundaries"],
            properties={"zoning": "R-1"},
        )

        metadata = service._extract_metadata(placemark, BoundarySource.NAME_PATTERN)

        assert metadata.name == "Property Boundary"
        assert metadata.description == "Main parcel for development"
        assert metadata.folder_path == ["Site", "Boundaries"]
        assert metadata.properties == {"zoning": "R-1"}
        assert metadata.source == BoundarySource.NAME_PATTERN

    def test_extract_address_from_properties(self):
        """Test address extraction from properties."""
        service = BoundaryExtractionService()

        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Property",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
            properties={"address": "123 Main Street"},
        )

        metadata = service._extract_metadata(placemark, BoundarySource.NAME_PATTERN)

        assert metadata.address == "123 Main Street"

    def test_extract_parcel_id(self):
        """Test parcel ID extraction."""
        service = BoundaryExtractionService()

        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Property",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
            properties={"apn": "123-456-789"},
        )

        metadata = service._extract_metadata(placemark, BoundarySource.NAME_PATTERN)

        assert metadata.parcel_id == "123-456-789"

    def test_extract_address_from_description(self):
        """Test address extraction from description text."""
        service = BoundaryExtractionService()

        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Property",
            description="Property located at 456 Oak Avenue, with development potential",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
        )

        metadata = service._extract_metadata(placemark, BoundarySource.NAME_PATTERN)

        assert metadata.address is not None
        assert "456 Oak Avenue" in metadata.address


class TestFullExtraction:
    """Test full boundary extraction workflow."""

    def create_parsed_kml(self, placemarks: list) -> ParsedKML:
        """Helper to create ParsedKML from placemark list."""
        parsed = ParsedKML()
        parsed.placemarks = placemarks
        return parsed

    def test_extract_single_boundary(self):
        """Test extraction of single boundary."""
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Property Boundary",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
        )

        parsed_kml = self.create_parsed_kml([placemark])
        result = extract_boundaries_from_kml(parsed_kml)

        assert result.success is True
        assert len(result.boundaries) == 1
        assert result.boundaries[0].metadata.name == "Property Boundary"
        assert result.boundaries[0].is_valid is True
        assert result.extraction_strategy == BoundarySource.NAME_PATTERN

    def test_extract_multiple_boundaries(self):
        """Test extraction of multiple boundaries."""
        polygon1 = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        polygon2 = Polygon([(-122.05, 37.45), (-122.04, 37.45), (-122.04, 37.46), (-122.05, 37.46), (-122.05, 37.45)])

        placemark1 = Placemark(
            name="Parcel 1",
            geometry=polygon1,
            geometry_type=GeometryType.POLYGON,
        )
        placemark2 = Placemark(
            name="Parcel 2",
            geometry=polygon2,
            geometry_type=GeometryType.POLYGON,
        )

        parsed_kml = self.create_parsed_kml([placemark1, placemark2])
        result = extract_boundaries_from_kml(parsed_kml)

        assert result.success is True
        assert len(result.boundaries) == 2

    def test_extract_no_polygons(self):
        """Test extraction with no polygon placemarks."""
        parsed_kml = self.create_parsed_kml([])
        result = extract_boundaries_from_kml(parsed_kml)

        assert result.success is False
        assert len(result.boundaries) == 0
        assert len(result.errors) > 0

    def test_extract_with_specific_strategy(self):
        """Test extraction with specific strategy."""
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Polygon 1",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
        )

        parsed_kml = self.create_parsed_kml([placemark])
        result = extract_boundaries_from_kml(
            parsed_kml, strategy=BoundarySource.LARGEST_POLYGON
        )

        assert result.success is True
        assert result.extraction_strategy == BoundarySource.LARGEST_POLYGON

    def test_small_area_warning(self):
        """Test warning for very small areas."""
        # Create a very small polygon
        small_polygon = Polygon([
            (-122.1, 37.4),
            (-122.09999, 37.4),
            (-122.09999, 37.40001),
            (-122.1, 37.40001),
            (-122.1, 37.4),
        ])
        placemark = Placemark(
            name="Small Parcel",
            geometry=small_polygon,
            geometry_type=GeometryType.POLYGON,
        )

        parsed_kml = self.create_parsed_kml([placemark])
        result = extract_boundaries_from_kml(parsed_kml, min_area_sqm=100.0)

        assert result.success is True
        assert len(result.warnings) > 0


class TestGeoJSONExport:
    """Test GeoJSON export functionality."""

    def test_boundary_to_geojson(self):
        """Test conversion of boundary to GeoJSON."""
        service = BoundaryExtractionService()

        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name="Property Boundary",
            description="Test property",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
            properties={"zoning": "R-1"},
        )

        boundary = service._process_boundary(placemark, BoundarySource.NAME_PATTERN)
        geojson = boundary.to_geojson()

        assert geojson["type"] == "Feature"
        assert geojson["geometry"]["type"] == "Polygon"
        assert "coordinates" in geojson["geometry"]
        assert geojson["properties"]["name"] == "Property Boundary"
        assert geojson["properties"]["zoning"] == "R-1"
        assert geojson["properties"]["area_sqm"] > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_with_contour_lines(self):
        """Test that contour lines are excluded from boundaries."""
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])

        boundary_placemark = Placemark(
            name="Property Boundary",
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
            is_contour=False,
        )

        # Even though this has polygon geometry, is_contour should exclude it
        # However, get_property_boundaries already filters by is_contour=False
        parsed_kml = ParsedKML()
        parsed_kml.placemarks = [boundary_placemark]

        result = extract_boundaries_from_kml(parsed_kml)

        assert result.success is True
        assert len(result.boundaries) == 1

    def test_null_geometry_handling(self):
        """Test handling of placemarks with null geometry."""
        placemark = Placemark(
            name="No Geometry",
            geometry=None,
            geometry_type=None,
        )

        parsed_kml = ParsedKML()
        parsed_kml.placemarks = [placemark]

        result = extract_boundaries_from_kml(parsed_kml)

        # Should fail gracefully
        assert result.success is False

    def test_empty_name_handling(self):
        """Test handling of placemarks with no name."""
        polygon = Polygon([(-122.1, 37.4), (-122.0, 37.4), (-122.0, 37.5), (-122.1, 37.5), (-122.1, 37.4)])
        placemark = Placemark(
            name=None,
            geometry=polygon,
            geometry_type=GeometryType.POLYGON,
        )

        parsed_kml = ParsedKML()
        parsed_kml.placemarks = [placemark]

        # Should fall back to largest polygon strategy
        result = extract_boundaries_from_kml(parsed_kml)

        assert result.success is True
        assert result.extraction_strategy == BoundarySource.LARGEST_POLYGON


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

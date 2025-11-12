"""
Comprehensive tests for KMZ parsing functionality.

Tests cover:
- KMZ validation
- KMZ extraction
- KML parsing from KMZ
- File listing and inspection
- Error handling
"""

import pytest
import tempfile
import zipfile
from pathlib import Path

from entmoot.core.parsers import (
    KMZParser,
    KMZValidator,
    parse_kmz_file,
    validate_kmz_file,
    GeometryType,
)


# Test fixtures path
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SIMPLE_KMZ = FIXTURES_DIR / "simple.kmz"
SIMPLE_KML = FIXTURES_DIR / "simple.kml"


class TestKMZValidator:
    """Tests for KMZ validation."""

    def test_validate_simple_kmz(self):
        """Test validation of simple valid KMZ."""
        result = validate_kmz_file(SIMPLE_KMZ)

        assert result.is_valid
        assert not result.errors
        assert result.has_kml
        assert len(result.kml_files) >= 1
        assert result.total_files >= 1
        assert result.archive_size > 0

    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        result = validate_kmz_file(Path("/nonexistent/file.kmz"))

        assert not result.is_valid
        assert "not found" in result.errors[0].lower()

    def test_validate_non_zip_file(self):
        """Test validation of non-ZIP file."""
        # Use a KML file instead of KMZ
        result = validate_kmz_file(SIMPLE_KML)

        assert not result.is_valid
        assert any("zip" in err.lower() for err in result.errors)

    def test_validate_empty_kmz(self, tmp_path):
        """Test validation of empty KMZ archive."""
        empty_kmz = tmp_path / "empty.kmz"
        with zipfile.ZipFile(empty_kmz, "w"):
            pass  # Create empty archive

        result = validate_kmz_file(empty_kmz)

        assert not result.is_valid
        assert "empty" in result.errors[0].lower()

    def test_validate_kmz_without_kml(self, tmp_path):
        """Test validation of KMZ without KML files."""
        no_kml_kmz = tmp_path / "no_kml.kmz"
        with zipfile.ZipFile(no_kml_kmz, "w") as zf:
            zf.writestr("readme.txt", "This is a test file")
            zf.writestr("data.json", '{"test": true}')

        result = validate_kmz_file(no_kml_kmz)

        assert not result.is_valid
        assert "no kml" in result.errors[0].lower()

    def test_validate_kmz_with_images(self, tmp_path):
        """Test validation of KMZ with image files."""
        kmz_with_images = tmp_path / "with_images.kmz"

        kml_content = """<?xml version="1.0"?>
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

        with zipfile.ZipFile(kmz_with_images, "w") as zf:
            zf.writestr("doc.kml", kml_content)
            zf.writestr("images/photo1.jpg", b"fake image data")
            zf.writestr("images/photo2.png", b"fake image data")

        result = validate_kmz_file(kmz_with_images)

        assert result.is_valid
        assert result.has_images
        assert len(result.image_files) == 2

    def test_validate_kmz_multiple_kml_files(self, tmp_path):
        """Test validation of KMZ with multiple KML files."""
        multi_kml_kmz = tmp_path / "multi_kml.kmz"

        kml_content = """<?xml version="1.0"?>
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

        with zipfile.ZipFile(multi_kml_kmz, "w") as zf:
            zf.writestr("doc.kml", kml_content)
            zf.writestr("overlay.kml", kml_content)
            zf.writestr("annotations.kml", kml_content)

        result = validate_kmz_file(multi_kml_kmz)

        assert result.is_valid
        assert len(result.kml_files) == 3
        assert len(result.warnings) > 0
        assert "multiple" in result.warnings[0].lower()

    def test_validate_empty_file(self, tmp_path):
        """Test validation of zero-byte file."""
        empty_file = tmp_path / "empty.kmz"
        empty_file.touch()

        result = validate_kmz_file(empty_file)

        assert not result.is_valid
        assert "empty" in result.errors[0].lower()

    def test_validate_corrupted_zip(self, tmp_path):
        """Test validation of corrupted ZIP file."""
        corrupted = tmp_path / "corrupted.kmz"
        corrupted.write_bytes(b"PK\x03\x04" + b"corrupted data" * 100)

        result = validate_kmz_file(corrupted)

        assert not result.is_valid

    def test_validate_directory_not_file(self, tmp_path):
        """Test validation rejects directories."""
        result = validate_kmz_file(tmp_path)

        assert not result.is_valid
        assert "not a file" in result.errors[0].lower()


class TestKMZParser:
    """Tests for KMZ parsing."""

    def test_parse_simple_kmz(self):
        """Test parsing simple KMZ file."""
        result = parse_kmz_file(SIMPLE_KMZ)

        assert result.placemark_count >= 1
        assert result.geometry_count >= 1
        assert "source_type" in result.properties
        assert result.properties["source_type"] == "kmz"

    def test_parse_kmz_extracts_placemarks(self):
        """Test that KMZ parsing extracts placemarks correctly."""
        result = parse_kmz_file(SIMPLE_KMZ)

        placemarks = result.placemarks
        assert len(placemarks) >= 1

        placemark = placemarks[0]
        assert placemark.name is not None
        assert placemark.geometry is not None
        assert placemark.geometry.is_valid

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            parse_kmz_file(Path("/nonexistent/file.kmz"))

    def test_parse_invalid_kmz(self):
        """Test parsing invalid KMZ raises error."""
        with pytest.raises(ValueError):
            parse_kmz_file(SIMPLE_KML)  # Try to parse KML as KMZ

    def test_parse_without_validation(self, tmp_path):
        """Test parsing without validation."""
        # Create valid KMZ
        kmz_file = tmp_path / "test.kmz"
        kml_content = """<?xml version="1.0"?>
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
        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("doc.kml", kml_content)

        parser = KMZParser(validate=False)
        result = parser.parse(kmz_file)

        assert result.placemark_count == 1

    def test_parse_kmz_with_doc_kml(self, tmp_path):
        """Test that parser prefers doc.kml when multiple KML files present."""
        kmz_file = tmp_path / "multi.kmz"

        doc_kml = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <name>Main Document</name>
                <Placemark>
                    <name>Main</name>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """

        other_kml = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <name>Other Document</name>
                <Placemark>
                    <name>Other</name>
                    <Point>
                        <coordinates>-122.085,37.423,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("overlay.kml", other_kml)
            zf.writestr("doc.kml", doc_kml)

        result = parse_kmz_file(kmz_file)

        assert result.document_name == "Main Document"

    def test_parse_kmz_without_doc_kml(self, tmp_path):
        """Test parser uses first KML when doc.kml not present."""
        kmz_file = tmp_path / "no_doc.kmz"

        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <name>First KML</name>
                <Placemark>
                    <name>Test</name>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("myfile.kml", kml_content)

        result = parse_kmz_file(kmz_file)

        assert result.document_name == "First KML"
        assert result.placemark_count == 1


class TestKMZExtraction:
    """Tests for KMZ extraction functionality."""

    def test_extract_all(self, tmp_path):
        """Test extracting all files from KMZ."""
        output_dir = tmp_path / "extracted"

        parser = KMZParser()
        result_dir = parser.extract_all(SIMPLE_KMZ, output_dir)

        assert result_dir.exists()
        assert result_dir.is_dir()

        # Check that doc.kml was extracted
        doc_kml = result_dir / "doc.kml"
        assert doc_kml.exists()

    def test_extract_all_with_images(self, tmp_path):
        """Test extracting KMZ with embedded images."""
        kmz_file = tmp_path / "with_images.kmz"
        output_dir = tmp_path / "extracted"

        kml_content = """<?xml version="1.0"?>
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

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("doc.kml", kml_content)
            zf.writestr("images/photo.jpg", b"fake image")

        parser = KMZParser()
        result_dir = parser.extract_all(kmz_file, output_dir)

        assert (result_dir / "doc.kml").exists()
        assert (result_dir / "images" / "photo.jpg").exists()

    def test_extract_nonexistent_file(self, tmp_path):
        """Test extracting non-existent file raises error."""
        parser = KMZParser()

        with pytest.raises(FileNotFoundError):
            parser.extract_all(Path("/nonexistent.kmz"), tmp_path)

    def test_extract_creates_output_dir(self, tmp_path):
        """Test that extract creates output directory if it doesn't exist."""
        output_dir = tmp_path / "deep" / "nested" / "dir"

        parser = KMZParser()
        result_dir = parser.extract_all(SIMPLE_KMZ, output_dir)

        assert result_dir.exists()
        assert result_dir == output_dir


class TestKMZListing:
    """Tests for KMZ content listing."""

    def test_list_contents_simple(self):
        """Test listing contents of simple KMZ."""
        parser = KMZParser()
        contents = parser.list_contents(SIMPLE_KMZ)

        assert "kml_files" in contents
        assert "image_files" in contents
        assert "other_files" in contents
        assert "total_files" in contents
        assert "total_size" in contents

        assert len(contents["kml_files"]) >= 1
        assert contents["total_files"] >= 1
        assert contents["total_size"] > 0

    def test_list_contents_with_images(self, tmp_path):
        """Test listing KMZ with images."""
        kmz_file = tmp_path / "with_images.kmz"

        kml_content = """<?xml version="1.0"?>
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

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("doc.kml", kml_content)
            zf.writestr("photo1.jpg", b"fake image 1")
            zf.writestr("photo2.png", b"fake image 2")
            zf.writestr("readme.txt", "This is a readme")

        parser = KMZParser()
        contents = parser.list_contents(kmz_file)

        assert len(contents["kml_files"]) == 1
        assert len(contents["image_files"]) == 2
        assert len(contents["other_files"]) == 1
        assert contents["total_files"] == 4

    def test_list_contents_nonexistent_file(self):
        """Test listing non-existent file raises error."""
        parser = KMZParser()

        with pytest.raises(FileNotFoundError):
            parser.list_contents(Path("/nonexistent.kmz"))

    def test_list_contents_invalid_zip(self):
        """Test listing invalid ZIP raises error."""
        parser = KMZParser()

        with pytest.raises(ValueError):
            parser.list_contents(SIMPLE_KML)  # Not a ZIP file


class TestKMZIntegration:
    """Integration tests for end-to-end KMZ processing."""

    def test_full_workflow_validation_to_parsing(self, tmp_path):
        """Test complete workflow from validation to parsing."""
        # Create KMZ
        kmz_file = tmp_path / "property.kmz"
        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <name>Test Property</name>
                <Placemark>
                    <name>Boundary</name>
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

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("doc.kml", kml_content)

        # Validate
        validation = validate_kmz_file(kmz_file)
        assert validation.is_valid

        # Parse
        result = parse_kmz_file(kmz_file)
        assert result.document_name == "Test Property"
        assert result.placemark_count == 1

        # Check geometry
        placemark = result.placemarks[0]
        assert placemark.geometry_type == GeometryType.POLYGON
        assert placemark.geometry.is_valid
        assert placemark.geometry.area > 0

    def test_complex_kmz_with_folders(self, tmp_path):
        """Test KMZ with complex KML structure."""
        kmz_file = tmp_path / "complex.kmz"

        # Use complex KML content
        with open(FIXTURES_DIR / "complex.kml", "r") as f:
            kml_content = f.read()

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("doc.kml", kml_content)

        result = parse_kmz_file(kmz_file)

        assert result.placemark_count > 5
        assert len(result.folders) > 0
        assert result.contour_count >= 2

        # Check different geometry types present
        polygons = result.get_placemarks_by_type(GeometryType.POLYGON)
        lines = result.get_placemarks_by_type(GeometryType.LINE_STRING)
        points = result.get_placemarks_by_type(GeometryType.POINT)

        assert len(polygons) >= 2
        assert len(lines) >= 2
        assert len(points) >= 2

    def test_kmz_preserves_metadata(self, tmp_path):
        """Test that KMZ parsing preserves all metadata."""
        kmz_file = tmp_path / "metadata.kmz"

        kml_content = """<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Document>
                <name>Property Map</name>
                <description>Test property with metadata</description>
                <Placemark>
                    <name>Parcel 1</name>
                    <description>Main parcel</description>
                    <ExtendedData>
                        <Data name="parcel_id">
                            <value>ABC-123</value>
                        </Data>
                        <Data name="area">
                            <value>10.5</value>
                        </Data>
                    </ExtendedData>
                    <Point>
                        <coordinates>-122.084,37.422,0</coordinates>
                    </Point>
                </Placemark>
            </Document>
        </kml>
        """

        with zipfile.ZipFile(kmz_file, "w") as zf:
            zf.writestr("doc.kml", kml_content)

        result = parse_kmz_file(kmz_file)

        assert result.document_name == "Property Map"
        assert result.document_description == "Test property with metadata"

        placemark = result.placemarks[0]
        assert placemark.name == "Parcel 1"
        assert placemark.description == "Main parcel"
        assert "parcel_id" in placemark.properties
        assert placemark.properties["parcel_id"] == "ABC-123"
        assert "area" in placemark.properties
        assert placemark.properties["area"] == "10.5"

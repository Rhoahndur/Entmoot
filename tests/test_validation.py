"""
Unit tests for file validation utilities.
"""

import pytest

from entmoot.core.validation import (
    ValidationError,
    validate_file_extension,
    validate_file_size,
    validate_magic_number,
    validate_mime_type,
)


class TestValidateFileExtension:
    """Tests for validate_file_extension function."""

    def test_valid_kmz_extension(self) -> None:
        """Test that .kmz extension is valid."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("file.kmz", allowed)
        assert result == ".kmz"

    def test_valid_kml_extension(self) -> None:
        """Test that .kml extension is valid."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("file.kml", allowed)
        assert result == ".kml"

    def test_valid_geojson_extension(self) -> None:
        """Test that .geojson extension is valid."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("file.geojson", allowed)
        assert result == ".geojson"

    def test_valid_tif_extension(self) -> None:
        """Test that .tif extension is valid."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("file.tif", allowed)
        assert result == ".tif"

    def test_valid_tiff_extension(self) -> None:
        """Test that .tiff extension is valid."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("file.tiff", allowed)
        assert result == ".tiff"

    def test_case_insensitive(self) -> None:
        """Test that extension validation is case-insensitive."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("FILE.KMZ", allowed)
        assert result == ".kmz"

    def test_invalid_extension(self) -> None:
        """Test that invalid extensions raise ValidationError."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        with pytest.raises(ValidationError, match="not allowed"):
            validate_file_extension("file.txt", allowed)

    def test_no_extension(self) -> None:
        """Test that files without extension raise ValidationError."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        with pytest.raises(ValidationError, match="no extension"):
            validate_file_extension("file", allowed)

    def test_with_path(self) -> None:
        """Test that files with paths work correctly."""
        allowed = (".kmz", ".kml", ".geojson", ".tif", ".tiff")
        result = validate_file_extension("/path/to/file.kmz", allowed)
        assert result == ".kmz"


class TestValidateMimeType:
    """Tests for validate_mime_type function."""

    def test_valid_kmz_mime_type(self) -> None:
        """Test valid KMZ MIME types."""
        validate_mime_type("application/vnd.google-earth.kmz", ".kmz")
        validate_mime_type("application/zip", ".kmz")

    def test_valid_kml_mime_type(self) -> None:
        """Test valid KML MIME types."""
        validate_mime_type("application/vnd.google-earth.kml+xml", ".kml")
        validate_mime_type("application/xml", ".kml")
        validate_mime_type("text/xml", ".kml")

    def test_valid_geojson_mime_type(self) -> None:
        """Test valid GeoJSON MIME types."""
        validate_mime_type("application/geo+json", ".geojson")
        validate_mime_type("application/json", ".geojson")

    def test_valid_tiff_mime_type(self) -> None:
        """Test valid TIFF MIME types."""
        validate_mime_type("image/tiff", ".tif")
        validate_mime_type("image/tiff", ".tiff")

    def test_mime_type_with_charset(self) -> None:
        """Test MIME type with charset parameter."""
        validate_mime_type("application/json; charset=utf-8", ".geojson")

    def test_case_insensitive(self) -> None:
        """Test that MIME type validation is case-insensitive."""
        validate_mime_type("APPLICATION/ZIP", ".kmz")

    def test_invalid_mime_type(self) -> None:
        """Test that invalid MIME types raise ValidationError."""
        with pytest.raises(ValidationError, match="does not match"):
            validate_mime_type("text/plain", ".kmz")

    def test_unknown_extension(self) -> None:
        """Test that unknown extensions raise ValidationError."""
        with pytest.raises(ValidationError, match="No MIME type mapping"):
            validate_mime_type("text/plain", ".xyz")


class TestValidateMagicNumber:
    """Tests for validate_magic_number function."""

    def test_valid_kmz_magic_number(self) -> None:
        """Test valid KMZ (ZIP) magic numbers."""
        # ZIP file signature
        validate_magic_number(b"PK\x03\x04test", ".kmz")

    def test_valid_kml_magic_number_xml_declaration(self) -> None:
        """Test valid KML magic number with XML declaration."""
        validate_magic_number(b"<?xml version='1.0'?>", ".kml")

    def test_valid_kml_magic_number_kml_tag(self) -> None:
        """Test valid KML magic number with kml tag."""
        validate_magic_number(b"<kml xmlns=...", ".kml")

    def test_valid_geojson_magic_number_object(self) -> None:
        """Test valid GeoJSON magic number with object."""
        validate_magic_number(b'{"type": "FeatureCollection"}', ".geojson")

    def test_valid_geojson_magic_number_array(self) -> None:
        """Test valid GeoJSON magic number with array."""
        validate_magic_number(b'[{"type": "Feature"}]', ".geojson")

    def test_valid_tiff_magic_number_little_endian(self) -> None:
        """Test valid TIFF magic number (little-endian)."""
        validate_magic_number(b"II\x2a\x00data", ".tif")

    def test_valid_tiff_magic_number_big_endian(self) -> None:
        """Test valid TIFF magic number (big-endian)."""
        validate_magic_number(b"MM\x00\x2adata", ".tiff")

    def test_invalid_magic_number(self) -> None:
        """Test that invalid magic numbers raise ValidationError."""
        with pytest.raises(ValidationError, match="does not match expected format"):
            validate_magic_number(b"invalid data", ".kmz")

    def test_empty_file(self) -> None:
        """Test that empty files raise ValidationError."""
        with pytest.raises(ValidationError, match="does not match expected format"):
            validate_magic_number(b"", ".kmz")


class TestValidateFileSize:
    """Tests for validate_file_size function."""

    def test_valid_file_size(self) -> None:
        """Test that valid file sizes pass validation."""
        validate_file_size(1024, 1024 * 1024)  # 1KB with 1MB limit

    def test_max_file_size(self) -> None:
        """Test file at exact max size."""
        validate_file_size(1024 * 1024, 1024 * 1024)  # Exactly at limit

    def test_file_too_large(self) -> None:
        """Test that files exceeding max size raise ValidationError."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_file_size(2 * 1024 * 1024, 1024 * 1024)  # 2MB with 1MB limit

    def test_empty_file(self) -> None:
        """Test that empty files raise ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            validate_file_size(0, 1024 * 1024)

    def test_negative_size(self) -> None:
        """Test that negative sizes raise ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            validate_file_size(-1, 1024 * 1024)

    def test_error_message_includes_sizes(self) -> None:
        """Test that error message includes actual and max sizes."""
        max_size = 50 * 1024 * 1024  # 50MB
        file_size = 51 * 1024 * 1024  # 51MB
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size(file_size, max_size)
        assert "51.00MB" in str(exc_info.value)
        assert "50MB" in str(exc_info.value)


@pytest.mark.asyncio
class TestScanForViruses:
    """Tests for scan_for_viruses function."""

    async def test_scan_for_viruses_not_implemented(self, tmp_path) -> None:  # type: ignore
        """Test that virus scanning returns None when not implemented."""
        from entmoot.core.validation import scan_for_viruses

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = await scan_for_viruses(test_file)
        assert result is None

"""
Tests for custom exception hierarchy.
"""

import pytest

from entmoot.core.errors import (
    APIError,
    CRSError,
    ConfigurationError,
    EntmootException,
    GeometryError,
    ParseError,
    ServiceUnavailableError,
    StorageError,
    ValidationError,
)


class TestEntmootException:
    """Tests for base EntmootException class."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = EntmootException(
            message="Test error",
            error_code="TEST_ERROR",
        )

        assert str(exc) == "TEST_ERROR: Test error"
        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 500
        assert exc.details == {}
        assert exc.suggestions == []

    def test_exception_with_details(self):
        """Test exception with details and suggestions."""
        exc = EntmootException(
            message="Test error with details",
            error_code="TEST_ERROR",
            status_code=400,
            details={"field": "test", "value": 123},
            suggestions=["Try this", "Or that"],
        )

        assert exc.status_code == 400
        assert exc.details == {"field": "test", "value": 123}
        assert exc.suggestions == ["Try this", "Or that"]

    def test_to_dict(self):
        """Test conversion to dictionary."""
        exc = EntmootException(
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            suggestions=["suggestion"],
        )

        result = exc.to_dict()

        assert result["error_code"] == "TEST_ERROR"
        assert result["message"] == "Test error"
        assert result["details"] == {"key": "value"}
        assert result["suggestions"] == ["suggestion"]

    def test_repr(self):
        """Test string representation."""
        exc = EntmootException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=404,
        )

        repr_str = repr(exc)

        assert "EntmootException" in repr_str
        assert "TEST_ERROR" in repr_str
        assert "Test error" in repr_str
        assert "404" in repr_str


class TestValidationError:
    """Tests for ValidationError class."""

    def test_basic_validation_error(self):
        """Test basic validation error."""
        exc = ValidationError(message="Invalid input")

        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 400
        assert exc.message == "Invalid input"
        assert any("Check the input format" in s for s in exc.suggestions)

    def test_validation_error_with_field(self):
        """Test validation error with field name."""
        exc = ValidationError(
            message="Invalid email",
            field="email",
        )

        assert exc.details["field"] == "email"

    def test_validation_error_with_suggestions(self):
        """Test validation error with custom suggestions."""
        suggestions = ["Use valid email format", "Check for typos"]
        exc = ValidationError(
            message="Invalid email",
            field="email",
            suggestions=suggestions,
        )

        assert exc.suggestions == suggestions


class TestParseError:
    """Tests for ParseError class."""

    def test_basic_parse_error(self):
        """Test basic parse error."""
        exc = ParseError(message="Failed to parse KML")

        assert exc.error_code == "PARSE_ERROR"
        assert exc.status_code == 422
        assert "Verify the file is a valid KML/KMZ file" in exc.suggestions

    def test_parse_error_with_file_type(self):
        """Test parse error with file type."""
        exc = ParseError(
            message="Invalid XML",
            file_type="KML",
        )

        assert exc.details["file_type"] == "KML"

    def test_parse_error_with_line_number(self):
        """Test parse error with line number."""
        exc = ParseError(
            message="Invalid tag",
            line_number=42,
        )

        assert exc.details["line_number"] == 42

    def test_parse_error_custom_suggestions(self):
        """Test parse error with custom suggestions."""
        suggestions = ["Fix line 42", "Check XML syntax"]
        exc = ParseError(
            message="Parse failed",
            suggestions=suggestions,
        )

        assert exc.suggestions == suggestions


class TestGeometryError:
    """Tests for GeometryError class."""

    def test_basic_geometry_error(self):
        """Test basic geometry error."""
        exc = GeometryError(message="Invalid polygon")

        assert exc.error_code == "GEOMETRY_ERROR"
        assert exc.status_code == 422
        assert "Check for self-intersecting polygons" in exc.suggestions

    def test_geometry_error_with_type(self):
        """Test geometry error with geometry type."""
        exc = GeometryError(
            message="Self-intersecting polygon",
            geometry_type="Polygon",
        )

        assert exc.details["geometry_type"] == "Polygon"


class TestCRSError:
    """Tests for CRSError class."""

    def test_basic_crs_error(self):
        """Test basic CRS error."""
        exc = CRSError(message="Invalid coordinate system")

        assert exc.error_code == "CRS_ERROR"
        assert exc.status_code == 422

    def test_crs_error_with_systems(self):
        """Test CRS error with source and target CRS."""
        exc = CRSError(
            message="Transformation failed",
            source_crs="EPSG:4326",
            target_crs="EPSG:3857",
        )

        assert exc.details["source_crs"] == "EPSG:4326"
        assert exc.details["target_crs"] == "EPSG:3857"


class TestStorageError:
    """Tests for StorageError class."""

    def test_basic_storage_error(self):
        """Test basic storage error."""
        exc = StorageError(message="Failed to save file")

        assert exc.error_code == "STORAGE_ERROR"
        assert exc.status_code == 500

    def test_storage_error_with_operation(self):
        """Test storage error with operation."""
        exc = StorageError(
            message="Save failed",
            operation="save",
            file_path="/tmp/test.kml",
        )

        assert exc.details["operation"] == "save"
        assert exc.details["file_path"] == "/tmp/test.kml"


class TestAPIError:
    """Tests for APIError class."""

    def test_basic_api_error(self):
        """Test basic API error."""
        exc = APIError(message="API request failed")

        assert exc.error_code == "API_ERROR"
        assert exc.status_code == 500

    def test_api_error_custom_code(self):
        """Test API error with custom code."""
        exc = APIError(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )

        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.status_code == 429


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError class."""

    def test_basic_service_error(self):
        """Test basic service unavailable error."""
        exc = ServiceUnavailableError(message="Service is down")

        assert exc.error_code == "SERVICE_UNAVAILABLE"
        assert exc.status_code == 503

    def test_service_error_with_name(self):
        """Test service error with service name."""
        exc = ServiceUnavailableError(
            message="Database is unavailable",
            service_name="database",
        )

        assert exc.details["service_name"] == "database"


class TestConfigurationError:
    """Tests for ConfigurationError class."""

    def test_basic_config_error(self):
        """Test basic configuration error."""
        exc = ConfigurationError(message="Missing configuration")

        assert exc.error_code == "CONFIGURATION_ERROR"
        assert exc.status_code == 500

    def test_config_error_with_key(self):
        """Test configuration error with config key."""
        exc = ConfigurationError(
            message="Invalid API key",
            config_key="API_KEY",
        )

        assert exc.details["config_key"] == "API_KEY"


class TestExceptionInheritance:
    """Tests for exception inheritance."""

    def test_all_inherit_from_base(self):
        """Test that all custom exceptions inherit from EntmootException."""
        exceptions = [
            ValidationError("test"),
            ParseError("test"),
            GeometryError("test"),
            CRSError("test"),
            StorageError("test"),
            APIError("test"),
            ServiceUnavailableError("test"),
            ConfigurationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, EntmootException)
            assert isinstance(exc, Exception)

    def test_exception_catching(self):
        """Test catching exceptions by base class."""
        try:
            raise ValidationError("test error")
        except EntmootException as e:
            assert e.error_code == "VALIDATION_ERROR"
            assert str(e) == "VALIDATION_ERROR: test error"

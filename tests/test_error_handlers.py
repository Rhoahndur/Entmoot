"""
Tests for FastAPI error handlers.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from entmoot.api.error_handlers import register_error_handlers
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


class TestModel(BaseModel):
    """Test model for validation."""

    name: str = Field(..., min_length=3)
    age: int = Field(..., gt=0, lt=150)


@pytest.fixture
def app():
    """Create test FastAPI app with error handlers."""
    test_app = FastAPI()

    # Add test routes FIRST
    @test_app.get("/test/validation-error")
    def raise_validation_error():
        raise ValidationError("Invalid input", field="test_field")

    @test_app.get("/test/parse-error")
    def raise_parse_error():
        raise ParseError("Parse failed", file_type="KML", line_number=42)

    @test_app.get("/test/geometry-error")
    def raise_geometry_error():
        raise GeometryError("Invalid geometry", geometry_type="Polygon")

    @test_app.get("/test/crs-error")
    def raise_crs_error():
        raise CRSError(
            "CRS transformation failed",
            source_crs="EPSG:4326",
            target_crs="EPSG:3857",
        )

    @test_app.get("/test/storage-error")
    def raise_storage_error():
        raise StorageError("Storage failed", operation="save")

    @test_app.get("/test/api-error")
    def raise_api_error():
        raise APIError("API error", error_code="RATE_LIMIT", status_code=429)

    @test_app.get("/test/service-unavailable")
    def raise_service_unavailable():
        raise ServiceUnavailableError("Service down", service_name="database")

    @test_app.get("/test/config-error")
    def raise_config_error():
        raise ConfigurationError("Config missing", config_key="API_KEY")

    @test_app.get("/test/generic-error")
    def raise_generic_error():
        raise RuntimeError("Unexpected error")

    @test_app.post("/test/pydantic-validation")
    def pydantic_validation(data: TestModel):
        return {"status": "ok"}

    # Register error handlers AFTER routes
    register_error_handlers(test_app)

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestEntmootExceptionHandler:
    """Tests for EntmootException handler."""

    def test_validation_error_handler(self, client):
        """Test ValidationError is handled correctly."""
        response = client.get("/test/validation-error")

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert data["message"] == "Invalid input"
        assert data["details"]["field"] == "test_field"
        assert "suggestions" in data

    def test_parse_error_handler(self, client):
        """Test ParseError is handled correctly."""
        response = client.get("/test/parse-error")

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "PARSE_ERROR"
        assert data["message"] == "Parse failed"
        assert data["details"]["file_type"] == "KML"
        assert data["details"]["line_number"] == 42

    def test_geometry_error_handler(self, client):
        """Test GeometryError is handled correctly."""
        response = client.get("/test/geometry-error")

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "GEOMETRY_ERROR"
        assert data["details"]["geometry_type"] == "Polygon"

    def test_crs_error_handler(self, client):
        """Test CRSError is handled correctly."""
        response = client.get("/test/crs-error")

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "CRS_ERROR"
        assert data["details"]["source_crs"] == "EPSG:4326"
        assert data["details"]["target_crs"] == "EPSG:3857"

    def test_storage_error_handler(self, client):
        """Test StorageError is handled correctly."""
        response = client.get("/test/storage-error")

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "STORAGE_ERROR"
        assert data["details"]["operation"] == "save"

    def test_api_error_handler(self, client):
        """Test APIError is handled correctly."""
        response = client.get("/test/api-error")

        assert response.status_code == 429
        data = response.json()
        assert data["error_code"] == "RATE_LIMIT"

    def test_service_unavailable_handler(self, client):
        """Test ServiceUnavailableError is handled correctly."""
        response = client.get("/test/service-unavailable")

        assert response.status_code == 503
        data = response.json()
        assert data["error_code"] == "SERVICE_UNAVAILABLE"
        assert data["details"]["service_name"] == "database"

    def test_config_error_handler(self, client):
        """Test ConfigurationError is handled correctly."""
        response = client.get("/test/config-error")

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "CONFIGURATION_ERROR"
        assert data["details"]["config_key"] == "API_KEY"


class TestPydanticValidationHandler:
    """Tests for Pydantic validation error handler."""

    def test_missing_field_validation(self, client):
        """Test validation error for missing field."""
        response = client.post("/test/pydantic-validation", json={})

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "validation_errors" in data["details"]
        assert data["errors"] is not None

    def test_invalid_type_validation(self, client):
        """Test validation error for invalid type."""
        response = client.post(
            "/test/pydantic-validation",
            json={"name": "John", "age": "not-a-number"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"

    def test_constraint_validation(self, client):
        """Test validation error for constraint violation."""
        response = client.post(
            "/test/pydantic-validation",
            json={"name": "Jo", "age": 25},  # name too short
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert len(data["errors"]) > 0

    def test_multiple_validation_errors(self, client):
        """Test multiple validation errors."""
        response = client.post(
            "/test/pydantic-validation",
            json={"name": "Jo", "age": -5},  # Both invalid
        )

        assert response.status_code == 422
        data = response.json()
        assert len(data["errors"]) >= 2


class TestGenericExceptionHandler:
    """Tests for generic exception handler."""

    def test_generic_error_handler(self, client):
        """Test generic exception is handled correctly."""
        response = client.get("/test/generic-error")

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "INTERNAL_ERROR"
        assert data["message"] == "An unexpected error occurred"
        # In development, details might be exposed
        # In production, they should not be

    def test_error_response_structure(self, client):
        """Test error response has correct structure."""
        response = client.get("/test/validation-error")

        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert "timestamp" in data
        # request_id might not be present without middleware


class TestErrorResponseConsistency:
    """Tests for consistent error response format."""

    def test_all_errors_have_required_fields(self, client):
        """Test all errors have required response fields."""
        endpoints = [
            "/test/validation-error",
            "/test/parse-error",
            "/test/geometry-error",
            "/test/storage-error",
            "/test/generic-error",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            data = response.json()

            # All errors should have these fields
            assert "error_code" in data
            assert "message" in data
            assert "timestamp" in data

    def test_errors_have_suggestions(self, client):
        """Test errors include suggestions for resolution."""
        response = client.get("/test/validation-error")
        data = response.json()

        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) > 0

    def test_errors_have_details(self, client):
        """Test errors include relevant details."""
        response = client.get("/test/parse-error")
        data = response.json()

        assert "details" in data
        assert isinstance(data["details"], dict)


class TestErrorHandlerRegistration:
    """Tests for error handler registration."""

    def test_register_error_handlers(self):
        """Test error handlers can be registered."""
        app = FastAPI()
        register_error_handlers(app)

        # Should have exception handlers registered
        assert len(app.exception_handlers) > 0

    def test_handlers_catch_custom_exceptions(self):
        """Test handlers catch all custom exception types."""
        app = FastAPI()
        register_error_handlers(app)

        # Add test route
        @app.get("/test")
        def test_route():
            raise ValidationError("Test error")

        client = TestClient(app)
        response = client.get("/test")

        # Should be handled by our error handler
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"

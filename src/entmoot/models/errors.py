"""
Pydantic models for standardized error responses.

This module defines the structure for API error responses to ensure
consistency across all endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ErrorDetail(BaseModel):
    """
    Detailed information about a specific error.

    Used for validation errors with multiple field-level issues.
    """

    field: Optional[str] = Field(None, description="Field name that caused the error")
    message: str = Field(..., description="Error message for this field")
    code: Optional[str] = Field(None, description="Error code for this specific issue")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field": "file_size",
                "message": "File size exceeds maximum allowed",
                "code": "VALUE_TOO_LARGE",
            }
        }
    )


class ErrorResponse(BaseModel):
    """
    Standardized error response model for all API errors.

    This model ensures consistent error formatting across the entire API,
    making it easier for clients to handle errors programmatically.

    Attributes:
        error_code: Machine-readable error identifier (e.g., 'VALIDATION_ERROR')
        message: Human-readable error message
        details: Optional dictionary with additional technical details
        timestamp: When the error occurred (UTC)
        request_id: Optional request correlation ID for tracing
        suggestions: Optional list of actionable suggestions for resolution
        errors: Optional list of detailed field-level errors
    """

    error_code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["VALIDATION_ERROR", "PARSE_ERROR", "STORAGE_ERROR"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["File validation failed", "Unable to parse KML file"],
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional technical details about the error",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred (UTC)",
    )
    request_id: Optional[str] = Field(
        None,
        description="Request correlation ID for tracing",
    )
    suggestions: Optional[List[str]] = Field(
        None,
        description="Actionable suggestions for resolving the error",
    )
    errors: Optional[List[ErrorDetail]] = Field(
        None,
        description="Detailed field-level errors (for validation)",
    )

    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: datetime, _info) -> str:
        """Serialize timestamp to ISO format string."""
        return timestamp.isoformat() + 'Z' if timestamp.tzinfo is None else timestamp.isoformat()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "VALIDATION_ERROR",
                "message": "File validation failed",
                "details": {
                    "file_type": "kml",
                    "validation_failed": "magic_number",
                },
                "timestamp": "2025-11-10T15:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "suggestions": [
                    "Verify the file is a valid KML file",
                    "Check for file corruption",
                ],
                "errors": [
                    {
                        "field": "file_content",
                        "message": "File signature does not match KML format",
                        "code": "INVALID_MAGIC_NUMBER",
                    }
                ],
            }
        }
    )


class ValidationErrorResponse(ErrorResponse):
    """
    Specialized error response for validation errors.

    Extends ErrorResponse with validation-specific defaults.
    """

    error_code: str = Field(
        default="VALIDATION_ERROR",
        description="Error code (defaults to VALIDATION_ERROR)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid file format",
                "details": {"field": "file", "expected": "KML/KMZ"},
                "timestamp": "2025-11-10T15:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "suggestions": ["Upload a valid KML or KMZ file"],
                "errors": [
                    {
                        "field": "file_extension",
                        "message": "Extension must be .kml or .kmz",
                        "code": "INVALID_EXTENSION",
                    }
                ],
            }
        }
    )


class ParseErrorResponse(ErrorResponse):
    """
    Specialized error response for parsing errors.

    Extends ErrorResponse with parse-specific defaults.
    """

    error_code: str = Field(
        default="PARSE_ERROR",
        description="Error code (defaults to PARSE_ERROR)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "PARSE_ERROR",
                "message": "Failed to parse KML file",
                "details": {
                    "file_type": "KML",
                    "line_number": 42,
                    "xml_error": "Invalid closing tag",
                },
                "timestamp": "2025-11-10T15:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "suggestions": [
                    "Verify the KML file is well-formed XML",
                    "Try opening in Google Earth to validate",
                ],
            }
        }
    )


class StorageErrorResponse(ErrorResponse):
    """
    Specialized error response for storage errors.

    Extends ErrorResponse with storage-specific defaults.
    """

    error_code: str = Field(
        default="STORAGE_ERROR",
        description="Error code (defaults to STORAGE_ERROR)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "STORAGE_ERROR",
                "message": "Failed to save uploaded file",
                "details": {
                    "operation": "save",
                    "reason": "Insufficient disk space",
                },
                "timestamp": "2025-11-10T15:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "suggestions": [
                    "Try uploading a smaller file",
                    "Contact support if the problem persists",
                ],
            }
        }
    )


class ServiceUnavailableResponse(ErrorResponse):
    """
    Specialized error response for service unavailability.

    Extends ErrorResponse with service unavailable defaults.
    """

    error_code: str = Field(
        default="SERVICE_UNAVAILABLE",
        description="Error code (defaults to SERVICE_UNAVAILABLE)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "Service is temporarily unavailable",
                "details": {
                    "service_name": "file_storage",
                    "reason": "Maintenance in progress",
                },
                "timestamp": "2025-11-10T15:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "suggestions": [
                    "Try again in a few minutes",
                    "Check the status page for updates",
                ],
            }
        }
    )

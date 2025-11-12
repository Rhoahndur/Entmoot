"""
Custom exception hierarchy for Entmoot application.

This module defines a comprehensive exception hierarchy for consistent
error handling throughout the application.
"""

from typing import Any, Dict, List, Optional


class EntmootException(Exception):
    """
    Base exception for all Entmoot-specific errors.

    All custom exceptions should inherit from this base class to allow
    for unified exception handling throughout the application.

    Attributes:
        error_code: String identifier for the error type
        message: User-friendly error message
        details: Technical details for logging/debugging
        status_code: HTTP status code for API responses
        suggestions: Optional list of resolution suggestions
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize EntmootException.

        Args:
            message: User-friendly error message
            error_code: String identifier for the error type
            status_code: HTTP status code (default: 500)
            details: Technical details for logging
            suggestions: List of suggestions for resolution
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.suggestions = suggestions or []

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for API responses.

        Returns:
            Dictionary representation of the error
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
        }

    def __str__(self) -> str:
        """String representation of the exception."""
        return f"{self.error_code}: {self.message}"

    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"error_code='{self.error_code}', "
            f"message='{self.message}', "
            f"status_code={self.status_code})"
        )


class ValidationError(EntmootException):
    """
    Raised when input validation fails.

    Used for invalid user input, malformed data, or constraint violations.
    Maps to HTTP 400 Bad Request.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize ValidationError.

        Args:
            message: User-friendly error message
            field: Name of the field that failed validation
            details: Technical details about the validation failure
            suggestions: List of suggestions for fixing the validation error
        """
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=error_details,
            suggestions=suggestions or ["Check the input format and try again"],
        )


class ParseError(EntmootException):
    """
    Raised when KML/KMZ parsing fails.

    Used for malformed KML/KMZ files, invalid XML structure, or
    unsupported geometry types.
    Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(
        self,
        message: str,
        file_type: Optional[str] = None,
        line_number: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize ParseError.

        Args:
            message: User-friendly error message
            file_type: Type of file being parsed (e.g., 'KML', 'KMZ')
            line_number: Line number where parsing failed (if applicable)
            details: Technical details about the parsing failure
            suggestions: List of suggestions for fixing the file
        """
        error_details = details or {}
        if file_type:
            error_details["file_type"] = file_type
        if line_number:
            error_details["line_number"] = line_number

        default_suggestions = [
            "Verify the file is a valid KML/KMZ file",
            "Check for XML syntax errors",
            "Try opening the file in Google Earth to validate it",
        ]

        super().__init__(
            message=message,
            error_code="PARSE_ERROR",
            status_code=422,
            details=error_details,
            suggestions=suggestions or default_suggestions,
        )


class GeometryError(EntmootException):
    """
    Raised when geometry processing fails.

    Used for invalid geometries, self-intersections, topology errors,
    or unsupported geometry operations.
    Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(
        self,
        message: str,
        geometry_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize GeometryError.

        Args:
            message: User-friendly error message
            geometry_type: Type of geometry that caused the error
            details: Technical details about the geometry error
            suggestions: List of suggestions for fixing the geometry
        """
        error_details = details or {}
        if geometry_type:
            error_details["geometry_type"] = geometry_type

        default_suggestions = [
            "Check for self-intersecting polygons",
            "Verify geometry coordinates are valid",
            "Ensure geometry follows the right-hand rule for polygons",
        ]

        super().__init__(
            message=message,
            error_code="GEOMETRY_ERROR",
            status_code=422,
            details=error_details,
            suggestions=suggestions or default_suggestions,
        )


class CRSError(EntmootException):
    """
    Raised when coordinate reference system operations fail.

    Used for invalid CRS definitions, transformation failures, or
    unsupported coordinate systems.
    Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(
        self,
        message: str,
        source_crs: Optional[str] = None,
        target_crs: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize CRSError.

        Args:
            message: User-friendly error message
            source_crs: Source coordinate reference system
            target_crs: Target coordinate reference system
            details: Technical details about the CRS error
            suggestions: List of suggestions for fixing the CRS issue
        """
        error_details = details or {}
        if source_crs:
            error_details["source_crs"] = source_crs
        if target_crs:
            error_details["target_crs"] = target_crs

        default_suggestions = [
            "Verify the coordinate reference system is supported",
            "Check EPSG codes are valid",
            "Ensure coordinates are in the expected format",
        ]

        super().__init__(
            message=message,
            error_code="CRS_ERROR",
            status_code=422,
            details=error_details,
            suggestions=suggestions or default_suggestions,
        )


class StorageError(EntmootException):
    """
    Raised when file storage operations fail.

    Used for disk full errors, permission issues, or file system failures.
    Maps to HTTP 500 Internal Server Error or 507 Insufficient Storage.
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize StorageError.

        Args:
            message: User-friendly error message
            operation: Storage operation that failed (e.g., 'save', 'delete')
            file_path: Path to the file involved in the error
            details: Technical details about the storage error
            suggestions: List of suggestions for resolution
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if file_path:
            # Don't include full path in user-facing error for security
            error_details["file_path"] = file_path

        default_suggestions = [
            "Try uploading the file again",
            "Contact support if the problem persists",
        ]

        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            status_code=500,
            details=error_details,
            suggestions=suggestions or default_suggestions,
        )


class APIError(EntmootException):
    """
    Raised for generic API-level errors.

    Used for rate limiting, authentication failures, or other
    API-specific issues.
    Maps to appropriate HTTP status code based on the specific error.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "API_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize APIError.

        Args:
            message: User-friendly error message
            error_code: Specific API error code
            status_code: HTTP status code
            details: Technical details about the API error
            suggestions: List of suggestions for resolution
        """
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
            suggestions=suggestions or ["Check the API documentation", "Try again later"],
        )


class ServiceUnavailableError(EntmootException):
    """
    Raised when a service is temporarily unavailable.

    Used for external service failures, maintenance mode, or
    temporary system unavailability.
    Maps to HTTP 503 Service Unavailable.
    """

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize ServiceUnavailableError.

        Args:
            message: User-friendly error message
            service_name: Name of the unavailable service
            details: Technical details about the service failure
            suggestions: List of suggestions for resolution
        """
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name

        default_suggestions = [
            "Try again in a few moments",
            "Check the service status page",
            "Contact support if the problem persists",
        ]

        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=error_details,
            suggestions=suggestions or default_suggestions,
        )


class ConfigurationError(EntmootException):
    """
    Raised when application configuration is invalid.

    Used for missing environment variables, invalid settings, or
    configuration validation failures.
    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        """
        Initialize ConfigurationError.

        Args:
            message: User-friendly error message
            config_key: Configuration key that is invalid
            details: Technical details about the configuration error
            suggestions: List of suggestions for resolution
        """
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        default_suggestions = [
            "Check environment variables are set correctly",
            "Verify configuration file syntax",
            "Contact system administrator",
        ]

        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details=error_details,
            suggestions=suggestions or default_suggestions,
        )

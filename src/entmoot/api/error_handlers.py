"""
FastAPI error handlers for consistent error responses.

This module provides global exception handlers that catch exceptions
and convert them to standardized error responses.
"""

import logging
import traceback
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from entmoot.core.config import settings
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
from entmoot.models.errors import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> Union[str, None]:
    """
    Extract request ID from request state.

    Args:
        request: FastAPI request object

    Returns:
        Request ID if available, None otherwise
    """
    return getattr(request.state, "request_id", None)


async def entmoot_exception_handler(
    request: Request, exc: EntmootException
) -> JSONResponse:
    """
    Handle EntmootException and its subclasses.

    Args:
        request: FastAPI request object
        exc: EntmootException instance

    Returns:
        JSONResponse with error details
    """
    request_id = get_request_id(request)

    # Log the error with context
    logger.error(
        f"EntmootException: {exc.error_code} - {exc.message}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details,
        },
    )

    # Build error response
    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details if exc.details else None,
        request_id=request_id,
        suggestions=exc.suggestions if exc.suggestions else None,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True),
    )


async def validation_error_handler(
    request: Request, exc: Union[RequestValidationError, PydanticValidationError]
) -> JSONResponse:
    """
    Handle Pydantic validation errors from FastAPI.

    Args:
        request: FastAPI request object
        exc: Pydantic ValidationError

    Returns:
        JSONResponse with validation error details
    """
    request_id = get_request_id(request)

    # Extract error details from Pydantic validation errors
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error.get("loc", []))
        errors.append(
            ErrorDetail(
                field=field_path,
                message=error.get("msg", "Validation error"),
                code=error.get("type", "validation_error"),
            )
        )

    # Log the validation error
    logger.warning(
        f"Validation error: {len(errors)} field(s) failed validation",
        extra={
            "request_id": request_id,
            "error_count": len(errors),
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Build error response
    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": [e.model_dump() for e in errors]},
        request_id=request_id,
        suggestions=["Check the request format and field values"],
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(exclude_none=True),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        request: FastAPI request object
        exc: Exception instance

    Returns:
        JSONResponse with generic error message
    """
    request_id = get_request_id(request)

    # Log the exception with full traceback
    # Note: request_id, path, and method are set by LoggingContextMiddleware
    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
        extra={
            "exception_type": type(exc).__name__,
        },
    )

    # Build error response
    # In production, don't expose internal error details
    details = None
    if settings.environment == "development":
        details = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details=details,
        request_id=request_id,
        suggestions=[
            "Try again later",
            "Contact support if the problem persists",
        ],
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(exclude_none=True),
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    Register all error handlers with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Register EntmootException handler (catches all our custom exceptions)
    app.add_exception_handler(EntmootException, entmoot_exception_handler)

    # Register specific handlers for custom exceptions
    # (These are redundant since EntmootException handler catches them,
    # but we keep them for explicit clarity and potential future customization)
    app.add_exception_handler(ValidationError, entmoot_exception_handler)
    app.add_exception_handler(ParseError, entmoot_exception_handler)
    app.add_exception_handler(GeometryError, entmoot_exception_handler)
    app.add_exception_handler(CRSError, entmoot_exception_handler)
    app.add_exception_handler(StorageError, entmoot_exception_handler)
    app.add_exception_handler(APIError, entmoot_exception_handler)
    app.add_exception_handler(ServiceUnavailableError, entmoot_exception_handler)
    app.add_exception_handler(ConfigurationError, entmoot_exception_handler)

    # Register Pydantic validation error handler
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(PydanticValidationError, validation_error_handler)

    # Register generic exception handler as catch-all
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Error handlers registered successfully")

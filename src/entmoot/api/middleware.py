"""
FastAPI middleware for request correlation and logging.

This module provides middleware for adding request IDs to all requests
and propagating them through logging.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID correlation.

    Generates or extracts a unique request ID for each request and makes it
    available throughout the request lifecycle for logging and error tracking.
    """

    def __init__(self, app, header_name: str = "X-Request-ID"):
        """
        Initialize RequestCorrelationMiddleware.

        Args:
            app: FastAPI application
            header_name: HTTP header name for request ID
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add correlation ID.

        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler

        Returns:
            Response with request ID header
        """
        # Try to get request ID from header, or generate a new one
        request_id = request.headers.get(self.header_name, str(uuid.uuid4()))

        # Store request ID in request state for access in routes
        request.state.request_id = request_id

        # Log request start
        # Note: request_id, method, and path are set by LoggingContextMiddleware
        logger.info(f"Request started: {request.method} {request.url.path}")

        # Start timer
        start_time = time.perf_counter()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Add request ID to response headers
            response.headers[self.header_name] = request_id

            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Duration: {duration_ms:.2f}ms"
            )

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- Error: {type(e).__name__} - Duration: {duration_ms:.2f}ms",
                exc_info=True
            )

            # Re-raise exception to be handled by error handlers
            raise


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add logging context to all requests.

    Automatically adds request information to the logging context
    for all log messages during request processing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with logging context.

        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler

        Returns:
            Response object
        """
        # Get request ID from state (should be set by RequestCorrelationMiddleware)
        request_id = getattr(request.state, "request_id", None)

        # Create a custom log record factory that adds request context
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            # Only set attributes if they don't already exist (to avoid overwriting extra={} params)
            # Use custom attribute names to avoid conflicts with LogRecord built-in attributes
            if request_id and not hasattr(record, 'request_id'):
                record.request_id = request_id
            if not hasattr(record, 'http_method'):
                record.http_method = request.method
            if not hasattr(record, 'request_path'):
                record.request_path = request.url.path
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            response = await call_next(request)
            return response
        finally:
            # Restore original factory
            logging.setLogRecordFactory(old_factory)

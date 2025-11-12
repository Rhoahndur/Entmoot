"""
Logging utility functions and decorators.

This module provides helper functions for enhanced logging,
including function call logging, performance tracking, and
sensitive data redaction.
"""

import functools
import logging
import re
import time
from typing import Any, Callable, List, Optional, Pattern, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Patterns for sensitive data that should be redacted
SENSITIVE_PATTERNS: List[Pattern[str]] = [
    re.compile(r"password[\"']?\s*[:=]\s*[\"']?([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"api[_-]?key[\"']?\s*[:=]\s*[\"']?([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"secret[\"']?\s*[:=]\s*[\"']?([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"token[\"']?\s*[:=]\s*[\"']?([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"auth[\"']?\s*[:=]\s*[\"']?([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    ),  # Email addresses
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN pattern
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # Credit card pattern
]

# Fields that should always be redacted
SENSITIVE_FIELDS: Set[str] = {
    "password",
    "api_key",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "private_key",
    "credit_card",
    "ssn",
    "auth",
    "authorization",
}


def redact_sensitive(data: Any, redaction_text: str = "***REDACTED***") -> Any:
    """
    Redact sensitive information from data structures.

    Recursively traverses dictionaries and lists to redact sensitive values.
    Supports strings, dictionaries, lists, and tuples.

    Args:
        data: Data to redact (string, dict, list, or tuple)
        redaction_text: Text to replace sensitive data with

    Returns:
        Data with sensitive information redacted

    Example:
        >>> redact_sensitive({"password": "secret123", "username": "john"})
        {"password": "***REDACTED***", "username": "john"}
    """
    if isinstance(data, dict):
        return {
            key: (
                redaction_text
                if key.lower() in SENSITIVE_FIELDS
                else redact_sensitive(value, redaction_text)
            )
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [redact_sensitive(item, redaction_text) for item in data]
    elif isinstance(data, tuple):
        return tuple(redact_sensitive(item, redaction_text) for item in data)
    elif isinstance(data, str):
        # Redact patterns in strings
        redacted = data
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub(redaction_text, redacted)
        return redacted
    else:
        return data


def log_function_call(
    log_args: bool = True,
    log_result: bool = True,
    log_level: int = logging.DEBUG,
    redact: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to log function calls with arguments and results.

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_level: Logging level to use
        redact: Whether to redact sensitive information

    Returns:
        Decorated function with logging

    Example:
        @log_function_call()
        def process_data(data: dict) -> dict:
            return {"processed": True}
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            func_name = f"{func.__module__}.{func.__qualname__}"

            # Prepare argument string
            if log_args:
                args_repr = [repr(arg) for arg in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                all_args = ", ".join(args_repr + kwargs_repr)

                if redact:
                    all_args = redact_sensitive(all_args)

                logger.log(log_level, f"Calling {func_name}({all_args})")
            else:
                logger.log(log_level, f"Calling {func_name}()")

            # Call the function
            result = func(*args, **kwargs)

            # Log result
            if log_result:
                result_repr = repr(result)
                if redact:
                    result_repr = redact_sensitive(result_repr)

                logger.log(log_level, f"{func_name} returned: {result_repr}")
            else:
                logger.log(log_level, f"{func_name} completed")

            return result

        return wrapper

    return decorator


def log_async_function_call(
    log_args: bool = True,
    log_result: bool = True,
    log_level: int = logging.DEBUG,
    redact: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to log async function calls with arguments and results.

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_level: Logging level to use
        redact: Whether to redact sensitive information

    Returns:
        Decorated async function with logging

    Example:
        @log_async_function_call()
        async def process_data(data: dict) -> dict:
            return {"processed": True}
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = f"{func.__module__}.{func.__qualname__}"

            # Prepare argument string
            if log_args:
                args_repr = [repr(arg) for arg in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                all_args = ", ".join(args_repr + kwargs_repr)

                if redact:
                    all_args = redact_sensitive(all_args)

                logger.log(log_level, f"Calling {func_name}({all_args})")
            else:
                logger.log(log_level, f"Calling {func_name}()")

            # Call the function
            result = await func(*args, **kwargs)

            # Log result
            if log_result:
                result_repr = repr(result)
                if redact:
                    result_repr = redact_sensitive(result_repr)

                logger.log(log_level, f"{func_name} returned: {result_repr}")
            else:
                logger.log(log_level, f"{func_name} completed")

            return result

        return wrapper

    return decorator


def log_performance(
    log_level: int = logging.INFO,
    threshold_ms: Optional[float] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to log function execution time.

    Args:
        log_level: Logging level to use
        threshold_ms: Only log if execution time exceeds this threshold (milliseconds)

    Returns:
        Decorated function with performance logging

    Example:
        @log_performance(threshold_ms=100)
        def slow_operation():
            time.sleep(0.2)  # This will be logged
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            func_name = f"{func.__module__}.{func.__qualname__}"
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000

                # Only log if threshold is not set or exceeded
                if threshold_ms is None or duration_ms >= threshold_ms:
                    logger.log(
                        log_level,
                        f"{func_name} executed in {duration_ms:.2f}ms",
                        extra={"duration_ms": duration_ms, "function": func_name},
                    )

        return wrapper

    return decorator


def log_async_performance(
    log_level: int = logging.INFO,
    threshold_ms: Optional[float] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to log async function execution time.

    Args:
        log_level: Logging level to use
        threshold_ms: Only log if execution time exceeds this threshold (milliseconds)

    Returns:
        Decorated async function with performance logging

    Example:
        @log_async_performance(threshold_ms=100)
        async def slow_operation():
            await asyncio.sleep(0.2)  # This will be logged
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = f"{func.__module__}.{func.__qualname__}"
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000

                # Only log if threshold is not set or exceeded
                if threshold_ms is None or duration_ms >= threshold_ms:
                    logger.log(
                        log_level,
                        f"{func_name} executed in {duration_ms:.2f}ms",
                        extra={"duration_ms": duration_ms, "function": func_name},
                    )

        return wrapper

    return decorator


def log_with_context(
    log_level: int,
    message: str,
    **context: Any,
) -> None:
    """
    Log a message with additional contextual information.

    Args:
        log_level: Logging level
        message: Log message
        **context: Additional context to include in the log

    Example:
        log_with_context(
            logging.INFO,
            "Processing request",
            request_id="123",
            user_id="456",
            action="upload",
        )
    """
    # Redact sensitive information from context
    safe_context = redact_sensitive(context)

    logger.log(log_level, message, extra=safe_context)


class PerformanceTimer:
    """
    Context manager for timing code blocks.

    Usage:
        with PerformanceTimer("database_query") as timer:
            result = db.query(...)
        # Automatically logs execution time
    """

    def __init__(
        self,
        operation_name: str,
        log_level: int = logging.INFO,
        threshold_ms: Optional[float] = None,
    ):
        """
        Initialize PerformanceTimer.

        Args:
            operation_name: Name of the operation being timed
            log_level: Logging level to use
            threshold_ms: Only log if execution time exceeds this threshold
        """
        self.operation_name = operation_name
        self.log_level = log_level
        self.threshold_ms = threshold_ms
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None

    def __enter__(self) -> "PerformanceTimer":
        """Start the timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the timer and log the result."""
        self.end_time = time.perf_counter()
        if self.start_time is not None:
            self.duration_ms = (self.end_time - self.start_time) * 1000

            # Only log if threshold is not set or exceeded
            if self.threshold_ms is None or self.duration_ms >= self.threshold_ms:
                logger.log(
                    self.log_level,
                    f"{self.operation_name} completed in {self.duration_ms:.2f}ms",
                    extra={
                        "duration_ms": self.duration_ms,
                        "operation": self.operation_name,
                    },
                )

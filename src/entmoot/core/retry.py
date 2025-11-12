"""
Retry mechanism with exponential backoff for transient failures.

This module provides decorators and utilities for automatically retrying
failed operations with configurable backoff strategies.
"""

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Default transient exceptions that should trigger retries
DEFAULT_TRANSIENT_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation

    Returns:
        Delay in seconds for this attempt
    """
    delay = base_delay * (exponential_base ** attempt)
    return min(delay, max_delay)


def should_retry(
    exception: Exception,
    retryable_exceptions: Tuple[Type[Exception], ...],
) -> bool:
    """
    Determine if an exception should trigger a retry.

    Args:
        exception: Exception that was raised
        retryable_exceptions: Tuple of exception types to retry

    Returns:
        True if the exception should trigger a retry
    """
    return isinstance(exception, retryable_exceptions)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying synchronous functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exception types to retry
        on_retry: Optional callback function called on each retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry(max_attempts=3, base_delay=1.0)
        def fetch_data():
            # This will be retried up to 3 times
            return requests.get("https://api.example.com/data")
    """
    if retryable_exceptions is None:
        retryable_exceptions = DEFAULT_TRANSIENT_EXCEPTIONS

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry this exception
                    if not should_retry(e, retryable_exceptions):
                        logger.debug(
                            f"Exception {type(e).__name__} is not retryable, "
                            f"raising immediately"
                        )
                        raise

                    # Check if we have attempts left
                    if attempt >= max_attempts - 1:
                        logger.warning(
                            f"Max retry attempts ({max_attempts}) reached for "
                            f"{func.__name__}, raising exception"
                        )
                        raise

                    # Calculate delay
                    delay = exponential_backoff(
                        attempt, base_delay, max_delay, exponential_base
                    )

                    # Log retry attempt
                    logger.info(
                        f"Retry attempt {attempt + 1}/{max_attempts} for "
                        f"{func.__name__} after {delay:.2f}s "
                        f"(error: {type(e).__name__}: {str(e)})"
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(
                                f"Error in retry callback: {callback_error}",
                                exc_info=True,
                            )

                    # Wait before retrying
                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error: no exception to raise")

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exception types to retry
        on_retry: Optional callback function called on each retry

    Returns:
        Decorated async function with retry logic

    Example:
        @async_retry(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            # This will be retried up to 3 times
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com/data") as response:
                    return await response.json()
    """
    if retryable_exceptions is None:
        retryable_exceptions = DEFAULT_TRANSIENT_EXCEPTIONS

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry this exception
                    if not should_retry(e, retryable_exceptions):
                        logger.debug(
                            f"Exception {type(e).__name__} is not retryable, "
                            f"raising immediately"
                        )
                        raise

                    # Check if we have attempts left
                    if attempt >= max_attempts - 1:
                        logger.warning(
                            f"Max retry attempts ({max_attempts}) reached for "
                            f"{func.__name__}, raising exception"
                        )
                        raise

                    # Calculate delay
                    delay = exponential_backoff(
                        attempt, base_delay, max_delay, exponential_base
                    )

                    # Log retry attempt
                    logger.info(
                        f"Retry attempt {attempt + 1}/{max_attempts} for "
                        f"{func.__name__} after {delay:.2f}s "
                        f"(error: {type(e).__name__}: {str(e)})"
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(
                                f"Error in retry callback: {callback_error}",
                                exc_info=True,
                            )

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error: no exception to raise")

        return wrapper

    return decorator


class RetryContext:
    """
    Context manager for retry logic with custom handling.

    Usage:
        retry_ctx = RetryContext(max_attempts=3, base_delay=1.0)
        async with retry_ctx:
            result = await some_operation()
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """
        Initialize RetryContext.

        Args:
            max_attempts: Maximum number of attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            retryable_exceptions: Tuple of exception types to retry
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions or DEFAULT_TRANSIENT_EXCEPTIONS
        self.attempt = 0

    async def __aenter__(self) -> "RetryContext":
        """Enter the async context."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> bool:
        """
        Exit the async context.

        Returns:
            True to suppress the exception (will retry), False to raise it
        """
        if exc_type is None:
            # No exception, success
            return True

        if not issubclass(exc_type, Exception):
            # Not a regular exception, don't retry
            return False

        if not should_retry(exc_val, self.retryable_exceptions):  # type: ignore
            # Not a retryable exception
            return False

        self.attempt += 1

        if self.attempt >= self.max_attempts:
            # Max attempts reached
            logger.warning(
                f"Max retry attempts ({self.max_attempts}) reached, raising exception"
            )
            return False

        # Calculate delay and wait
        delay = exponential_backoff(
            self.attempt - 1,
            self.base_delay,
            self.max_delay,
            self.exponential_base,
        )

        logger.info(
            f"Retry attempt {self.attempt}/{self.max_attempts} "
            f"after {delay:.2f}s (error: {exc_type.__name__}: {str(exc_val)})"
        )

        await asyncio.sleep(delay)

        # Suppress the exception to allow retry
        return True

"""
Centralized logging configuration for the Entmoot application.

This module provides structured logging with multiple handlers,
formats, and log levels for development and production environments.
"""

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from entmoot.core.config import settings


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Outputs log records as JSON for easy parsing by log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # Add custom fields
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "request_id",
                "user_id",
                "duration_ms",
            ]:
                log_data[key] = value

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output in development.

    Adds color codes to log levels for better readability.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted and colored log string
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for other formatters
        record.levelname = levelname

        return formatted


def get_log_level(level_name: str) -> int:
    """
    Convert log level name to logging constant.

    Args:
        level_name: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logging level constant
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name.upper(), logging.INFO)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
    json_logs: bool = False,
    enable_console: bool = True,
) -> None:
    """
    Configure application-wide logging.

    Sets up console and file handlers with appropriate formatters
    based on the environment (development vs production).

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (if file logging is enabled)
        json_logs: Whether to use JSON format for file logs
        enable_console: Whether to enable console logging
    """
    # Determine log level
    if log_level is None:
        log_level = "DEBUG" if settings.environment == "development" else "INFO"

    level = get_log_level(log_level)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (development-friendly)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        if settings.environment == "development":
            # Colored output for development
            console_format = (
                "%(levelname)s | %(asctime)s | %(name)s:%(lineno)d | %(message)s"
            )
            console_formatter = ColoredFormatter(
                console_format, datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            # Plain format for production
            console_format = (
                "%(levelname)s - %(asctime)s - %(name)s - %(message)s"
            )
            console_formatter = logging.Formatter(
                console_format, datefmt="%Y-%m-%d %H:%M:%S"
            )

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler (with rotation)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (10MB per file, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)

        if json_logs:
            # JSON format for production/log aggregation
            file_formatter = JSONFormatter()
        else:
            # Standard format for file logs
            file_format = (
                "%(asctime)s - %(levelname)s - %(name)s - "
                "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
            )
            file_formatter = logging.Formatter(
                file_format, datefmt="%Y-%m-%d %H:%M:%S"
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # Log startup message
    root_logger.info(
        f"Logging initialized: level={log_level}, "
        f"environment={settings.environment}, "
        f"json_logs={json_logs}, "
        f"console={enable_console}, "
        f"file={log_file is not None}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """
    Context manager for adding contextual information to logs.

    Usage:
        with LogContext(request_id="123", user_id="456"):
            logger.info("Processing request")
            # This log will include request_id and user_id
    """

    def __init__(self, **kwargs: Any):
        """
        Initialize LogContext with contextual fields.

        Args:
            **kwargs: Key-value pairs to add to log records
        """
        self.context = kwargs
        self.old_factory = None

    def __enter__(self) -> "LogContext":
        """Enter the context."""
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def add_log_context(**kwargs: Any) -> LogContext:
    """
    Create a log context with additional fields.

    Args:
        **kwargs: Key-value pairs to add to log records

    Returns:
        LogContext instance

    Example:
        with add_log_context(request_id="abc123"):
            logger.info("Processing request")
    """
    return LogContext(**kwargs)

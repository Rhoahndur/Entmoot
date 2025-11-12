"""
Tests for logging utilities and configuration.
"""

import asyncio
import json
import logging
import time
from io import StringIO

import pytest

from entmoot.core.logging_config import (
    JSONFormatter,
    LogContext,
    add_log_context,
    get_log_level,
    setup_logging,
)
from entmoot.utils.logging import (
    PerformanceTimer,
    log_async_function_call,
    log_async_performance,
    log_function_call,
    log_performance,
    log_with_context,
    redact_sensitive,
)


class TestLoggingConfig:
    """Tests for logging configuration."""

    def test_get_log_level(self):
        """Test log level name conversion."""
        assert get_log_level("DEBUG") == logging.DEBUG
        assert get_log_level("INFO") == logging.INFO
        assert get_log_level("WARNING") == logging.WARNING
        assert get_log_level("ERROR") == logging.ERROR
        assert get_log_level("CRITICAL") == logging.CRITICAL
        assert get_log_level("invalid") == logging.INFO  # Default

    def test_get_log_level_case_insensitive(self):
        """Test log level is case insensitive."""
        assert get_log_level("debug") == logging.DEBUG
        assert get_log_level("DeBuG") == logging.DEBUG

    def test_setup_logging_console_only(self):
        """Test logging setup with console handler only."""
        setup_logging(log_level="DEBUG", enable_console=True)

        logger = logging.getLogger()
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) >= 1

    def test_log_context(self):
        """Test LogContext context manager."""
        logger = logging.getLogger("test_context")

        # Store original factory
        old_factory = logging.getLogRecordFactory()

        with LogContext(request_id="123", user_id="456"):
            # Get the current factory and create a record
            factory = logging.getLogRecordFactory()
            record = factory(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
                func=None,
                sinfo=None,
            )
            # Context should add fields to records
            assert hasattr(record, "request_id")
            assert hasattr(record, "user_id")
            assert record.request_id == "123"
            assert record.user_id == "456"

        # Verify factory is restored
        assert logging.getLogRecordFactory() == old_factory

    def test_add_log_context(self):
        """Test add_log_context helper function."""
        context = add_log_context(request_id="abc", operation="test")
        assert isinstance(context, LogContext)


class TestJSONFormatter:
    """Tests for JSON log formatter."""

    def test_json_formatter_basic(self):
        """Test JSON formatter with basic record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert data["message"] == "Test message"
        assert data["line"] == 42

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatter with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.request_id = "123"
        record.duration_ms = 45.67

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["request_id"] == "123"
        assert data["duration_ms"] == 45.67


class TestRedactSensitive:
    """Tests for sensitive data redaction."""

    def test_redact_string_password(self):
        """Test redacting password in string."""
        text = 'password: "secret123"'
        redacted = redact_sensitive(text)
        assert "secret123" not in redacted
        assert "***REDACTED***" in redacted

    def test_redact_dict_password(self):
        """Test redacting password in dictionary."""
        data = {"username": "john", "password": "secret123"}
        redacted = redact_sensitive(data)
        assert redacted["username"] == "john"
        assert redacted["password"] == "***REDACTED***"

    def test_redact_dict_api_key(self):
        """Test redacting API key in dictionary."""
        data = {"api_key": "abc123", "data": "value"}
        redacted = redact_sensitive(data)
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["data"] == "value"

    def test_redact_nested_dict(self):
        """Test redacting nested dictionary."""
        data = {
            "user": {"name": "john", "password": "secret"},
            "settings": {"api_key": "key123"},
        }
        redacted = redact_sensitive(data)
        assert redacted["user"]["name"] == "john"
        assert redacted["user"]["password"] == "***REDACTED***"
        assert redacted["settings"]["api_key"] == "***REDACTED***"

    def test_redact_list(self):
        """Test redacting list of dictionaries."""
        data = [
            {"name": "john", "password": "secret1"},
            {"name": "jane", "password": "secret2"},
        ]
        redacted = redact_sensitive(data)
        assert redacted[0]["name"] == "john"
        assert redacted[0]["password"] == "***REDACTED***"
        assert redacted[1]["password"] == "***REDACTED***"

    def test_redact_email_pattern(self):
        """Test redacting email addresses."""
        text = "Contact: john.doe@example.com"
        redacted = redact_sensitive(text)
        assert "john.doe@example.com" not in redacted

    def test_redact_custom_text(self):
        """Test custom redaction text."""
        data = {"password": "secret"}
        redacted = redact_sensitive(data, redaction_text="[HIDDEN]")
        assert redacted["password"] == "[HIDDEN]"


class TestLogFunctionCall:
    """Tests for log_function_call decorator."""

    def test_log_function_call_basic(self, caplog):
        """Test basic function call logging."""

        @log_function_call(log_level=logging.INFO)
        def test_func(x, y):
            return x + y

        with caplog.at_level(logging.INFO):
            result = test_func(2, 3)

        assert result == 5
        assert "Calling" in caplog.text
        assert "returned" in caplog.text

    def test_log_function_call_no_args(self, caplog):
        """Test function call logging without arguments."""

        @log_function_call(log_args=False, log_result=False, log_level=logging.INFO)
        def test_func():
            return "result"

        with caplog.at_level(logging.INFO):
            test_func()

        assert "Calling" in caplog.text
        assert "completed" in caplog.text

    def test_log_function_call_with_redaction(self, caplog):
        """Test function call logging with sensitive data redaction."""

        @log_function_call(log_level=logging.INFO, redact=True)
        def test_func(password):
            return {"status": "ok"}

        with caplog.at_level(logging.INFO):
            test_func(password="secret123")

        # Password should be redacted in logs
        assert "secret123" not in caplog.text


class TestLogAsyncFunctionCall:
    """Tests for log_async_function_call decorator."""

    @pytest.mark.asyncio
    async def test_log_async_function_call(self, caplog):
        """Test async function call logging."""

        @log_async_function_call(log_level=logging.INFO)
        async def test_func(x):
            await asyncio.sleep(0.01)
            return x * 2

        with caplog.at_level(logging.INFO):
            result = await test_func(5)

        assert result == 10
        assert "Calling" in caplog.text
        assert "returned" in caplog.text


class TestLogPerformance:
    """Tests for performance logging decorators."""

    def test_log_performance_basic(self, caplog):
        """Test basic performance logging."""

        @log_performance(log_level=logging.INFO)
        def slow_func():
            time.sleep(0.05)
            return "done"

        with caplog.at_level(logging.INFO):
            result = slow_func()

        assert result == "done"
        assert "executed in" in caplog.text
        assert "ms" in caplog.text

    def test_log_performance_with_threshold(self, caplog):
        """Test performance logging with threshold."""

        @log_performance(log_level=logging.INFO, threshold_ms=100)
        def fast_func():
            time.sleep(0.01)  # Less than threshold
            return "done"

        with caplog.at_level(logging.INFO):
            fast_func()

        # Should not log since below threshold
        assert "executed in" not in caplog.text

    @pytest.mark.asyncio
    async def test_log_async_performance(self, caplog):
        """Test async performance logging."""

        @log_async_performance(log_level=logging.INFO)
        async def slow_async_func():
            await asyncio.sleep(0.05)
            return "done"

        with caplog.at_level(logging.INFO):
            result = await slow_async_func()

        assert result == "done"
        assert "executed in" in caplog.text


class TestLogWithContext:
    """Tests for log_with_context function."""

    def test_log_with_context_basic(self, caplog):
        """Test logging with additional context."""
        with caplog.at_level(logging.INFO):
            log_with_context(
                logging.INFO,
                "Processing request",
                request_id="123",
                user_id="456",
            )

        assert "Processing request" in caplog.text

    def test_log_with_context_redaction(self, caplog):
        """Test logging with context includes redaction."""
        with caplog.at_level(logging.INFO):
            log_with_context(
                logging.INFO,
                "User login",
                username="john",
                password="secret",
            )

        # Password should be redacted
        assert "secret" not in caplog.text or "REDACTED" in caplog.text


class TestPerformanceTimer:
    """Tests for PerformanceTimer context manager."""

    def test_performance_timer_basic(self, caplog):
        """Test basic performance timer."""
        with caplog.at_level(logging.INFO):
            with PerformanceTimer("test_operation"):
                time.sleep(0.05)

        assert "test_operation completed" in caplog.text
        assert "ms" in caplog.text

    def test_performance_timer_with_threshold(self, caplog):
        """Test performance timer with threshold."""
        with caplog.at_level(logging.INFO):
            with PerformanceTimer("fast_operation", threshold_ms=100):
                time.sleep(0.01)  # Less than threshold

        # Should not log since below threshold
        assert "fast_operation completed" not in caplog.text

    def test_performance_timer_duration(self):
        """Test performance timer duration calculation."""
        with PerformanceTimer("test") as timer:
            time.sleep(0.05)

        assert timer.duration_ms is not None
        assert timer.duration_ms >= 45  # At least 45ms (accounting for variance)

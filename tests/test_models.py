"""
Tests for upload models.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from entmoot.models.upload import (
    ErrorResponse,
    FileType,
    UploadMetadata,
    UploadResponse,
    UploadStatus,
)


class TestFileType:
    """Tests for FileType enum."""

    def test_file_types(self) -> None:
        """Test that all file types are defined."""
        assert FileType.KMZ == "kmz"
        assert FileType.KML == "kml"
        assert FileType.GEOJSON == "geojson"
        assert FileType.GEOTIFF == "tif"
        assert FileType.TIFF == "tiff"


class TestUploadStatus:
    """Tests for UploadStatus enum."""

    def test_statuses(self) -> None:
        """Test that all statuses are defined."""
        assert UploadStatus.PENDING == "pending"
        assert UploadStatus.PROCESSING == "processing"
        assert UploadStatus.COMPLETED == "completed"
        assert UploadStatus.FAILED == "failed"


class TestUploadMetadata:
    """Tests for UploadMetadata model."""

    def test_valid_metadata(self) -> None:
        """Test creating valid metadata."""
        upload_id = uuid4()
        metadata = UploadMetadata(
            upload_id=upload_id,
            filename="test.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
        )

        assert metadata.upload_id == upload_id
        assert metadata.filename == "test.kmz"
        assert metadata.file_type == FileType.KMZ
        assert metadata.file_size == 1024
        assert metadata.status == UploadStatus.PENDING

    def test_filename_validation_with_slash(self) -> None:
        """Test that filenames with slashes are rejected."""
        with pytest.raises(ValidationError, match="invalid characters"):
            UploadMetadata(
                upload_id=uuid4(),
                filename="path/to/test.kmz",
                file_type="kmz",  # type: ignore
                file_size=1024,
                content_type="application/zip",
            )

    def test_filename_validation_with_backslash(self) -> None:
        """Test that filenames with backslashes are rejected."""
        with pytest.raises(ValidationError, match="invalid characters"):
            UploadMetadata(
                upload_id=uuid4(),
                filename="path\\to\\test.kmz",
                file_type="kmz",  # type: ignore
                file_size=1024,
                content_type="application/zip",
            )

    def test_filename_validation_with_dotdot(self) -> None:
        """Test that filenames with .. are rejected."""
        with pytest.raises(ValidationError, match="invalid characters"):
            UploadMetadata(
                upload_id=uuid4(),
                filename="../test.kmz",
                file_type="kmz",  # type: ignore
                file_size=1024,
                content_type="application/zip",
            )

    def test_with_error_message(self) -> None:
        """Test metadata with error message."""
        metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="test.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            status=UploadStatus.FAILED,
            error_message="Test error",
        )

        assert metadata.status == UploadStatus.FAILED
        assert metadata.error_message == "Test error"

    def test_with_custom_upload_time(self) -> None:
        """Test metadata with custom upload time."""
        upload_time = datetime(2025, 1, 1, 12, 0, 0)
        metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="test.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=upload_time,
        )

        assert metadata.upload_time == upload_time


class TestUploadResponse:
    """Tests for UploadResponse model."""

    def test_valid_response(self) -> None:
        """Test creating valid response."""
        upload_id = uuid4()
        response = UploadResponse(
            upload_id=upload_id,
            filename="test.kmz",
            file_size=1024,
        )

        assert response.upload_id == upload_id
        assert response.filename == "test.kmz"
        assert response.file_size == 1024
        assert response.message == "File uploaded successfully"

    def test_custom_message(self) -> None:
        """Test response with custom message."""
        response = UploadResponse(
            upload_id=uuid4(),
            filename="test.kmz",
            file_size=1024,
            message="Custom success message",
        )

        assert response.message == "Custom success message"


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self) -> None:
        """Test creating error response."""
        response = ErrorResponse(
            error="TEST_ERROR",
            message="Test error message",
        )

        assert response.error == "TEST_ERROR"
        assert response.message == "Test error message"
        assert response.details is None

    def test_error_response_with_details(self) -> None:
        """Test error response with details."""
        response = ErrorResponse(
            error="TEST_ERROR",
            message="Test error message",
            details="Additional error details",
        )

        assert response.details == "Additional error details"

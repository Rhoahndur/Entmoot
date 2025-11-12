"""
Pydantic models for file upload operations.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FileType(str, Enum):
    """Supported file types for upload."""

    KMZ = "kmz"
    KML = "kml"
    GEOJSON = "geojson"
    GEOTIFF = "tif"
    TIFF = "tiff"


class UploadStatus(str, Enum):
    """Upload processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadMetadata(BaseModel):
    """
    Metadata for an uploaded file.

    Attributes:
        upload_id: Unique identifier for the upload
        filename: Original filename
        file_type: Type of file uploaded
        file_size: Size in bytes
        content_type: MIME type
        upload_time: Timestamp of upload
        status: Processing status
        error_message: Error message if upload failed
    """

    upload_id: UUID = Field(..., description="Unique identifier for the upload")
    filename: str = Field(..., description="Original filename", min_length=1, max_length=255)
    file_type: FileType = Field(..., description="Type of file uploaded")
    file_size: int = Field(..., description="File size in bytes", gt=0)
    content_type: str = Field(..., description="MIME type of the file")
    upload_time: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")
    status: UploadStatus = Field(
        default=UploadStatus.PENDING, description="Processing status"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "upload_id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "property_boundary.kmz",
                "file_type": "kmz",
                "file_size": 1024000,
                "content_type": "application/vnd.google-earth.kmz",
                "upload_time": "2025-11-10T12:00:00Z",
                "status": "pending",
            }
        }
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename doesn't contain path traversal characters."""
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError("Filename contains invalid characters")
        return v


class UploadResponse(BaseModel):
    """
    Response model for successful upload.

    Attributes:
        upload_id: Unique identifier for the upload
        filename: Original filename
        file_size: Size in bytes
        message: Success message
    """

    upload_id: UUID = Field(..., description="Unique identifier for the upload")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    message: str = Field(default="File uploaded successfully", description="Success message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "upload_id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "property_boundary.kmz",
                "file_size": 1024000,
                "message": "File uploaded successfully",
            }
        }
    )


class ErrorResponse(BaseModel):
    """
    Error response model.

    Attributes:
        error: Error type
        message: Human-readable error message
        details: Additional error details
    """

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[str] = Field(None, description="Additional error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "FILE_TOO_LARGE",
                "message": "File size exceeds maximum allowed size of 50MB",
                "details": "Uploaded file size: 52428800 bytes",
            }
        }
    )

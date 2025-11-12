"""
File upload API endpoint.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from entmoot.core.config import settings
from entmoot.core.errors import ValidationError
from entmoot.core.storage import storage_service
from entmoot.core.validation import (
    scan_for_viruses,
    validate_file_extension,
    validate_file_size,
    validate_magic_number,
    validate_mime_type,
)
from entmoot.models.errors import ErrorResponse
from entmoot.models.upload import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or validation error"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Upload a file",
    description=(
        "Upload a KMZ, KML, GeoJSON, or GeoTIFF file for processing. "
        f"Maximum file size: {settings.max_upload_size_mb}MB. "
        "Files are validated for type, size, and integrity."
    ),
)
async def upload_file(
    file: Annotated[
        UploadFile,
        File(
            description=(
                f"File to upload. Supported types: {', '.join(settings.allowed_extensions)}. "
                f"Maximum size: {settings.max_upload_size_mb}MB."
            )
        ),
    ],
) -> UploadResponse:
    """
    Upload a geospatial data file.

    This endpoint accepts KMZ, KML, GeoJSON, and GeoTIFF files for processing.
    Files are validated for:
    - File extension
    - MIME type matching extension
    - File size (max 50MB by default)
    - Magic number (file signature) verification
    - Optional virus scanning (if enabled)

    Args:
        file: The uploaded file (multipart/form-data)

    Returns:
        UploadResponse with upload ID and metadata

    Raises:
        HTTPException: 400 for validation errors, 413 for file too large, 500 for server errors
    """
    logger.info(f"Received upload request for file: {file.filename}")

    # Validate filename exists
    if not file.filename:
        logger.warning("Upload rejected: no filename provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="INVALID_REQUEST",
                message="Filename is required",
            ).model_dump(mode='json'),
        )

    try:
        # 1. Validate file extension
        extension = validate_file_extension(file.filename, settings.allowed_extensions)
        logger.debug(f"File extension validated: {extension}")

        # 2. Validate MIME type
        content_type = file.content_type or "application/octet-stream"
        validate_mime_type(content_type, extension)
        logger.debug(f"MIME type validated: {content_type}")

        # 3. Read file content (streaming for memory efficiency)
        # We read in chunks but for validation we need the full content
        file_content = await file.read()
        file_size = len(file_content)
        logger.debug(f"File read: {file_size} bytes")

        # 4. Validate file size
        try:
            validate_file_size(file_size, settings.max_upload_size_bytes)
        except ValidationError as e:
            logger.warning(f"File size validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=ErrorResponse(
                    error_code="FILE_TOO_LARGE",
                    message=str(e),
                    details={
                        "file_size": file_size,
                        "max_size": settings.max_upload_size_bytes,
                    },
                ).model_dump(mode='json'),
            )

        # 5. Validate magic number (file signature)
        validate_magic_number(file_content, extension)
        logger.debug("Magic number validated")

        # 6. Save file to storage
        metadata = await storage_service.save_file(
            file_content=file_content,
            filename=file.filename,
            content_type=content_type,
            file_type=extension.lstrip("."),
        )
        logger.info(f"File saved successfully: {metadata.upload_id}")

        # 7. Virus scan (if enabled)
        if settings.virus_scan_enabled:
            file_path = await storage_service.get_file_path(metadata.upload_id)
            if file_path:
                virus_result = await scan_for_viruses(file_path)
                if virus_result:
                    logger.error(f"Virus detected in upload {metadata.upload_id}: {virus_result}")
                    # Delete the infected file
                    await storage_service.delete_upload(metadata.upload_id)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=ErrorResponse(
                            error_code="VIRUS_DETECTED",
                            message="File failed virus scan",
                            details={"virus_result": virus_result},
                        ).model_dump(mode='json'),
                    )

        # 8. Return success response
        return UploadResponse(
            upload_id=metadata.upload_id,
            filename=metadata.filename,
            file_size=metadata.file_size,
            message="File uploaded successfully",
        )

    except ValidationError as e:
        logger.warning(f"Validation error for {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="VALIDATION_ERROR",
                message=str(e),
            ).model_dump(mode='json'),
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An error occurred while processing the upload",
                details={"error": str(e)} if settings.environment == "development" else None,
            ).model_dump(mode='json'),
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Upload service health check",
    description="Check if the upload service is operational",
)
async def upload_health_check() -> JSONResponse:
    """
    Health check for upload service.

    Verifies that:
    - Upload directory exists and is writable
    - Service is operational

    Returns:
        JSON response with health status
    """
    try:
        # Check if uploads directory exists and is writable
        if not settings.uploads_dir.exists():
            settings.uploads_dir.mkdir(parents=True, exist_ok=True)

        # Try to write a test file
        test_file = settings.uploads_dir / ".health_check"
        test_file.touch()
        test_file.unlink()

        return JSONResponse(
            content={
                "status": "healthy",
                "service": "upload",
                "max_upload_size_mb": settings.max_upload_size_mb,
                "allowed_extensions": list(settings.allowed_extensions),
                "virus_scan_enabled": settings.virus_scan_enabled,
            }
        )
    except Exception as e:
        logger.error(f"Upload service health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "upload",
                "error": str(e),
            },
        )

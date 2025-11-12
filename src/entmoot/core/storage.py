"""
File storage service for managing uploaded files.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from entmoot.core.config import settings
from entmoot.models.upload import UploadMetadata, UploadStatus

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Custom exception for storage operations."""

    pass


class FileStorageService:
    """
    Service for managing file storage operations.

    This service handles:
    - Atomic file writes (write to temp, then move)
    - Metadata tracking using JSON sidecar files
    - Directory organization by upload ID
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """
        Initialize the storage service.

        Args:
            base_dir: Base directory for uploads (defaults to settings.uploads_dir)
        """
        self.base_dir = base_dir or settings.uploads_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileStorageService initialized with base_dir: {self.base_dir}")

    def _get_upload_dir(self, upload_id: UUID) -> Path:
        """
        Get the directory for a specific upload.

        Args:
            upload_id: Unique upload identifier

        Returns:
            Path to the upload directory
        """
        return self.base_dir / str(upload_id)

    def _get_metadata_path(self, upload_id: UUID) -> Path:
        """
        Get the path to the metadata file for an upload.

        Args:
            upload_id: Unique upload identifier

        Returns:
            Path to the metadata JSON file
        """
        return self._get_upload_dir(upload_id) / "metadata.json"

    def _get_file_path(self, upload_id: UUID, filename: str) -> Path:
        """
        Get the path where the uploaded file should be stored.

        Args:
            upload_id: Unique upload identifier
            filename: Original filename

        Returns:
            Path to the file storage location
        """
        return self._get_upload_dir(upload_id) / filename

    async def save_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        file_type: str,
    ) -> UploadMetadata:
        """
        Save an uploaded file with atomic write operation.

        This method:
        1. Generates a unique upload ID
        2. Creates the upload directory
        3. Writes file to a temporary location
        4. Moves file to final location (atomic operation)
        5. Writes metadata to a JSON sidecar file

        Args:
            file_content: The file content as bytes
            filename: Original filename
            content_type: MIME type
            file_type: File type/extension

        Returns:
            UploadMetadata with upload information

        Raises:
            StorageError: If file save operation fails
        """
        upload_id = uuid4()
        upload_dir = self._get_upload_dir(upload_id)

        try:
            # Create upload directory
            upload_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created upload directory: {upload_dir}")

            # Prepare paths
            final_path = self._get_file_path(upload_id, filename)
            temp_path = final_path.with_suffix(final_path.suffix + ".tmp")

            # Write to temporary file
            temp_path.write_bytes(file_content)
            logger.debug(f"Wrote file to temporary location: {temp_path}")

            # Atomic move to final location
            shutil.move(str(temp_path), str(final_path))
            logger.debug(f"Moved file to final location: {final_path}")

            # Create metadata
            metadata = UploadMetadata(
                upload_id=upload_id,
                filename=filename,
                file_type=file_type,  # type: ignore
                file_size=len(file_content),
                content_type=content_type,
                upload_time=datetime.utcnow(),
                status=UploadStatus.COMPLETED,
            )

            # Save metadata to JSON
            await self.save_metadata(metadata)

            logger.info(
                f"Successfully saved file {filename} with upload_id: {upload_id}, "
                f"size: {len(file_content)} bytes"
            )

            return metadata

        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            # Cleanup on failure
            if upload_dir.exists():
                shutil.rmtree(upload_dir, ignore_errors=True)
            raise StorageError(f"Failed to save file: {e}") from e

    async def save_metadata(self, metadata: UploadMetadata) -> None:
        """
        Save upload metadata to a JSON file.

        Args:
            metadata: Upload metadata to save

        Raises:
            StorageError: If metadata save fails
        """
        metadata_path = self._get_metadata_path(metadata.upload_id)

        try:
            # Convert metadata to dict and handle datetime serialization
            metadata_dict = metadata.model_dump(mode="json")

            # Write metadata atomically
            temp_path = metadata_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(metadata_dict, indent=2))
            shutil.move(str(temp_path), str(metadata_path))

            logger.debug(f"Saved metadata to: {metadata_path}")

        except Exception as e:
            logger.error(f"Failed to save metadata for {metadata.upload_id}: {e}")
            raise StorageError(f"Failed to save metadata: {e}") from e

    async def get_metadata(self, upload_id: UUID) -> Optional[UploadMetadata]:
        """
        Retrieve metadata for an upload.

        Args:
            upload_id: Unique upload identifier

        Returns:
            UploadMetadata if found, None otherwise
        """
        metadata_path = self._get_metadata_path(upload_id)

        if not metadata_path.exists():
            logger.warning(f"Metadata not found for upload_id: {upload_id}")
            return None

        try:
            metadata_dict = json.loads(metadata_path.read_text())
            return UploadMetadata(**metadata_dict)
        except Exception as e:
            logger.error(f"Failed to read metadata for {upload_id}: {e}")
            return None

    async def get_file_path(self, upload_id: UUID) -> Optional[Path]:
        """
        Get the path to an uploaded file.

        Args:
            upload_id: Unique upload identifier

        Returns:
            Path to the file if it exists, None otherwise
        """
        metadata = await self.get_metadata(upload_id)
        if not metadata:
            return None

        file_path = self._get_file_path(upload_id, metadata.filename)
        return file_path if file_path.exists() else None

    async def delete_upload(self, upload_id: UUID) -> bool:
        """
        Delete an upload and its metadata.

        Args:
            upload_id: Unique upload identifier

        Returns:
            True if deletion succeeded, False otherwise
        """
        upload_dir = self._get_upload_dir(upload_id)

        if not upload_dir.exists():
            logger.warning(f"Upload directory not found: {upload_dir}")
            return False

        try:
            shutil.rmtree(upload_dir)
            logger.info(f"Deleted upload: {upload_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete upload {upload_id}: {e}")
            return False

    async def list_uploads(self) -> list[UUID]:
        """
        List all upload IDs in the storage directory.

        Returns:
            List of upload UUIDs
        """
        upload_ids = []

        if not self.base_dir.exists():
            return upload_ids

        for item in self.base_dir.iterdir():
            if item.is_dir():
                try:
                    upload_id = UUID(item.name)
                    upload_ids.append(upload_id)
                except ValueError:
                    logger.warning(f"Invalid upload directory name: {item.name}")
                    continue

        return upload_ids


# Global storage service instance
storage_service = FileStorageService()

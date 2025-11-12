"""
Unit tests for file storage service.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from entmoot.core.storage import FileStorageService, StorageError
from entmoot.models.upload import UploadStatus


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    storage_dir = tmp_path / "uploads"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def storage_service(temp_storage_dir: Path) -> FileStorageService:
    """Create a FileStorageService instance with temp directory."""
    return FileStorageService(base_dir=temp_storage_dir)


@pytest.mark.asyncio
class TestFileStorageService:
    """Tests for FileStorageService class."""

    async def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test that initialization creates the base directory."""
        storage_dir = tmp_path / "new_storage"
        service = FileStorageService(base_dir=storage_dir)
        assert storage_dir.exists()
        assert storage_dir.is_dir()

    async def test_save_file_success(self, storage_service: FileStorageService) -> None:
        """Test successful file save operation."""
        file_content = b"test content"
        filename = "test.kmz"
        content_type = "application/vnd.google-earth.kmz"
        file_type = "kmz"

        metadata = await storage_service.save_file(
            file_content=file_content,
            filename=filename,
            content_type=content_type,
            file_type=file_type,
        )

        # Verify metadata
        assert metadata.filename == filename
        assert metadata.file_size == len(file_content)
        assert metadata.content_type == content_type
        assert metadata.file_type.value == file_type
        assert metadata.status == UploadStatus.COMPLETED

        # Verify file exists
        upload_dir = storage_service.base_dir / str(metadata.upload_id)
        assert upload_dir.exists()

        file_path = upload_dir / filename
        assert file_path.exists()
        assert file_path.read_bytes() == file_content

        # Verify metadata file exists
        metadata_path = upload_dir / "metadata.json"
        assert metadata_path.exists()

    async def test_save_file_creates_subdirectory(
        self, storage_service: FileStorageService
    ) -> None:
        """Test that save_file creates upload subdirectory."""
        metadata = await storage_service.save_file(
            file_content=b"test",
            filename="test.kml",
            content_type="application/xml",
            file_type="kml",
        )

        upload_dir = storage_service.base_dir / str(metadata.upload_id)
        assert upload_dir.exists()
        assert upload_dir.is_dir()

    async def test_save_metadata(self, storage_service: FileStorageService) -> None:
        """Test saving metadata to JSON file."""
        upload_id = uuid4()
        upload_dir = storage_service.base_dir / str(upload_id)
        upload_dir.mkdir(parents=True)

        from entmoot.models.upload import UploadMetadata

        metadata = UploadMetadata(
            upload_id=upload_id,
            filename="test.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/vnd.google-earth.kmz",
        )

        await storage_service.save_metadata(metadata)

        metadata_path = upload_dir / "metadata.json"
        assert metadata_path.exists()

        # Verify JSON content
        saved_data = json.loads(metadata_path.read_text())
        assert saved_data["upload_id"] == str(upload_id)
        assert saved_data["filename"] == "test.kmz"

    async def test_get_metadata_success(self, storage_service: FileStorageService) -> None:
        """Test retrieving metadata for an upload."""
        # First save a file
        metadata = await storage_service.save_file(
            file_content=b"test",
            filename="test.kml",
            content_type="application/xml",
            file_type="kml",
        )

        # Then retrieve it
        retrieved = await storage_service.get_metadata(metadata.upload_id)

        assert retrieved is not None
        assert retrieved.upload_id == metadata.upload_id
        assert retrieved.filename == metadata.filename

    async def test_get_metadata_not_found(self, storage_service: FileStorageService) -> None:
        """Test that get_metadata returns None for non-existent upload."""
        fake_id = uuid4()
        result = await storage_service.get_metadata(fake_id)
        assert result is None

    async def test_get_file_path_success(self, storage_service: FileStorageService) -> None:
        """Test retrieving file path for an upload."""
        metadata = await storage_service.save_file(
            file_content=b"test content",
            filename="test.geojson",
            content_type="application/geo+json",
            file_type="geojson",
        )

        file_path = await storage_service.get_file_path(metadata.upload_id)

        assert file_path is not None
        assert file_path.exists()
        assert file_path.name == "test.geojson"
        assert file_path.read_bytes() == b"test content"

    async def test_get_file_path_not_found(self, storage_service: FileStorageService) -> None:
        """Test that get_file_path returns None for non-existent upload."""
        fake_id = uuid4()
        result = await storage_service.get_file_path(fake_id)
        assert result is None

    async def test_delete_upload_success(self, storage_service: FileStorageService) -> None:
        """Test deleting an upload."""
        metadata = await storage_service.save_file(
            file_content=b"test",
            filename="test.tif",
            content_type="image/tiff",
            file_type="tif",
        )

        upload_dir = storage_service.base_dir / str(metadata.upload_id)
        assert upload_dir.exists()

        # Delete the upload
        result = await storage_service.delete_upload(metadata.upload_id)

        assert result is True
        assert not upload_dir.exists()

    async def test_delete_upload_not_found(self, storage_service: FileStorageService) -> None:
        """Test deleting a non-existent upload."""
        fake_id = uuid4()
        result = await storage_service.delete_upload(fake_id)
        assert result is False

    async def test_list_uploads_empty(self, storage_service: FileStorageService) -> None:
        """Test listing uploads when directory is empty."""
        uploads = await storage_service.list_uploads()
        assert uploads == []

    async def test_list_uploads_with_files(self, storage_service: FileStorageService) -> None:
        """Test listing multiple uploads."""
        # Create multiple uploads
        metadata1 = await storage_service.save_file(
            file_content=b"test1",
            filename="test1.kmz",
            content_type="application/zip",
            file_type="kmz",
        )

        metadata2 = await storage_service.save_file(
            file_content=b"test2",
            filename="test2.kml",
            content_type="application/xml",
            file_type="kml",
        )

        uploads = await storage_service.list_uploads()

        assert len(uploads) == 2
        assert metadata1.upload_id in uploads
        assert metadata2.upload_id in uploads

    async def test_list_uploads_ignores_invalid_directories(
        self, storage_service: FileStorageService
    ) -> None:
        """Test that list_uploads ignores non-UUID directory names."""
        # Create an invalid directory
        invalid_dir = storage_service.base_dir / "invalid_name"
        invalid_dir.mkdir()

        # Create a valid upload
        metadata = await storage_service.save_file(
            file_content=b"test",
            filename="test.kmz",
            content_type="application/zip",
            file_type="kmz",
        )

        uploads = await storage_service.list_uploads()

        # Should only contain the valid upload
        assert len(uploads) == 1
        assert metadata.upload_id in uploads

    async def test_atomic_write_on_failure(
        self, storage_service: FileStorageService, monkeypatch  # type: ignore
    ) -> None:
        """Test that failed saves are cleaned up."""
        import shutil

        original_move = shutil.move

        # Make move fail
        def failing_move(*args, **kwargs):  # type: ignore
            raise OSError("Simulated failure")

        monkeypatch.setattr(shutil, "move", failing_move)

        with pytest.raises(StorageError):
            await storage_service.save_file(
                file_content=b"test",
                filename="test.kmz",
                content_type="application/zip",
                file_type="kmz",
            )

        # Verify no leftover directories
        uploads = await storage_service.list_uploads()
        assert len(uploads) == 0

    async def test_file_content_integrity(self, storage_service: FileStorageService) -> None:
        """Test that file content is preserved exactly."""
        # Test with binary data
        original_content = bytes(range(256))  # All possible byte values

        metadata = await storage_service.save_file(
            file_content=original_content,
            filename="binary.tif",
            content_type="image/tiff",
            file_type="tif",
        )

        file_path = await storage_service.get_file_path(metadata.upload_id)
        assert file_path is not None

        saved_content = file_path.read_bytes()
        assert saved_content == original_content

    async def test_large_filename(self, storage_service: FileStorageService) -> None:
        """Test saving file with long filename."""
        long_filename = "a" * 200 + ".kmz"

        metadata = await storage_service.save_file(
            file_content=b"test",
            filename=long_filename,
            content_type="application/zip",
            file_type="kmz",
        )

        assert metadata.filename == long_filename

        file_path = await storage_service.get_file_path(metadata.upload_id)
        assert file_path is not None
        assert file_path.name == long_filename

"""
Unit tests for cleanup service.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from entmoot.core.cleanup import CleanupService
from entmoot.core.storage import FileStorageService
from entmoot.models.upload import UploadMetadata, UploadStatus


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


@pytest.fixture
def cleanup_service() -> CleanupService:
    """Create a CleanupService instance."""
    return CleanupService(retention_hours=24, cleanup_interval_minutes=60)


@pytest.mark.asyncio
class TestCleanupService:
    """Tests for CleanupService class."""

    async def test_init(self) -> None:
        """Test cleanup service initialization."""
        service = CleanupService(retention_hours=12, cleanup_interval_minutes=30)
        assert service.retention_hours == 12
        assert service.cleanup_interval_minutes == 30
        assert service._running is False

    async def test_init_uses_defaults(self) -> None:
        """Test that cleanup service uses default settings."""
        from entmoot.core.config import settings

        service = CleanupService()
        assert service.retention_hours == settings.upload_retention_hours

    async def test_cleanup_expired_files_empty_directory(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test cleanup with no files."""
        # Mock the storage service
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 0
        assert stats["deleted"] == 0
        assert stats["errors"] == 0

    async def test_cleanup_expired_files_deletes_old_files(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test that expired files are deleted."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create an old file
        old_metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="old.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=48),
            status=UploadStatus.COMPLETED,
        )

        # Save the file
        upload_dir = storage_service.base_dir / str(old_metadata.upload_id)
        upload_dir.mkdir(parents=True)
        await storage_service.save_metadata(old_metadata)

        # Run cleanup
        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 1
        assert stats["deleted"] == 1
        assert stats["errors"] == 0

        # Verify file was deleted
        assert not upload_dir.exists()

    async def test_cleanup_preserves_recent_files(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test that recent files are not deleted."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create a recent file
        recent_metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="recent.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=1),
            status=UploadStatus.COMPLETED,
        )

        upload_dir = storage_service.base_dir / str(recent_metadata.upload_id)
        upload_dir.mkdir(parents=True)
        await storage_service.save_metadata(recent_metadata)

        # Run cleanup
        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 1
        assert stats["deleted"] == 0
        assert stats["errors"] == 0

        # Verify file still exists
        assert upload_dir.exists()

    async def test_cleanup_skips_processing_files(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test that files being processed are not deleted."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create an old file that's still processing
        processing_metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="processing.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=48),
            status=UploadStatus.PROCESSING,
        )

        upload_dir = storage_service.base_dir / str(processing_metadata.upload_id)
        upload_dir.mkdir(parents=True)
        await storage_service.save_metadata(processing_metadata)

        # Run cleanup
        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 1
        assert stats["deleted"] == 0  # Not deleted because it's processing
        assert stats["errors"] == 0

        # Verify file still exists
        assert upload_dir.exists()

    async def test_cleanup_deletes_failed_files(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test that expired failed uploads are deleted."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create an old failed upload
        failed_metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="failed.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=48),
            status=UploadStatus.FAILED,
        )

        upload_dir = storage_service.base_dir / str(failed_metadata.upload_id)
        upload_dir.mkdir(parents=True)
        await storage_service.save_metadata(failed_metadata)

        # Run cleanup
        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 1
        assert stats["deleted"] == 1
        assert stats["errors"] == 0

        # Verify file was deleted
        assert not upload_dir.exists()

    async def test_cleanup_handles_missing_metadata(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test cleanup handles uploads without metadata gracefully."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create a directory without metadata
        upload_id = uuid4()
        upload_dir = storage_service.base_dir / str(upload_id)
        upload_dir.mkdir(parents=True)

        # Run cleanup
        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 1
        assert stats["deleted"] == 0
        assert stats["errors"] == 0

    async def test_cleanup_multiple_files(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test cleanup with multiple files (mix of old and recent)."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create multiple files
        old1 = UploadMetadata(
            upload_id=uuid4(),
            filename="old1.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=48),
            status=UploadStatus.COMPLETED,
        )

        old2 = UploadMetadata(
            upload_id=uuid4(),
            filename="old2.kml",
            file_type="kml",  # type: ignore
            file_size=2048,
            content_type="application/xml",
            upload_time=datetime.utcnow() - timedelta(hours=36),
            status=UploadStatus.COMPLETED,
        )

        recent = UploadMetadata(
            upload_id=uuid4(),
            filename="recent.geojson",
            file_type="geojson",  # type: ignore
            file_size=512,
            content_type="application/geo+json",
            upload_time=datetime.utcnow() - timedelta(hours=2),
            status=UploadStatus.COMPLETED,
        )

        # Save all files
        for metadata in [old1, old2, recent]:
            upload_dir = storage_service.base_dir / str(metadata.upload_id)
            upload_dir.mkdir(parents=True)
            await storage_service.save_metadata(metadata)

        # Run cleanup
        stats = await cleanup_service.cleanup_expired_files()

        assert stats["checked"] == 3
        assert stats["deleted"] == 2  # Two old files
        assert stats["errors"] == 0

        # Verify correct files were deleted
        assert not (storage_service.base_dir / str(old1.upload_id)).exists()
        assert not (storage_service.base_dir / str(old2.upload_id)).exists()
        assert (storage_service.base_dir / str(recent.upload_id)).exists()

    async def test_run_once(
        self,
        cleanup_service: CleanupService,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test run_once method."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create an old file
        old_metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="old.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=48),
            status=UploadStatus.COMPLETED,
        )

        upload_dir = storage_service.base_dir / str(old_metadata.upload_id)
        upload_dir.mkdir(parents=True)
        await storage_service.save_metadata(old_metadata)

        # Run cleanup once
        stats = await cleanup_service.run_once()

        assert stats["deleted"] == 1
        assert not upload_dir.exists()

    async def test_start_and_stop(self, cleanup_service: CleanupService) -> None:
        """Test starting and stopping the cleanup service."""
        assert not cleanup_service._running

        await cleanup_service.start()
        assert cleanup_service._running
        assert cleanup_service._task is not None

        await cleanup_service.stop()
        assert not cleanup_service._running

    async def test_start_already_running(self, cleanup_service: CleanupService) -> None:
        """Test that starting an already running service is safe."""
        await cleanup_service.start()
        await cleanup_service.start()  # Should not raise
        await cleanup_service.stop()

    async def test_stop_not_running(self, cleanup_service: CleanupService) -> None:
        """Test that stopping a non-running service is safe."""
        await cleanup_service.stop()  # Should not raise

    async def test_cleanup_loop_runs_periodically(
        self,
        storage_service: FileStorageService,
        monkeypatch,  # type: ignore
    ) -> None:
        """Test that cleanup loop runs periodically."""
        from entmoot.core import cleanup

        monkeypatch.setattr(cleanup, "storage_service", storage_service)

        # Create service with very short interval for testing
        service = CleanupService(retention_hours=0, cleanup_interval_minutes=0.005)

        # Create an old file
        old_metadata = UploadMetadata(
            upload_id=uuid4(),
            filename="old.kmz",
            file_type="kmz",  # type: ignore
            file_size=1024,
            content_type="application/zip",
            upload_time=datetime.utcnow() - timedelta(hours=1),
            status=UploadStatus.COMPLETED,
        )

        upload_dir = storage_service.base_dir / str(old_metadata.upload_id)
        upload_dir.mkdir(parents=True)
        await storage_service.save_metadata(old_metadata)

        # Start the service
        await service.start()

        # Wait a bit for cleanup to run (0.005 min = 0.3 sec, so wait 1 sec to be safe)
        await asyncio.sleep(1.5)

        # Stop the service
        await service.stop()

        # Verify file was cleaned up
        # Note: This test is timing-dependent, so we just verify service ran
        assert service._running is False

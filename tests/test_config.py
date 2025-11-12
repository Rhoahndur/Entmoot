"""
Tests for configuration module.
"""

import pytest
from pathlib import Path

from entmoot.core.config import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = Settings()
        assert settings.max_upload_size_mb == 50
        assert settings.upload_retention_hours == 24
        assert settings.virus_scan_enabled is False
        assert settings.api_v1_prefix == "/api/v1"
        assert settings.environment == "development"

    def test_max_upload_size_bytes(self) -> None:
        """Test max_upload_size_bytes property."""
        settings = Settings(max_upload_size_mb=10)
        assert settings.max_upload_size_bytes == 10 * 1024 * 1024

    def test_uploads_dir_created(self, tmp_path: Path) -> None:
        """Test that uploads directory is created on initialization."""
        upload_dir = tmp_path / "test_uploads"
        assert not upload_dir.exists()

        settings = Settings(uploads_dir=upload_dir)
        assert upload_dir.exists()

    def test_allowed_extensions(self) -> None:
        """Test that allowed extensions are properly configured."""
        settings = Settings()
        assert ".kmz" in settings.allowed_extensions
        assert ".kml" in settings.allowed_extensions
        assert ".geojson" in settings.allowed_extensions
        assert ".tif" in settings.allowed_extensions
        assert ".tiff" in settings.allowed_extensions

    def test_custom_values(self, tmp_path: Path) -> None:
        """Test setting custom configuration values."""
        upload_dir = tmp_path / "custom_uploads"
        settings = Settings(
            max_upload_size_mb=100,
            upload_retention_hours=48,
            uploads_dir=upload_dir,
            virus_scan_enabled=True,
            environment="production",
        )

        assert settings.max_upload_size_mb == 100
        assert settings.upload_retention_hours == 48
        assert settings.uploads_dir == upload_dir
        assert settings.virus_scan_enabled is True
        assert settings.environment == "production"

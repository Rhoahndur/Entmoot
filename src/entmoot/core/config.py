"""
Configuration settings for the Entmoot application.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Attributes:
        max_upload_size_mb: Maximum file upload size in megabytes
        upload_retention_hours: Hours to retain uploaded files before cleanup
        uploads_dir: Directory for storing uploaded files
        allowed_extensions: Tuple of allowed file extensions
        virus_scan_enabled: Whether virus scanning is enabled
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="ENTMOOT_",
    )

    # Upload settings
    max_upload_size_mb: int = 50
    upload_retention_hours: int = 24
    uploads_dir: Path = Path("./data/uploads")

    # Allowed file types
    allowed_extensions: tuple[str, ...] = (".kmz", ".kml", ".geojson", ".tif", ".tiff")

    # Security settings
    virus_scan_enabled: bool = False

    # API settings
    api_v1_prefix: str = "/api/v1"
    port: int = 8000

    # CORS settings
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:4173"

    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    def model_post_init(self, __context: object) -> None:
        """Create uploads directory if it doesn't exist."""
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

"""
KMZ ZIP validation module.

Validates KMZ files (zipped KML) for proper ZIP structure and required files.
"""

import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class KMZValidationResult:
    """
    Result of KMZ validation.

    Attributes:
        is_valid: Whether the KMZ is valid
        errors: List of validation errors
        warnings: List of validation warnings
        has_kml: Whether file contains KML file(s)
        kml_files: List of KML files found in archive
        has_images: Whether file contains image files
        image_files: List of image files found
        total_files: Total number of files in archive
        archive_size: Size of archive in bytes
    """

    is_valid: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    has_kml: bool = False
    kml_files: List[str] = field(default_factory=list)
    has_images: bool = False
    image_files: List[str] = field(default_factory=list)
    total_files: int = 0
    archive_size: int = 0

    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)


class KMZValidator:
    """
    Validates KMZ files (zipped KML containers).

    Checks:
    - Valid ZIP archive
    - Contains at least one .kml file
    - Archive not corrupted
    - File size within reasonable limits
    """

    MAX_ARCHIVE_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500 MB
    SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}

    def __init__(self) -> None:
        """Initialize KMZ validator."""
        self.result: Optional[KMZValidationResult] = None

    def validate(self, kmz_path: Union[str, Path]) -> KMZValidationResult:
        """
        Validate KMZ file.

        Args:
            kmz_path: Path to KMZ file

        Returns:
            KMZValidationResult with validation status and details
        """
        self.result = KMZValidationResult()

        try:
            kmz_path = Path(kmz_path) if isinstance(kmz_path, str) else kmz_path

            # Check if file exists
            if not kmz_path.exists():
                self.result.add_error(f"File not found: {kmz_path}")
                return self.result

            # Check if file is a file (not directory)
            if not kmz_path.is_file():
                self.result.add_error(f"Not a file: {kmz_path}")
                return self.result

            # Check file size
            file_size = kmz_path.stat().st_size
            self.result.archive_size = file_size

            if file_size == 0:
                self.result.add_error("KMZ file is empty")
                return self.result

            if file_size > self.MAX_ARCHIVE_SIZE:
                self.result.add_error(
                    f"KMZ file too large: {file_size} bytes "
                    f"(max {self.MAX_ARCHIVE_SIZE} bytes)"
                )
                return self.result

            # Validate ZIP structure
            if not self._validate_zip(kmz_path):
                return self.result

            # Validate contents
            self._validate_contents(kmz_path)

            # Final validation check
            if not self.result.errors:
                self.result.is_valid = True
                if not self.result.has_kml:
                    self.result.add_error("No KML files found in KMZ archive")
                    self.result.is_valid = False

            return self.result

        except Exception as e:
            logger.error(f"Unexpected error during KMZ validation: {e}")
            self.result.add_error(f"Validation failed: {e}")
            return self.result

    def _validate_zip(self, kmz_path: Path) -> bool:
        """
        Validate that file is a valid ZIP archive.

        Args:
            kmz_path: Path to KMZ file

        Returns:
            True if valid ZIP, False otherwise
        """
        try:
            with zipfile.ZipFile(kmz_path, "r") as zf:
                # Test ZIP integrity
                bad_file = zf.testzip()
                if bad_file is not None:
                    self.result.add_error(
                        f"Corrupt file in archive: {bad_file}"
                    )
                    return False

                # Get file count
                file_list = zf.namelist()
                self.result.total_files = len(file_list)

                if self.result.total_files == 0:
                    self.result.add_error("KMZ archive is empty")
                    return False

                # Check total uncompressed size
                total_size = sum(zf.getinfo(name).file_size for name in file_list)
                if total_size > self.MAX_UNCOMPRESSED_SIZE:
                    self.result.add_error(
                        f"Uncompressed size too large: {total_size} bytes "
                        f"(max {self.MAX_UNCOMPRESSED_SIZE} bytes)"
                    )
                    return False

                return True

        except zipfile.BadZipFile:
            self.result.add_error("Invalid ZIP file format")
            return False
        except Exception as e:
            self.result.add_error(f"Failed to read ZIP archive: {e}")
            return False

    def _validate_contents(self, kmz_path: Path) -> None:
        """
        Validate contents of KMZ archive.

        Args:
            kmz_path: Path to KMZ file
        """
        try:
            with zipfile.ZipFile(kmz_path, "r") as zf:
                for file_info in zf.infolist():
                    # Skip directories
                    if file_info.is_dir():
                        continue

                    filename = file_info.filename
                    file_path = Path(filename)
                    extension = file_path.suffix.lower()

                    # Check for KML files
                    if extension == ".kml":
                        self.result.kml_files.append(filename)
                        self.result.has_kml = True

                        # Validate KML file is not empty
                        if file_info.file_size == 0:
                            self.result.add_warning(
                                f"KML file is empty: {filename}"
                            )

                    # Check for image files
                    elif extension in self.SUPPORTED_IMAGE_EXTENSIONS:
                        self.result.image_files.append(filename)
                        self.result.has_images = True

                    # Check for suspicious files
                    elif extension in {".exe", ".bat", ".sh", ".cmd"}:
                        self.result.add_warning(
                            f"Potentially dangerous file found: {filename}"
                        )

                # Warn about multiple KML files
                if len(self.result.kml_files) > 1:
                    self.result.add_warning(
                        f"Multiple KML files found: {len(self.result.kml_files)}. "
                        "Will use doc.kml if present, otherwise first file."
                    )

        except Exception as e:
            logger.error(f"Error validating KMZ contents: {e}")
            self.result.add_error(f"Failed to validate contents: {e}")


def validate_kmz_file(file_path: Union[str, Path]) -> KMZValidationResult:
    """
    Convenience function to validate a KMZ file.

    Args:
        file_path: Path to KMZ file

    Returns:
        KMZValidationResult
    """
    validator = KMZValidator()
    return validator.validate(file_path)

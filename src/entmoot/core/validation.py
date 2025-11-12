"""
File validation utilities for upload operations.
"""

import logging
from pathlib import Path
from typing import Optional

from entmoot.core.errors import ValidationError

logger = logging.getLogger(__name__)


# MIME type mappings for supported file types
MIME_TYPE_MAPPING = {
    ".kmz": ["application/vnd.google-earth.kmz", "application/zip", "application/octet-stream"],
    ".kml": [
        "application/vnd.google-earth.kml+xml",
        "application/xml",
        "text/xml",
        "text/plain",
        "application/octet-stream",  # Browsers often use this for unknown types
    ],
    ".geojson": ["application/geo+json", "application/json", "text/plain", "application/octet-stream"],
    ".tif": ["image/tiff", "application/octet-stream"],
    ".tiff": ["image/tiff", "application/octet-stream"],
}

# Magic number signatures for file type detection
MAGIC_NUMBERS = {
    # ZIP files (KMZ is a ZIP file)
    ".kmz": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    # KML files start with XML declaration or tag
    ".kml": [b"<?xml", b"<kml"],
    # GeoJSON files start with { or [
    ".geojson": [b"{", b"["],
    # TIFF files
    ".tif": [b"II\x2a\x00", b"MM\x00\x2a"],  # Little-endian  # Big-endian
    ".tiff": [b"II\x2a\x00", b"MM\x00\x2a"],
}


def validate_file_extension(filename: str, allowed_extensions: tuple[str, ...]) -> str:
    """
    Validate that the file has an allowed extension.

    Args:
        filename: The name of the file to validate
        allowed_extensions: Tuple of allowed file extensions (with dots)

    Returns:
        The lowercase file extension (with dot)

    Raises:
        ValidationError: If the file extension is not allowed
    """
    file_path = Path(filename)
    extension = file_path.suffix.lower()

    if not extension:
        raise ValidationError("File has no extension")

    if extension not in allowed_extensions:
        raise ValidationError(
            f"File type '{extension}' not allowed. "
            f"Allowed types: {', '.join(allowed_extensions)}"
        )

    return extension


def validate_mime_type(content_type: str, extension: str) -> None:
    """
    Validate that the MIME type matches the file extension.

    Args:
        content_type: The MIME type from the upload
        extension: The file extension (with dot, lowercase)

    Raises:
        ValidationError: If MIME type doesn't match extension
    """
    # Get allowed MIME types for this extension
    allowed_types = MIME_TYPE_MAPPING.get(extension, [])

    if not allowed_types:
        raise ValidationError(f"No MIME type mapping found for extension: {extension}")

    # Check if the content type matches any allowed type
    # We do a case-insensitive comparison and handle parameters (e.g., charset)
    content_type_base = content_type.split(";")[0].strip().lower()

    if content_type_base not in [mime.lower() for mime in allowed_types]:
        raise ValidationError(
            f"MIME type '{content_type}' does not match file extension '{extension}'. "
            f"Expected one of: {', '.join(allowed_types)}"
        )


def validate_magic_number(file_content: bytes, extension: str) -> None:
    """
    Validate file content using magic number (file signature) detection.

    Args:
        file_content: The first bytes of the file
        extension: The file extension (with dot, lowercase)

    Raises:
        ValidationError: If magic number doesn't match expected file type
    """
    expected_signatures = MAGIC_NUMBERS.get(extension, [])

    if not expected_signatures:
        logger.warning(f"No magic number validation available for {extension}")
        return

    # Check if file starts with any of the expected signatures
    for signature in expected_signatures:
        if file_content.startswith(signature):
            return

    raise ValidationError(
        f"File content does not match expected format for '{extension}' files. "
        f"File may be corrupted or mislabeled."
    )


def validate_file_size(file_size: int, max_size_bytes: int) -> None:
    """
    Validate that the file size is within allowed limits.

    Args:
        file_size: Size of the file in bytes
        max_size_bytes: Maximum allowed size in bytes

    Raises:
        ValidationError: If file is too large
    """
    if file_size <= 0:
        raise ValidationError("File is empty")

    if file_size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValidationError(
            f"File size ({actual_mb:.2f}MB) exceeds maximum allowed size of {max_mb:.0f}MB"
        )


async def scan_for_viruses(file_path: Path) -> Optional[str]:
    """
    Placeholder for virus scanning functionality.

    This function is a placeholder for integration with antivirus software
    like ClamAV. When implemented, it should scan the file and return
    None if clean, or a string describing the threat if infected.

    Args:
        file_path: Path to the file to scan

    Returns:
        None if file is clean, error message if infected

    Note:
        To enable virus scanning:
        1. Install ClamAV (https://www.clamav.net/)
        2. Install Python bindings: pip install clamd
        3. Set ENTMOOT_VIRUS_SCAN_ENABLED=true
        4. Implement scanning logic here using clamd.ClamdUnixSocket()
    """
    logger.debug(f"Virus scanning not enabled for file: {file_path}")
    return None

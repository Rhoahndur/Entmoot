"""
KMZ parsing module.

Extracts and parses KML from KMZ (zipped KML) files, handling embedded resources.
"""

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Union

from .kml_parser import KMLParser, ParsedKML
from .kmz_validator import KMZValidator

logger = logging.getLogger(__name__)


class KMZParser:
    """
    Parse KMZ files by extracting and parsing contained KML.

    Handles:
    - KMZ extraction
    - Main KML file selection (doc.kml or first .kml)
    - Embedded resource handling
    - Temporary file cleanup
    """

    def __init__(self, validate: bool = True) -> None:
        """
        Initialize KMZ parser.

        Args:
            validate: Whether to validate KMZ and KML before parsing
        """
        self.validate = validate

    def parse(self, kmz_path: Union[str, Path]) -> ParsedKML:
        """
        Parse KMZ file.

        Args:
            kmz_path: Path to KMZ file

        Returns:
            ParsedKML with all extracted data from main KML file

        Raises:
            ValueError: If KMZ is invalid or contains no KML files
            FileNotFoundError: If KMZ file doesn't exist
        """
        kmz_path = Path(kmz_path) if isinstance(kmz_path, str) else kmz_path

        if not kmz_path.exists():
            raise FileNotFoundError(f"KMZ file not found: {kmz_path}")

        try:
            # Validate KMZ if requested
            if self.validate:
                validator = KMZValidator()
                validation_result = validator.validate(kmz_path)
                if not validation_result.is_valid:
                    error_msg = "; ".join(validation_result.errors)
                    raise ValueError(f"Invalid KMZ: {error_msg}")

                if not validation_result.has_kml:
                    raise ValueError("KMZ contains no KML files")

            # Extract and parse KML
            kml_content = self._extract_main_kml(kmz_path)
            if kml_content is None:
                raise ValueError("Failed to extract KML from KMZ")

            # Parse the extracted KML
            parser = KMLParser(validate=self.validate)
            result = parser.parse(kml_content)

            # Add KMZ source info to properties
            result.properties["source_file"] = str(kmz_path.name)
            result.properties["source_type"] = "kmz"

            return result

        except Exception as e:
            logger.error(f"Failed to parse KMZ: {e}")
            raise

    def _extract_main_kml(self, kmz_path: Path) -> Optional[bytes]:
        """
        Extract the main KML file from KMZ archive.

        Priority:
        1. doc.kml (KML convention)
        2. First .kml file found

        Args:
            kmz_path: Path to KMZ file

        Returns:
            KML content as bytes, or None if no KML found
        """
        try:
            with zipfile.ZipFile(kmz_path, "r") as zf:
                kml_files = [
                    name for name in zf.namelist() if name.lower().endswith(".kml")
                ]

                if not kml_files:
                    logger.error("No KML files found in KMZ archive")
                    return None

                # Look for doc.kml first
                main_kml = None
                for name in kml_files:
                    if Path(name).name.lower() == "doc.kml":
                        main_kml = name
                        break

                # If no doc.kml, use first KML file
                if main_kml is None:
                    main_kml = kml_files[0]
                    logger.info(
                        f"No doc.kml found, using first KML file: {main_kml}"
                    )

                # Extract and read KML
                logger.info(f"Extracting KML file: {main_kml}")
                kml_content = zf.read(main_kml)
                return kml_content

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {e}")
            raise ValueError(f"Invalid KMZ file: {e}")
        except Exception as e:
            logger.error(f"Failed to extract KML from KMZ: {e}")
            raise

    def extract_all(
        self, kmz_path: Union[str, Path], output_dir: Union[str, Path]
    ) -> Path:
        """
        Extract all contents of KMZ to output directory.

        Useful for accessing embedded images and resources.

        Args:
            kmz_path: Path to KMZ file
            output_dir: Directory to extract files to

        Returns:
            Path to extraction directory

        Raises:
            ValueError: If KMZ is invalid
            FileNotFoundError: If KMZ file doesn't exist
        """
        kmz_path = Path(kmz_path) if isinstance(kmz_path, str) else kmz_path
        output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir

        if not kmz_path.exists():
            raise FileNotFoundError(f"KMZ file not found: {kmz_path}")

        try:
            # Create output directory if it doesn't exist
            output_dir.mkdir(parents=True, exist_ok=True)

            # Extract all files
            with zipfile.ZipFile(kmz_path, "r") as zf:
                zf.extractall(output_dir)
                logger.info(f"Extracted {len(zf.namelist())} files to {output_dir}")

            return output_dir

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {e}")
            raise ValueError(f"Invalid KMZ file: {e}")
        except Exception as e:
            logger.error(f"Failed to extract KMZ: {e}")
            raise

    def list_contents(self, kmz_path: Union[str, Path]) -> dict:
        """
        List all files in KMZ archive without extracting.

        Args:
            kmz_path: Path to KMZ file

        Returns:
            Dictionary with file information

        Raises:
            ValueError: If KMZ is invalid
            FileNotFoundError: If KMZ file doesn't exist
        """
        kmz_path = Path(kmz_path) if isinstance(kmz_path, str) else kmz_path

        if not kmz_path.exists():
            raise FileNotFoundError(f"KMZ file not found: {kmz_path}")

        try:
            contents = {
                "kml_files": [],
                "image_files": [],
                "other_files": [],
                "total_files": 0,
                "total_size": 0,
            }

            with zipfile.ZipFile(kmz_path, "r") as zf:
                for file_info in zf.infolist():
                    if file_info.is_dir():
                        continue

                    filename = file_info.filename
                    file_size = file_info.file_size
                    extension = Path(filename).suffix.lower()

                    contents["total_files"] += 1
                    contents["total_size"] += file_size

                    if extension == ".kml":
                        contents["kml_files"].append(
                            {"name": filename, "size": file_size}
                        )
                    elif extension in {".jpg", ".jpeg", ".png", ".gif", ".bmp"}:
                        contents["image_files"].append(
                            {"name": filename, "size": file_size}
                        )
                    else:
                        contents["other_files"].append(
                            {"name": filename, "size": file_size}
                        )

            return contents

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {e}")
            raise ValueError(f"Invalid KMZ file: {e}")
        except Exception as e:
            logger.error(f"Failed to read KMZ contents: {e}")
            raise


def parse_kmz_file(file_path: Union[str, Path], validate: bool = True) -> ParsedKML:
    """
    Convenience function to parse a KMZ file.

    Args:
        file_path: Path to KMZ file
        validate: Whether to validate before parsing

    Returns:
        ParsedKML
    """
    parser = KMZParser(validate=validate)
    return parser.parse(file_path)

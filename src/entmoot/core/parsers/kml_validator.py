"""
KML XML validation module.

Validates KML files for structural correctness, proper XML formatting,
and required KML elements before parsing.
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = "{http://www.opengis.net/kml/2.2}"


@dataclass
class KMLValidationResult:
    """
    Result of KML validation.

    Attributes:
        is_valid: Whether the KML is valid
        errors: List of validation errors
        warnings: List of validation warnings
        has_placemarks: Whether file contains any placemarks
        has_geometries: Whether file contains any geometries
        geometry_count: Number of geometries found
        namespace: KML namespace used in file
    """

    is_valid: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    has_placemarks: bool = False
    has_geometries: bool = False
    geometry_count: int = 0
    namespace: Optional[str] = None

    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)


class KMLValidator:
    """
    Validates KML files for structural correctness.

    Checks:
    - Valid XML structure
    - Proper KML namespace
    - Required root element (kml)
    - Presence of Document or Folder elements
    - Valid geometry elements
    """

    REQUIRED_ROOT = "kml"
    SUPPORTED_GEOMETRIES = {
        "Point",
        "LineString",
        "LinearRing",
        "Polygon",
        "MultiGeometry",
    }

    def __init__(self) -> None:
        """Initialize KML validator."""
        self.result: Optional[KMLValidationResult] = None

    def validate(self, kml_content: Union[str, bytes, Path]) -> KMLValidationResult:
        """
        Validate KML content.

        Args:
            kml_content: KML content as string, bytes, or file path

        Returns:
            KMLValidationResult with validation status and details
        """
        self.result = KMLValidationResult()

        try:
            # Load KML content
            if isinstance(kml_content, Path):
                if not kml_content.exists():
                    self.result.add_error(f"File not found: {kml_content}")
                    return self.result
                with open(kml_content, "rb") as f:
                    kml_bytes = f.read()
            elif isinstance(kml_content, str):
                kml_bytes = kml_content.encode("utf-8")
            else:
                kml_bytes = kml_content

            # Check if content is empty
            if not kml_bytes or len(kml_bytes.strip()) == 0:
                self.result.add_error("KML content is empty")
                return self.result

            # Parse XML
            try:
                root = ET.fromstring(kml_bytes)
            except ET.ParseError as e:
                self.result.add_error(f"Invalid XML structure: {e}")
                return self.result

            # Validate root element
            if not self._validate_root(root):
                return self.result

            # Extract namespace
            self._extract_namespace(root)

            # Validate structure
            self._validate_structure(root)

            # Validate geometries
            self._validate_geometries(root)

            # Final validation check
            if not self.result.errors:
                self.result.is_valid = True
                if self.result.geometry_count == 0:
                    self.result.add_warning("No geometries found in KML file")
                if not self.result.has_placemarks:
                    self.result.add_warning("No placemarks found in KML file")

            return self.result

        except Exception as e:
            logger.error(f"Unexpected error during KML validation: {e}")
            self.result.add_error(f"Validation failed: {e}")
            return self.result

    def _validate_root(self, root: ET.Element) -> bool:
        """
        Validate root element is 'kml'.

        Args:
            root: XML root element

        Returns:
            True if root is valid, False otherwise
        """
        # Check root tag (with or without namespace)
        tag = root.tag.split("}")[1] if "}" in root.tag else root.tag

        if tag != self.REQUIRED_ROOT:
            self.result.add_error(
                f"Invalid root element: expected '{self.REQUIRED_ROOT}', got '{tag}'"
            )
            return False

        return True

    def _extract_namespace(self, root: ET.Element) -> None:
        """
        Extract KML namespace from root element.

        Args:
            root: XML root element
        """
        if "}" in root.tag:
            self.result.namespace = root.tag.split("}")[0] + "}"
        else:
            self.result.add_warning("No namespace found in KML file")

    def _validate_structure(self, root: ET.Element) -> None:
        """
        Validate KML structure (Document, Folder, Placemark hierarchy).

        Args:
            root: XML root element
        """
        ns = self.result.namespace or ""

        # Look for Document or Folder elements
        document = root.find(f".//{ns}Document")
        folders = root.findall(f".//{ns}Folder")
        placemarks = root.findall(f".//{ns}Placemark")

        if not document and not folders and not placemarks:
            self.result.add_error(
                "No Document, Folder, or Placemark elements found in KML"
            )
            return

        # Check for placemarks
        if placemarks:
            self.result.has_placemarks = True
        else:
            self.result.add_warning("No Placemark elements found")

    def _validate_geometries(self, root: ET.Element) -> None:
        """
        Validate geometry elements in KML.

        Args:
            root: XML root element
        """
        ns = self.result.namespace or ""
        geometry_count = 0

        for geom_type in self.SUPPORTED_GEOMETRIES:
            elements = root.findall(f".//{ns}{geom_type}")
            geometry_count += len(elements)

            # Validate specific geometry requirements
            for elem in elements:
                self._validate_geometry_element(elem, geom_type)

        self.result.geometry_count = geometry_count
        self.result.has_geometries = geometry_count > 0

    def _validate_geometry_element(
        self, element: ET.Element, geom_type: str
    ) -> None:
        """
        Validate individual geometry element.

        Args:
            element: Geometry XML element
            geom_type: Type of geometry
        """
        ns = self.result.namespace or ""

        # Check for coordinates element
        if geom_type in {"Point", "LineString", "LinearRing"}:
            coords = element.find(f"{ns}coordinates")
            if coords is None:
                self.result.add_error(
                    f"{geom_type} missing required 'coordinates' element"
                )
            elif not coords.text or not coords.text.strip():
                self.result.add_error(f"{geom_type} has empty coordinates")

        elif geom_type == "Polygon":
            outer = element.find(f"{ns}outerBoundaryIs")
            if outer is None:
                self.result.add_error("Polygon missing required 'outerBoundaryIs'")
            else:
                linear_ring = outer.find(f"{ns}LinearRing")
                if linear_ring is None:
                    self.result.add_error(
                        "Polygon outerBoundaryIs missing LinearRing"
                    )
                else:
                    coords = linear_ring.find(f"{ns}coordinates")
                    if coords is None:
                        self.result.add_error(
                            "Polygon LinearRing missing coordinates"
                        )
                    elif not coords.text or not coords.text.strip():
                        self.result.add_error("Polygon has empty coordinates")

        elif geom_type == "MultiGeometry":
            # Check that it contains at least one child geometry
            child_geoms = []
            for child_type in self.SUPPORTED_GEOMETRIES:
                if child_type != "MultiGeometry":
                    child_geoms.extend(element.findall(f"{ns}{child_type}"))

            if not child_geoms:
                self.result.add_error("MultiGeometry contains no child geometries")


def validate_kml_file(file_path: Union[str, Path]) -> KMLValidationResult:
    """
    Convenience function to validate a KML file.

    Args:
        file_path: Path to KML file

    Returns:
        KMLValidationResult
    """
    validator = KMLValidator()
    return validator.validate(Path(file_path))


def validate_kml_string(kml_content: str) -> KMLValidationResult:
    """
    Convenience function to validate KML string content.

    Args:
        kml_content: KML content as string

    Returns:
        KMLValidationResult
    """
    validator = KMLValidator()
    return validator.validate(kml_content)

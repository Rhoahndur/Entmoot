"""
KML parsing module.

Parses KML files and extracts Placemarks with geometries, metadata, and properties.
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from shapely.geometry.base import BaseGeometry

from .geometry import (
    GeometryType,
    ParsedGeometry,
    extract_elevation_from_text,
    is_contour_line,
    kml_to_shapely,
)
from .kml_validator import KMLValidator

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = "{http://www.opengis.net/kml/2.2}"


@dataclass
class Placemark:
    """
    Represents a KML Placemark with geometry and metadata.

    Attributes:
        id: Optional placemark ID
        name: Placemark name
        description: Placemark description
        geometry: Parsed Shapely geometry
        geometry_type: Type of geometry
        properties: Additional properties and extended data
        style_url: Reference to style
        folder_path: Hierarchical path of folders containing this placemark
        is_contour: Whether this is a topographic contour line
        elevation: Elevation value (for contours)
    """

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    geometry: Optional[BaseGeometry] = None
    geometry_type: Optional[GeometryType] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    style_url: Optional[str] = None
    folder_path: List[str] = field(default_factory=list)
    is_contour: bool = False
    elevation: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Placemark to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "geometry_type": self.geometry_type.value if self.geometry_type else None,
            "properties": self.properties,
            "style_url": self.style_url,
            "folder_path": self.folder_path,
            "is_contour": self.is_contour,
            "elevation": self.elevation,
            "geometry_wkt": self.geometry.wkt if self.geometry else None,
        }


@dataclass
class ParsedKML:
    """
    Result of KML parsing containing all extracted data.

    Attributes:
        placemarks: List of parsed placemarks
        document_name: Document name from KML
        document_description: Document description
        folders: Folder structure
        styles: Style definitions
        properties: Document-level properties
        namespace: KML namespace used
        parse_errors: List of errors encountered during parsing
    """

    placemarks: List[Placemark] = field(default_factory=list)
    document_name: Optional[str] = None
    document_description: Optional[str] = None
    folders: List[str] = field(default_factory=list)
    styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    namespace: Optional[str] = None
    parse_errors: List[str] = field(default_factory=list)

    @property
    def placemark_count(self) -> int:
        """Get total number of placemarks."""
        return len(self.placemarks)

    @property
    def geometry_count(self) -> int:
        """Get total number of valid geometries."""
        return sum(1 for p in self.placemarks if p.geometry is not None)

    @property
    def contour_count(self) -> int:
        """Get number of contour lines."""
        return sum(1 for p in self.placemarks if p.is_contour)

    def get_placemarks_by_type(self, geometry_type: GeometryType) -> List[Placemark]:
        """Get placemarks filtered by geometry type."""
        return [
            p for p in self.placemarks if p.geometry_type == geometry_type
        ]

    def get_contours(self) -> List[Placemark]:
        """Get all contour line placemarks."""
        return [p for p in self.placemarks if p.is_contour]

    def get_property_boundaries(self) -> List[Placemark]:
        """Get placemarks that represent property boundaries (Polygons)."""
        return [
            p
            for p in self.placemarks
            if p.geometry_type == GeometryType.POLYGON and not p.is_contour
        ]


class KMLParser:
    """
    Parse KML files and extract Placemarks with geometries.

    Handles:
    - Document and Folder hierarchy
    - Placemarks with various geometry types
    - Extended data and properties
    - Style references
    - Contour line detection
    """

    def __init__(self, validate: bool = True) -> None:
        """
        Initialize KML parser.

        Args:
            validate: Whether to validate KML before parsing
        """
        self.validate = validate
        self.result: Optional[ParsedKML] = None
        self.namespace: str = KML_NS

    def parse(self, kml_content: Union[str, bytes, Path]) -> ParsedKML:
        """
        Parse KML content.

        Args:
            kml_content: KML content as string, bytes, or file path

        Returns:
            ParsedKML with all extracted data

        Raises:
            ValueError: If KML is invalid and validation is enabled
        """
        self.result = ParsedKML()

        try:
            # Validate if requested
            if self.validate:
                validator = KMLValidator()
                validation_result = validator.validate(kml_content)
                if not validation_result.is_valid:
                    error_msg = "; ".join(validation_result.errors)
                    raise ValueError(f"Invalid KML: {error_msg}")

                self.namespace = validation_result.namespace or KML_NS
                self.result.namespace = self.namespace

            # Load KML content
            if isinstance(kml_content, Path):
                with open(kml_content, "rb") as f:
                    kml_bytes = f.read()
            elif isinstance(kml_content, str):
                kml_bytes = kml_content.encode("utf-8")
            else:
                kml_bytes = kml_content

            # Parse XML
            root = ET.fromstring(kml_bytes)

            # Extract namespace if not already set
            if not self.result.namespace:
                if "}" in root.tag:
                    self.namespace = root.tag.split("}")[0] + "}"
                    self.result.namespace = self.namespace

            # Parse document-level elements
            self._parse_document(root)

            # Parse styles
            self._parse_styles(root)

            # Parse placemarks (recursively through folders)
            self._parse_placemarks(root)

            return self.result

        except Exception as e:
            logger.error(f"Failed to parse KML: {e}")
            self.result.parse_errors.append(str(e))
            raise

    def _parse_document(self, root: ET.Element) -> None:
        """
        Parse Document-level elements.

        Args:
            root: XML root element
        """
        document = root.find(f"{self.namespace}Document")
        if document is not None:
            # Get document name
            name_elem = document.find(f"{self.namespace}name")
            if name_elem is not None and name_elem.text:
                self.result.document_name = name_elem.text.strip()

            # Get document description
            desc_elem = document.find(f"{self.namespace}description")
            if desc_elem is not None and desc_elem.text:
                self.result.document_description = desc_elem.text.strip()

            # Parse extended data
            self._parse_extended_data(document, self.result.properties)

    def _parse_styles(self, root: ET.Element) -> None:
        """
        Parse Style and StyleMap elements.

        Args:
            root: XML root element
        """
        # Parse Style elements
        for style in root.findall(f".//{self.namespace}Style"):
            style_id = style.get("id")
            if style_id:
                style_data: Dict[str, Any] = {"id": style_id}

                # Parse LineStyle
                line_style = style.find(f"{self.namespace}LineStyle")
                if line_style is not None:
                    color = line_style.find(f"{self.namespace}color")
                    width = line_style.find(f"{self.namespace}width")
                    style_data["line"] = {
                        "color": color.text if color is not None else None,
                        "width": float(width.text) if width is not None and width.text else 1.0,
                    }

                # Parse PolyStyle
                poly_style = style.find(f"{self.namespace}PolyStyle")
                if poly_style is not None:
                    color = poly_style.find(f"{self.namespace}color")
                    fill = poly_style.find(f"{self.namespace}fill")
                    style_data["polygon"] = {
                        "color": color.text if color is not None else None,
                        "fill": fill.text == "1" if fill is not None and fill.text else True,
                    }

                self.result.styles[style_id] = style_data

    def _parse_placemarks(
        self, element: ET.Element, folder_path: Optional[List[str]] = None
    ) -> None:
        """
        Recursively parse Placemarks from element and its folders.

        Args:
            element: XML element to search
            folder_path: Current folder hierarchy path
        """
        folder_path = folder_path or []

        # Look for Document element first
        document = element.find(f"{self.namespace}Document")
        if document is not None:
            self._parse_element_placemarks(document, folder_path)
        else:
            self._parse_element_placemarks(element, folder_path)

    def _parse_element_placemarks(
        self, element: ET.Element, folder_path: List[str]
    ) -> None:
        """
        Recursively parse Placemarks from element and its folders.

        Args:
            element: XML element to search
            folder_path: Current folder hierarchy path
        """
        # Parse direct child placemarks
        for placemark_elem in element.findall(f"{self.namespace}Placemark"):
            try:
                placemark = self._parse_placemark(placemark_elem, folder_path)
                if placemark and placemark.geometry:
                    self.result.placemarks.append(placemark)
            except Exception as e:
                logger.warning(f"Failed to parse placemark: {e}")
                self.result.parse_errors.append(f"Placemark parse error: {e}")

        # Parse folders recursively
        for folder in element.findall(f"{self.namespace}Folder"):
            folder_name_elem = folder.find(f"{self.namespace}name")
            folder_name = (
                folder_name_elem.text.strip()
                if folder_name_elem is not None and folder_name_elem.text
                else "Unnamed Folder"
            )
            self.result.folders.append("/".join(folder_path + [folder_name]))
            self._parse_element_placemarks(folder, folder_path + [folder_name])

    def _parse_placemark(
        self, element: ET.Element, folder_path: List[str]
    ) -> Optional[Placemark]:
        """
        Parse a single Placemark element.

        Args:
            element: Placemark XML element
            folder_path: Folder hierarchy path

        Returns:
            Placemark object or None if parsing fails
        """
        placemark = Placemark(folder_path=folder_path.copy())

        # Get placemark ID
        placemark.id = element.get("id")

        # Get name
        name_elem = element.find(f"{self.namespace}name")
        if name_elem is not None and name_elem.text:
            placemark.name = name_elem.text.strip()

        # Get description
        desc_elem = element.find(f"{self.namespace}description")
        if desc_elem is not None and desc_elem.text:
            placemark.description = desc_elem.text.strip()

        # Get style URL
        style_elem = element.find(f"{self.namespace}styleUrl")
        if style_elem is not None and style_elem.text:
            placemark.style_url = style_elem.text.strip().lstrip("#")

        # Parse extended data
        self._parse_extended_data(element, placemark.properties)

        # Parse geometry
        geometry_result = self._parse_geometry(element)
        if geometry_result:
            placemark.geometry = geometry_result.geometry
            placemark.geometry_type = geometry_result.geometry_type

            # Check if this is a contour line
            if placemark.geometry_type == GeometryType.LINE_STRING:
                placemark.is_contour = is_contour_line(
                    placemark.name, placemark.description
                )
                if placemark.is_contour:
                    # Extract elevation
                    elevation = extract_elevation_from_text(
                        placemark.name or ""
                    ) or extract_elevation_from_text(placemark.description or "")
                    placemark.elevation = elevation

        return placemark

    def _parse_geometry(self, element: ET.Element) -> Optional[ParsedGeometry]:
        """
        Parse geometry from Placemark element.

        Args:
            element: Placemark XML element

        Returns:
            ParsedGeometry or None if no geometry found
        """
        # Try each geometry type
        for geom_type in ["Point", "LineString", "Polygon", "MultiGeometry"]:
            geom_elem = element.find(f"{self.namespace}{geom_type}")
            if geom_elem is not None:
                return self._parse_geometry_element(geom_elem, geom_type)

        return None

    def _parse_geometry_element(
        self, element: ET.Element, geom_type: str
    ) -> Optional[ParsedGeometry]:
        """
        Parse specific geometry element.

        Args:
            element: Geometry XML element
            geom_type: Type of geometry

        Returns:
            ParsedGeometry or None
        """
        try:
            if geom_type == "Point":
                coords_elem = element.find(f"{self.namespace}coordinates")
                if coords_elem is not None and coords_elem.text:
                    geometry = kml_to_shapely("Point", coords_elem.text.strip())
                    return ParsedGeometry(
                        geometry=geometry, geometry_type=GeometryType.POINT
                    )

            elif geom_type == "LineString":
                coords_elem = element.find(f"{self.namespace}coordinates")
                if coords_elem is not None and coords_elem.text:
                    geometry = kml_to_shapely("LineString", coords_elem.text.strip())
                    return ParsedGeometry(
                        geometry=geometry, geometry_type=GeometryType.LINE_STRING
                    )

            elif geom_type == "Polygon":
                # Parse outer boundary
                outer = element.find(f"{self.namespace}outerBoundaryIs")
                if outer is not None:
                    outer_ring = outer.find(f"{self.namespace}LinearRing")
                    if outer_ring is not None:
                        outer_coords = outer_ring.find(f"{self.namespace}coordinates")
                        if outer_coords is not None and outer_coords.text:
                            # Parse inner boundaries (holes)
                            inner_boundaries = []
                            for inner in element.findall(
                                f"{self.namespace}innerBoundaryIs"
                            ):
                                inner_ring = inner.find(f"{self.namespace}LinearRing")
                                if inner_ring is not None:
                                    inner_coords = inner_ring.find(
                                        f"{self.namespace}coordinates"
                                    )
                                    if inner_coords is not None and inner_coords.text:
                                        inner_boundaries.append(
                                            inner_coords.text.strip()
                                        )

                            geometry = kml_to_shapely(
                                "Polygon",
                                "",
                                outer_boundary=outer_coords.text.strip(),
                                inner_boundaries=inner_boundaries if inner_boundaries else None,
                            )
                            return ParsedGeometry(
                                geometry=geometry, geometry_type=GeometryType.POLYGON
                            )

            elif geom_type == "MultiGeometry":
                # For now, just parse the first geometry in MultiGeometry
                # In a production system, you might want to create a MultiPolygon or GeometryCollection
                for child_type in ["Point", "LineString", "Polygon"]:
                    child_elem = element.find(f"{self.namespace}{child_type}")
                    if child_elem is not None:
                        return self._parse_geometry_element(child_elem, child_type)

            return None

        except Exception as e:
            logger.error(f"Failed to parse {geom_type}: {e}")
            return None

    def _parse_extended_data(
        self, element: ET.Element, properties: Dict[str, Any]
    ) -> None:
        """
        Parse ExtendedData elements and add to properties.

        Args:
            element: XML element containing ExtendedData
            properties: Dictionary to populate with properties
        """
        extended_data = element.find(f"{self.namespace}ExtendedData")
        if extended_data is not None:
            # Parse Data elements
            for data in extended_data.findall(f"{self.namespace}Data"):
                name = data.get("name")
                value_elem = data.find(f"{self.namespace}value")
                if name and value_elem is not None and value_elem.text:
                    properties[name] = value_elem.text.strip()

            # Parse SchemaData
            for schema_data in extended_data.findall(f"{self.namespace}SchemaData"):
                for simple_data in schema_data.findall(
                    f"{self.namespace}SimpleData"
                ):
                    name = simple_data.get("name")
                    if name and simple_data.text:
                        properties[name] = simple_data.text.strip()


def parse_kml_file(file_path: Union[str, Path], validate: bool = True) -> ParsedKML:
    """
    Convenience function to parse a KML file.

    Args:
        file_path: Path to KML file
        validate: Whether to validate before parsing

    Returns:
        ParsedKML
    """
    parser = KMLParser(validate=validate)
    return parser.parse(Path(file_path))


def parse_kml_string(kml_content: str, validate: bool = True) -> ParsedKML:
    """
    Convenience function to parse KML string content.

    Args:
        kml_content: KML content as string
        validate: Whether to validate before parsing

    Returns:
        ParsedKML
    """
    parser = KMLParser(validate=validate)
    return parser.parse(kml_content)

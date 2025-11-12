"""
Geometry parsing and conversion utilities for KML/KMZ files.

This module handles conversion of KML coordinate strings to Shapely geometries,
preserving metadata and handling various coordinate formats.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from shapely.geometry import LinearRing, LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class GeometryType(str, Enum):
    """Supported KML geometry types."""

    POINT = "Point"
    LINE_STRING = "LineString"
    LINEAR_RING = "LinearRing"
    POLYGON = "Polygon"
    MULTI_GEOMETRY = "MultiGeometry"


@dataclass
class ParsedGeometry:
    """
    Container for parsed KML geometry with metadata.

    Attributes:
        geometry: Shapely geometry object
        geometry_type: Type of geometry (Point, LineString, Polygon, etc.)
        name: Optional name from KML
        description: Optional description from KML
        properties: Additional metadata and extended data
        altitude_mode: KML altitude mode (clampToGround, relativeToGround, absolute)
        extrude: Whether to extrude geometry to ground
    """

    geometry: BaseGeometry
    geometry_type: GeometryType
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    altitude_mode: Optional[str] = None
    extrude: bool = False

    def __post_init__(self) -> None:
        """Validate geometry after initialization."""
        if not isinstance(self.geometry, BaseGeometry):
            raise ValueError(f"Invalid geometry type: {type(self.geometry)}")
        if not self.geometry.is_valid:
            logger.warning(
                f"Invalid geometry created: {self.geometry.is_valid_reason if hasattr(self.geometry, 'is_valid_reason') else 'unknown reason'}"
            )


def parse_kml_coordinates(
    coord_string: str, reverse_coords: bool = False
) -> List[Tuple[float, ...]]:
    """
    Parse KML coordinate string into list of coordinate tuples.

    KML coordinates are in lon,lat,alt format (or lon,lat), separated by whitespace.
    Multiple coordinates are separated by whitespace or newlines.

    Args:
        coord_string: Raw coordinate string from KML
        reverse_coords: If True, reverse to lat,lon order (default: False, keep lon,lat)

    Returns:
        List of coordinate tuples (lon, lat, [alt])

    Raises:
        ValueError: If coordinate string is invalid or malformed

    Examples:
        >>> parse_kml_coordinates("-122.0822035425683,37.42228990140251,0")
        [(-122.0822035425683, 37.42228990140251, 0.0)]

        >>> parse_kml_coordinates("-122.08,37.42 -122.09,37.43")
        [(-122.08, 37.42), (-122.09, 37.43)]
    """
    if not coord_string or not coord_string.strip():
        raise ValueError("Empty coordinate string")

    # Clean up whitespace and split
    coord_string = coord_string.strip()
    # Split on whitespace (including newlines)
    coord_parts = re.split(r"\s+", coord_string)

    coordinates: List[Tuple[float, ...]] = []

    for part in coord_parts:
        if not part:
            continue

        # Split on comma
        values = part.split(",")

        if len(values) < 2:
            raise ValueError(f"Invalid coordinate format: {part} (need at least lon,lat)")

        try:
            lon = float(values[0])
            lat = float(values[1])
            alt = float(values[2]) if len(values) > 2 else None

            # Validate coordinate ranges
            if not (-180 <= lon <= 180):
                raise ValueError(f"Longitude out of range: {lon}")
            if not (-90 <= lat <= 90):
                raise ValueError(f"Latitude out of range: {lat}")

            if reverse_coords:
                coord = (lat, lon, alt) if alt is not None else (lat, lon)
            else:
                coord = (lon, lat, alt) if alt is not None else (lon, lat)

            coordinates.append(coord)

        except (ValueError, IndexError) as e:
            raise ValueError(f"Failed to parse coordinate: {part}") from e

    if not coordinates:
        raise ValueError("No valid coordinates found")

    return coordinates


def kml_to_shapely(
    geometry_type: str,
    coord_string: str,
    outer_boundary: Optional[str] = None,
    inner_boundaries: Optional[List[str]] = None,
) -> BaseGeometry:
    """
    Convert KML coordinates to Shapely geometry.

    Args:
        geometry_type: Type of geometry (Point, LineString, LinearRing, Polygon)
        coord_string: Coordinate string for simple geometries
        outer_boundary: Outer boundary coordinates for Polygon
        inner_boundaries: Inner boundary (hole) coordinates for Polygon

    Returns:
        Shapely geometry object

    Raises:
        ValueError: If geometry type is unsupported or coordinates are invalid
    """
    try:
        if geometry_type == "Point":
            coords = parse_kml_coordinates(coord_string)
            if len(coords) != 1:
                raise ValueError(f"Point must have exactly 1 coordinate, got {len(coords)}")
            # Shapely Point takes x, y, [z] which is lon, lat, [alt]
            return Point(coords[0][:2])  # Use only x, y (lon, lat)

        elif geometry_type == "LineString":
            coords = parse_kml_coordinates(coord_string)
            if len(coords) < 2:
                raise ValueError(
                    f"LineString must have at least 2 coordinates, got {len(coords)}"
                )
            # Use only x, y coordinates
            return LineString([c[:2] for c in coords])

        elif geometry_type == "LinearRing":
            coords = parse_kml_coordinates(coord_string)
            if len(coords) < 3:
                raise ValueError(
                    f"LinearRing must have at least 3 coordinates, got {len(coords)}"
                )
            # Use only x, y coordinates
            return LinearRing([c[:2] for c in coords])

        elif geometry_type == "Polygon":
            if outer_boundary is None:
                raise ValueError("Polygon requires outer boundary coordinates")

            # Parse outer boundary
            outer_coords = parse_kml_coordinates(outer_boundary)
            if len(outer_coords) < 3:
                raise ValueError(
                    f"Polygon outer boundary must have at least 3 coordinates, got {len(outer_coords)}"
                )

            # Use only x, y coordinates for outer shell
            shell = [c[:2] for c in outer_coords]

            # Parse inner boundaries (holes) if present
            holes = []
            if inner_boundaries:
                for inner_boundary in inner_boundaries:
                    inner_coords = parse_kml_coordinates(inner_boundary)
                    if len(inner_coords) < 3:
                        logger.warning(
                            f"Polygon hole must have at least 3 coordinates, got {len(inner_coords)}, skipping"
                        )
                        continue
                    holes.append([c[:2] for c in inner_coords])

            return Polygon(shell, holes if holes else None)

        else:
            raise ValueError(f"Unsupported geometry type: {geometry_type}")

    except Exception as e:
        logger.error(f"Failed to convert {geometry_type} to Shapely: {e}")
        raise


def extract_elevation_from_text(text: str) -> Optional[float]:
    """
    Extract elevation value from text (for contour lines).

    Looks for patterns like:
    - "1200" (plain number)
    - "1200m"
    - "1200 ft"
    - "elevation: 1200"
    - "1200' contour"

    Args:
        text: Text to search for elevation

    Returns:
        Elevation value if found, None otherwise
    """
    if not text:
        return None

    # Try various patterns
    patterns = [
        r"elevation[:\s]+(\d+\.?\d*)",  # elevation: 1200
        r"(\d+\.?\d*)\s*(?:m|meter|metre)s?",  # 1200m, 1200 meters
        r"(\d+\.?\d*)\s*(?:ft|foot|feet|')",  # 1200ft, 1200', 1200 feet
        r"(\d+\.?\d*)\s*contour",  # 1200 contour
        r"^(\d+\.?\d*)$",  # Plain number (if text is just a number)
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def is_contour_line(name: Optional[str], description: Optional[str]) -> bool:
    """
    Determine if a LineString represents a topographic contour line.

    Args:
        name: Placemark name
        description: Placemark description

    Returns:
        True if this appears to be a contour line
    """
    if not name and not description:
        return False

    text = f"{name or ''} {description or ''}".lower()

    # Look for contour-related keywords
    contour_keywords = [
        "contour",
        "elevation",
        "topo",
        "topographic",
        "isoline",
        "isohypse",
    ]

    return any(keyword in text for keyword in contour_keywords)

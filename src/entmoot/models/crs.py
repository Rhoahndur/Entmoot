"""
Data models for Coordinate Reference System (CRS) management.

This module defines data structures for handling CRS metadata,
coordinate transformations, and spatial bounding boxes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class CoordinateOrder(str, Enum):
    """Coordinate order convention for different CRS."""

    LON_LAT = "lon_lat"  # Longitude, Latitude (e.g., GeoJSON)
    LAT_LON = "lat_lon"  # Latitude, Longitude (e.g., some KML)
    XY = "xy"  # X, Y (projected coordinates)
    YX = "yx"  # Y, X (some projected systems)


class DistanceUnit(str, Enum):
    """Units for distance measurements."""

    METERS = "meters"
    FEET = "feet"
    KILOMETERS = "kilometers"
    MILES = "miles"
    DEGREES = "degrees"


@dataclass
class CRSInfo:
    """
    Comprehensive information about a Coordinate Reference System.

    Attributes:
        epsg: EPSG code (e.g., 4326 for WGS84)
        wkt: Well-Known Text representation
        proj4: PROJ4 string representation
        name: Human-readable name
        units: Distance units for this CRS
        is_geographic: True for lat/lon systems, False for projected
        coordinate_order: Order of coordinates in this system
        authority: Authority name (e.g., 'EPSG', 'ESRI')
        code: Authority-specific code
    """

    epsg: Optional[int] = None
    wkt: Optional[str] = None
    proj4: Optional[str] = None
    name: Optional[str] = None
    units: DistanceUnit = DistanceUnit.METERS
    is_geographic: bool = True
    coordinate_order: CoordinateOrder = CoordinateOrder.LON_LAT
    authority: Optional[str] = None
    code: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate and normalize CRS information."""
        if self.epsg is not None and self.authority is None:
            self.authority = "EPSG"
            self.code = str(self.epsg)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "epsg": self.epsg,
            "wkt": self.wkt,
            "proj4": self.proj4,
            "name": self.name,
            "units": self.units.value if self.units else None,
            "is_geographic": self.is_geographic,
            "coordinate_order": self.coordinate_order.value if self.coordinate_order else None,
            "authority": self.authority,
            "code": self.code,
        }

    @classmethod
    def from_epsg(cls, epsg: int) -> "CRSInfo":
        """
        Create CRSInfo from EPSG code.

        Args:
            epsg: EPSG code

        Returns:
            CRSInfo instance
        """
        return cls(
            epsg=epsg,
            authority="EPSG",
            code=str(epsg),
        )

    def __str__(self) -> str:
        """String representation."""
        if self.epsg:
            return f"EPSG:{self.epsg}"
        elif self.authority and self.code:
            return f"{self.authority}:{self.code}"
        elif self.name:
            return self.name
        return "Unknown CRS"


@dataclass
class CoordinateTransformation:
    """
    Parameters for coordinate transformation between CRS.

    Attributes:
        source_crs: Source coordinate reference system
        target_crs: Target coordinate reference system
        always_xy: Whether to enforce x,y (lon,lat) axis order
        accuracy: Expected accuracy in meters (for validation)
        area_of_use: Geographic area where transformation is valid
    """

    source_crs: CRSInfo
    target_crs: CRSInfo
    always_xy: bool = True
    accuracy: Optional[float] = None
    area_of_use: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "source_crs": self.source_crs.to_dict(),
            "target_crs": self.target_crs.to_dict(),
            "always_xy": self.always_xy,
            "accuracy": self.accuracy,
            "area_of_use": self.area_of_use,
        }

    def __str__(self) -> str:
        """String representation."""
        return f"{self.source_crs} -> {self.target_crs}"


@dataclass
class BoundingBox:
    """
    Spatial bounding box with CRS awareness.

    Attributes:
        min_x: Minimum X coordinate (or longitude)
        min_y: Minimum Y coordinate (or latitude)
        max_x: Maximum X coordinate (or longitude)
        max_y: Maximum Y coordinate (or latitude)
        crs: Coordinate reference system
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: CRSInfo

    def __post_init__(self) -> None:
        """Validate bounding box."""
        if self.min_x > self.max_x:
            raise ValueError(f"min_x ({self.min_x}) must be <= max_x ({self.max_x})")
        if self.min_y > self.max_y:
            raise ValueError(f"min_y ({self.min_y}) must be <= max_y ({self.max_y})")

    @property
    def width(self) -> float:
        """Calculate width of bounding box."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Calculate height of bounding box."""
        return self.max_y - self.min_y

    @property
    def center(self) -> Tuple[float, float]:
        """Calculate center point of bounding box."""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
        )

    def contains(self, x: float, y: float) -> bool:
        """
        Check if point is within bounding box.

        Args:
            x: X coordinate (or longitude)
            y: Y coordinate (or latitude)

        Returns:
            True if point is within bounds
        """
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def intersects(self, other: "BoundingBox") -> bool:
        """
        Check if this bounding box intersects another.

        Args:
            other: Another bounding box (should be in same CRS)

        Returns:
            True if bounding boxes intersect
        """
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "crs": self.crs.to_dict(),
        }

    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to tuple (min_x, min_y, max_x, max_y)."""
        return (self.min_x, self.min_y, self.max_x, self.max_y)

    def __str__(self) -> str:
        """String representation."""
        return f"BBox({self.min_x:.6f}, {self.min_y:.6f}, {self.max_x:.6f}, {self.max_y:.6f}) [{self.crs}]"

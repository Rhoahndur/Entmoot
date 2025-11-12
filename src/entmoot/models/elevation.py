"""
Elevation data models for USGS integration.

This module defines data models for elevation queries, including
single point elevations, DEM tile metadata, and elevation datasets.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ElevationUnit(str, Enum):
    """Units for elevation measurements."""

    METERS = "meters"
    FEET = "feet"


class ElevationDatum(str, Enum):
    """Vertical datum types for elevation data."""

    NAVD88 = "NAVD88"  # North American Vertical Datum of 1988
    NGVD29 = "NGVD29"  # National Geodetic Vertical Datum of 1929
    WGS84 = "WGS84"  # World Geodetic System 1984
    MSL = "MSL"  # Mean Sea Level


class ElevationDataSource(str, Enum):
    """Source dataset for elevation data."""

    USGS_3DEP_1M = "3DEP 1-meter"
    USGS_3DEP_1_3M = "3DEP 1/3 arc-second"
    USGS_3DEP_1ARC = "3DEP 1 arc-second"
    USGS_3DEP_2ARC = "3DEP 2 arc-second"
    NED = "National Elevation Dataset"
    SRTM = "Shuttle Radar Topography Mission"
    CACHED = "Cached"
    UNKNOWN = "Unknown"


class ElevationQueryStatus(str, Enum):
    """Status of elevation query."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some points succeeded, some failed
    FAILED = "failed"
    CACHED = "cached"
    OUT_OF_BOUNDS = "out_of_bounds"


class USRegion(str, Enum):
    """US regions for elevation data coverage."""

    CONUS = "Continental US"
    ALASKA = "Alaska"
    HAWAII = "Hawaii"
    PUERTO_RICO = "Puerto Rico"
    US_VIRGIN_ISLANDS = "US Virgin Islands"
    GUAM = "Guam"
    AMERICAN_SAMOA = "American Samoa"


class ElevationPoint(BaseModel):
    """
    Single point elevation data.

    Attributes:
        longitude: Longitude coordinate (WGS84)
        latitude: Latitude coordinate (WGS84)
        elevation: Elevation value
        unit: Elevation unit
        datum: Vertical datum
        resolution: Data resolution in arc-seconds
        data_source: Source dataset name
        query_timestamp: When the query was made
        x_coord: Optional X coordinate in data CRS
        y_coord: Optional Y coordinate in data CRS
    """

    longitude: float = Field(..., ge=-180, le=180, description="Longitude (WGS84)")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude (WGS84)")
    elevation: Optional[float] = Field(None, description="Elevation value")
    unit: ElevationUnit = Field(default=ElevationUnit.METERS, description="Elevation unit")
    datum: ElevationDatum = Field(
        default=ElevationDatum.NAVD88, description="Vertical datum"
    )
    resolution: Optional[float] = Field(None, description="Data resolution in arc-seconds")
    data_source: ElevationDataSource = Field(
        default=ElevationDataSource.UNKNOWN, description="Source dataset"
    )
    query_timestamp: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="Query timestamp"
    )
    x_coord: Optional[float] = Field(None, description="X coordinate in data CRS")
    y_coord: Optional[float] = Field(None, description="Y coordinate in data CRS")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "longitude": self.longitude,
            "latitude": self.latitude,
            "elevation": self.elevation,
            "unit": self.unit.value,
            "datum": self.datum.value,
            "resolution": self.resolution,
            "data_source": self.data_source.value,
            "query_timestamp": self.query_timestamp.isoformat() if self.query_timestamp else None,
            "x_coord": self.x_coord,
            "y_coord": self.y_coord,
        }


class ElevationQuery(BaseModel):
    """
    Metadata for an elevation query.

    Attributes:
        query_id: Unique identifier for the query
        query_type: Type of query (point, batch, bbox)
        status: Query status
        timestamp: When the query was made
        point_count: Number of points queried
        success_count: Number of successful queries
        failed_count: Number of failed queries
        cache_hit: Whether result came from cache
        duration_ms: Query duration in milliseconds
        error_message: Error message if query failed
    """

    query_id: str = Field(..., description="Unique query identifier")
    query_type: str = Field(..., description="Query type (point/batch/bbox)")
    status: ElevationQueryStatus = Field(
        default=ElevationQueryStatus.SUCCESS, description="Query status"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")
    point_count: int = Field(default=1, ge=0, description="Number of points queried")
    success_count: int = Field(default=0, ge=0, description="Successful queries")
    failed_count: int = Field(default=0, ge=0, description="Failed queries")
    cache_hit: bool = Field(default=False, description="Result from cache")
    duration_ms: Optional[float] = Field(None, ge=0, description="Query duration (ms)")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query_id": self.query_id,
            "query_type": self.query_type,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "point_count": self.point_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "cache_hit": self.cache_hit,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
        }


class DEMTileMetadata(BaseModel):
    """
    Metadata for a DEM tile.

    Attributes:
        tile_id: Unique tile identifier
        min_lon: Minimum longitude
        min_lat: Minimum latitude
        max_lon: Maximum longitude
        max_lat: Maximum latitude
        resolution: Resolution in arc-seconds
        unit: Elevation unit
        datum: Vertical datum
        data_source: Source dataset
        download_url: URL to download the tile
        file_path: Local file path if downloaded
        file_size_bytes: File size in bytes
        download_timestamp: When tile was downloaded
        last_accessed: Last access timestamp
        region: US region
    """

    tile_id: str = Field(..., description="Unique tile identifier")
    min_lon: float = Field(..., ge=-180, le=180, description="Minimum longitude")
    min_lat: float = Field(..., ge=-90, le=90, description="Minimum latitude")
    max_lon: float = Field(..., ge=-180, le=180, description="Maximum longitude")
    max_lat: float = Field(..., ge=-90, le=90, description="Maximum latitude")
    resolution: float = Field(..., gt=0, description="Resolution in arc-seconds")
    unit: ElevationUnit = Field(default=ElevationUnit.METERS, description="Elevation unit")
    datum: ElevationDatum = Field(
        default=ElevationDatum.NAVD88, description="Vertical datum"
    )
    data_source: ElevationDataSource = Field(
        default=ElevationDataSource.USGS_3DEP_1ARC, description="Source dataset"
    )
    download_url: Optional[str] = Field(None, description="Download URL")
    file_path: Optional[str] = Field(None, description="Local file path")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="File size")
    download_timestamp: Optional[datetime] = Field(None, description="Download timestamp")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    region: Optional[USRegion] = Field(None, description="US region")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tile_id": self.tile_id,
            "bounds": [self.min_lon, self.min_lat, self.max_lon, self.max_lat],
            "resolution": self.resolution,
            "unit": self.unit.value,
            "datum": self.datum.value,
            "data_source": self.data_source.value,
            "download_url": self.download_url,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "download_timestamp": (
                self.download_timestamp.isoformat() if self.download_timestamp else None
            ),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "region": self.region.value if self.region else None,
        }

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)


class ElevationBatchResponse(BaseModel):
    """
    Response for batch elevation queries.

    Attributes:
        query: Query metadata
        points: List of elevation points
        min_elevation: Minimum elevation in batch
        max_elevation: Maximum elevation in batch
        mean_elevation: Mean elevation in batch
        elevation_range: Range of elevations
    """

    query: ElevationQuery
    points: List[ElevationPoint] = Field(default_factory=list)
    min_elevation: Optional[float] = Field(None, description="Minimum elevation")
    max_elevation: Optional[float] = Field(None, description="Maximum elevation")
    mean_elevation: Optional[float] = Field(None, description="Mean elevation")
    elevation_range: Optional[float] = Field(None, description="Elevation range")

    def compute_statistics(self) -> None:
        """Compute elevation statistics from points."""
        valid_elevations = [p.elevation for p in self.points if p.elevation is not None]

        if valid_elevations:
            self.min_elevation = min(valid_elevations)
            self.max_elevation = max(valid_elevations)
            self.mean_elevation = sum(valid_elevations) / len(valid_elevations)
            self.elevation_range = self.max_elevation - self.min_elevation
        else:
            self.min_elevation = None
            self.max_elevation = None
            self.mean_elevation = None
            self.elevation_range = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query.to_dict(),
            "points": [p.to_dict() for p in self.points],
            "statistics": {
                "min_elevation": self.min_elevation,
                "max_elevation": self.max_elevation,
                "mean_elevation": self.mean_elevation,
                "elevation_range": self.elevation_range,
            },
        }


@dataclass
class DEMTileRequest:
    """
    Request for DEM tile download.

    Attributes:
        min_lon: Minimum longitude
        min_lat: Minimum latitude
        max_lon: Maximum longitude
        max_lat: Maximum latitude
        resolution: Desired resolution in arc-seconds
        output_format: Output format (GeoTIFF, etc.)
        datum: Desired vertical datum
        unit: Desired elevation unit
    """

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    resolution: float = 1.0  # 1 arc-second default
    output_format: str = "GeoTIFF"
    datum: ElevationDatum = ElevationDatum.NAVD88
    unit: ElevationUnit = ElevationUnit.METERS

    def __post_init__(self) -> None:
        """Validate tile request."""
        if not (-180 <= self.min_lon <= 180):
            raise ValueError(f"Invalid min_lon: {self.min_lon}")
        if not (-90 <= self.min_lat <= 90):
            raise ValueError(f"Invalid min_lat: {self.min_lat}")
        if not (-180 <= self.max_lon <= 180):
            raise ValueError(f"Invalid max_lon: {self.max_lon}")
        if not (-90 <= self.max_lat <= 90):
            raise ValueError(f"Invalid max_lat: {self.max_lat}")
        if self.min_lon >= self.max_lon:
            raise ValueError(f"min_lon ({self.min_lon}) must be < max_lon ({self.max_lon})")
        if self.min_lat >= self.max_lat:
            raise ValueError(f"min_lat ({self.min_lat}) must be < max_lat ({self.max_lat})")
        if self.resolution <= 0:
            raise ValueError(f"Resolution must be positive: {self.resolution}")

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)

    @property
    def width_degrees(self) -> float:
        """Get width in degrees."""
        return self.max_lon - self.min_lon

    @property
    def height_degrees(self) -> float:
        """Get height in degrees."""
        return self.max_lat - self.min_lat

    @property
    def area_sq_degrees(self) -> float:
        """Get area in square degrees."""
        return self.width_degrees * self.height_degrees

"""
Pydantic models for property boundary data.

This module defines the data structures for property boundaries extracted from
KML/KMZ files, including metrics, metadata, and validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry


class BoundarySource(str, Enum):
    """Source of boundary identification."""

    NAME_PATTERN = "name_pattern"
    LAYER_NAME = "layer_name"
    METADATA = "metadata"
    LARGEST_POLYGON = "largest_polygon"
    MANUAL = "manual"


class GeometryIssue(str, Enum):
    """Types of geometry validation issues."""

    UNCLOSED_RING = "unclosed_ring"
    SELF_INTERSECTION = "self_intersection"
    INSUFFICIENT_VERTICES = "insufficient_vertices"
    INVALID_COORDINATES = "invalid_coordinates"
    INVALID_GEOMETRY = "invalid_geometry"


class BoundaryMetrics(BaseModel):
    """
    Calculated metrics for a property boundary.

    Attributes:
        area_sqm: Area in square meters
        area_acres: Area in acres
        perimeter_m: Perimeter in meters
        perimeter_ft: Perimeter in feet
        centroid_lon: Centroid longitude
        centroid_lat: Centroid latitude
        bbox_min_lon: Bounding box minimum longitude
        bbox_min_lat: Bounding box minimum latitude
        bbox_max_lon: Bounding box maximum longitude
        bbox_max_lat: Bounding box maximum latitude
        has_holes: Whether the polygon has interior holes
        hole_count: Number of interior holes
        vertex_count: Number of vertices in the outer boundary
    """

    area_sqm: float = Field(..., description="Area in square meters", ge=0)
    area_acres: float = Field(..., description="Area in acres", ge=0)
    perimeter_m: float = Field(..., description="Perimeter in meters", ge=0)
    perimeter_ft: float = Field(..., description="Perimeter in feet", ge=0)
    centroid_lon: float = Field(..., description="Centroid longitude", ge=-180, le=180)
    centroid_lat: float = Field(..., description="Centroid latitude", ge=-90, le=90)
    bbox_min_lon: float = Field(..., description="Bounding box min longitude", ge=-180, le=180)
    bbox_min_lat: float = Field(..., description="Bounding box min latitude", ge=-90, le=90)
    bbox_max_lon: float = Field(..., description="Bounding box max longitude", ge=-180, le=180)
    bbox_max_lat: float = Field(..., description="Bounding box max latitude", ge=-90, le=90)
    has_holes: bool = Field(default=False, description="Whether polygon has holes")
    hole_count: int = Field(default=0, description="Number of interior holes", ge=0)
    vertex_count: int = Field(..., description="Number of vertices", gt=2)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "area_sqm": 4046.86,
                "area_acres": 1.0,
                "perimeter_m": 253.95,
                "perimeter_ft": 833.33,
                "centroid_lon": -122.084,
                "centroid_lat": 37.422,
                "bbox_min_lon": -122.085,
                "bbox_min_lat": 37.421,
                "bbox_max_lon": -122.083,
                "bbox_max_lat": 37.423,
                "has_holes": False,
                "hole_count": 0,
                "vertex_count": 50,
            }
        }
    )


class BoundaryMetadata(BaseModel):
    """
    Metadata associated with a property boundary.

    Attributes:
        name: Property or boundary name
        description: Property description
        address: Property address if available
        parcel_id: Parcel ID if available
        properties: Additional custom properties from extended data
        folder_path: Folder hierarchy from KML
        extraction_time: When boundary was extracted
        source: How the boundary was identified
    """

    name: Optional[str] = Field(None, description="Property/boundary name")
    description: Optional[str] = Field(None, description="Property description")
    address: Optional[str] = Field(None, description="Property address")
    parcel_id: Optional[str] = Field(None, description="Parcel ID")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom properties"
    )
    folder_path: List[str] = Field(
        default_factory=list, description="Folder hierarchy from KML"
    )
    extraction_time: datetime = Field(
        default_factory=datetime.utcnow, description="Extraction timestamp"
    )
    source: BoundarySource = Field(..., description="Identification source")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Property Boundary",
                "description": "Main parcel for development site",
                "address": "123 Main Street, Anytown, CA",
                "parcel_id": "APN-123-456-789",
                "properties": {"zoning": "R-1", "owner": "John Doe"},
                "folder_path": ["Site Boundaries", "Primary Parcel"],
                "source": "name_pattern",
            }
        }
    )


class SubParcel(BaseModel):
    """
    Represents a sub-parcel in a multi-polygon property.

    Attributes:
        parcel_id: Unique identifier for this sub-parcel
        geometry_wkt: WKT representation of the polygon
        area_sqm: Area in square meters
        area_acres: Area in acres
        centroid_lon: Centroid longitude
        centroid_lat: Centroid latitude
    """

    parcel_id: str = Field(..., description="Sub-parcel identifier")
    geometry_wkt: str = Field(..., description="WKT representation")
    area_sqm: float = Field(..., description="Area in square meters", ge=0)
    area_acres: float = Field(..., description="Area in acres", ge=0)
    centroid_lon: float = Field(..., description="Centroid longitude", ge=-180, le=180)
    centroid_lat: float = Field(..., description="Centroid latitude", ge=-90, le=90)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "parcel_id": "parcel_1",
                "geometry_wkt": "POLYGON((-122.084 37.422, ...))",
                "area_sqm": 2023.43,
                "area_acres": 0.5,
                "centroid_lon": -122.084,
                "centroid_lat": 37.422,
            }
        }
    )


class PropertyBoundary(BaseModel):
    """
    Main model representing a property boundary with all associated data.

    Attributes:
        geometry_wkt: WKT representation of the boundary polygon
        metrics: Calculated boundary metrics
        metadata: Boundary metadata and properties
        is_valid: Whether the geometry is valid
        validation_issues: List of validation issues found
        is_multi_parcel: Whether this is a multi-polygon property
        sub_parcels: Sub-parcels if multi-polygon
        repaired: Whether geometry was auto-repaired
    """

    geometry_wkt: str = Field(..., description="WKT representation of boundary")
    metrics: BoundaryMetrics = Field(..., description="Boundary metrics")
    metadata: BoundaryMetadata = Field(..., description="Boundary metadata")
    is_valid: bool = Field(..., description="Whether geometry is valid")
    validation_issues: List[GeometryIssue] = Field(
        default_factory=list, description="Validation issues"
    )
    is_multi_parcel: bool = Field(
        default=False, description="Whether property has multiple disconnected parcels"
    )
    sub_parcels: List[SubParcel] = Field(
        default_factory=list, description="Sub-parcels for multi-polygon properties"
    )
    repaired: bool = Field(default=False, description="Whether geometry was auto-repaired")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "geometry_wkt": "POLYGON((-122.084 37.422, -122.083 37.422, -122.083 37.421, -122.084 37.421, -122.084 37.422))",
                "metrics": {
                    "area_sqm": 4046.86,
                    "area_acres": 1.0,
                    "perimeter_m": 253.95,
                    "perimeter_ft": 833.33,
                    "centroid_lon": -122.084,
                    "centroid_lat": 37.422,
                },
                "metadata": {"name": "Property Boundary", "source": "name_pattern"},
                "is_valid": True,
                "validation_issues": [],
                "is_multi_parcel": False,
                "sub_parcels": [],
                "repaired": False,
            }
        }
    )

    def to_geojson(self) -> Dict[str, Any]:
        """
        Export boundary as GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        from shapely import wkt

        geom = wkt.loads(self.geometry_wkt)

        return {
            "type": "Feature",
            "geometry": {
                "type": geom.geom_type,
                "coordinates": self._geometry_to_coords(geom),
            },
            "properties": {
                "name": self.metadata.name,
                "description": self.metadata.description,
                "area_sqm": self.metrics.area_sqm,
                "area_acres": self.metrics.area_acres,
                "perimeter_m": self.metrics.perimeter_m,
                "perimeter_ft": self.metrics.perimeter_ft,
                "is_valid": self.is_valid,
                "is_multi_parcel": self.is_multi_parcel,
                "has_holes": self.metrics.has_holes,
                "source": self.metadata.source,
                **self.metadata.properties,
            },
        }

    def _geometry_to_coords(self, geom: BaseGeometry) -> List[Any]:
        """Convert Shapely geometry to GeoJSON coordinate array."""
        if isinstance(geom, ShapelyPolygon):
            coords = [list(geom.exterior.coords)]
            for interior in geom.interiors:
                coords.append(list(interior.coords))
            return coords
        return list(geom.coords)


class BoundaryExtractionResult(BaseModel):
    """
    Result of boundary extraction operation.

    Attributes:
        success: Whether extraction was successful
        boundaries: List of extracted boundaries
        total_placemarks: Total placemarks processed
        total_polygons: Total polygon placemarks found
        extraction_strategy: Strategy used for identification
        errors: List of errors encountered
        warnings: List of warnings
    """

    success: bool = Field(..., description="Whether extraction succeeded")
    boundaries: List[PropertyBoundary] = Field(
        default_factory=list, description="Extracted boundaries"
    )
    total_placemarks: int = Field(default=0, description="Total placemarks processed", ge=0)
    total_polygons: int = Field(default=0, description="Total polygon placemarks", ge=0)
    extraction_strategy: Optional[BoundarySource] = Field(
        None, description="Strategy used for identification"
    )
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Warnings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "boundaries": [],
                "total_placemarks": 15,
                "total_polygons": 3,
                "extraction_strategy": "name_pattern",
                "errors": [],
                "warnings": [],
            }
        }
    )

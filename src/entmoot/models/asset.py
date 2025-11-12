"""
Asset data models for site planning and placement.

This module defines the asset framework for managing physical site elements
like buildings, equipment yards, roads, and other infrastructure.
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from shapely.geometry.base import BaseGeometry
from shapely import wkt
from shapely.validation import make_valid


class AssetType(str, Enum):
    """Types of assets that can be placed on a site."""

    BUILDING = "building"
    EQUIPMENT_YARD = "equipment_yard"
    ROAD = "road"
    PARKING = "parking"
    UTILITY = "utility"
    STRUCTURE = "structure"
    LANDSCAPE = "landscape"
    CUSTOM = "custom"


class PlacedAsset(BaseModel):
    """
    Represents a physical asset placed on a site.

    Attributes:
        id: Unique identifier for the asset
        name: Human-readable name
        asset_type: Type of asset
        geometry_wkt: WKT representation of asset footprint
        rotation: Rotation angle in degrees (0-360)
        metadata: Additional custom metadata
        created_at: Creation timestamp
        min_spacing_m: Minimum spacing required from other assets
    """

    id: str = Field(..., description="Unique asset identifier")
    name: str = Field(..., description="Asset name", min_length=1)
    asset_type: AssetType = Field(..., description="Type of asset")
    geometry_wkt: str = Field(..., description="WKT representation of asset footprint")
    rotation: float = Field(
        default=0.0,
        description="Rotation angle in degrees",
        ge=0.0,
        lt=360.0
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    min_spacing_m: float = Field(
        default=0.0,
        description="Minimum spacing required from other assets",
        ge=0.0
    )

    @field_validator('geometry_wkt')
    @classmethod
    def validate_geometry(cls, v: str) -> str:
        """Validate that geometry WKT is valid."""
        try:
            geom = wkt.loads(v)
            if not geom.is_valid:
                # Try to repair
                geom = make_valid(geom)
                if not geom.is_valid:
                    raise ValueError("Geometry is invalid and could not be repaired")
                # Return repaired WKT
                return geom.wkt
            return v
        except Exception as e:
            raise ValueError(f"Invalid geometry WKT: {str(e)}")

    def get_geometry(self) -> BaseGeometry:
        """Get Shapely geometry from WKT."""
        return wkt.loads(self.geometry_wkt)

    def get_area_sqm(self) -> float:
        """Calculate area in square meters."""
        geom = self.get_geometry()
        if hasattr(geom, 'area'):
            return geom.area
        return 0.0

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Get bounding box (minx, miny, maxx, maxy)."""
        return self.get_geometry().bounds

    def get_buffered_geometry(self, buffer_distance: float = 0.0) -> BaseGeometry:
        """
        Get asset geometry with optional buffer.

        Args:
            buffer_distance: Distance to buffer in meters

        Returns:
            Buffered geometry
        """
        geom = self.get_geometry()
        if buffer_distance > 0:
            return geom.buffer(buffer_distance)
        return geom


class SpacingRule(BaseModel):
    """
    Defines minimum spacing requirements between asset types.

    Attributes:
        from_asset_type: Source asset type
        to_asset_type: Target asset type
        min_spacing_m: Minimum spacing in meters
        description: Description of the rule
    """

    from_asset_type: AssetType = Field(..., description="Source asset type")
    to_asset_type: AssetType = Field(..., description="Target asset type")
    min_spacing_m: float = Field(..., description="Minimum spacing in meters", gt=0)
    description: Optional[str] = Field(None, description="Rule description")


# Standard spacing rules (in meters)
DEFAULT_SPACING_RULES: Dict[tuple[AssetType, AssetType], float] = {
    (AssetType.BUILDING, AssetType.BUILDING): 30.0,  # Building-to-building: 30m
    (AssetType.BUILDING, AssetType.ROAD): 10.0,  # Road-to-building: 10m
    (AssetType.EQUIPMENT_YARD, AssetType.EQUIPMENT_YARD): 20.0,  # Yard-to-yard: 20m
    (AssetType.EQUIPMENT_YARD, AssetType.BUILDING): 15.0,  # Building-to-yard: 15m
    (AssetType.UTILITY, AssetType.BUILDING): 5.0,  # Utility-to-building: 5m
}


def get_required_spacing(
    asset1_type: AssetType,
    asset2_type: AssetType,
    custom_rules: Optional[Dict[tuple[AssetType, AssetType], float]] = None
) -> float:
    """
    Get required spacing between two asset types.

    Args:
        asset1_type: First asset type
        asset2_type: Second asset type
        custom_rules: Optional custom spacing rules to override defaults

    Returns:
        Minimum spacing in meters (0 if no rule defined)
    """
    rules = custom_rules or DEFAULT_SPACING_RULES

    # Check both directions
    spacing = rules.get((asset1_type, asset2_type))
    if spacing is not None:
        return spacing

    spacing = rules.get((asset2_type, asset1_type))
    if spacing is not None:
        return spacing

    return 0.0

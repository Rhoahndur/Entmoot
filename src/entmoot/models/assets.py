"""
Asset models for site planning optimization.

This module defines asset types that can be placed on a property during
layout optimization, including buildings, equipment yards, parking lots,
and storage tanks.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon, box
from shapely.geometry.base import BaseGeometry
from shapely.affinity import rotate as shapely_rotate, translate as shapely_translate


class AssetType(str, Enum):
    """Types of assets that can be placed."""

    BUILDING = "building"
    EQUIPMENT_YARD = "equipment_yard"
    PARKING_LOT = "parking_lot"
    STORAGE_TANK = "storage_tank"


class RotationAngle(float, Enum):
    """Standard rotation angles (degrees)."""

    NORTH = 0.0
    EAST = 90.0
    SOUTH = 180.0
    WEST = 270.0


class Asset(BaseModel, ABC):
    """
    Abstract base class for all assets.

    Attributes:
        id: Unique identifier for the asset
        name: Human-readable name
        asset_type: Type of asset
        position: (x, y) position of asset centroid
        rotation: Rotation angle in degrees (0-360, 0 = North)
        dimensions: (width, length) in meters
        area_sqm: Required area in square meters
        min_setback_m: Minimum setback from property line (meters)
        min_spacing_m: Minimum spacing from other assets (meters)
        max_slope_percent: Maximum allowable slope (%)
        min_road_distance_m: Minimum distance to road access (meters)
        max_road_distance_m: Maximum distance to road access (meters)
        priority: Priority for placement (1-10, higher = more important)
        metadata: Additional custom metadata
    """

    id: str = Field(..., description="Unique asset identifier")
    name: str = Field(..., description="Asset name", min_length=1)
    asset_type: AssetType = Field(..., description="Type of asset")
    position: Tuple[float, float] = Field(
        default=(0.0, 0.0), description="(x, y) centroid position"
    )
    rotation: float = Field(default=0.0, description="Rotation angle in degrees", ge=0, lt=360)
    dimensions: Tuple[float, float] = Field(..., description="(width, length) in meters")
    area_sqm: float = Field(..., description="Required area in square meters", gt=0)
    min_setback_m: float = Field(
        default=7.62, description="Minimum setback from property line (meters)", ge=0
    )
    min_spacing_m: float = Field(
        default=3.0, description="Minimum spacing from other assets (meters)", ge=0
    )
    max_slope_percent: float = Field(
        default=15.0, description="Maximum allowable slope (%)", ge=0
    )
    min_road_distance_m: float = Field(
        default=0.0, description="Minimum distance to road (meters)", ge=0
    )
    max_road_distance_m: float = Field(
        default=500.0, description="Maximum distance to road (meters)", ge=0
    )
    priority: int = Field(default=5, description="Placement priority (1-10)", ge=1, le=10)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        """Validate dimensions are positive."""
        width, length = v
        if width <= 0 or length <= 0:
            raise ValueError(f"Dimensions must be positive, got {v}")
        return v

    @field_validator("area_sqm")
    @classmethod
    def validate_area(cls, v: float, info) -> float:
        """Validate area matches dimensions."""
        if "dimensions" in info.data:
            width, length = info.data["dimensions"]
            expected_area = width * length
            # Allow some tolerance for rounding
            if abs(v - expected_area) > 0.1:
                raise ValueError(
                    f"Area {v} does not match dimensions {width}x{length} = {expected_area}"
                )
        return v

    def get_geometry(self) -> ShapelyPolygon:
        """
        Get the asset's footprint as a Shapely polygon.

        Returns:
            Shapely Polygon representing the asset footprint
        """
        width, length = self.dimensions
        x, y = self.position

        # Create rectangle centered at origin
        half_width = width / 2
        half_length = length / 2
        rect = box(-half_width, -half_length, half_width, half_length)

        # Rotate around origin
        if self.rotation != 0:
            rect = shapely_rotate(rect, self.rotation, origin=(0, 0))

        # Translate to position
        rect = shapely_translate(rect, xoff=x, yoff=y)

        return rect

    def get_setback_geometry(self) -> ShapelyPolygon:
        """
        Get the asset's setback zone (buffered footprint).

        Returns:
            Shapely Polygon representing the setback zone
        """
        return self.get_geometry().buffer(self.min_setback_m)

    def get_spacing_geometry(self) -> ShapelyPolygon:
        """
        Get the asset's spacing zone (for separation from other assets).

        Returns:
            Shapely Polygon representing the spacing zone
        """
        return self.get_geometry().buffer(self.min_spacing_m)

    def set_position(self, x: float, y: float) -> None:
        """
        Set the asset's position.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.position = (x, y)

    def set_rotation(self, angle: float) -> None:
        """
        Set the asset's rotation angle.

        Args:
            angle: Rotation angle in degrees (0-360)
        """
        self.rotation = angle % 360

    def intersects(self, other_geometry: BaseGeometry) -> bool:
        """
        Check if asset intersects with another geometry.

        Args:
            other_geometry: Shapely geometry to check

        Returns:
            True if geometries intersect
        """
        return self.get_geometry().intersects(other_geometry)

    def contains_point(self, point: ShapelyPoint) -> bool:
        """
        Check if asset contains a point.

        Args:
            point: Shapely Point

        Returns:
            True if point is within asset footprint
        """
        return self.get_geometry().contains(point)

    @abstractmethod
    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """
        Validate asset-specific constraints.

        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        pass

    def to_geojson(self) -> Dict[str, Any]:
        """
        Export asset as GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        geom = self.get_geometry()

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [list(geom.exterior.coords)],
            },
            "properties": {
                "id": self.id,
                "name": self.name,
                "asset_type": self.asset_type.value,
                "position": self.position,
                "rotation": self.rotation,
                "dimensions": self.dimensions,
                "area_sqm": self.area_sqm,
                "priority": self.priority,
                **self.metadata,
            },
        }


class BuildingAsset(Asset):
    """
    Building asset with specific constraints.

    Attributes:
        num_stories: Number of stories
        building_height_m: Total building height in meters
        foundation_type: Type of foundation (slab, crawlspace, basement)
        requires_utilities: Whether building requires utility access
    """

    num_stories: int = Field(default=1, description="Number of stories", ge=1)
    building_height_m: float = Field(default=3.0, description="Total height in meters", gt=0)
    foundation_type: str = Field(default="slab", description="Foundation type")
    requires_utilities: bool = Field(default=True, description="Requires utility access")

    def __init__(self, **data):
        """Initialize with building defaults."""
        if "asset_type" not in data:
            data["asset_type"] = AssetType.BUILDING
        if "max_slope_percent" not in data:
            data["max_slope_percent"] = 5.0  # Buildings need flatter ground
        if "min_setback_m" not in data:
            data["min_setback_m"] = 7.62  # 25 feet
        super().__init__(**data)

    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """Validate building-specific constraints."""
        errors = []

        # Buildings need relatively flat ground
        if self.max_slope_percent > 10.0:
            errors.append(
                f"Building max slope {self.max_slope_percent}% exceeds recommended 10%"
            )

        # Check height vs stories
        min_height = self.num_stories * 2.5  # Minimum ~8ft per story
        if self.building_height_m < min_height:
            errors.append(
                f"Building height {self.building_height_m}m insufficient for {self.num_stories} stories"
            )

        # Buildings should have reasonable dimensions
        width, length = self.dimensions
        if width < 5.0 or length < 5.0:
            errors.append(f"Building dimensions {width}x{length}m may be too small")

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "building_001",
                "name": "Main Office Building",
                "asset_type": "building",
                "position": (100.0, 100.0),
                "rotation": 0.0,
                "dimensions": (30.0, 50.0),
                "area_sqm": 1500.0,
                "num_stories": 2,
                "building_height_m": 7.0,
                "foundation_type": "slab",
            }
        }
    )


class EquipmentYardAsset(Asset):
    """
    Equipment yard/storage area.

    Attributes:
        surface_type: Surface material (gravel, concrete, asphalt)
        drainage_required: Whether drainage system is required
        fenced: Whether area needs fencing
    """

    surface_type: str = Field(default="gravel", description="Surface material")
    drainage_required: bool = Field(default=True, description="Drainage required")
    fenced: bool = Field(default=True, description="Requires fencing")

    def __init__(self, **data):
        """Initialize with equipment yard defaults."""
        if "asset_type" not in data:
            data["asset_type"] = AssetType.EQUIPMENT_YARD
        if "max_slope_percent" not in data:
            data["max_slope_percent"] = 10.0  # More tolerant than buildings
        if "min_setback_m" not in data:
            data["min_setback_m"] = 3.0  # Less strict setback
        super().__init__(**data)

    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """Validate equipment yard constraints."""
        errors = []

        # Equipment yards need reasonable size
        if self.area_sqm < 100.0:
            errors.append(f"Equipment yard area {self.area_sqm}sqm may be too small")

        # Check slope for drainage
        if self.drainage_required and self.max_slope_percent < 1.0:
            errors.append("Drainage required but max slope too flat for proper drainage")

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "yard_001",
                "name": "Equipment Storage Yard",
                "asset_type": "equipment_yard",
                "position": (200.0, 150.0),
                "dimensions": (40.0, 60.0),
                "area_sqm": 2400.0,
                "surface_type": "gravel",
                "fenced": True,
            }
        }
    )


class ParkingLotAsset(Asset):
    """
    Parking lot asset.

    Attributes:
        num_spaces: Number of parking spaces
        surface_type: Surface material (asphalt, concrete, gravel)
        ada_compliant: Whether ADA compliant
        lighting_required: Whether lighting is required
    """

    num_spaces: int = Field(..., description="Number of parking spaces", ge=1)
    surface_type: str = Field(default="asphalt", description="Surface material")
    ada_compliant: bool = Field(default=True, description="ADA compliant")
    lighting_required: bool = Field(default=True, description="Requires lighting")

    def __init__(self, **data):
        """Initialize with parking lot defaults."""
        if "asset_type" not in data:
            data["asset_type"] = AssetType.PARKING_LOT
        if "max_slope_percent" not in data:
            data["max_slope_percent"] = 5.0  # Parking needs to be flat
        if "min_setback_m" not in data:
            data["min_setback_m"] = 3.0
        super().__init__(**data)

    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """Validate parking lot constraints."""
        errors = []

        # Estimate required area (typical space: 2.5m x 5.0m = 12.5 sqm + circulation)
        min_area_per_space = 25.0  # Includes circulation
        required_area = self.num_spaces * min_area_per_space

        if self.area_sqm < required_area:
            errors.append(
                f"Parking area {self.area_sqm}sqm insufficient for {self.num_spaces} spaces "
                f"(need ~{required_area}sqm)"
            )

        # Parking lots need to be relatively flat
        if self.max_slope_percent > 8.0:
            errors.append(f"Parking lot max slope {self.max_slope_percent}% exceeds recommended 8%")

        # ADA requires accessible spaces
        if self.ada_compliant and self.num_spaces >= 25:
            min_accessible = max(1, int(self.num_spaces * 0.04))
            if "accessible_spaces" not in self.metadata:
                errors.append(
                    f"ADA compliance requires at least {min_accessible} accessible spaces"
                )

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "parking_001",
                "name": "Main Parking Lot",
                "asset_type": "parking_lot",
                "position": (150.0, 200.0),
                "dimensions": (30.0, 50.0),
                "area_sqm": 1500.0,
                "num_spaces": 60,
                "surface_type": "asphalt",
                "ada_compliant": True,
            }
        }
    )


class StorageTankAsset(Asset):
    """
    Storage tank asset (fuel, water, etc.).

    Attributes:
        capacity_liters: Tank capacity in liters
        tank_height_m: Tank height in meters
        tank_type: Type of contents (fuel, water, chemical)
        containment_required: Whether secondary containment is required
    """

    capacity_liters: float = Field(..., description="Tank capacity in liters", gt=0)
    tank_height_m: float = Field(..., description="Tank height in meters", gt=0)
    tank_type: str = Field(default="fuel", description="Type of contents")
    containment_required: bool = Field(default=True, description="Secondary containment required")

    def __init__(self, **data):
        """Initialize with storage tank defaults."""
        if "asset_type" not in data:
            data["asset_type"] = AssetType.STORAGE_TANK
        if "max_slope_percent" not in data:
            data["max_slope_percent"] = 5.0  # Tanks need flat ground
        if "min_setback_m" not in data:
            data["min_setback_m"] = 15.0  # Larger setback for safety
        if "min_spacing_m" not in data:
            data["min_spacing_m"] = 10.0  # Larger spacing for safety
        super().__init__(**data)

    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """Validate storage tank constraints."""
        errors = []

        # Tanks need flat ground
        if self.max_slope_percent > 5.0:
            errors.append(f"Storage tank max slope {self.max_slope_percent}% exceeds recommended 5%")

        # Check if dimensions match expected tank size
        # Assume cylindrical: area ≈ π * r^2, but footprint includes containment
        width, _ = self.dimensions
        # Very rough check - tank should fit in footprint
        if width < 3.0:
            errors.append(f"Storage tank dimensions {self.dimensions} may be too small")

        # Containment area should be larger than tank
        if self.containment_required:
            # Containment typically 110% of tank volume
            if "containment_area_sqm" not in self.metadata:
                errors.append("Secondary containment required but containment area not specified")

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "tank_001",
                "name": "Fuel Storage Tank",
                "asset_type": "storage_tank",
                "position": (250.0, 250.0),
                "dimensions": (10.0, 10.0),
                "area_sqm": 100.0,
                "capacity_liters": 50000,
                "tank_height_m": 5.0,
                "tank_type": "fuel",
                "containment_required": True,
            }
        }
    )


def create_asset_from_dict(asset_data: Dict[str, Any]) -> Asset:
    """
    Factory function to create an asset from a dictionary.

    Args:
        asset_data: Dictionary containing asset data

    Returns:
        Appropriate Asset subclass instance

    Raises:
        ValueError: If asset_type is invalid or missing
    """
    asset_type = asset_data.get("asset_type")

    if asset_type == AssetType.BUILDING or asset_type == "building":
        return BuildingAsset(**asset_data)
    elif asset_type == AssetType.EQUIPMENT_YARD or asset_type == "equipment_yard":
        return EquipmentYardAsset(**asset_data)
    elif asset_type == AssetType.PARKING_LOT or asset_type == "parking_lot":
        return ParkingLotAsset(**asset_data)
    elif asset_type == AssetType.STORAGE_TANK or asset_type == "storage_tank":
        return StorageTankAsset(**asset_data)
    else:
        raise ValueError(f"Unknown asset type: {asset_type}")

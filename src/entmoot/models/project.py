"""
Pydantic models for project configuration and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AssetType(str, Enum):
    """Asset types for site layout."""

    BUILDINGS = "buildings"
    EQUIPMENT_YARD = "equipment_yard"
    PARKING_LOT = "parking_lot"
    STORAGE_TANKS = "storage_tanks"


class AssetConfig(BaseModel):
    """Configuration for a single asset type."""

    type: AssetType = Field(..., description="Type of asset")
    quantity: int = Field(..., ge=1, description="Number of instances")
    width: float = Field(..., gt=0, description="Width in feet")
    length: float = Field(..., gt=0, description="Length in feet")
    height: Optional[float] = Field(None, gt=0, description="Height in feet (optional)")


class ConstraintConfig(BaseModel):
    """Constraint configuration for site layout."""

    setback_distance: float = Field(20, ge=0, description="Setback distance in feet")
    min_distance_between_assets: float = Field(
        10, ge=0, description="Minimum distance between assets in feet"
    )
    exclusion_zones_enabled: bool = Field(True, description="Enable exclusion zones")
    respect_property_lines: bool = Field(True, description="Respect property boundaries")
    respect_easements: bool = Field(True, description="Respect easements")
    wetland_buffer: float = Field(50, ge=0, description="Wetland buffer distance in feet")
    slope_limit: float = Field(15, ge=0, le=30, description="Maximum buildable slope percentage")


class RoadConfig(BaseModel):
    """Road design configuration."""

    min_width: float = Field(24, gt=0, description="Minimum road width in feet")
    max_grade: float = Field(8, gt=0, le=15, description="Maximum road grade percentage")
    turning_radius: float = Field(25, gt=0, description="Minimum turning radius in feet")
    surface_type: str = Field("paved", description="Road surface type")
    include_sidewalks: bool = Field(True, description="Include sidewalks in road design")


class OptimizationWeights(BaseModel):
    """Optimization weights for layout generation."""

    cost: float = Field(40, ge=0, le=100, description="Weight for cost minimization")
    buildable_area: float = Field(30, ge=0, le=100, description="Weight for buildable area maximization")
    accessibility: float = Field(15, ge=0, le=100, description="Weight for accessibility")
    environmental_impact: float = Field(
        10, ge=0, le=100, description="Weight for environmental impact"
    )
    aesthetics: float = Field(5, ge=0, le=100, description="Weight for aesthetics")

    @field_validator("cost", "buildable_area", "accessibility", "environmental_impact", "aesthetics")
    @classmethod
    def validate_total_weight(cls, v, info):
        """Validate that weights sum to 100."""
        # This will be checked in a model_validator instead
        return v


class ProjectConfig(BaseModel):
    """Complete project configuration."""

    project_name: str = Field(..., min_length=1, max_length=255, description="Project name")
    upload_id: str = Field(..., description="Upload ID from file upload")
    assets: List[AssetConfig] = Field(..., min_length=1, description="List of assets to place")
    constraints: ConstraintConfig = Field(..., description="Constraint configuration")
    road_design: RoadConfig = Field(..., description="Road design configuration")
    optimization_weights: OptimizationWeights = Field(
        ..., description="Optimization weights"
    )


class ProjectStatus(str, Enum):
    """Project status enumeration."""

    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectResponse(BaseModel):
    """Response model for project creation."""

    project_id: str = Field(..., description="Unique project identifier")
    project_name: str = Field(..., description="Project name")
    status: ProjectStatus = Field(..., description="Current project status")
    created_at: datetime = Field(..., description="Project creation timestamp")
    message: str = Field(..., description="Response message")


class ProjectStatusResponse(BaseModel):
    """Response model for project status check."""

    project_id: str = Field(..., description="Project identifier")
    status: ProjectStatus = Field(..., description="Current status")
    progress: float = Field(0, ge=0, le=100, description="Progress percentage")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")


class Coordinate(BaseModel):
    """A geographic coordinate."""

    latitude: float = Field(..., description="Latitude in degrees")
    longitude: float = Field(..., description="Longitude in degrees")


class PlacedAsset(BaseModel):
    """A placed asset in the generated layout."""

    id: str = Field(..., description="Asset identifier")
    type: AssetType = Field(..., description="Asset type")
    position: Coordinate = Field(..., description="Asset centroid position")
    rotation: float = Field(..., ge=0, lt=360, description="Rotation in degrees")
    width: float = Field(..., description="Width in feet")
    length: float = Field(..., description="Length in feet")
    height: Optional[float] = Field(None, description="Height in feet")
    polygon: List['Coordinate'] = Field(default_factory=list, description="Footprint corners")


class RoadSegment(BaseModel):
    """A road segment in the generated layout."""

    id: str = Field(..., description="Segment identifier")
    points: List[Coordinate] = Field(..., description="Road centerline points")
    width: float = Field(..., description="Road width in feet")
    grade: float = Field(..., description="Road grade percentage")
    surface_type: str = Field(default="paved", description="Road surface type")
    length: float = Field(..., description="Road length in feet")


class EarthworkSummary(BaseModel):
    """Summary of earthwork calculations."""

    total_cut_volume: float = Field(..., description="Total cut volume in cubic yards")
    total_fill_volume: float = Field(..., description="Total fill volume in cubic yards")
    net_volume: float = Field(..., description="Net volume (cut - fill) in cubic yards")
    estimated_cost: float = Field(..., description="Estimated earthwork cost in USD")


class LayoutResults(BaseModel):
    """Complete layout generation results."""

    project_id: str = Field(..., description="Project identifier")
    placed_assets: List[PlacedAsset] = Field(..., description="List of placed assets")
    road_network: List[RoadSegment] = Field(..., description="Generated road network")
    earthwork: EarthworkSummary = Field(..., description="Earthwork calculations")
    total_cost: float = Field(..., description="Total project cost estimate in USD")
    buildable_area_used: float = Field(..., description="Percentage of buildable area used")
    constraints_satisfied: bool = Field(..., description="Whether all constraints are satisfied")
    fitness_score: float = Field(..., description="Overall layout fitness score (0-1)")
    alternatives: List[Dict[str, Any]] = Field(
        default_factory=list, description="Alternative layout options"
    )


class Bounds(BaseModel):
    """Map bounds for visualization."""

    north: float = Field(..., description="Northern latitude bound")
    south: float = Field(..., description="Southern latitude bound")
    east: float = Field(..., description="Eastern longitude bound")
    west: float = Field(..., description="Western longitude bound")


class ConstraintType(str, Enum):
    """Types of constraints for site layout."""

    SETBACK = "setback"
    WETLAND = "wetland"
    SLOPE = "slope"
    EASEMENT = "easement"
    EXCLUSION = "exclusion"
    PROPERTY_LINE = "property_line"


class ConstraintZone(BaseModel):
    """Constraint zone polygon."""

    id: str = Field(..., description="Zone identifier")
    type: ConstraintType = Field(..., description="Constraint type")
    polygon: List[Coordinate] = Field(..., description="Zone boundary coordinates")
    severity: str = Field(..., description="Constraint severity (low, medium, high)")
    description: Optional[str] = Field(None, description="Zone description")


class BuildableArea(BaseModel):
    """Buildable area polygon."""

    polygon: List[Coordinate] = Field(..., description="Area boundary coordinates")
    area: float = Field(..., description="Area in square feet")
    usable: bool = Field(..., description="Whether area is usable")


class EarthworkVolumes(BaseModel):
    """Earthwork volume calculations."""

    cut: float = Field(..., description="Cut volume in cubic yards")
    fill: float = Field(..., description="Fill volume in cubic yards")
    net: float = Field(..., description="Net volume (fill - cut) in cubic yards")
    balance_ratio: float = Field(..., description="Cut/fill ratio")


class CostBreakdown(BaseModel):
    """Detailed cost breakdown."""

    earthwork: float = Field(..., description="Earthwork costs in USD")
    roads: float = Field(..., description="Road construction costs in USD")
    utilities: float = Field(..., description="Utility costs in USD")
    drainage: float = Field(..., description="Drainage costs in USD")
    landscaping: float = Field(..., description="Landscaping costs in USD")
    contingency: float = Field(..., description="Contingency costs in USD")
    total: float = Field(..., description="Total cost in USD")


class LayoutMetrics(BaseModel):
    """Metrics for a layout alternative."""

    property_area: float = Field(..., description="Total property area in square feet")
    buildable_area: float = Field(..., description="Buildable area in square feet")
    buildable_percentage: float = Field(..., description="Percentage of buildable area")
    assets_placed: int = Field(..., description="Number of assets placed")
    total_road_length: float = Field(..., description="Total road length in feet")
    earthwork_volumes: EarthworkVolumes = Field(..., description="Earthwork volume summary")
    estimated_cost: CostBreakdown = Field(..., description="Cost breakdown")
    constraint_violations: int = Field(..., description="Number of constraint violations")
    optimization_score: float = Field(..., description="Optimization score (0-100)")


class ConstraintViolation(BaseModel):
    """Constraint violation record."""

    asset_id: str = Field(..., description="Asset that violates constraint")
    constraint_type: ConstraintType = Field(..., description="Type of constraint violated")
    severity: str = Field(..., description="Violation severity (warning, error)")
    message: str = Field(..., description="Violation message")
    location: Optional[Coordinate] = Field(None, description="Violation location")


class RoadNetwork(BaseModel):
    """Road network structure."""

    segments: List[RoadSegment] = Field(..., description="Road segments")
    total_length: float = Field(..., description="Total road length in feet")
    intersections: List[Coordinate] = Field(..., description="Intersection points")


class LayoutAlternative(BaseModel):
    """A layout alternative/option."""

    id: str = Field(..., description="Alternative identifier")
    name: str = Field(..., description="Alternative name")
    description: Optional[str] = Field(None, description="Alternative description")
    metrics: LayoutMetrics = Field(..., description="Layout metrics")
    assets: List[PlacedAsset] = Field(..., description="Placed assets")
    road_network: RoadNetwork = Field(..., description="Road network")
    constraint_zones: List[ConstraintZone] = Field(..., description="Constraint zones")
    buildable_areas: List[BuildableArea] = Field(..., description="Buildable areas")
    earthwork_zones: List[Dict[str, Any]] = Field(
        default_factory=list, description="Earthwork zones"
    )
    violations: List[ConstraintViolation] = Field(..., description="Constraint violations")
    created_at: str = Field(..., description="Creation timestamp")


class OptimizationResults(BaseModel):
    """Complete optimization results response."""

    project_id: str = Field(..., description="Project identifier")
    project_name: str = Field(..., description="Project name")
    property_boundary: List[Coordinate] = Field(..., description="Property boundary coordinates")
    bounds: Bounds = Field(..., description="Map bounds")
    alternatives: List[LayoutAlternative] = Field(..., description="Layout alternatives")
    selected_alternative_id: Optional[str] = Field(None, description="Selected alternative ID")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

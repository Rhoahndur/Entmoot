"""Pydantic models for existing conditions from OpenStreetMap."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class OSMFeatureType(str, Enum):
    """Types of features fetched from OpenStreetMap."""

    BUILDING = "building"
    ROAD = "road"
    UTILITY = "utility"
    WATER = "water"


class OSMRoadClass(str, Enum):
    """Road classification derived from OSM highway tags."""

    MOTORWAY = "motorway"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    RESIDENTIAL = "residential"
    SERVICE = "service"
    OTHER = "other"


class OSMUtilityType(str, Enum):
    """Utility infrastructure types from OSM."""

    POWER_LINE = "power_line"
    HIGH_VOLTAGE = "high_voltage"
    PIPELINE = "pipeline"
    GAS_LINE = "gas_line"
    DEFAULT = "default"


class OSMWaterType(str, Enum):
    """Water feature types from OSM."""

    STREAM = "stream"
    RIVER = "river"
    POND = "pond"
    LAKE = "lake"
    WETLAND = "wetland"


class OSMFeature(BaseModel):
    """A single feature extracted from OpenStreetMap data."""

    osm_id: int = Field(..., description="OpenStreetMap element ID")
    feature_type: OSMFeatureType = Field(..., description="High-level feature category")
    geometry_wkt: str = Field(..., description="Geometry in WKT format")
    tags: Dict[str, str] = Field(default_factory=dict, description="Raw OSM tags")

    # Sub-classification fields (set by parser based on tags)
    road_class: Optional[OSMRoadClass] = None
    utility_type: Optional[OSMUtilityType] = None
    water_type: Optional[OSMWaterType] = None


class ExistingConditionsData(BaseModel):
    """Collection of existing conditions fetched from OpenStreetMap."""

    buildings: List[OSMFeature] = Field(default_factory=list)
    roads: List[OSMFeature] = Field(default_factory=list)
    utilities: List[OSMFeature] = Field(default_factory=list)
    water_features: List[OSMFeature] = Field(default_factory=list)

    bbox: Optional[Dict[str, float]] = None
    query_timestamp: Optional[datetime] = None

    @property
    def feature_count(self) -> int:
        """Total number of features across all categories."""
        return (
            len(self.buildings) + len(self.roads) + len(self.utilities) + len(self.water_features)
        )

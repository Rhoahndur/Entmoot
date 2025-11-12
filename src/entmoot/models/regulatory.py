"""
Pydantic models for regulatory constraint data.

This module defines data structures for regulatory constraints including
floodplain data, flood zones, and regulatory data sources.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry


class FloodZoneType(str, Enum):
    """FEMA flood zone classifications."""

    # Special Flood Hazard Areas (SFHA) - High Risk
    A = "A"  # 1% annual chance flood, no BFE determined
    AE = "AE"  # 1% annual chance flood, BFE determined
    AH = "AH"  # 1% annual chance shallow flooding (1-3 feet), BFE determined
    AO = "AO"  # 1% annual chance sheet flow flooding, depth determined
    AR = "AR"  # 1% annual chance flooding, temporarily protected by flood control
    A99 = "A99"  # 1% annual chance flooding, protected by federal flood control

    # Coastal High Hazard Areas (V Zones) - Highest Risk
    V = "V"  # 1% annual chance coastal flood with wave action, no BFE
    VE = "VE"  # 1% annual chance coastal flood with wave action, BFE determined

    # Moderate to Low Risk Areas
    B = "B"  # 0.2% annual chance flood (older maps)
    C = "C"  # Minimal flood risk (older maps)
    X = "X"  # Minimal to moderate flood risk (newer maps)
    X_PROTECTED = "X_PROTECTED"  # 0.2% annual chance, protected by levee

    # Undetermined Risk
    D = "D"  # Undetermined flood risk

    # Other
    OPEN_WATER = "OPEN_WATER"  # Open water areas
    UNKNOWN = "UNKNOWN"  # Unknown or unmapped


class RegulatoryDataSource(str, Enum):
    """Source of regulatory constraint data."""

    FEMA_NFHL = "fema_nfhl"
    FEMA_MANUAL = "fema_manual"
    LOCAL_JURISDICTION = "local_jurisdiction"
    THIRD_PARTY = "third_party"
    CACHED = "cached"
    UNKNOWN = "unknown"


class FloodZone(BaseModel):
    """
    Represents a FEMA flood zone with geometry and metadata.

    Attributes:
        zone_type: FEMA flood zone classification
        zone_subtype: Additional zone classification detail
        geometry_wkt: WKT representation of the flood zone polygon
        base_flood_elevation: Base Flood Elevation in feet (if available)
        static_bfe: Static BFE value
        depth: Flood depth in feet (for AO zones)
        velocity: Velocity zone indicator
        floodway: Whether area is in regulatory floodway
        coastal_zone: Whether area is in coastal high hazard area
        effective_date: Date the flood map became effective
        study_type: Type of flood study conducted
        source_citation: FIRM panel or study reference
        area_sqm: Area of flood zone in square meters
        vertical_datum: Vertical datum used for BFE (e.g., NAVD88, NGVD29)
    """

    zone_type: FloodZoneType = Field(..., description="FEMA flood zone classification")
    zone_subtype: Optional[str] = Field(None, description="Additional zone detail")
    geometry_wkt: str = Field(..., description="WKT representation of zone polygon")
    base_flood_elevation: Optional[float] = Field(
        None, description="Base Flood Elevation in feet", ge=-100, le=30000
    )
    static_bfe: Optional[float] = Field(
        None, description="Static BFE value", ge=-100, le=30000
    )
    depth: Optional[float] = Field(None, description="Flood depth in feet (AO zones)", ge=0)
    velocity: Optional[float] = Field(None, description="Velocity in fps", ge=0)
    floodway: bool = Field(default=False, description="In regulatory floodway")
    coastal_zone: bool = Field(default=False, description="In coastal high hazard area")
    effective_date: Optional[datetime] = Field(None, description="Map effective date")
    study_type: Optional[str] = Field(None, description="Type of flood study")
    source_citation: Optional[str] = Field(None, description="FIRM panel or study reference")
    area_sqm: Optional[float] = Field(None, description="Zone area in square meters", ge=0)
    vertical_datum: Optional[str] = Field(None, description="Vertical datum (NAVD88, NGVD29)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_type": "AE",
                "zone_subtype": None,
                "geometry_wkt": "POLYGON((-122.084 37.422, -122.083 37.422, -122.083 37.421, -122.084 37.421, -122.084 37.422))",
                "base_flood_elevation": 15.5,
                "static_bfe": 15.5,
                "depth": None,
                "velocity": None,
                "floodway": False,
                "coastal_zone": False,
                "effective_date": "2020-06-19T00:00:00Z",
                "study_type": "Detailed Study",
                "source_citation": "FIRM Panel 06085C0125E",
                "area_sqm": 5000.0,
                "vertical_datum": "NAVD88",
            }
        }
    )

    def is_high_risk(self) -> bool:
        """Check if zone is high-risk Special Flood Hazard Area."""
        high_risk_zones = {
            FloodZoneType.A,
            FloodZoneType.AE,
            FloodZoneType.AH,
            FloodZoneType.AO,
            FloodZoneType.AR,
            FloodZoneType.A99,
            FloodZoneType.V,
            FloodZoneType.VE,
        }
        return self.zone_type in high_risk_zones

    def requires_flood_insurance(self) -> bool:
        """Check if flood insurance is required (SFHA zones)."""
        return self.is_high_risk()


class FloodplainData(BaseModel):
    """
    Collection of flood zones for a specific location or property.

    Attributes:
        zones: List of flood zones affecting the area
        location_lon: Query location longitude
        location_lat: Query location latitude
        bbox_min_lon: Bounding box minimum longitude
        bbox_min_lat: Bounding box minimum latitude
        bbox_max_lon: Bounding box maximum longitude
        bbox_max_lat: Bounding box maximum latitude
        community_name: NFIP community name
        community_id: NFIP community ID
        panel_id: FIRM panel identifier
        highest_risk_zone: Most restrictive flood zone present
        in_sfha: Whether location is in Special Flood Hazard Area
        insurance_required: Whether flood insurance is required
        query_date: When data was retrieved
        data_source: Source of the data
        cache_hit: Whether data came from cache
    """

    zones: List[FloodZone] = Field(default_factory=list, description="Flood zones")
    location_lon: Optional[float] = Field(
        None, description="Query location longitude", ge=-180, le=180
    )
    location_lat: Optional[float] = Field(
        None, description="Query location latitude", ge=-90, le=90
    )
    bbox_min_lon: Optional[float] = Field(
        None, description="Bounding box min longitude", ge=-180, le=180
    )
    bbox_min_lat: Optional[float] = Field(
        None, description="Bounding box min latitude", ge=-90, le=90
    )
    bbox_max_lon: Optional[float] = Field(
        None, description="Bounding box max longitude", ge=-180, le=180
    )
    bbox_max_lat: Optional[float] = Field(
        None, description="Bounding box max latitude", ge=-90, le=90
    )
    community_name: Optional[str] = Field(None, description="NFIP community name")
    community_id: Optional[str] = Field(None, description="NFIP community ID")
    panel_id: Optional[str] = Field(None, description="FIRM panel ID")
    highest_risk_zone: Optional[FloodZoneType] = Field(
        None, description="Most restrictive flood zone"
    )
    in_sfha: bool = Field(default=False, description="In Special Flood Hazard Area")
    insurance_required: bool = Field(default=False, description="Flood insurance required")
    query_date: datetime = Field(
        default_factory=datetime.utcnow, description="Data retrieval timestamp"
    )
    data_source: RegulatoryDataSource = Field(
        default=RegulatoryDataSource.FEMA_NFHL, description="Data source"
    )
    cache_hit: bool = Field(default=False, description="Data from cache")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zones": [],
                "location_lon": -122.084,
                "location_lat": 37.422,
                "community_name": "Santa Clara County",
                "community_id": "060286",
                "panel_id": "06085C0125E",
                "highest_risk_zone": "AE",
                "in_sfha": True,
                "insurance_required": True,
                "query_date": "2025-11-10T00:00:00Z",
                "data_source": "fema_nfhl",
                "cache_hit": False,
            }
        }
    )

    def get_max_bfe(self) -> Optional[float]:
        """Get the maximum Base Flood Elevation across all zones."""
        bfes = [z.base_flood_elevation for z in self.zones if z.base_flood_elevation is not None]
        return max(bfes) if bfes else None

    def get_zone_summary(self) -> Dict[str, int]:
        """Get summary count of each zone type."""
        summary: Dict[str, int] = {}
        for zone in self.zones:
            zone_str = zone.zone_type.value
            summary[zone_str] = summary.get(zone_str, 0) + 1
        return summary


class RegulatoryConstraint(BaseModel):
    """
    Generic regulatory constraint that can affect property development.

    Attributes:
        constraint_type: Type of constraint (floodplain, wetland, etc.)
        severity: Impact severity (high, medium, low)
        description: Human-readable description
        geometry_wkt: WKT representation of constraint area
        affects_development: Whether it affects development
        requires_permit: Whether special permits are required
        mitigation_possible: Whether mitigation is possible
        metadata: Additional constraint-specific data
        data_source: Source of constraint data
        effective_date: When constraint became effective
        expiration_date: When constraint expires (if applicable)
    """

    constraint_type: str = Field(..., description="Constraint type")
    severity: str = Field(..., description="Impact severity", pattern="^(high|medium|low)$")
    description: str = Field(..., description="Constraint description")
    geometry_wkt: Optional[str] = Field(None, description="WKT representation")
    affects_development: bool = Field(default=True, description="Affects development")
    requires_permit: bool = Field(default=False, description="Requires special permit")
    mitigation_possible: bool = Field(default=True, description="Mitigation possible")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    data_source: RegulatoryDataSource = Field(..., description="Data source")
    effective_date: Optional[datetime] = Field(None, description="Effective date")
    expiration_date: Optional[datetime] = Field(None, description="Expiration date")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "constraint_type": "floodplain",
                "severity": "high",
                "description": "Property is in FEMA Zone AE with BFE of 15.5 feet",
                "geometry_wkt": "POLYGON((-122.084 37.422, -122.083 37.422, -122.083 37.421, -122.084 37.421, -122.084 37.422))",
                "affects_development": True,
                "requires_permit": True,
                "mitigation_possible": True,
                "metadata": {"zone": "AE", "bfe": 15.5, "panel_id": "06085C0125E"},
                "data_source": "fema_nfhl",
                "effective_date": "2020-06-19T00:00:00Z",
            }
        }
    )

    @classmethod
    def from_floodplain_data(cls, floodplain: FloodplainData) -> Optional["RegulatoryConstraint"]:
        """
        Create a RegulatoryConstraint from FloodplainData.

        Args:
            floodplain: FloodplainData object

        Returns:
            RegulatoryConstraint or None if no constraint
        """
        if not floodplain.in_sfha or not floodplain.zones:
            return None

        # Find highest risk zone
        high_risk_zones = [z for z in floodplain.zones if z.is_high_risk()]
        if not high_risk_zones:
            return None

        primary_zone = high_risk_zones[0]
        max_bfe = floodplain.get_max_bfe()

        description = f"Property is in FEMA Zone {primary_zone.zone_type.value}"
        if max_bfe is not None:
            description += f" with Base Flood Elevation of {max_bfe} feet"
        if floodplain.community_name:
            description += f" ({floodplain.community_name})"

        metadata = {
            "zone": primary_zone.zone_type.value,
            "bfe": max_bfe,
            "panel_id": floodplain.panel_id,
            "community_id": floodplain.community_id,
            "total_zones": len(floodplain.zones),
            "zone_summary": floodplain.get_zone_summary(),
        }

        # Determine severity
        if primary_zone.zone_type in {FloodZoneType.V, FloodZoneType.VE}:
            severity = "high"
        elif primary_zone.zone_type in {
            FloodZoneType.AE,
            FloodZoneType.AH,
            FloodZoneType.AO,
        }:
            severity = "high"
        else:
            severity = "medium"

        return cls(
            constraint_type="floodplain",
            severity=severity,
            description=description,
            geometry_wkt=primary_zone.geometry_wkt,
            affects_development=True,
            requires_permit=True,
            mitigation_possible=True,
            metadata=metadata,
            data_source=floodplain.data_source,
            effective_date=primary_zone.effective_date,
        )

"""
Constraint data models for site planning.

This module defines the constraint framework for managing spatial and regulatory
restrictions on property development, including setbacks, exclusion zones, and
regulatory constraints.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry
from shapely import wkt, ops
from shapely.validation import make_valid


class ConstraintType(str, Enum):
    """Types of constraints that can be applied to a site."""

    # Setback types
    PROPERTY_LINE = "property_line"
    ROAD = "road"
    WATER_FEATURE = "water_feature"
    WETLAND = "wetland"
    FLOODPLAIN = "floodplain"
    UTILITY = "utility"
    NEIGHBOR = "neighbor"

    # Topographic constraints
    STEEP_SLOPE = "steep_slope"

    # Environmental/Cultural
    ARCHAEOLOGICAL = "archaeological"
    ENVIRONMENTAL = "environmental"
    HABITAT = "habitat"

    # Regulatory
    ZONING = "zoning"
    EASEMENT = "easement"

    # Buffer zones
    BUFFER_ZONE = "buffer_zone"

    # Custom
    CUSTOM = "custom"


class ConstraintSeverity(str, Enum):
    """Severity level of a constraint."""

    BLOCKING = "blocking"  # Absolute prohibition
    WARNING = "warning"    # Strong recommendation against
    PREFERENCE = "preference"  # Soft preference


class ConstraintPriority(str, Enum):
    """Priority level for constraint conflict resolution."""

    CRITICAL = "critical"  # Cannot be overridden (regulatory, safety)
    HIGH = "high"         # Requires special approval to override
    MEDIUM = "medium"     # Can be overridden with justification
    LOW = "low"          # Soft preference, easily overridden


class Constraint(BaseModel, ABC):
    """
    Abstract base class for all constraints.

    Attributes:
        id: Unique identifier for the constraint
        name: Human-readable name
        description: Detailed description
        constraint_type: Type of constraint
        severity: How strictly to enforce
        priority: Priority for conflict resolution
        geometry_wkt: WKT representation of spatial constraint
        metadata: Additional custom metadata
        created_at: Creation timestamp
        created_by: User or system that created constraint
        can_override: Whether this constraint can be overridden
        override_reason: Reason for override if applicable
    """

    id: str = Field(..., description="Unique constraint identifier")
    name: str = Field(..., description="Constraint name", min_length=1)
    description: Optional[str] = Field(None, description="Detailed description")
    constraint_type: ConstraintType = Field(..., description="Type of constraint")
    severity: ConstraintSeverity = Field(
        default=ConstraintSeverity.BLOCKING,
        description="Severity level"
    )
    priority: ConstraintPriority = Field(
        default=ConstraintPriority.MEDIUM,
        description="Priority for conflict resolution"
    )
    geometry_wkt: str = Field(..., description="WKT representation of constraint area")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    created_by: Optional[str] = Field(None, description="Creator")
    can_override: bool = Field(default=False, description="Whether constraint can be overridden")
    override_reason: Optional[str] = Field(None, description="Override justification")

    model_config = ConfigDict(arbitrary_types_allowed=True)

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

    def get_area_acres(self) -> float:
        """Calculate area in acres."""
        return self.get_area_sqm() * 0.000247105

    def intersects(self, other_geometry: BaseGeometry) -> bool:
        """Check if constraint intersects with another geometry."""
        return self.get_geometry().intersects(other_geometry)

    def contains(self, point: ShapelyPoint) -> bool:
        """Check if constraint contains a point."""
        return self.get_geometry().contains(point)

    @abstractmethod
    def validate_constraint(self) -> tuple[bool, List[str]]:
        """
        Validate the constraint configuration.

        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        pass

    def to_geojson(self) -> Dict[str, Any]:
        """
        Export constraint as GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        geom = self.get_geometry()

        coords = []
        if isinstance(geom, ShapelyPolygon):
            coords = [list(geom.exterior.coords)]
            for interior in geom.interiors:
                coords.append(list(interior.coords))
        else:
            coords = list(geom.coords)

        return {
            "type": "Feature",
            "geometry": {
                "type": geom.geom_type,
                "coordinates": coords,
            },
            "properties": {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "constraint_type": self.constraint_type,
                "severity": self.severity,
                "priority": self.priority,
                "area_sqm": self.get_area_sqm(),
                "area_acres": self.get_area_acres(),
                "can_override": self.can_override,
                "created_at": self.created_at.isoformat(),
                **self.metadata,
            },
        }


class SetbackConstraint(Constraint):
    """
    Distance-based constraint requiring minimum separation.

    Attributes:
        setback_distance_m: Required setback distance in meters
        source_feature_wkt: WKT of the feature to maintain distance from
        buffer_type: Type of buffer (flat, rounded, etc.)
    """

    setback_distance_m: float = Field(
        ...,
        description="Required setback distance in meters",
        gt=0
    )
    source_feature_wkt: Optional[str] = Field(
        None,
        description="WKT of source feature (e.g., property line)"
    )
    buffer_type: str = Field(
        default="flat",
        description="Buffer style: flat, round, square"
    )

    @field_validator('source_feature_wkt')
    @classmethod
    def validate_source_geometry(cls, v: Optional[str]) -> Optional[str]:
        """Validate source feature geometry."""
        if v is None:
            return v
        try:
            geom = wkt.loads(v)
            if not geom.is_valid:
                geom = make_valid(geom)
            return geom.wkt
        except Exception as e:
            raise ValueError(f"Invalid source feature geometry: {str(e)}")

    def validate_constraint(self) -> tuple[bool, List[str]]:
        """Validate setback constraint configuration."""
        errors = []

        # Check setback distance is reasonable
        if self.setback_distance_m > 1000:  # 1km seems excessive
            errors.append("Setback distance exceeds 1000m, may be unreasonable")

        # Verify geometry is consistent with source + buffer
        if self.source_feature_wkt:
            try:
                source_geom = wkt.loads(self.source_feature_wkt)
                buffered = source_geom.buffer(self.setback_distance_m)
                constraint_geom = self.get_geometry()

                # Check if constraint geometry roughly matches buffered source
                if not buffered.buffer(1).contains(constraint_geom.centroid):
                    errors.append(
                        "Constraint geometry does not match expected buffer from source"
                    )
            except Exception as e:
                errors.append(f"Error validating buffer consistency: {str(e)}")

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "setback_property_001",
                "name": "Property Line Setback",
                "description": "Required 25ft setback from property boundary",
                "constraint_type": "property_line",
                "severity": "blocking",
                "priority": "high",
                "geometry_wkt": "POLYGON((...))",
                "setback_distance_m": 7.62,
                "buffer_type": "flat",
            }
        }
    )


class ExclusionZoneConstraint(Constraint):
    """
    Area-based constraint that completely prohibits development.

    Attributes:
        reason: Reason for exclusion
        is_permanent: Whether exclusion is permanent or temporary
        expiration_date: When temporary exclusion expires
        regulatory_reference: Reference to regulation requiring exclusion
    """

    reason: str = Field(..., description="Reason for exclusion", min_length=1)
    is_permanent: bool = Field(default=True, description="Whether exclusion is permanent")
    expiration_date: Optional[datetime] = Field(
        None,
        description="Expiration for temporary exclusions"
    )
    regulatory_reference: Optional[str] = Field(
        None,
        description="Reference to applicable regulation"
    )

    @field_validator('expiration_date')
    @classmethod
    def validate_expiration(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate expiration date logic."""
        if v and info.data.get('is_permanent'):
            raise ValueError("Permanent exclusions cannot have expiration dates")
        if not info.data.get('is_permanent') and v is None:
            raise ValueError("Temporary exclusions must have expiration dates")
        if v and v < datetime.utcnow():
            raise ValueError("Expiration date cannot be in the past")
        return v

    def validate_constraint(self) -> tuple[bool, List[str]]:
        """Validate exclusion zone constraint."""
        errors = []

        # Check that reason is provided
        if not self.reason or len(self.reason.strip()) == 0:
            errors.append("Exclusion zone must have a reason")

        # For regulatory exclusions, should have reference
        if self.constraint_type in [ConstraintType.WETLAND, ConstraintType.FLOODPLAIN]:
            if not self.regulatory_reference:
                errors.append(
                    f"Regulatory constraint {self.constraint_type} should have reference"
                )

        # Exclusion zones should generally be blocking
        if self.severity != ConstraintSeverity.BLOCKING:
            errors.append("Exclusion zones should typically be 'blocking' severity")

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "exclusion_wetland_001",
                "name": "Wetland Exclusion",
                "description": "Federally protected wetland area",
                "constraint_type": "wetland",
                "severity": "blocking",
                "priority": "critical",
                "geometry_wkt": "POLYGON((...))",
                "reason": "Protected wetland habitat per Clean Water Act",
                "is_permanent": True,
                "regulatory_reference": "33 CFR 328.3",
            }
        }
    )


class RegulatoryConstraint(Constraint):
    """
    Constraint derived from external regulatory data or requirements.

    Attributes:
        regulation_name: Name of applicable regulation
        regulation_code: Code/section reference
        authority: Regulatory authority (Federal, State, Local)
        compliance_requirement: What's required for compliance
        data_source: Source of regulatory data
        verification_date: When regulation was last verified
        verification_url: URL to regulation or data source
    """

    regulation_name: str = Field(..., description="Name of regulation", min_length=1)
    regulation_code: Optional[str] = Field(None, description="Code/section reference")
    authority: str = Field(
        ...,
        description="Regulatory authority (Federal, State, Local)",
        min_length=1
    )
    compliance_requirement: str = Field(
        ...,
        description="Compliance requirement",
        min_length=1
    )
    data_source: Optional[str] = Field(None, description="Source of regulatory data")
    verification_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last verification date"
    )
    verification_url: Optional[str] = Field(None, description="URL to source")

    def validate_constraint(self) -> tuple[bool, List[str]]:
        """Validate regulatory constraint."""
        errors = []

        # Regulatory constraints should be high priority
        if self.priority == ConstraintPriority.LOW:
            errors.append("Regulatory constraints should not be LOW priority")

        # Should have data source for traceability
        if not self.data_source and not self.verification_url:
            errors.append(
                "Regulatory constraints should have data_source or verification_url"
            )

        # Check verification date is not too old (more than 1 year)
        age_days = (datetime.utcnow() - self.verification_date).days
        if age_days > 365:
            errors.append(
                f"Regulation verification is {age_days} days old, may need update"
            )

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "reg_floodplain_001",
                "name": "100-Year Floodplain",
                "description": "FEMA designated 100-year floodplain",
                "constraint_type": "floodplain",
                "severity": "blocking",
                "priority": "critical",
                "geometry_wkt": "POLYGON((...))",
                "regulation_name": "National Flood Insurance Program",
                "regulation_code": "44 CFR 60",
                "authority": "Federal (FEMA)",
                "compliance_requirement": "No habitable structures in floodplain",
                "data_source": "FEMA NFHL",
                "verification_url": "https://msc.fema.gov",
            }
        }
    )


class UserDefinedConstraint(Constraint):
    """
    Custom constraint defined by user with flexible rules.

    Attributes:
        rule_description: Description of the custom rule
        parameters: Custom parameters for the rule
        evaluation_logic: Description of how to evaluate
        notes: Additional notes about the constraint
    """

    rule_description: str = Field(
        ...,
        description="Description of custom rule",
        min_length=1
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom parameters"
    )
    evaluation_logic: Optional[str] = Field(
        None,
        description="How to evaluate this constraint"
    )
    notes: Optional[str] = Field(None, description="Additional notes")

    def validate_constraint(self) -> tuple[bool, List[str]]:
        """Validate user-defined constraint."""
        errors = []

        # Check that rule is described
        if not self.rule_description or len(self.rule_description.strip()) == 0:
            errors.append("User-defined constraint must have rule_description")

        # User-defined constraints should be overridable
        if not self.can_override and self.priority == ConstraintPriority.CRITICAL:
            errors.append(
                "User-defined constraints should not be CRITICAL priority unless regulatory"
            )

        return (len(errors) == 0, errors)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "custom_view_001",
                "name": "Preserve Mountain View",
                "description": "Area where structures would block mountain view",
                "constraint_type": "custom",
                "severity": "preference",
                "priority": "low",
                "geometry_wkt": "POLYGON((...))",
                "rule_description": "Preserve view corridor to mountains",
                "parameters": {"max_height_ft": 15, "view_azimuth": 270},
                "notes": "Owner preference for unobstructed view",
            }
        }
    )


# Standard setback distances (in meters) for common constraint types
STANDARD_SETBACKS: Dict[ConstraintType, float] = {
    ConstraintType.PROPERTY_LINE: 7.62,     # 25 feet
    ConstraintType.ROAD: 15.24,             # 50 feet
    ConstraintType.WATER_FEATURE: 30.48,    # 100 feet
    ConstraintType.WETLAND: 15.24,          # 50 feet
    ConstraintType.UTILITY: 3.05,           # 10 feet
    ConstraintType.STEEP_SLOPE: 6.10,       # 20 feet
}


def create_standard_setback(
    constraint_id: str,
    constraint_type: ConstraintType,
    source_geometry: BaseGeometry,
    name: Optional[str] = None,
    distance_override: Optional[float] = None,
    **kwargs
) -> SetbackConstraint:
    """
    Create a standard setback constraint with default distances.

    Args:
        constraint_id: Unique ID for constraint
        constraint_type: Type of constraint
        source_geometry: Geometry to buffer from
        name: Custom name (defaults to type-based name)
        distance_override: Override standard distance
        **kwargs: Additional constraint parameters

    Returns:
        Configured SetbackConstraint
    """
    distance = distance_override or STANDARD_SETBACKS.get(constraint_type, 10.0)

    if name is None:
        name = f"{constraint_type.value.replace('_', ' ').title()} Setback"

    # Create buffer
    buffered_geom = source_geometry.buffer(distance)

    return SetbackConstraint(
        id=constraint_id,
        name=name,
        constraint_type=constraint_type,
        geometry_wkt=buffered_geom.wkt,
        source_feature_wkt=source_geometry.wkt,
        setback_distance_m=distance,
        **kwargs
    )

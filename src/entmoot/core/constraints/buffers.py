"""
Buffer generation engine for setback constraints.

This module provides functionality for creating spatial buffers around various
feature types (property lines, roads, water features, utilities) with configurable
distances and automatic constraint generation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import logging

from shapely.geometry import (
    Point,
    LineString,
    Polygon,
    MultiPoint,
    MultiLineString,
    MultiPolygon,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from entmoot.models.constraints import (
    SetbackConstraint,
    RegulatoryConstraint,
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
)


logger = logging.getLogger(__name__)


class BufferStyle(str, Enum):
    """Buffer style options."""

    FLAT = "flat"  # Flat end caps for line buffers
    ROUND = "round"  # Rounded end caps (default Shapely behavior)
    SQUARE = "square"  # Square end caps


class RoadType(str, Enum):
    """Road classification for setback determination."""

    MAJOR = "major"  # Major roads/highways
    LOCAL = "local"  # Local streets
    DRIVEWAY = "driveway"  # Driveways and private roads
    COLLECTOR = "collector"  # Collector roads


class WaterFeatureType(str, Enum):
    """Water feature classification."""

    STREAM = "stream"  # Streams and creeks
    RIVER = "river"  # Rivers
    POND = "pond"  # Ponds
    LAKE = "lake"  # Lakes
    WETLAND = "wetland"  # Wetlands


@dataclass
class BufferConfig:
    """
    Configuration for buffer generation.

    Attributes:
        distance_m: Buffer distance in meters
        style: Buffer style (flat, round, square)
        simplify_tolerance: Tolerance for geometry simplification (0 = no simplification)
        resolution: Number of segments per quadrant for round buffers (default 16)
        cap_style: Cap style for line buffers (1=round, 2=flat, 3=square)
        join_style: Join style for corners (1=round, 2=mitre, 3=bevel)
        mitre_limit: Limit for mitre joins
        single_sided: Whether to create single-sided buffer (for lines only)
    """

    distance_m: float
    style: BufferStyle = BufferStyle.ROUND
    simplify_tolerance: float = 0.0
    resolution: int = 16
    cap_style: int = 1  # 1=round, 2=flat, 3=square
    join_style: int = 1  # 1=round, 2=mitre, 3=bevel
    mitre_limit: float = 5.0
    single_sided: bool = False

    def __post_init__(self):
        """Validate and adjust buffer configuration."""
        if self.distance_m <= 0:
            raise ValueError("Buffer distance must be positive")

        # Map style to cap_style
        if self.style == BufferStyle.FLAT:
            self.cap_style = 2
        elif self.style == BufferStyle.SQUARE:
            self.cap_style = 3
        else:  # ROUND
            self.cap_style = 1

        if self.simplify_tolerance < 0:
            self.simplify_tolerance = 0.0


# Standard buffer distances (in meters) for various features
PROPERTY_LINE_SETBACK = {
    "default": 7.62,  # 25 feet
    "front": 7.62,    # 25 feet
    "side": 4.57,     # 15 feet
    "rear": 6.10,     # 20 feet
}

ROAD_SETBACK = {
    RoadType.MAJOR: 30.48,      # 100 feet
    RoadType.COLLECTOR: 22.86,  # 75 feet
    RoadType.LOCAL: 15.24,      # 50 feet
    RoadType.DRIVEWAY: 7.62,    # 25 feet
}

WATER_FEATURE_SETBACK = {
    WaterFeatureType.STREAM: 30.48,   # 100 feet (federal requirement)
    WaterFeatureType.RIVER: 45.72,    # 150 feet
    WaterFeatureType.POND: 15.24,     # 50 feet
    WaterFeatureType.LAKE: 30.48,     # 100 feet
    WaterFeatureType.WETLAND: 15.24,  # 50 feet
}

UTILITY_SETBACK = {
    "power_line": 15.24,     # 50 feet
    "high_voltage": 30.48,   # 100 feet
    "pipeline": 12.19,       # 40 feet
    "gas_line": 9.14,        # 30 feet
    "default": 9.14,         # 30 feet
}


class BufferGenerator:
    """
    Main buffer generation engine.

    Generates spatial buffers around geometries and creates corresponding
    constraint objects with proper metadata.
    """

    def __init__(self, auto_validate: bool = True, auto_repair: bool = True):
        """
        Initialize buffer generator.

        Args:
            auto_validate: Automatically validate generated geometries
            auto_repair: Automatically repair invalid geometries
        """
        self.auto_validate = auto_validate
        self.auto_repair = auto_repair
        self._buffer_cache: Dict[str, BaseGeometry] = {}

    def create_buffer(
        self,
        geometry: BaseGeometry,
        config: BufferConfig,
        inward: bool = False,
    ) -> BaseGeometry:
        """
        Create a buffer around a geometry.

        Args:
            geometry: Source geometry to buffer
            config: Buffer configuration
            inward: If True, create inward buffer (negative buffer)

        Returns:
            Buffered geometry

        Raises:
            ValueError: If buffer operation fails
        """
        try:
            # Ensure geometry is valid
            if not geometry.is_valid:
                if self.auto_repair:
                    geometry = make_valid(geometry)
                    logger.warning("Repaired invalid input geometry")
                else:
                    raise ValueError("Input geometry is invalid")

            # Calculate buffer distance (negative for inward)
            distance = -config.distance_m if inward else config.distance_m

            # Create buffer
            if config.single_sided and isinstance(geometry, LineString):
                # Single-sided buffer (left side if positive, right if negative)
                buffered = geometry.buffer(
                    distance,
                    cap_style=config.cap_style,
                    join_style=config.join_style,
                    mitre_limit=config.mitre_limit,
                    resolution=config.resolution,
                    single_sided=True,
                )
            else:
                # Standard buffer
                buffered = geometry.buffer(
                    distance,
                    cap_style=config.cap_style,
                    join_style=config.join_style,
                    mitre_limit=config.mitre_limit,
                    resolution=config.resolution,
                )

            # Simplify if requested
            if config.simplify_tolerance > 0:
                buffered = buffered.simplify(
                    config.simplify_tolerance,
                    preserve_topology=True
                )

            # Validate result
            if self.auto_validate:
                if not buffered.is_valid:
                    if self.auto_repair:
                        buffered = make_valid(buffered)
                        logger.warning("Repaired invalid buffered geometry")
                    else:
                        raise ValueError("Generated buffer is invalid")

                # Check for empty or degenerate results
                if buffered.is_empty:
                    raise ValueError("Buffer operation resulted in empty geometry")

                # Warn about unusual results
                if buffered.area == 0 and hasattr(buffered, 'area'):
                    logger.warning("Buffer has zero area")

            return buffered

        except Exception as e:
            logger.error(f"Buffer creation failed: {str(e)}")
            raise ValueError(f"Failed to create buffer: {str(e)}")

    def create_multi_buffer(
        self,
        geometries: List[BaseGeometry],
        config: BufferConfig,
        merge: bool = True,
    ) -> Union[BaseGeometry, List[BaseGeometry]]:
        """
        Create buffers for multiple geometries.

        Args:
            geometries: List of geometries to buffer
            config: Buffer configuration
            merge: If True, merge overlapping buffers into single geometry

        Returns:
            Single merged geometry or list of individual buffers
        """
        if not geometries:
            raise ValueError("No geometries provided")

        buffers = []
        for geom in geometries:
            try:
                buffered = self.create_buffer(geom, config)
                buffers.append(buffered)
            except Exception as e:
                logger.warning(f"Skipping geometry due to buffer error: {str(e)}")
                continue

        if not buffers:
            raise ValueError("No valid buffers created")

        if merge:
            # Use unary_union for efficient merging
            merged = unary_union(buffers)
            return merged

        return buffers

    def simplify_buffer(
        self,
        geometry: BaseGeometry,
        tolerance: float,
        preserve_topology: bool = True,
    ) -> BaseGeometry:
        """
        Simplify a buffer geometry to reduce vertex count.

        Args:
            geometry: Geometry to simplify
            tolerance: Simplification tolerance in meters
            preserve_topology: Whether to preserve topology

        Returns:
            Simplified geometry
        """
        simplified = geometry.simplify(tolerance, preserve_topology=preserve_topology)

        if self.auto_validate and not simplified.is_valid:
            if self.auto_repair:
                simplified = make_valid(simplified)
            else:
                logger.warning("Simplification resulted in invalid geometry")
                return geometry

        return simplified

    def create_property_setback(
        self,
        property_boundary: BaseGeometry,
        constraint_id: str,
        setback_distance: Optional[float] = None,
        setback_type: str = "default",
        **kwargs
    ) -> SetbackConstraint:
        """
        Create property line setback constraint.

        Args:
            property_boundary: Property boundary geometry
            constraint_id: Unique constraint ID
            setback_distance: Override default distance (meters)
            setback_type: Type of setback (default, front, side, rear)
            **kwargs: Additional constraint parameters

        Returns:
            Configured SetbackConstraint
        """
        distance = setback_distance or PROPERTY_LINE_SETBACK.get(
            setback_type,
            PROPERTY_LINE_SETBACK["default"]
        )

        config = BufferConfig(
            distance_m=distance,
            style=BufferStyle.ROUND,
        )

        # Create inward buffer from property boundary
        buffer_geom = self.create_buffer(property_boundary, config, inward=True)

        # Property setbacks are typically blocking constraints
        return SetbackConstraint(
            id=constraint_id,
            name=f"Property Line Setback ({setback_type})",
            description=f"{distance:.1f}m setback from property boundary",
            constraint_type=ConstraintType.PROPERTY_LINE,
            severity=kwargs.get("severity", ConstraintSeverity.BLOCKING),
            priority=kwargs.get("priority", ConstraintPriority.HIGH),
            geometry_wkt=buffer_geom.wkt,
            source_feature_wkt=property_boundary.wkt,
            setback_distance_m=distance,
            buffer_type=config.style.value,
            **{k: v for k, v in kwargs.items() if k not in ["severity", "priority"]}
        )

    def create_road_setback(
        self,
        road_geometry: BaseGeometry,
        constraint_id: str,
        road_type: RoadType = RoadType.LOCAL,
        setback_distance: Optional[float] = None,
        **kwargs
    ) -> SetbackConstraint:
        """
        Create road setback constraint.

        Args:
            road_geometry: Road centerline or polygon geometry
            constraint_id: Unique constraint ID
            road_type: Classification of road
            setback_distance: Override default distance (meters)
            **kwargs: Additional constraint parameters

        Returns:
            Configured SetbackConstraint
        """
        distance = setback_distance or ROAD_SETBACK[road_type]

        config = BufferConfig(
            distance_m=distance,
            style=BufferStyle.ROUND,
        )

        buffer_geom = self.create_buffer(road_geometry, config)

        return SetbackConstraint(
            id=constraint_id,
            name=f"{road_type.value.title()} Road Setback",
            description=f"{distance:.1f}m setback from {road_type.value} road",
            constraint_type=ConstraintType.ROAD,
            severity=kwargs.get("severity", ConstraintSeverity.BLOCKING),
            priority=kwargs.get("priority", ConstraintPriority.HIGH),
            geometry_wkt=buffer_geom.wkt,
            source_feature_wkt=road_geometry.wkt,
            setback_distance_m=distance,
            buffer_type=config.style.value,
            metadata={"road_type": road_type.value, **kwargs.get("metadata", {})},
            **{k: v for k, v in kwargs.items() if k not in ["severity", "priority", "metadata"]}
        )

    def create_water_feature_setback(
        self,
        water_geometry: BaseGeometry,
        constraint_id: str,
        feature_type: WaterFeatureType = WaterFeatureType.STREAM,
        setback_distance: Optional[float] = None,
        regulatory_info: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> RegulatoryConstraint:
        """
        Create water feature setback constraint.

        Water feature setbacks are typically regulatory constraints with
        federal/state requirements.

        Args:
            water_geometry: Water feature geometry
            constraint_id: Unique constraint ID
            feature_type: Type of water feature
            setback_distance: Override default distance (meters)
            regulatory_info: Regulatory information dict
            **kwargs: Additional constraint parameters

        Returns:
            Configured RegulatoryConstraint
        """
        distance = setback_distance or WATER_FEATURE_SETBACK[feature_type]

        config = BufferConfig(
            distance_m=distance,
            style=BufferStyle.ROUND,
        )

        buffer_geom = self.create_buffer(water_geometry, config)

        # Default regulatory information
        reg_info = regulatory_info or {}
        regulation_name = reg_info.get(
            "regulation_name",
            "Clean Water Act - Riparian Buffer Requirements"
        )
        authority = reg_info.get("authority", "Federal (EPA)")
        regulation_code = reg_info.get("regulation_code", "33 USC 1344")

        return RegulatoryConstraint(
            id=constraint_id,
            name=f"{feature_type.value.title()} Setback",
            description=f"{distance:.1f}m regulatory setback from {feature_type.value}",
            constraint_type=ConstraintType.WATER_FEATURE,
            severity=ConstraintSeverity.BLOCKING,
            priority=ConstraintPriority.CRITICAL,
            geometry_wkt=buffer_geom.wkt,
            regulation_name=regulation_name,
            authority=authority,
            regulation_code=regulation_code,
            compliance_requirement=f"Minimum {distance:.1f}m setback from water feature",
            data_source=reg_info.get("data_source", "National Hydrography Dataset"),
            metadata={
                "feature_type": feature_type.value,
                "setback_distance_m": distance,
                "source_feature_wkt": water_geometry.wkt,
                **kwargs.get("metadata", {}),
            },
            **{k: v for k, v in kwargs.items() if k not in ["metadata"]}
        )

    def create_utility_setback(
        self,
        utility_geometry: BaseGeometry,
        constraint_id: str,
        utility_type: str = "default",
        setback_distance: Optional[float] = None,
        **kwargs
    ) -> SetbackConstraint:
        """
        Create utility corridor setback constraint.

        Args:
            utility_geometry: Utility line or corridor geometry
            constraint_id: Unique constraint ID
            utility_type: Type of utility (power_line, pipeline, gas_line, etc.)
            setback_distance: Override default distance (meters)
            **kwargs: Additional constraint parameters

        Returns:
            Configured SetbackConstraint
        """
        distance = setback_distance or UTILITY_SETBACK.get(
            utility_type,
            UTILITY_SETBACK["default"]
        )

        config = BufferConfig(
            distance_m=distance,
            style=BufferStyle.ROUND,
        )

        buffer_geom = self.create_buffer(utility_geometry, config)

        # Utility setbacks are typically high priority
        return SetbackConstraint(
            id=constraint_id,
            name=f"{utility_type.replace('_', ' ').title()} Setback",
            description=f"{distance:.1f}m setback from {utility_type}",
            constraint_type=ConstraintType.UTILITY,
            severity=kwargs.get("severity", ConstraintSeverity.BLOCKING),
            priority=kwargs.get("priority", ConstraintPriority.HIGH),
            geometry_wkt=buffer_geom.wkt,
            source_feature_wkt=utility_geometry.wkt,
            setback_distance_m=distance,
            buffer_type=config.style.value,
            metadata={"utility_type": utility_type, **kwargs.get("metadata", {})},
            **{k: v for k, v in kwargs.items() if k not in ["severity", "priority", "metadata"]}
        )

    def validate_buffer(
        self,
        buffer_geometry: BaseGeometry,
        source_geometry: BaseGeometry,
        expected_distance: float,
    ) -> tuple[bool, List[str]]:
        """
        Validate a buffer geometry.

        Args:
            buffer_geometry: The generated buffer
            source_geometry: The original source geometry
            expected_distance: Expected buffer distance

        Returns:
            Tuple of (is_valid, list of warnings/errors)
        """
        issues = []

        # Check validity
        if not buffer_geometry.is_valid:
            issues.append("Buffer geometry is invalid")
            return (False, issues)

        # Check for empty geometry
        if buffer_geometry.is_empty:
            issues.append("Buffer geometry is empty")
            return (False, issues)

        # Check for self-intersections (for polygons)
        if isinstance(buffer_geometry, (Polygon, MultiPolygon)):
            if not buffer_geometry.is_simple:
                issues.append("Buffer has self-intersections")

        # Check that buffer contains or encompasses source
        if not buffer_geometry.contains(source_geometry):
            # For very small buffers, containment might fail due to precision
            if not buffer_geometry.intersects(source_geometry):
                issues.append("Buffer does not intersect source geometry")

        # Warn about unusual buffer sizes
        if hasattr(buffer_geometry, 'area') and hasattr(source_geometry, 'area'):
            source_area = source_geometry.area
            buffer_area = buffer_geometry.area

            if source_area > 0:
                ratio = buffer_area / source_area
                if ratio > 100:
                    issues.append(f"Buffer area is {ratio:.1f}x larger than source (unusually large)")
                elif ratio < 1.1 and expected_distance > 1:
                    issues.append("Buffer area is only slightly larger than source (may be too small)")

        is_valid = len([i for i in issues if "invalid" in i.lower() or "empty" in i.lower()]) == 0
        return (is_valid, issues)


def create_buffer_from_config(
    geometry: BaseGeometry,
    distance_m: float,
    style: str = "round",
    simplify_tolerance: float = 0.0,
    **kwargs
) -> BaseGeometry:
    """
    Convenience function to create a buffer from simple parameters.

    Args:
        geometry: Source geometry
        distance_m: Buffer distance in meters
        style: Buffer style (flat, round, square)
        simplify_tolerance: Simplification tolerance
        **kwargs: Additional BufferConfig parameters

    Returns:
        Buffered geometry
    """
    config = BufferConfig(
        distance_m=distance_m,
        style=BufferStyle(style),
        simplify_tolerance=simplify_tolerance,
        **kwargs
    )

    generator = BufferGenerator()
    return generator.create_buffer(geometry, config)

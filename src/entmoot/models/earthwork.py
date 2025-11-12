"""
Data models for earthwork calculations.

This module defines data models for grading, volume calculations,
and earthwork cost estimation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List
import numpy as np


class SoilType(str, Enum):
    """Soil types with different shrink/swell factors."""

    CLAY = "clay"
    SAND = "sand"
    ROCK = "rock"
    LOAM = "loam"
    MIXED = "mixed"


class GradingZoneType(str, Enum):
    """Types of grading zones."""

    BUILDING_PAD = "building_pad"
    ROAD_CORRIDOR = "road_corridor"
    TRANSITION = "transition"
    DRAINAGE_SWALE = "drainage_swale"
    NATURAL = "natural"


@dataclass
class SoilProperties:
    """
    Properties of soil types for earthwork calculations.

    Attributes:
        soil_type: Type of soil
        shrink_factor: Volume shrinkage for compaction (1.0 = no change)
        swell_factor: Volume expansion when excavated (1.0 = no change)
        density_pcf: Density in pounds per cubic foot
        angle_of_repose: Natural angle of repose in degrees
    """

    soil_type: SoilType
    shrink_factor: float
    swell_factor: float
    density_pcf: float
    angle_of_repose: float

    @classmethod
    def get_default(cls, soil_type: SoilType) -> "SoilProperties":
        """
        Get default soil properties for a given type.

        Args:
            soil_type: Type of soil

        Returns:
            SoilProperties with default values
        """
        defaults = {
            SoilType.CLAY: cls(
                soil_type=SoilType.CLAY,
                shrink_factor=1.25,  # Clay shrinks when compacted
                swell_factor=1.30,  # Clay swells when excavated
                density_pcf=110.0,
                angle_of_repose=15.0,
            ),
            SoilType.SAND: cls(
                soil_type=SoilType.SAND,
                shrink_factor=1.10,
                swell_factor=1.15,
                density_pcf=100.0,
                angle_of_repose=30.0,
            ),
            SoilType.ROCK: cls(
                soil_type=SoilType.ROCK,
                shrink_factor=1.50,
                swell_factor=1.60,
                density_pcf=165.0,
                angle_of_repose=35.0,
            ),
            SoilType.LOAM: cls(
                soil_type=SoilType.LOAM,
                shrink_factor=1.15,
                swell_factor=1.20,
                density_pcf=80.0,
                angle_of_repose=25.0,
            ),
            SoilType.MIXED: cls(
                soil_type=SoilType.MIXED,
                shrink_factor=1.20,
                swell_factor=1.25,
                density_pcf=105.0,
                angle_of_repose=25.0,
            ),
        }
        return defaults[soil_type]


@dataclass
class GradingZone:
    """
    Definition of a grading zone.

    Attributes:
        zone_type: Type of grading zone
        geometry: Shapely geometry defining the zone boundary
        target_elevation: Target elevation for flat zones (building pads)
        target_slope: Target slope for sloped zones (roads, swales)
        slope_direction: Direction of slope in degrees (0=North)
        transition_slope: Slope ratio for transition zones (e.g., 3.0 for 3:1)
        crown_height: Road crown height in feet
        cross_slope: Road cross-slope percentage
        priority: Priority for overlapping zones (higher = wins)
    """

    zone_type: GradingZoneType
    geometry: Any  # Shapely geometry
    target_elevation: Optional[float] = None
    target_slope: Optional[float] = None
    slope_direction: Optional[float] = None
    transition_slope: float = 3.0  # 3:1 default
    crown_height: float = 0.0
    cross_slope: float = 0.0
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "zone_type": self.zone_type.value,
            "target_elevation": self.target_elevation,
            "target_slope": self.target_slope,
            "slope_direction": self.slope_direction,
            "transition_slope": self.transition_slope,
            "crown_height": self.crown_height,
            "cross_slope": self.cross_slope,
            "priority": self.priority,
        }


@dataclass
class VolumeResult:
    """
    Result of volume calculation.

    Attributes:
        cut_volume_cy: Total cut volume in cubic yards
        fill_volume_cy: Total fill volume in cubic yards
        net_volume_cy: Net volume (cut - fill) in cubic yards
        balanced_volume_cy: Volume that is balanced on-site
        import_volume_cy: Volume to import (if fill > cut)
        export_volume_cy: Volume to export (if cut > fill)
        cut_area_sf: Area of cut in square feet
        fill_area_sf: Area of fill in square feet
        average_cut_depth_ft: Average depth of cut in feet
        average_fill_depth_ft: Average depth of fill in feet
    """

    cut_volume_cy: float
    fill_volume_cy: float
    net_volume_cy: float
    balanced_volume_cy: float
    import_volume_cy: float
    export_volume_cy: float
    cut_area_sf: float
    fill_area_sf: float
    average_cut_depth_ft: float
    average_fill_depth_ft: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cut_volume_cy": float(self.cut_volume_cy),
            "fill_volume_cy": float(self.fill_volume_cy),
            "net_volume_cy": float(self.net_volume_cy),
            "balanced_volume_cy": float(self.balanced_volume_cy),
            "import_volume_cy": float(self.import_volume_cy),
            "export_volume_cy": float(self.export_volume_cy),
            "cut_area_sf": float(self.cut_area_sf),
            "fill_area_sf": float(self.fill_area_sf),
            "average_cut_depth_ft": float(self.average_cut_depth_ft),
            "average_fill_depth_ft": float(self.average_fill_depth_ft),
        }


@dataclass
class CostDatabase:
    """
    Cost database for earthwork operations.

    All costs in dollars per cubic yard.

    Attributes:
        excavation_cost_cy: Cost to excavate per cubic yard
        fill_cost_cy: Cost to place fill per cubic yard
        haul_cost_cy_mile: Cost to haul per cubic yard per mile
        import_cost_cy: Cost to import material per cubic yard
        export_cost_cy: Cost to export material per cubic yard
        rock_excavation_cy: Cost for rock excavation per cubic yard
        compaction_cost_cy: Cost for compaction per cubic yard
    """

    excavation_cost_cy: float = 5.00
    fill_cost_cy: float = 8.00
    haul_cost_cy_mile: float = 2.50
    import_cost_cy: float = 25.00
    export_cost_cy: float = 15.00
    rock_excavation_cy: float = 35.00
    compaction_cost_cy: float = 3.50

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "excavation_cost_cy": self.excavation_cost_cy,
            "fill_cost_cy": self.fill_cost_cy,
            "haul_cost_cy_mile": self.haul_cost_cy_mile,
            "import_cost_cy": self.import_cost_cy,
            "export_cost_cy": self.export_cost_cy,
            "rock_excavation_cy": self.rock_excavation_cy,
            "compaction_cost_cy": self.compaction_cost_cy,
        }


@dataclass
class EarthworkCost:
    """
    Detailed cost breakdown for earthwork.

    Attributes:
        excavation_cost: Total excavation cost
        fill_cost: Total fill placement cost
        haul_cost: Total haul cost
        import_cost: Total import cost
        export_cost: Total export cost
        compaction_cost: Total compaction cost
        total_cost: Total earthwork cost
        cost_breakdown: Detailed breakdown by category
    """

    excavation_cost: float
    fill_cost: float
    haul_cost: float
    import_cost: float
    export_cost: float
    compaction_cost: float
    total_cost: float
    cost_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "excavation_cost": float(self.excavation_cost),
            "fill_cost": float(self.fill_cost),
            "haul_cost": float(self.haul_cost),
            "import_cost": float(self.import_cost),
            "export_cost": float(self.export_cost),
            "compaction_cost": float(self.compaction_cost),
            "total_cost": float(self.total_cost),
            "cost_breakdown": {k: float(v) for k, v in self.cost_breakdown.items()},
        }


@dataclass
class CrossSection:
    """
    Cross-section through terrain.

    Attributes:
        start_point: (x, y) coordinates of start
        end_point: (x, y) coordinates of end
        distance: Distance along section in feet
        pre_elevation: Pre-grading elevations
        post_elevation: Post-grading elevations
        cut_fill: Cut/fill depths (positive=cut, negative=fill)
        section_volume_cy: Volume calculated from this section
    """

    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    distance: np.ndarray
    pre_elevation: np.ndarray
    post_elevation: np.ndarray
    cut_fill: np.ndarray
    section_volume_cy: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without arrays)."""
        return {
            "start_point": self.start_point,
            "end_point": self.end_point,
            "section_volume_cy": float(self.section_volume_cy),
            "max_cut": float(np.max(self.cut_fill)),
            "max_fill": float(np.min(self.cut_fill)),
            "length_ft": float(self.distance[-1]),
        }


@dataclass
class BalancingResult:
    """
    Result of earthwork balancing optimization.

    Attributes:
        is_balanced: Whether cut and fill are balanced
        balance_ratio: Ratio of fill to cut (1.0 = perfect balance)
        optimal_haul_distance: Optimal average haul distance
        haul_zones: List of (from_zone, to_zone, volume) tuples
        recommendations: List of recommendations for balancing
    """

    is_balanced: bool
    balance_ratio: float
    optimal_haul_distance: float
    haul_zones: List[Tuple[Any, Any, float]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_balanced": self.is_balanced,
            "balance_ratio": float(self.balance_ratio),
            "optimal_haul_distance": float(self.optimal_haul_distance),
            "recommendations": self.recommendations,
        }

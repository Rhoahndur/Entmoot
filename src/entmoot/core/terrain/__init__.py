"""
Terrain analysis module for Entmoot.

This module provides terrain analysis capabilities including:
- Slope calculation using multiple algorithms
- Aspect calculation with cardinal direction mapping
- Solar exposure analysis
- Wind exposure metrics
- Terrain classification
- Buildability analysis and zone identification
"""

from entmoot.core.terrain.aspect import (
    AspectCalculator,
    CardinalDirection,
    aspect_to_cardinal,
    calculate_aspect,
)
from entmoot.core.terrain.buildability import (
    BuildabilityAnalyzer,
    BuildabilityClass,
    BuildabilityResult,
    BuildabilityThresholds,
    BuildableZone,
    analyze_buildability,
)

# Core slope and aspect calculation modules
from entmoot.core.terrain.slope import (
    SlopeCalculator,
    SlopeClassification,
    SlopeMethod,
    calculate_slope,
    classify_slope,
)

# Optional DEM modules (may have additional dependencies)
try:
    from entmoot.core.terrain.dem_loader import DEMLoader
    from entmoot.core.terrain.dem_processor import DEMProcessor
    from entmoot.core.terrain.dem_validator import DEMValidator

    DEM_MODULES_AVAILABLE = True
except ImportError:
    DEM_MODULES_AVAILABLE = False

__all__ = [
    "SlopeCalculator",
    "SlopeMethod",
    "SlopeClassification",
    "calculate_slope",
    "classify_slope",
    "AspectCalculator",
    "CardinalDirection",
    "calculate_aspect",
    "aspect_to_cardinal",
    "BuildabilityAnalyzer",
    "BuildabilityThresholds",
    "BuildabilityClass",
    "BuildableZone",
    "BuildabilityResult",
    "analyze_buildability",
]

if DEM_MODULES_AVAILABLE:
    __all__.extend(
        [
            "DEMLoader",
            "DEMValidator",
            "DEMProcessor",
        ]
    )

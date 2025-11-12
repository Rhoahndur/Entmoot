"""
Constraint management core functionality.
"""

from .collection import ConstraintCollection, ConstraintStatistics
from .validator import ConstraintValidator
from .aggregator import ConstraintAggregator
from .buffers import (
    BufferGenerator,
    BufferConfig,
    BufferStyle,
    RoadType,
    WaterFeatureType,
    PROPERTY_LINE_SETBACK,
    ROAD_SETBACK,
    WATER_FEATURE_SETBACK,
    UTILITY_SETBACK,
    create_buffer_from_config,
)

__all__ = [
    "ConstraintCollection",
    "ConstraintStatistics",
    "ConstraintValidator",
    "ConstraintAggregator",
    "BufferGenerator",
    "BufferConfig",
    "BufferStyle",
    "RoadType",
    "WaterFeatureType",
    "PROPERTY_LINE_SETBACK",
    "ROAD_SETBACK",
    "WATER_FEATURE_SETBACK",
    "UTILITY_SETBACK",
    "create_buffer_from_config",
]

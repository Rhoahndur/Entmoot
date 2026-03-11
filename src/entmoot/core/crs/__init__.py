"""
Coordinate Reference System (CRS) management module.

This module provides comprehensive CRS handling including:
- CRS detection from various file formats
- Coordinate transformation between CRS
- UTM zone detection and utilities
"""

from entmoot.core.crs.detector import (
    CRSDetectionError,
    crs_to_info,
    detect_crs_from_file,
    detect_crs_from_geojson,
    detect_crs_from_geotiff,
    detect_crs_from_kml,
    detect_crs_from_ogr,
    detect_crs_from_prj,
    parse_crs_string,
)
from entmoot.core.crs.transformer import (
    CRSTransformer,
    TransformationError,
    transform_coordinates,
    transform_to_web_mercator,
    transform_utm_to_wgs84,
    transform_wgs84_to_utm,
    validate_transformation_accuracy,
)
from entmoot.core.crs.utm import (
    calculate_scale_factor,
    calculate_utm_central_meridian,
    detect_utm_zone,
    format_utm_zone,
    get_utm_crs_info,
    get_utm_epsg,
    get_utm_letter_designator,
    get_utm_zone_bounds,
    is_in_utm_zone,
)

__all__ = [
    # Detector
    "CRSDetectionError",
    "detect_crs_from_file",
    "detect_crs_from_geojson",
    "detect_crs_from_geotiff",
    "detect_crs_from_kml",
    "detect_crs_from_ogr",
    "detect_crs_from_prj",
    "parse_crs_string",
    "crs_to_info",
    # Transformer
    "CRSTransformer",
    "TransformationError",
    "transform_coordinates",
    "transform_to_web_mercator",
    "transform_utm_to_wgs84",
    "transform_wgs84_to_utm",
    "validate_transformation_accuracy",
    # UTM utilities
    "calculate_scale_factor",
    "calculate_utm_central_meridian",
    "detect_utm_zone",
    "format_utm_zone",
    "get_utm_crs_info",
    "get_utm_epsg",
    "get_utm_letter_designator",
    "get_utm_zone_bounds",
    "is_in_utm_zone",
]

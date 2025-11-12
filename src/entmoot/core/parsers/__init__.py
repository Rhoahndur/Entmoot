"""
KMZ/KML parsing module for Entmoot.

This module provides comprehensive parsing and validation of KML and KMZ files,
which are the primary input format for property boundaries and geographic data.
"""

from .geometry import (
    GeometryType,
    ParsedGeometry,
    parse_kml_coordinates,
    kml_to_shapely,
)
from .kml_parser import KMLParser, ParsedKML, Placemark, parse_kml_file, parse_kml_string
from .kml_validator import KMLValidator, KMLValidationResult, validate_kml_file, validate_kml_string
from .kmz_parser import KMZParser, parse_kmz_file
from .kmz_validator import KMZValidator, KMZValidationResult, validate_kmz_file

__all__ = [
    # Geometry
    "GeometryType",
    "ParsedGeometry",
    "parse_kml_coordinates",
    "kml_to_shapely",
    # KML
    "KMLParser",
    "ParsedKML",
    "Placemark",
    "KMLValidator",
    "KMLValidationResult",
    "parse_kml_file",
    "parse_kml_string",
    "validate_kml_file",
    "validate_kml_string",
    # KMZ
    "KMZParser",
    "KMZValidator",
    "KMZValidationResult",
    "parse_kmz_file",
    "validate_kmz_file",
]

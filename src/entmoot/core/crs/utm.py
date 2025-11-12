"""
UTM zone detection and utilities.

This module provides functionality to automatically detect the appropriate
UTM (Universal Transverse Mercator) zone for given WGS84 coordinates.
"""

import math
from typing import Tuple

from entmoot.models.crs import CRSInfo, CoordinateOrder, DistanceUnit


def detect_utm_zone(longitude: float, latitude: float) -> Tuple[int, bool]:
    """
    Detect the appropriate UTM zone for given WGS84 coordinates.

    UTM zones are numbered from 1 to 60, each covering 6 degrees of longitude.
    Zone 1 starts at 180°W. The hemisphere (north/south) is determined by latitude.

    Special cases:
    - Norway: Uses zone 32V instead of 31V for some areas
    - Svalbard: Uses zones 31X and 33X instead of 32X for some areas

    Args:
        longitude: Longitude in decimal degrees (-180 to 180)
        latitude: Latitude in decimal degrees (-90 to 90)

    Returns:
        Tuple of (zone_number, is_northern_hemisphere)

    Raises:
        ValueError: If coordinates are out of valid range
    """
    if not -180 <= longitude <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    if not -90 <= latitude <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")

    # Determine hemisphere
    is_northern = latitude >= 0

    # Calculate base zone number
    # Zone 1 starts at -180°, each zone is 6° wide
    zone_number = int((longitude + 180) / 6) + 1

    # Handle edge case at 180° longitude
    if zone_number > 60:
        zone_number = 1

    # Handle special cases in Norway
    if latitude >= 56.0 and latitude < 64.0 and longitude >= 3.0 and longitude < 12.0:
        zone_number = 32

    # Handle special cases in Svalbard
    if latitude >= 72.0 and latitude < 84.0:
        if longitude >= 0.0 and longitude < 9.0:
            zone_number = 31
        elif longitude >= 9.0 and longitude < 21.0:
            zone_number = 33
        elif longitude >= 21.0 and longitude < 33.0:
            zone_number = 35
        elif longitude >= 33.0 and longitude < 42.0:
            zone_number = 37

    return zone_number, is_northern


def get_utm_epsg(zone_number: int, is_northern: bool) -> int:
    """
    Get EPSG code for UTM zone.

    Args:
        zone_number: UTM zone number (1-60)
        is_northern: True for northern hemisphere, False for southern

    Returns:
        EPSG code

    Raises:
        ValueError: If zone_number is out of valid range
    """
    if not 1 <= zone_number <= 60:
        raise ValueError(f"UTM zone must be between 1 and 60, got {zone_number}")

    if is_northern:
        # Northern hemisphere: EPSG 32601 to 32660
        return 32600 + zone_number
    else:
        # Southern hemisphere: EPSG 32701 to 32760
        return 32700 + zone_number


def get_utm_crs_info(longitude: float, latitude: float) -> CRSInfo:
    """
    Get complete CRS information for the appropriate UTM zone.

    Args:
        longitude: Longitude in decimal degrees (-180 to 180)
        latitude: Latitude in decimal degrees (-90 to 90)

    Returns:
        CRSInfo object for the detected UTM zone

    Raises:
        ValueError: If coordinates are out of valid range
    """
    zone_number, is_northern = detect_utm_zone(longitude, latitude)
    epsg = get_utm_epsg(zone_number, is_northern)
    hemisphere = "N" if is_northern else "S"

    return CRSInfo(
        epsg=epsg,
        name=f"WGS 84 / UTM zone {zone_number}{hemisphere}",
        units=DistanceUnit.METERS,
        is_geographic=False,
        coordinate_order=CoordinateOrder.XY,
        authority="EPSG",
        code=str(epsg),
    )


def get_utm_zone_bounds(zone_number: int) -> Tuple[float, float]:
    """
    Get the longitude bounds for a UTM zone.

    Args:
        zone_number: UTM zone number (1-60)

    Returns:
        Tuple of (min_longitude, max_longitude)

    Raises:
        ValueError: If zone_number is out of valid range
    """
    if not 1 <= zone_number <= 60:
        raise ValueError(f"UTM zone must be between 1 and 60, got {zone_number}")

    # Zone 1 starts at -180°, each zone is 6° wide
    min_lon = -180 + (zone_number - 1) * 6
    max_lon = min_lon + 6

    return (min_lon, max_lon)


def calculate_utm_central_meridian(zone_number: int) -> float:
    """
    Calculate the central meridian for a UTM zone.

    Args:
        zone_number: UTM zone number (1-60)

    Returns:
        Central meridian in decimal degrees

    Raises:
        ValueError: If zone_number is out of valid range
    """
    if not 1 <= zone_number <= 60:
        raise ValueError(f"UTM zone must be between 1 and 60, got {zone_number}")

    # Central meridian is in the middle of the zone
    # Zone 1 starts at -180°, each zone is 6° wide
    return -180 + (zone_number - 1) * 6 + 3


def is_in_utm_zone(longitude: float, latitude: float, zone_number: int) -> bool:
    """
    Check if coordinates fall within a specific UTM zone.

    Note: This checks the standard zone bounds and does not account
    for special cases in Norway and Svalbard.

    Args:
        longitude: Longitude in decimal degrees
        latitude: Latitude in decimal degrees
        zone_number: UTM zone number to check

    Returns:
        True if coordinates are in the specified zone
    """
    try:
        detected_zone, _ = detect_utm_zone(longitude, latitude)
        return detected_zone == zone_number
    except ValueError:
        return False


def calculate_scale_factor(
    longitude: float, latitude: float, zone_number: int
) -> float:
    """
    Calculate the scale factor at a point in a UTM zone.

    The scale factor varies from 0.9996 at the central meridian to
    approximately 1.0004 at the zone edges.

    Args:
        longitude: Longitude in decimal degrees
        latitude: Latitude in decimal degrees
        zone_number: UTM zone number

    Returns:
        Scale factor (dimensionless)
    """
    central_meridian = calculate_utm_central_meridian(zone_number)

    # Convert to radians
    lat_rad = math.radians(latitude)
    lon_rad = math.radians(longitude)
    cm_rad = math.radians(central_meridian)

    # Distance from central meridian
    delta_lon = lon_rad - cm_rad

    # UTM scale factor at central meridian
    k0 = 0.9996

    # Simplified scale factor calculation
    # Full calculation would involve more complex geodetic formulas
    scale = k0 * (1 + (delta_lon ** 2) * (math.cos(lat_rad) ** 2) / 2)

    return scale


def get_utm_letter_designator(latitude: float) -> str:
    """
    Get the UTM latitude band letter designator.

    UTM divides the world into latitude bands of 8 degrees each (except X which is 12 degrees).
    Bands are lettered C to X (omitting I and O).

    Args:
        latitude: Latitude in decimal degrees (-80 to 84)

    Returns:
        Letter designator (C-X)

    Raises:
        ValueError: If latitude is out of UTM range
    """
    if latitude < -80 or latitude > 84:
        raise ValueError(f"UTM is only defined between 80°S and 84°N, got {latitude}")

    # Letter bands from south to north
    bands = "CDEFGHJKLMNPQRSTUVWXX"

    # Special handling for X band (72°N to 84°N)
    if latitude >= 72:
        return "X"

    # Each band is 8 degrees, starting at -80
    index = int((latitude + 80) / 8)
    return bands[index]


def format_utm_zone(zone_number: int, is_northern: bool, include_band: bool = False,
                    latitude: float = 0.0) -> str:
    """
    Format UTM zone as a string.

    Args:
        zone_number: UTM zone number (1-60)
        is_northern: True for northern hemisphere
        include_band: Whether to include latitude band letter
        latitude: Latitude for band calculation (required if include_band=True)

    Returns:
        Formatted UTM zone string (e.g., "32N" or "32T")
    """
    if include_band:
        letter = get_utm_letter_designator(latitude)
        return f"{zone_number}{letter}"
    else:
        hemisphere = "N" if is_northern else "S"
        return f"{zone_number}{hemisphere}"

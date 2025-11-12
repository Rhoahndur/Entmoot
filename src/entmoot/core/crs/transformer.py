"""
Coordinate transformation service.

This module provides functionality for transforming coordinates between
different coordinate reference systems using pyproj.
"""

from typing import List, Optional, Tuple, Union

import numpy as np
from pyproj import CRS, Transformer

from entmoot.models.crs import (
    BoundingBox,
    CRSInfo,
    CoordinateOrder,
    CoordinateTransformation,
)


class TransformationError(Exception):
    """Raised when coordinate transformation fails."""
    pass


class CRSTransformer:
    """
    Service for transforming coordinates between CRS.

    This class provides methods for transforming individual points,
    batches of coordinates, and bounding boxes between different
    coordinate reference systems.
    """

    def __init__(self, source_crs: CRSInfo, target_crs: CRSInfo, always_xy: bool = True):
        """
        Initialize transformer.

        Args:
            source_crs: Source coordinate reference system
            target_crs: Target coordinate reference system
            always_xy: If True, enforce x,y (lon,lat) order regardless of CRS convention

        Raises:
            TransformationError: If transformer cannot be created
        """
        self.source_crs = source_crs
        self.target_crs = target_crs
        self.always_xy = always_xy

        try:
            # Create pyproj CRS objects
            if source_crs.epsg:
                src_crs = CRS.from_epsg(source_crs.epsg)
            elif source_crs.wkt:
                src_crs = CRS.from_wkt(source_crs.wkt)
            elif source_crs.proj4:
                src_crs = CRS.from_proj4(source_crs.proj4)
            else:
                raise TransformationError("Source CRS must have EPSG, WKT, or PROJ4")

            if target_crs.epsg:
                tgt_crs = CRS.from_epsg(target_crs.epsg)
            elif target_crs.wkt:
                tgt_crs = CRS.from_wkt(target_crs.wkt)
            elif target_crs.proj4:
                tgt_crs = CRS.from_proj4(target_crs.proj4)
            else:
                raise TransformationError("Target CRS must have EPSG, WKT, or PROJ4")

            # Create transformer
            self.transformer = Transformer.from_crs(
                src_crs,
                tgt_crs,
                always_xy=always_xy,
            )

        except Exception as e:
            raise TransformationError(f"Failed to create transformer: {e}")

    def transform(self, x: float, y: float, z: Optional[float] = None) -> Tuple[float, ...]:
        """
        Transform a single coordinate.

        Args:
            x: X coordinate (or longitude)
            y: Y coordinate (or latitude)
            z: Z coordinate (elevation/height), optional

        Returns:
            Transformed coordinates as tuple (x, y) or (x, y, z)

        Raises:
            TransformationError: If transformation fails
        """
        try:
            if z is not None:
                xx, yy, zz = self.transformer.transform(x, y, z)
                return (xx, yy, zz)
            else:
                xx, yy = self.transformer.transform(x, y)
                return (xx, yy)
        except Exception as e:
            raise TransformationError(f"Transformation failed: {e}")

    def transform_batch(
        self,
        x_coords: Union[List[float], np.ndarray],
        y_coords: Union[List[float], np.ndarray],
        z_coords: Optional[Union[List[float], np.ndarray]] = None,
    ) -> Tuple[np.ndarray, ...]:
        """
        Transform a batch of coordinates efficiently.

        Args:
            x_coords: Array of X coordinates (or longitudes)
            y_coords: Array of Y coordinates (or latitudes)
            z_coords: Array of Z coordinates (elevations), optional

        Returns:
            Tuple of transformed coordinate arrays (xx, yy) or (xx, yy, zz)

        Raises:
            TransformationError: If transformation fails
        """
        try:
            # Convert to numpy arrays
            x_arr = np.asarray(x_coords)
            y_arr = np.asarray(y_coords)

            if len(x_arr) != len(y_arr):
                raise TransformationError("x_coords and y_coords must have same length")

            if z_coords is not None:
                z_arr = np.asarray(z_coords)
                if len(z_arr) != len(x_arr):
                    raise TransformationError("z_coords must have same length as x_coords")
                xx, yy, zz = self.transformer.transform(x_arr, y_arr, z_arr)
                return (xx, yy, zz)
            else:
                xx, yy = self.transformer.transform(x_arr, y_arr)
                return (xx, yy)

        except TransformationError:
            raise
        except Exception as e:
            raise TransformationError(f"Batch transformation failed: {e}")

    def transform_bounds(self, bbox: BoundingBox) -> BoundingBox:
        """
        Transform a bounding box to target CRS.

        Note: This transforms the corners and creates a new axis-aligned
        bounding box, which may be larger than the actual transformed bounds.

        Args:
            bbox: Bounding box in source CRS

        Returns:
            Transformed bounding box in target CRS

        Raises:
            TransformationError: If transformation fails
        """
        try:
            # Transform all four corners
            corners_x = [bbox.min_x, bbox.max_x, bbox.min_x, bbox.max_x]
            corners_y = [bbox.min_y, bbox.min_y, bbox.max_y, bbox.max_y]

            transformed_x, transformed_y = self.transform_batch(corners_x, corners_y)

            # Create new axis-aligned bounding box
            return BoundingBox(
                min_x=float(np.min(transformed_x)),
                min_y=float(np.min(transformed_y)),
                max_x=float(np.max(transformed_x)),
                max_y=float(np.max(transformed_y)),
                crs=self.target_crs,
            )

        except Exception as e:
            raise TransformationError(f"Bounding box transformation failed: {e}")

    def inverse_transform(self, x: float, y: float, z: Optional[float] = None) -> Tuple[float, ...]:
        """
        Transform coordinates from target CRS back to source CRS.

        Args:
            x: X coordinate in target CRS
            y: Y coordinate in target CRS
            z: Z coordinate, optional

        Returns:
            Coordinates in source CRS

        Raises:
            TransformationError: If transformation fails
        """
        # Create inverse transformer
        inverse = CRSTransformer(self.target_crs, self.source_crs, self.always_xy)
        return inverse.transform(x, y, z)

    def get_transformation_info(self) -> CoordinateTransformation:
        """
        Get information about this transformation.

        Returns:
            CoordinateTransformation object with metadata
        """
        return CoordinateTransformation(
            source_crs=self.source_crs,
            target_crs=self.target_crs,
            always_xy=self.always_xy,
        )


def transform_coordinates(
    x: float,
    y: float,
    source_crs: CRSInfo,
    target_crs: CRSInfo,
    z: Optional[float] = None,
) -> Tuple[float, ...]:
    """
    Transform a single coordinate between CRS (convenience function).

    Args:
        x: X coordinate (or longitude)
        y: Y coordinate (or latitude)
        source_crs: Source CRS
        target_crs: Target CRS
        z: Z coordinate, optional

    Returns:
        Transformed coordinates

    Raises:
        TransformationError: If transformation fails
    """
    transformer = CRSTransformer(source_crs, target_crs)
    return transformer.transform(x, y, z)


def transform_wgs84_to_utm(
    longitude: float,
    latitude: float,
    utm_zone: Optional[int] = None,
) -> Tuple[float, float, CRSInfo]:
    """
    Transform WGS84 coordinates to appropriate UTM zone.

    If UTM zone is not specified, it will be auto-detected.

    Args:
        longitude: Longitude in decimal degrees
        latitude: Latitude in decimal degrees
        utm_zone: UTM zone number (1-60), or None to auto-detect

    Returns:
        Tuple of (easting, northing, utm_crs_info)

    Raises:
        TransformationError: If transformation fails
    """
    from entmoot.core.crs.utm import get_utm_crs_info, get_utm_epsg, detect_utm_zone

    # Create WGS84 CRS info
    wgs84 = CRSInfo.from_epsg(4326)

    # Detect or use specified UTM zone
    if utm_zone is None:
        utm_crs = get_utm_crs_info(longitude, latitude)
    else:
        is_northern = latitude >= 0
        epsg = get_utm_epsg(utm_zone, is_northern)
        utm_crs = CRSInfo.from_epsg(epsg)

    # Transform
    transformer = CRSTransformer(wgs84, utm_crs)
    easting, northing = transformer.transform(longitude, latitude)

    return easting, northing, utm_crs


def transform_utm_to_wgs84(
    easting: float,
    northing: float,
    utm_zone: int,
    is_northern: bool = True,
) -> Tuple[float, float]:
    """
    Transform UTM coordinates to WGS84.

    Args:
        easting: Easting in meters
        northing: Northing in meters
        utm_zone: UTM zone number (1-60)
        is_northern: True for northern hemisphere

    Returns:
        Tuple of (longitude, latitude) in decimal degrees

    Raises:
        TransformationError: If transformation fails
    """
    from entmoot.core.crs.utm import get_utm_epsg

    # Create CRS info
    wgs84 = CRSInfo.from_epsg(4326)
    utm_epsg = get_utm_epsg(utm_zone, is_northern)
    utm_crs = CRSInfo.from_epsg(utm_epsg)

    # Transform
    transformer = CRSTransformer(utm_crs, wgs84)
    longitude, latitude = transformer.transform(easting, northing)

    return longitude, latitude


def transform_to_web_mercator(
    longitude: float,
    latitude: float,
    source_epsg: int = 4326,
) -> Tuple[float, float]:
    """
    Transform coordinates to Web Mercator (EPSG:3857).

    Args:
        longitude: Longitude (or X coordinate)
        latitude: Latitude (or Y coordinate)
        source_epsg: Source EPSG code (default: 4326 for WGS84)

    Returns:
        Tuple of (x, y) in Web Mercator

    Raises:
        TransformationError: If transformation fails
    """
    source_crs = CRSInfo.from_epsg(source_epsg)
    target_crs = CRSInfo.from_epsg(3857)

    transformer = CRSTransformer(source_crs, target_crs)
    return transformer.transform(longitude, latitude)


def validate_transformation_accuracy(
    x: float,
    y: float,
    source_crs: CRSInfo,
    target_crs: CRSInfo,
    max_error_meters: float = 0.01,
) -> bool:
    """
    Validate transformation accuracy by doing round-trip conversion.

    Args:
        x: X coordinate
        y: Y coordinate
        source_crs: Source CRS
        target_crs: Target CRS
        max_error_meters: Maximum acceptable error in meters

    Returns:
        True if round-trip error is within tolerance

    Raises:
        TransformationError: If transformation fails
    """
    try:
        # Forward transformation
        forward = CRSTransformer(source_crs, target_crs)
        x_target, y_target = forward.transform(x, y)

        # Reverse transformation
        backward = CRSTransformer(target_crs, source_crs)
        x_back, y_back = backward.transform(x_target, y_target)

        # Calculate error
        if source_crs.is_geographic:
            # Convert degree error to meters (approximate at equator)
            error_x = abs(x - x_back) * 111319.9  # meters per degree
            error_y = abs(y - y_back) * 111319.9
        else:
            error_x = abs(x - x_back)
            error_y = abs(y - y_back)

        total_error = (error_x ** 2 + error_y ** 2) ** 0.5

        return total_error <= max_error_meters

    except Exception as e:
        raise TransformationError(f"Validation failed: {e}")

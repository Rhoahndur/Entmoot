"""
DEM validator for checking quality and validity of Digital Elevation Models.

Performs comprehensive validation checks including no-data values,
resolution consistency, bounds validation, and CRS checks.
"""

import logging
from typing import Optional, List, Tuple
import numpy as np

from entmoot.models.terrain import (
    DEMData,
    DEMMetadata,
    DEMValidationResult,
)

logger = logging.getLogger(__name__)


class DEMValidator:
    """
    Validate Digital Elevation Models for quality and consistency.

    Performs checks for:
    - No-data/null values
    - Resolution consistency
    - Bounds validation
    - CRS information
    - Elevation value reasonableness
    - Data quality issues
    """

    # Reasonable elevation ranges (meters)
    MIN_ELEVATION_METERS = -500.0  # Dead Sea is ~-430m
    MAX_ELEVATION_METERS = 9000.0  # Mt. Everest is ~8849m

    # Quality thresholds
    MAX_NO_DATA_PERCENTAGE = 50.0  # Warn if >50% no-data
    MAX_SPIKE_THRESHOLD = 500.0  # Suspicious elevation change (meters)

    def __init__(
        self,
        min_elevation: Optional[float] = None,
        max_elevation: Optional[float] = None,
        max_no_data_pct: float = MAX_NO_DATA_PERCENTAGE,
    ) -> None:
        """
        Initialize DEM validator.

        Args:
            min_elevation: Minimum reasonable elevation (meters)
            max_elevation: Maximum reasonable elevation (meters)
            max_no_data_pct: Maximum acceptable no-data percentage
        """
        self.min_elevation = min_elevation or self.MIN_ELEVATION_METERS
        self.max_elevation = max_elevation or self.MAX_ELEVATION_METERS
        self.max_no_data_pct = max_no_data_pct

    def validate(self, dem_data: DEMData) -> DEMValidationResult:
        """
        Perform comprehensive validation of DEM data.

        Args:
            dem_data: DEM data to validate

        Returns:
            DEMValidationResult with validation status and issues
        """
        result = DEMValidationResult(is_valid=True, metadata=dem_data.metadata)

        logger.info("Starting DEM validation")

        # Run validation checks
        self._validate_metadata(dem_data.metadata, result)
        self._validate_elevation_data(dem_data, result)
        self._validate_resolution(dem_data.metadata, result)
        self._validate_bounds(dem_data.metadata, result)
        self._validate_crs(dem_data.metadata, result)
        self._check_no_data_percentage(dem_data, result)
        self._check_elevation_range(dem_data, result)
        self._check_for_spikes(dem_data, result)

        if result.is_valid:
            logger.info("DEM validation passed")
        else:
            logger.warning(f"DEM validation failed with {len(result.issues)} issues")

        return result

    def _validate_metadata(
        self, metadata: DEMMetadata, result: DEMValidationResult
    ) -> None:
        """
        Validate DEM metadata.

        Args:
            metadata: DEM metadata
            result: Validation result to update
        """
        # Check dimensions
        if metadata.width <= 0:
            result.add_issue(f"Invalid width: {metadata.width}")
        if metadata.height <= 0:
            result.add_issue(f"Invalid height: {metadata.height}")

        # Check resolution
        if metadata.resolution[0] <= 0:
            result.add_issue(f"Invalid x resolution: {metadata.resolution[0]}")
        if metadata.resolution[1] <= 0:
            result.add_issue(f"Invalid y resolution: {metadata.resolution[1]}")

        # Warn about very small DEMs
        if metadata.width < 10 or metadata.height < 10:
            result.add_warning(
                f"Very small DEM: {metadata.width}x{metadata.height} pixels"
            )

    def _validate_elevation_data(
        self, dem_data: DEMData, result: DEMValidationResult
    ) -> None:
        """
        Validate elevation data array.

        Args:
            dem_data: DEM data
            result: Validation result to update
        """
        elevation = dem_data.elevation

        # Check shape
        expected_shape = (dem_data.metadata.height, dem_data.metadata.width)
        if elevation.shape != expected_shape:
            result.add_issue(
                f"Elevation shape {elevation.shape} does not match "
                f"metadata dimensions {expected_shape}"
            )
            return

        # Check for all NaN/no-data
        valid_mask = ~np.isnan(elevation)
        if not np.any(valid_mask):
            result.add_issue("All elevation values are no-data/NaN")
            return

        # Check data type
        if not np.issubdtype(elevation.dtype, np.floating):
            result.add_warning(
                f"Elevation data type {elevation.dtype} is not floating-point"
            )

    def _validate_resolution(
        self, metadata: DEMMetadata, result: DEMValidationResult
    ) -> None:
        """
        Validate resolution consistency.

        Args:
            metadata: DEM metadata
            result: Validation result to update
        """
        x_res, y_res = metadata.resolution

        # Check for consistent resolution (square pixels)
        if abs(x_res - y_res) > 0.01:
            result.add_warning(
                f"Non-square pixels: x={x_res:.3f}, y={y_res:.3f}. "
                "Some algorithms assume square pixels."
            )

        # Check for very low resolution
        if x_res > 100 or y_res > 100:
            result.add_warning(
                f"Very low resolution: {x_res:.1f}x{y_res:.1f}. "
                "May not be suitable for detailed analysis."
            )

        # Check for very high resolution
        if x_res < 0.1 or y_res < 0.1:
            result.add_warning(
                f"Very high resolution: {x_res:.3f}x{y_res:.3f}. "
                "May require significant processing resources."
            )

    def _validate_bounds(
        self, metadata: DEMMetadata, result: DEMValidationResult
    ) -> None:
        """
        Validate bounds are reasonable.

        Args:
            metadata: DEM metadata
            result: Validation result to update
        """
        min_x, min_y, max_x, max_y = metadata.bounds

        # Check bounds order
        if min_x >= max_x:
            result.add_issue(f"Invalid bounds: min_x ({min_x}) >= max_x ({max_x})")
        if min_y >= max_y:
            result.add_issue(f"Invalid bounds: min_y ({min_y}) >= max_y ({max_y})")

        # Check for suspiciously large bounds (likely coordinate system issue)
        width = max_x - min_x
        height = max_y - min_y

        # If bounds are in degrees (lat/lon)
        if -180 <= min_x <= 180 and -90 <= min_y <= 90:
            if width > 10 or height > 10:
                result.add_warning(
                    "Very large extent in geographic coordinates. "
                    "Consider reprojecting to a projected CRS."
                )
        else:
            # Projected coordinates - check for huge extents
            if width > 1_000_000 or height > 1_000_000:
                result.add_warning(
                    f"Very large extent: {width:.0f}x{height:.0f}. "
                    "Verify CRS is correct."
                )

    def _validate_crs(
        self, metadata: DEMMetadata, result: DEMValidationResult
    ) -> None:
        """
        Validate CRS information.

        Args:
            metadata: DEM metadata
            result: Validation result to update
        """
        if metadata.crs is None:
            result.add_warning(
                "No CRS information available. "
                "Spatial operations may not work correctly."
            )
            return

        # Check if CRS is geographic (lat/lon)
        if metadata.crs.is_geographic:
            result.add_warning(
                "DEM uses geographic CRS (lat/lon). "
                "Consider reprojecting to projected CRS for accurate distance calculations."
            )

    def _check_no_data_percentage(
        self, dem_data: DEMData, result: DEMValidationResult
    ) -> None:
        """
        Check percentage of no-data values.

        Args:
            dem_data: DEM data
            result: Validation result to update
        """
        metrics = dem_data.get_metrics()

        if metrics.no_data_percentage > self.max_no_data_pct:
            result.add_warning(
                f"High percentage of no-data values: {metrics.no_data_percentage:.1f}% "
                f"(threshold: {self.max_no_data_pct:.1f}%)"
            )

        # Warn about clustered no-data
        if metrics.no_data_percentage > 10:
            result.add_warning(
                "Significant no-data regions detected. "
                "Consider interpolation or using a different DEM source."
            )

    def _check_elevation_range(
        self, dem_data: DEMData, result: DEMValidationResult
    ) -> None:
        """
        Check if elevation values are reasonable.

        Args:
            dem_data: DEM data
            result: Validation result to update
        """
        metrics = dem_data.get_metrics()

        # Skip if all no-data
        if metrics.valid_pixel_count == 0:
            return

        # Check minimum elevation
        if metrics.min_elevation < self.min_elevation:
            result.add_warning(
                f"Elevation below reasonable minimum: {metrics.min_elevation:.1f}m "
                f"(threshold: {self.min_elevation:.1f}m). "
                "Verify elevation unit and data quality."
            )

        # Check maximum elevation
        if metrics.max_elevation > self.max_elevation:
            result.add_warning(
                f"Elevation above reasonable maximum: {metrics.max_elevation:.1f}m "
                f"(threshold: {self.max_elevation:.1f}m). "
                "Verify elevation unit and data quality."
            )

        # Check for suspiciously flat terrain
        if metrics.elevation_range < 1.0:
            result.add_warning(
                f"Very flat terrain: elevation range = {metrics.elevation_range:.2f}m. "
                "Verify DEM quality."
            )

    def _check_for_spikes(
        self, dem_data: DEMData, result: DEMValidationResult
    ) -> None:
        """
        Check for elevation spikes (outliers).

        Args:
            dem_data: DEM data
            result: Validation result to update
        """
        elevation = dem_data.elevation
        metrics = dem_data.get_metrics()

        # Skip if all no-data
        if metrics.valid_pixel_count == 0:
            return

        # Calculate elevation differences with neighbors
        # Use central differences where possible
        valid_mask = ~np.isnan(elevation)

        # Compute gradients
        dy, dx = np.gradient(elevation)

        # Mask invalid gradients
        dy[~valid_mask] = np.nan
        dx[~valid_mask] = np.nan

        # Find maximum gradient magnitude
        gradient_mag = np.sqrt(dx**2 + dy**2)
        max_gradient = np.nanmax(gradient_mag)

        # Adjust threshold based on resolution
        resolution = dem_data.metadata.resolution[0]
        spike_threshold = self.MAX_SPIKE_THRESHOLD * resolution

        if max_gradient > spike_threshold:
            result.add_warning(
                f"Suspicious elevation spikes detected (max gradient: {max_gradient:.1f}m). "
                "DEM may contain errors or artifacts."
            )

        # Check for outliers using statistical method
        valid_elevations = elevation[valid_mask]
        mean = metrics.mean_elevation
        std = metrics.std_elevation

        # Count values outside 3 standard deviations
        outlier_mask = np.abs(valid_elevations - mean) > (3 * std)
        outlier_count = np.sum(outlier_mask)
        outlier_pct = (outlier_count / metrics.valid_pixel_count) * 100

        if outlier_pct > 1.0:  # More than 1% outliers
            result.add_warning(
                f"High percentage of outlier values: {outlier_pct:.1f}%. "
                "Consider smoothing or filtering the DEM."
            )

    def validate_metadata_only(self, metadata: DEMMetadata) -> DEMValidationResult:
        """
        Validate only metadata without elevation data.

        Useful for quick validation before loading large files.

        Args:
            metadata: DEM metadata to validate

        Returns:
            DEMValidationResult
        """
        result = DEMValidationResult(is_valid=True, metadata=metadata)

        self._validate_metadata(metadata, result)
        self._validate_resolution(metadata, result)
        self._validate_bounds(metadata, result)
        self._validate_crs(metadata, result)

        return result

    def check_compatibility(
        self, dem1_metadata: DEMMetadata, dem2_metadata: DEMMetadata
    ) -> DEMValidationResult:
        """
        Check if two DEMs are compatible for operations like differencing.

        Args:
            dem1_metadata: First DEM metadata
            dem2_metadata: Second DEM metadata

        Returns:
            DEMValidationResult indicating compatibility
        """
        result = DEMValidationResult(is_valid=True)

        # Check CRS compatibility
        if dem1_metadata.crs and dem2_metadata.crs:
            if not dem1_metadata.crs.equals(dem2_metadata.crs):
                result.add_issue(
                    f"CRS mismatch: {dem1_metadata.crs.name} vs {dem2_metadata.crs.name}"
                )
        else:
            result.add_warning("Cannot verify CRS compatibility (missing CRS)")

        # Check resolution compatibility
        res1 = dem1_metadata.resolution
        res2 = dem2_metadata.resolution
        res_diff_x = abs(res1[0] - res2[0])
        res_diff_y = abs(res1[1] - res2[1])

        if res_diff_x > 0.01 or res_diff_y > 0.01:
            result.add_warning(
                f"Resolution mismatch: {res1} vs {res2}. "
                "Resampling may be required."
            )

        # Check bounds overlap
        bounds1 = dem1_metadata.bounds
        bounds2 = dem2_metadata.bounds

        if not self._bounds_overlap(bounds1, bounds2):
            result.add_warning("DEMs do not overlap spatially")

        # Check elevation units
        if dem1_metadata.elevation_unit != dem2_metadata.elevation_unit:
            result.add_warning(
                f"Elevation unit mismatch: {dem1_metadata.elevation_unit} vs "
                f"{dem2_metadata.elevation_unit}"
            )

        return result

    def _bounds_overlap(
        self, bounds1: Tuple[float, float, float, float],
        bounds2: Tuple[float, float, float, float]
    ) -> bool:
        """
        Check if two bounds overlap.

        Args:
            bounds1: First bounds (min_x, min_y, max_x, max_y)
            bounds2: Second bounds (min_x, min_y, max_x, max_y)

        Returns:
            True if bounds overlap
        """
        min_x1, min_y1, max_x1, max_y1 = bounds1
        min_x2, min_y2, max_x2, max_y2 = bounds2

        # Check for no overlap
        if max_x1 < min_x2 or max_x2 < min_x1:
            return False
        if max_y1 < min_y2 or max_y2 < min_y1:
            return False

        return True

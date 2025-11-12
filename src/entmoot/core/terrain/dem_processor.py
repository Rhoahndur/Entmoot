"""
DEM processor for resampling, cropping, and interpolation operations.

Provides functionality for:
- Resampling to different resolutions
- Cropping to property boundaries
- Interpolating no-data values
- Smoothing and filtering
"""

import logging
from typing import Optional, Tuple, Union
import numpy as np
from scipy import ndimage, interpolate
from shapely.geometry import Polygon, box
from pyproj import CRS, Transformer

try:
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling as RioResampling
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

from entmoot.models.terrain import (
    DEMData,
    DEMMetadata,
    ResamplingMethod,
    InterpolationMethod,
)
from entmoot.core.errors import ParseError, ValidationError

logger = logging.getLogger(__name__)


class DEMProcessor:
    """
    Process Digital Elevation Models with various operations.

    Features:
    - Resampling to target resolutions
    - Cropping to boundaries with buffers
    - No-data interpolation
    - Smoothing and filtering
    """

    def __init__(self) -> None:
        """Initialize DEM processor."""
        if not RASTERIO_AVAILABLE:
            raise ImportError(
                "rasterio is required for DEM processing. "
                "Install with: pip install rasterio"
            )

    def resample(
        self,
        dem_data: DEMData,
        target_resolution: float,
        method: ResamplingMethod = ResamplingMethod.BILINEAR,
    ) -> DEMData:
        """
        Resample DEM to target resolution.

        Args:
            dem_data: Input DEM data
            target_resolution: Target resolution in CRS units
            method: Resampling method to use

        Returns:
            Resampled DEM data
        """
        current_resolution = dem_data.metadata.resolution[0]

        if abs(current_resolution - target_resolution) < 0.001:
            logger.info("Resolution already matches target, skipping resample")
            return dem_data

        logger.info(
            f"Resampling DEM from {current_resolution:.2f} to "
            f"{target_resolution:.2f} using {method.value}"
        )

        # Determine if upsampling or downsampling
        is_upsampling = target_resolution < current_resolution

        # Calculate new dimensions
        bounds = dem_data.metadata.bounds
        width = int((bounds[2] - bounds[0]) / target_resolution)
        height = int((bounds[3] - bounds[1]) / target_resolution)

        # Create transform for new resolution
        transform = from_bounds(*bounds, width, height)

        # Map resampling method
        rio_method = self._map_resampling_method(method, is_upsampling)

        # Create output array
        resampled = np.empty((height, width), dtype=np.float32)

        # Perform resampling
        try:
            reproject(
                source=dem_data.elevation,
                destination=resampled,
                src_transform=rasterio.transform.from_bounds(
                    *bounds,
                    dem_data.metadata.width,
                    dem_data.metadata.height
                ),
                src_crs=dem_data.metadata.crs,
                dst_transform=transform,
                dst_crs=dem_data.metadata.crs,
                resampling=rio_method,
                src_nodata=dem_data.metadata.no_data_value,
                dst_nodata=dem_data.metadata.no_data_value,
            )
        except Exception as e:
            raise ParseError(f"Resampling failed: {str(e)}") from e

        # Create new metadata
        new_metadata = DEMMetadata(
            width=width,
            height=height,
            resolution=(target_resolution, target_resolution),
            bounds=bounds,
            crs=dem_data.metadata.crs,
            no_data_value=dem_data.metadata.no_data_value,
            elevation_unit=dem_data.metadata.elevation_unit,
            dtype=str(resampled.dtype),
            transform=tuple(transform)[:6],
        )

        logger.info(f"Resampled to {width}x{height} pixels")

        return DEMData(elevation=resampled, metadata=new_metadata)

    def crop(
        self,
        dem_data: DEMData,
        boundary: Union[Polygon, Tuple[float, float, float, float]],
        buffer_meters: float = 100.0,
    ) -> DEMData:
        """
        Crop DEM to boundary extent with buffer.

        Args:
            dem_data: Input DEM data
            boundary: Boundary polygon or bounds tuple (min_x, min_y, max_x, max_y)
            buffer_meters: Buffer distance in meters

        Returns:
            Cropped DEM data
        """
        logger.info(f"Cropping DEM with {buffer_meters}m buffer")

        # Get boundary bounds
        if isinstance(boundary, Polygon):
            crop_bounds = boundary.bounds
            boundary_geom = boundary
        else:
            crop_bounds = boundary
            boundary_geom = box(*crop_bounds)

        # Add buffer
        if buffer_meters > 0:
            # Convert buffer to CRS units if needed
            if dem_data.metadata.crs and dem_data.metadata.crs.is_geographic:
                # Approximate: 1 degree ≈ 111km at equator
                buffer_degrees = buffer_meters / 111000.0
                boundary_geom = boundary_geom.buffer(buffer_degrees)
            else:
                boundary_geom = boundary_geom.buffer(buffer_meters)

            crop_bounds = boundary_geom.bounds

        # Ensure crop bounds are within DEM bounds
        dem_bounds = dem_data.metadata.bounds
        crop_bounds = (
            max(crop_bounds[0], dem_bounds[0]),
            max(crop_bounds[1], dem_bounds[1]),
            min(crop_bounds[2], dem_bounds[2]),
            min(crop_bounds[3], dem_bounds[3]),
        )

        # Check if bounds overlap
        if (
            crop_bounds[0] >= crop_bounds[2]
            or crop_bounds[1] >= crop_bounds[3]
        ):
            raise ValidationError(
                "Crop bounds do not overlap with DEM extent"
            )

        # Calculate pixel indices
        resolution = dem_data.metadata.resolution
        col_start = int((crop_bounds[0] - dem_bounds[0]) / resolution[0])
        row_start = int((dem_bounds[3] - crop_bounds[3]) / resolution[1])
        col_end = int((crop_bounds[2] - dem_bounds[0]) / resolution[0])
        row_end = int((dem_bounds[3] - crop_bounds[1]) / resolution[1])

        # Ensure indices are within array bounds
        col_start = max(0, col_start)
        row_start = max(0, row_start)
        col_end = min(dem_data.metadata.width, col_end)
        row_end = min(dem_data.metadata.height, row_end)

        # Crop elevation data
        cropped_elevation = dem_data.elevation[row_start:row_end, col_start:col_end]

        # Calculate actual cropped bounds
        actual_bounds = (
            dem_bounds[0] + col_start * resolution[0],
            dem_bounds[3] - row_end * resolution[1],
            dem_bounds[0] + col_end * resolution[0],
            dem_bounds[3] - row_start * resolution[1],
        )

        # Create new metadata
        new_metadata = DEMMetadata(
            width=cropped_elevation.shape[1],
            height=cropped_elevation.shape[0],
            resolution=resolution,
            bounds=actual_bounds,
            crs=dem_data.metadata.crs,
            no_data_value=dem_data.metadata.no_data_value,
            elevation_unit=dem_data.metadata.elevation_unit,
            dtype=str(cropped_elevation.dtype),
        )

        logger.info(
            f"Cropped to {new_metadata.width}x{new_metadata.height} pixels"
        )

        return DEMData(elevation=cropped_elevation, metadata=new_metadata)

    def interpolate_gaps(
        self,
        dem_data: DEMData,
        method: InterpolationMethod = InterpolationMethod.LINEAR,
        max_gap_size: Optional[int] = None,
    ) -> DEMData:
        """
        Interpolate no-data gaps in DEM.

        Args:
            dem_data: Input DEM data
            method: Interpolation method
            max_gap_size: Maximum gap size to interpolate (pixels)

        Returns:
            DEM data with interpolated values
        """
        elevation = dem_data.elevation.copy()
        valid_mask = ~np.isnan(elevation)

        # Check if there are any gaps
        if np.all(valid_mask):
            logger.info("No gaps to interpolate")
            return dem_data

        gap_count = np.sum(~valid_mask)
        logger.info(f"Interpolating {gap_count:,} no-data pixels using {method.value}")

        # Get valid data coordinates and values
        rows, cols = np.indices(elevation.shape)
        valid_points = np.column_stack((rows[valid_mask], cols[valid_mask]))
        valid_values = elevation[valid_mask]

        # Get gap coordinates
        gap_points = np.column_stack((rows[~valid_mask], cols[~valid_mask]))

        if len(valid_points) == 0:
            logger.warning("No valid data for interpolation")
            return dem_data

        # Filter large gaps if requested
        if max_gap_size is not None:
            gap_points = self._filter_large_gaps(
                gap_points, valid_mask, max_gap_size
            )

        if len(gap_points) == 0:
            logger.info("No gaps within size threshold")
            return dem_data

        try:
            # Perform interpolation
            if method == InterpolationMethod.NEAREST:
                interpolated = self._interpolate_nearest(
                    valid_points, valid_values, gap_points
                )
            elif method == InterpolationMethod.LINEAR:
                interpolated = self._interpolate_linear(
                    valid_points, valid_values, gap_points
                )
            elif method == InterpolationMethod.CUBIC:
                interpolated = self._interpolate_cubic(
                    elevation, valid_mask
                )
                # For cubic, return directly as it operates on full grid
                return DEMData(elevation=interpolated, metadata=dem_data.metadata)
            else:
                raise ValueError(f"Unsupported interpolation method: {method}")

            # Fill interpolated values
            elevation[gap_points[:, 0], gap_points[:, 1]] = interpolated

            logger.info("Interpolation complete")

        except Exception as e:
            raise ParseError(f"Interpolation failed: {str(e)}") from e

        return DEMData(elevation=elevation, metadata=dem_data.metadata)

    def smooth(
        self,
        dem_data: DEMData,
        sigma: float = 1.0,
        preserve_edges: bool = True,
    ) -> DEMData:
        """
        Smooth DEM using Gaussian filter.

        Args:
            dem_data: Input DEM data
            sigma: Gaussian kernel standard deviation
            preserve_edges: Preserve sharp edges (bilateral filtering)

        Returns:
            Smoothed DEM data
        """
        logger.info(f"Smoothing DEM with sigma={sigma}")

        elevation = dem_data.elevation.copy()
        valid_mask = ~np.isnan(elevation)

        if not preserve_edges:
            # Simple Gaussian smoothing
            smoothed = ndimage.gaussian_filter(
                elevation, sigma=sigma, mode='reflect'
            )
            # Restore no-data values
            smoothed[~valid_mask] = np.nan
        else:
            # Bilateral filter approximation
            smoothed = self._bilateral_filter(elevation, sigma, valid_mask)

        return DEMData(elevation=smoothed, metadata=dem_data.metadata)

    def remove_spikes(
        self,
        dem_data: DEMData,
        threshold: float = 3.0,
    ) -> DEMData:
        """
        Remove elevation spikes (outliers).

        Args:
            dem_data: Input DEM data
            threshold: Outlier threshold in standard deviations

        Returns:
            DEM data with spikes removed
        """
        logger.info(f"Removing spikes with threshold={threshold} std")

        elevation = dem_data.elevation.copy()
        valid_mask = ~np.isnan(elevation)

        if not np.any(valid_mask):
            return dem_data

        # Calculate local statistics
        mean = np.nanmean(elevation)
        std = np.nanstd(elevation)

        # Identify spikes
        spike_mask = np.abs(elevation - mean) > (threshold * std)
        spike_count = np.sum(spike_mask & valid_mask)

        if spike_count == 0:
            logger.info("No spikes detected")
            return dem_data

        logger.info(f"Removing {spike_count} spike pixels")

        # Set spikes to NaN
        elevation[spike_mask] = np.nan

        # Interpolate removed values
        dem_with_gaps = DEMData(elevation=elevation, metadata=dem_data.metadata)
        return self.interpolate_gaps(dem_with_gaps, method=InterpolationMethod.LINEAR)

    def _map_resampling_method(
        self, method: ResamplingMethod, is_upsampling: bool
    ) -> "RioResampling":
        """Map our resampling method to rasterio method."""
        if method == ResamplingMethod.NEAREST:
            return RioResampling.nearest
        elif method == ResamplingMethod.BILINEAR:
            return RioResampling.bilinear
        elif method == ResamplingMethod.CUBIC:
            return RioResampling.cubic
        elif method == ResamplingMethod.AVERAGE:
            return RioResampling.average if not is_upsampling else RioResampling.bilinear
        else:
            return RioResampling.bilinear

    def _filter_large_gaps(
        self, gap_points: np.ndarray, valid_mask: np.ndarray, max_size: int
    ) -> np.ndarray:
        """Filter out gaps larger than max_size."""
        # Label connected gap regions
        gap_mask = ~valid_mask
        labeled, num_features = ndimage.label(gap_mask)

        # Find sizes of each gap
        sizes = ndimage.sum(gap_mask, labeled, range(1, num_features + 1))

        # Create mask for small gaps
        small_gaps_mask = np.zeros_like(gap_mask, dtype=bool)
        for i, size in enumerate(sizes, start=1):
            if size <= max_size:
                small_gaps_mask[labeled == i] = True

        # Filter gap points
        filtered_points = []
        for point in gap_points:
            if small_gaps_mask[point[0], point[1]]:
                filtered_points.append(point)

        return np.array(filtered_points) if filtered_points else np.array([]).reshape(0, 2)

    def _interpolate_nearest(
        self, valid_points: np.ndarray, valid_values: np.ndarray, gap_points: np.ndarray
    ) -> np.ndarray:
        """Nearest neighbor interpolation."""
        interp = interpolate.NearestNDInterpolator(valid_points, valid_values)
        return interp(gap_points)

    def _interpolate_linear(
        self, valid_points: np.ndarray, valid_values: np.ndarray, gap_points: np.ndarray
    ) -> np.ndarray:
        """Linear interpolation."""
        interp = interpolate.LinearNDInterpolator(valid_points, valid_values)
        interpolated = interp(gap_points)

        # Handle points outside convex hull with nearest neighbor
        nan_mask = np.isnan(interpolated)
        if np.any(nan_mask):
            nn_interp = interpolate.NearestNDInterpolator(valid_points, valid_values)
            interpolated[nan_mask] = nn_interp(gap_points[nan_mask])

        return interpolated

    def _interpolate_cubic(
        self, elevation: np.ndarray, valid_mask: np.ndarray
    ) -> np.ndarray:
        """Cubic interpolation using inpainting."""
        # Use scipy's interpolation for cubic
        filled = elevation.copy()

        # Get valid data
        rows, cols = np.indices(elevation.shape)
        valid_points = np.column_stack((rows[valid_mask].flatten(), cols[valid_mask].flatten()))
        valid_values = elevation[valid_mask].flatten()

        if len(valid_points) < 16:  # Need enough points for cubic
            logger.warning("Not enough points for cubic interpolation, using linear")
            return self._interpolate_linear(
                valid_points, valid_values,
                np.column_stack((rows[~valid_mask].flatten(), cols[~valid_mask].flatten()))
            )

        # Use RBF interpolation for smooth results
        from scipy.interpolate import Rbf
        rbf = Rbf(valid_points[:, 0], valid_points[:, 1], valid_values, function='cubic', smooth=1)

        # Interpolate gaps
        gap_points = np.column_stack((rows[~valid_mask], cols[~valid_mask]))
        filled[~valid_mask] = rbf(gap_points[:, 0], gap_points[:, 1])

        return filled

    def _bilateral_filter(
        self, elevation: np.ndarray, sigma_spatial: float, valid_mask: np.ndarray
    ) -> np.ndarray:
        """
        Approximate bilateral filter for edge-preserving smoothing.

        This is a simplified version that combines Gaussian smoothing
        with gradient-based edge detection.
        """
        # Compute gradients
        gy, gx = np.gradient(elevation)
        gradient_mag = np.sqrt(gx**2 + gy**2)

        # Create edge-aware weights
        edge_threshold = np.nanpercentile(gradient_mag[valid_mask], 75)
        edge_weight = np.exp(-(gradient_mag / edge_threshold)**2)

        # Apply weighted Gaussian smoothing
        smoothed = ndimage.gaussian_filter(elevation, sigma=sigma_spatial, mode='reflect')

        # Blend based on edge weight
        result = edge_weight * elevation + (1 - edge_weight) * smoothed

        # Restore no-data
        result[~valid_mask] = np.nan

        return result

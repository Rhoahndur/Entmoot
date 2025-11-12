"""
Pre-grading elevation model.

Extracts existing elevations from DEM and creates pre-grading surface
for comparison with post-grading design.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Union, Any
import numpy as np
from numpy.typing import NDArray

try:
    import rasterio
    from rasterio.transform import Affine
    from rasterio.features import rasterize
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

from entmoot.models.terrain import DEMData, DEMMetadata
from entmoot.core.errors import ValidationError

logger = logging.getLogger(__name__)


class PreGradingModel:
    """
    Pre-grading elevation model.

    Extracts and stores existing terrain elevations for comparison
    with post-grading design.
    """

    def __init__(self, dem_data: DEMData) -> None:
        """
        Initialize pre-grading model.

        Args:
            dem_data: DEM data containing elevation information

        Raises:
            ValidationError: If DEM data is invalid
        """
        if not RASTERIO_AVAILABLE:
            raise ImportError("rasterio is required. Install with: pip install rasterio")

        if dem_data.elevation is None or dem_data.elevation.size == 0:
            raise ValidationError("DEM data must contain elevation information")

        self.dem_data = dem_data
        self.metadata = dem_data.metadata
        self.elevation = dem_data.elevation.copy()

        # Calculate surface area
        self.surface_area_sf = self._calculate_surface_area()

        logger.info(
            f"Initialized pre-grading model: "
            f"{self.metadata.width}x{self.metadata.height}, "
            f"surface area: {self.surface_area_sf:,.0f} sq ft"
        )

    def _calculate_surface_area(self) -> float:
        """
        Calculate 3D surface area accounting for slope.

        Returns:
            Surface area in square feet
        """
        # Get cell dimensions
        cell_width = self.metadata.resolution[0]  # meters
        cell_height = self.metadata.resolution[1]  # meters

        # Convert to feet (1 meter = 3.28084 feet)
        cell_width_ft = cell_width * 3.28084
        cell_height_ft = cell_height * 3.28084

        # Calculate planar area
        planar_area = cell_width_ft * cell_height_ft * self.elevation.size

        # Calculate 3D surface area using slope
        # For each cell, calculate actual surface area based on slope
        from entmoot.core.terrain.slope import calculate_slope

        try:
            # Calculate slope in degrees
            slope_degrees = calculate_slope(
                self.elevation,
                cell_size=cell_width,
                units="degrees"
            )

            # Convert slope to radians
            slope_radians = np.deg2rad(slope_degrees)

            # Surface area adjustment factor: 1 / cos(slope)
            # For flat terrain, cos(0) = 1, so factor = 1
            # For sloped terrain, factor > 1
            valid_mask = ~np.isnan(slope_radians)
            area_factors = np.ones_like(slope_radians)
            area_factors[valid_mask] = 1.0 / np.cos(slope_radians[valid_mask])

            # Calculate 3D surface area
            surface_area = np.sum(area_factors) * cell_width_ft * cell_height_ft

            return float(surface_area)

        except Exception as e:
            logger.warning(f"Failed to calculate 3D surface area: {e}. Using planar area.")
            return planar_area

    def get_elevation_at_point(self, x: float, y: float) -> Optional[float]:
        """
        Get elevation at a specific coordinate.

        Args:
            x: X coordinate in CRS units
            y: Y coordinate in CRS units

        Returns:
            Elevation in feet, or None if point is outside DEM
        """
        # Convert coordinates to pixel indices
        col, row = self._coords_to_pixel(x, y)

        # Check if point is within DEM bounds
        if not (0 <= row < self.metadata.height and 0 <= col < self.metadata.width):
            return None

        # Get elevation value
        elevation = self.elevation[row, col]

        # Check for no-data values
        if np.isnan(elevation):
            return None

        return float(elevation)

    def get_elevation_profile(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        num_points: int = 100
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]:
        """
        Get elevation profile along a line.

        Args:
            start: (x, y) starting coordinates
            end: (x, y) ending coordinates
            num_points: Number of sample points along line

        Returns:
            Tuple of (distance, elevation) arrays
        """
        # Create points along the line
        x_coords = np.linspace(start[0], end[0], num_points)
        y_coords = np.linspace(start[1], end[1], num_points)

        # Calculate distance from start
        dx = x_coords - start[0]
        dy = y_coords - start[1]
        distance = np.sqrt(dx**2 + dy**2) * 3.28084  # Convert to feet

        # Sample elevations
        elevations = np.zeros(num_points)
        for i in range(num_points):
            elev = self.get_elevation_at_point(x_coords[i], y_coords[i])
            elevations[i] = elev if elev is not None else np.nan

        return distance, elevations

    def _coords_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert coordinates to pixel indices.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Tuple of (col, row) pixel indices
        """
        # Get transform parameters
        if self.metadata.transform:
            a, b, c, d, e, f = self.metadata.transform
            # Inverse transform
            col = int((x - c) / a)
            row = int((y - f) / e)
        else:
            # Fallback: use bounds and resolution
            min_x, min_y, max_x, max_y = self.metadata.bounds
            col = int((x - min_x) / self.metadata.resolution[0])
            row = int((max_y - y) / self.metadata.resolution[1])

        return col, row

    def extract_zone_elevations(
        self,
        geometry: Any,
        resolution: Optional[float] = None
    ) -> NDArray[np.floating[Any]]:
        """
        Extract elevation values within a geometry.

        Args:
            geometry: Shapely geometry defining the zone
            resolution: Optional resolution for sampling (meters)

        Returns:
            Array of elevation values within the zone
        """
        if resolution is None:
            resolution = min(self.metadata.resolution)

        # Create a mask from the geometry
        mask = self._create_geometry_mask(geometry)

        # Extract elevations
        elevations = self.elevation[mask]

        # Filter out no-data values
        elevations = elevations[~np.isnan(elevations)]

        return elevations

    def _create_geometry_mask(self, geometry: Any) -> NDArray[np.bool_]:
        """
        Create a boolean mask for a geometry.

        Args:
            geometry: Shapely geometry

        Returns:
            Boolean mask array
        """
        # Create transform
        if self.metadata.transform:
            transform = Affine(*self.metadata.transform)
        else:
            min_x, min_y, max_x, max_y = self.metadata.bounds
            transform = Affine.translation(min_x, max_y) * Affine.scale(
                self.metadata.resolution[0],
                -self.metadata.resolution[1]
            )

        # Rasterize the geometry
        try:
            mask = rasterize(
                [(geometry, 1)],
                out_shape=(self.metadata.height, self.metadata.width),
                transform=transform,
                fill=0,
                dtype=np.uint8
            )
            return mask.astype(bool)
        except Exception as e:
            logger.error(f"Failed to create geometry mask: {e}")
            return np.zeros((self.metadata.height, self.metadata.width), dtype=bool)

    def get_statistics(self) -> dict:
        """
        Get statistics about the pre-grading surface.

        Returns:
            Dictionary of statistics
        """
        # Filter valid elevations
        valid_elevations = self.elevation[~np.isnan(self.elevation)]

        if len(valid_elevations) == 0:
            return {
                "min_elevation": np.nan,
                "max_elevation": np.nan,
                "mean_elevation": np.nan,
                "median_elevation": np.nan,
                "std_elevation": np.nan,
                "surface_area_sf": 0.0,
            }

        return {
            "min_elevation": float(np.min(valid_elevations)),
            "max_elevation": float(np.max(valid_elevations)),
            "mean_elevation": float(np.mean(valid_elevations)),
            "median_elevation": float(np.median(valid_elevations)),
            "std_elevation": float(np.std(valid_elevations)),
            "surface_area_sf": self.surface_area_sf,
            "elevation_range": float(np.max(valid_elevations) - np.min(valid_elevations)),
        }

    def export_surface(self, output_path: Union[str, Path]) -> None:
        """
        Export pre-grading surface to GeoTIFF.

        Args:
            output_path: Path to output GeoTIFF file
        """
        output_path = Path(output_path)

        # Create transform
        if self.metadata.transform:
            transform = Affine(*self.metadata.transform)
        else:
            min_x, min_y, max_x, max_y = self.metadata.bounds
            transform = Affine.translation(min_x, max_y) * Affine.scale(
                self.metadata.resolution[0],
                -self.metadata.resolution[1]
            )

        # Write to GeoTIFF
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=self.metadata.height,
            width=self.metadata.width,
            count=1,
            dtype=self.elevation.dtype,
            crs=self.metadata.crs.to_string() if self.metadata.crs else None,
            transform=transform,
            nodata=np.nan,
        ) as dst:
            dst.write(self.elevation, 1)

        logger.info(f"Exported pre-grading surface to {output_path}")

    def to_dict(self) -> dict:
        """
        Convert to dictionary representation.

        Returns:
            Dictionary with model information
        """
        return {
            "metadata": self.metadata.to_dict(),
            "statistics": self.get_statistics(),
        }

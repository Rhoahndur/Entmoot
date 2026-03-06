"""
Terrain service — loads and prepares DEM data for the optimization pipeline.

Provides a TerrainData container with sampling methods, and a
prepare_terrain_data() function that wires together DEMLoader,
DEMValidator, DEMProcessor, and SlopeCalculator.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from rasterio.transform import Affine
from shapely.geometry import Point, Polygon

from entmoot.core.terrain.dem_loader import DEMLoader
from entmoot.core.terrain.dem_validator import DEMValidator
from entmoot.core.terrain.dem_processor import DEMProcessor
from entmoot.core.terrain.slope import SlopeCalculator

logger = logging.getLogger(__name__)


class TerrainPreparationError(Exception):
    """Raised when DEM preparation fails (validation, reprojection, etc.)."""

    pass


class TerrainData:
    """Container holding processed terrain arrays with spatial sampling methods."""

    def __init__(
        self,
        elevation: NDArray[np.floating],
        slope_percent: NDArray[np.floating],
        transform: Affine,
        cell_size: float,
        bounds: Tuple[float, float, float, float],
    ) -> None:
        self.elevation = elevation
        self.slope_percent = slope_percent
        self.transform = transform
        self.cell_size = cell_size
        self.bounds = bounds  # (min_x, min_y, max_x, max_y)

    # ---- coordinate → pixel helpers ----

    def _xy_to_rowcol(self, x: float, y: float) -> Tuple[int, int]:
        """Convert UTM x,y to raster row,col using the inverse affine."""
        inv = ~self.transform
        col_f, row_f = inv * (x, y)
        col = int(col_f)
        row = int(row_f)
        return row, col

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.elevation.shape[0] and 0 <= col < self.elevation.shape[1]

    # ---- public sampling API ----

    def sample_elevation(self, x: float, y: float) -> Optional[float]:
        """Sample elevation at a UTM coordinate. Returns None if outside grid."""
        row, col = self._xy_to_rowcol(x, y)
        if not self._in_bounds(row, col):
            return None
        val = float(self.elevation[row, col])
        return None if np.isnan(val) else val

    def sample_slope(self, x: float, y: float) -> Optional[float]:
        """Sample slope % at a UTM coordinate. Returns None if outside grid."""
        row, col = self._xy_to_rowcol(x, y)
        if not self._in_bounds(row, col):
            return None
        val = float(self.slope_percent[row, col])
        return None if np.isnan(val) else val

    def get_mean_slope_in_footprint(self, polygon: Polygon) -> Optional[float]:
        """Return mean slope % under a Shapely polygon (UTM coords).

        Samples the raster pixels whose centres fall within the polygon.
        Returns None when no pixels overlap.
        """
        minx, miny, maxx, maxy = polygon.bounds

        # Convert corners to pixel space
        r_min, c_min = self._xy_to_rowcol(minx, maxy)  # top-left
        r_max, c_max = self._xy_to_rowcol(maxx, miny)  # bottom-right

        r_min = max(0, r_min)
        c_min = max(0, c_min)
        r_max = min(self.slope_percent.shape[0] - 1, r_max)
        c_max = min(self.slope_percent.shape[1] - 1, c_max)

        if r_min > r_max or c_min > c_max:
            return None

        values = []
        for r in range(r_min, r_max + 1):
            for c in range(c_min, c_max + 1):
                # Pixel centre in UTM
                px, py = self.transform * (c + 0.5, r + 0.5)
                if polygon.contains(Point(px, py)):
                    v = self.slope_percent[r, c]
                    if not np.isnan(v):
                        values.append(float(v))

        return float(np.mean(values)) if values else None

    def get_elevation_under_footprint(self, polygon: Polygon) -> NDArray[np.floating]:
        """Return 1-D array of elevation values under a polygon (UTM)."""
        minx, miny, maxx, maxy = polygon.bounds
        r_min, c_min = self._xy_to_rowcol(minx, maxy)
        r_max, c_max = self._xy_to_rowcol(maxx, miny)

        r_min = max(0, r_min)
        c_min = max(0, c_min)
        r_max = min(self.elevation.shape[0] - 1, r_max)
        c_max = min(self.elevation.shape[1] - 1, c_max)

        values = []
        for r in range(r_min, r_max + 1):
            for c in range(c_min, c_max + 1):
                px, py = self.transform * (c + 0.5, r + 0.5)
                if polygon.contains(Point(px, py)):
                    v = self.elevation[r, c]
                    if not np.isnan(v):
                        values.append(float(v))

        return np.array(values, dtype=np.float64) if values else np.array([], dtype=np.float64)


def prepare_terrain_data(
    dem_file_path: Path,
    site_boundary_utm: Polygon,
    target_crs_epsg: int,
) -> TerrainData:
    """Load, validate, reproject, crop and compute slope from a DEM file.

    Args:
        dem_file_path: Path to the GeoTIFF DEM.
        site_boundary_utm: Property boundary already in target UTM CRS.
        target_crs_epsg: EPSG code of the target UTM CRS.

    Returns:
        TerrainData ready for use by the optimiser.

    Raises:
        TerrainPreparationError: If validation fails critically.
    """
    import rasterio
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from pyproj import CRS

    logger.info(f"Preparing terrain data from {dem_file_path}")

    # 1. Load
    loader = DEMLoader()
    dem_data = loader.load(dem_file_path)
    logger.info(
        f"Loaded DEM: {dem_data.metadata.width}x{dem_data.metadata.height}, "
        f"CRS: {dem_data.metadata.crs}"
    )

    # 2. Validate
    validator = DEMValidator()
    validation = validator.validate(dem_data)
    if not validation.is_valid:
        issues = "; ".join(validation.issues)
        raise TerrainPreparationError(f"DEM validation failed: {issues}")
    for w in validation.warnings:
        logger.warning(f"DEM warning: {w}")

    # 3. Reproject to target CRS if needed
    target_crs = CRS.from_epsg(target_crs_epsg)
    src_crs = dem_data.metadata.crs

    if src_crs and not src_crs.equals(target_crs):
        logger.info(f"Reprojecting DEM from {src_crs.name} to EPSG:{target_crs_epsg}")
        src_bounds = dem_data.metadata.bounds
        src_transform = (
            Affine(*dem_data.metadata.transform)
            if dem_data.metadata.transform
            else (
                Affine(
                    dem_data.metadata.resolution[0],
                    0,
                    src_bounds[0],
                    0,
                    -dem_data.metadata.resolution[1],
                    src_bounds[3],
                )
            )
        )

        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            target_crs,
            dem_data.metadata.width,
            dem_data.metadata.height,
            *src_bounds,
        )

        dst_array = np.empty((dst_height, dst_width), dtype=np.float32)
        reproject(
            source=dem_data.elevation,
            destination=dst_array,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )

        elevation = dst_array
        transform = dst_transform
        cell_size = abs(dst_transform.a)
    else:
        elevation = dem_data.elevation
        if dem_data.metadata.transform:
            transform = Affine(*dem_data.metadata.transform)
        else:
            b = dem_data.metadata.bounds
            transform = Affine(
                dem_data.metadata.resolution[0],
                0,
                b[0],
                0,
                -dem_data.metadata.resolution[1],
                b[3],
            )
        cell_size = dem_data.metadata.resolution[0]

    # 4. Crop to boundary + 100 m buffer
    processor = DEMProcessor()
    from entmoot.models.terrain import DEMData, DEMMetadata

    cropped_bounds = (
        transform.c,
        transform.f + transform.e * elevation.shape[0],
        transform.c + transform.a * elevation.shape[1],
        transform.f,
    )

    crop_meta = DEMMetadata(
        width=elevation.shape[1],
        height=elevation.shape[0],
        resolution=(abs(transform.a), abs(transform.e)),
        bounds=cropped_bounds,
        crs=target_crs,
        no_data_value=np.nan,
        dtype="float32",
        transform=(transform.a, transform.b, transform.c, transform.d, transform.e, transform.f),
    )
    crop_dem = DEMData(elevation=elevation, metadata=crop_meta)
    cropped = processor.crop(crop_dem, site_boundary_utm, buffer_meters=100.0)

    elevation = cropped.elevation
    cell_size = cropped.metadata.resolution[0]
    bounds = cropped.metadata.bounds

    # Rebuild transform from cropped bounds
    transform = Affine(
        cell_size,
        0,
        bounds[0],
        0,
        -cell_size,
        bounds[3],
    )

    # 5. Compute slope (percent)
    slope_calc = SlopeCalculator(cell_size=cell_size, units="percent")
    # Need at least 3x3 for slope calculation
    if elevation.shape[0] >= 3 and elevation.shape[1] >= 3:
        slope_percent = slope_calc.calculate(elevation)
    else:
        logger.warning("DEM too small for slope calculation, using zeros")
        slope_percent = np.zeros_like(elevation)

    logger.info(
        f"Terrain data ready: {elevation.shape[1]}x{elevation.shape[0]} pixels, "
        f"cell_size={cell_size:.2f}m"
    )

    return TerrainData(
        elevation=elevation,
        slope_percent=slope_percent,
        transform=transform,
        cell_size=cell_size,
        bounds=bounds,
    )

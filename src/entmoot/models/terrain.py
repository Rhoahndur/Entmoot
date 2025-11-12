"""
Terrain data models for DEM processing.

This module defines data models for Digital Elevation Models (DEMs),
including metadata, elevation data, and terrain metrics.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any
from enum import Enum

import numpy as np
from pyproj import CRS


class ElevationUnit(str, Enum):
    """Elevation unit types."""

    METERS = "meters"
    FEET = "feet"


class InterpolationMethod(str, Enum):
    """Interpolation methods for DEM processing."""

    NEAREST = "nearest"
    LINEAR = "linear"
    CUBIC = "cubic"


class ResamplingMethod(str, Enum):
    """Resampling methods for DEM processing."""

    NEAREST = "nearest"
    BILINEAR = "bilinear"
    CUBIC = "cubic"
    AVERAGE = "average"


@dataclass
class DEMMetadata:
    """
    Metadata for a Digital Elevation Model.

    Attributes:
        width: Number of columns in the raster
        height: Number of rows in the raster
        resolution: Tuple of (x_resolution, y_resolution) in CRS units
        bounds: Tuple of (min_x, min_y, max_x, max_y) in CRS units
        crs: Coordinate Reference System
        no_data_value: Value representing missing/invalid data
        elevation_unit: Unit of elevation values (meters or feet)
        dtype: Data type of elevation values
        transform: Affine transformation matrix (6 parameters)
    """

    width: int
    height: int
    resolution: Tuple[float, float]
    bounds: Tuple[float, float, float, float]
    crs: CRS
    no_data_value: Optional[float] = None
    elevation_unit: ElevationUnit = ElevationUnit.METERS
    dtype: str = "float32"
    transform: Optional[Tuple[float, ...]] = None

    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        if self.width <= 0:
            raise ValueError(f"Width must be positive, got {self.width}")
        if self.height <= 0:
            raise ValueError(f"Height must be positive, got {self.height}")
        if self.resolution[0] <= 0 or self.resolution[1] <= 0:
            raise ValueError(f"Resolution must be positive, got {self.resolution}")

        # Validate bounds
        min_x, min_y, max_x, max_y = self.bounds
        if min_x >= max_x:
            raise ValueError(f"min_x ({min_x}) must be less than max_x ({max_x})")
        if min_y >= max_y:
            raise ValueError(f"min_y ({min_y}) must be less than max_y ({max_y})")

    @property
    def pixel_count(self) -> int:
        """Total number of pixels in the DEM."""
        return self.width * self.height

    @property
    def area_sqm(self) -> float:
        """Approximate area covered by the DEM in square meters."""
        width_m = (self.bounds[2] - self.bounds[0]) * self.resolution[0]
        height_m = (self.bounds[3] - self.bounds[1]) * self.resolution[1]
        return width_m * height_m

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "bounds": self.bounds,
            "crs": self.crs.to_string() if self.crs else None,
            "no_data_value": self.no_data_value,
            "elevation_unit": self.elevation_unit.value,
            "dtype": self.dtype,
            "pixel_count": self.pixel_count,
            "area_sqm": self.area_sqm,
        }


@dataclass
class TerrainMetrics:
    """
    Statistical metrics for terrain elevation data.

    Attributes:
        min_elevation: Minimum elevation value
        max_elevation: Maximum elevation value
        mean_elevation: Mean elevation value
        median_elevation: Median elevation value
        std_elevation: Standard deviation of elevation
        elevation_range: Range between min and max elevation
        valid_pixel_count: Number of valid (non-no-data) pixels
        no_data_pixel_count: Number of no-data pixels
        no_data_percentage: Percentage of no-data pixels
    """

    min_elevation: float
    max_elevation: float
    mean_elevation: float
    median_elevation: float
    std_elevation: float
    elevation_range: float
    valid_pixel_count: int
    no_data_pixel_count: int
    no_data_percentage: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "min_elevation": float(self.min_elevation),
            "max_elevation": float(self.max_elevation),
            "mean_elevation": float(self.mean_elevation),
            "median_elevation": float(self.median_elevation),
            "std_elevation": float(self.std_elevation),
            "elevation_range": float(self.elevation_range),
            "valid_pixel_count": int(self.valid_pixel_count),
            "no_data_pixel_count": int(self.no_data_pixel_count),
            "no_data_percentage": float(self.no_data_percentage),
        }


@dataclass
class DEMData:
    """
    Container for DEM elevation data and metadata.

    Attributes:
        elevation: 2D numpy array of elevation values
        metadata: DEM metadata
        metrics: Optional terrain metrics (computed on demand)
    """

    elevation: np.ndarray
    metadata: DEMMetadata
    metrics: Optional[TerrainMetrics] = None

    def __post_init__(self) -> None:
        """Validate DEM data after initialization."""
        if self.elevation.ndim != 2:
            raise ValueError(
                f"Elevation array must be 2D, got {self.elevation.ndim} dimensions"
            )
        if self.elevation.shape != (self.metadata.height, self.metadata.width):
            raise ValueError(
                f"Elevation shape {self.elevation.shape} does not match "
                f"metadata dimensions ({self.metadata.height}, {self.metadata.width})"
            )

    def compute_metrics(self) -> TerrainMetrics:
        """
        Compute terrain metrics from elevation data.

        Returns:
            TerrainMetrics object with statistical information
        """
        # Create mask for valid data
        if self.metadata.no_data_value is not None and not np.isnan(self.metadata.no_data_value):
            valid_mask = self.elevation != self.metadata.no_data_value
            valid_data = self.elevation[valid_mask]
        else:
            valid_mask = ~np.isnan(self.elevation)
            valid_data = self.elevation[valid_mask]

        # Handle case where all data is no-data
        if len(valid_data) == 0:
            return TerrainMetrics(
                min_elevation=np.nan,
                max_elevation=np.nan,
                mean_elevation=np.nan,
                median_elevation=np.nan,
                std_elevation=np.nan,
                elevation_range=np.nan,
                valid_pixel_count=0,
                no_data_pixel_count=self.metadata.pixel_count,
                no_data_percentage=100.0,
            )

        # Compute statistics
        min_elev = float(np.min(valid_data))
        max_elev = float(np.max(valid_data))
        mean_elev = float(np.mean(valid_data))
        median_elev = float(np.median(valid_data))
        std_elev = float(np.std(valid_data))
        elev_range = max_elev - min_elev

        valid_count = int(np.sum(valid_mask))
        no_data_count = self.metadata.pixel_count - valid_count
        no_data_pct = (no_data_count / self.metadata.pixel_count) * 100.0

        metrics = TerrainMetrics(
            min_elevation=min_elev,
            max_elevation=max_elev,
            mean_elevation=mean_elev,
            median_elevation=median_elev,
            std_elevation=std_elev,
            elevation_range=elev_range,
            valid_pixel_count=valid_count,
            no_data_pixel_count=no_data_count,
            no_data_percentage=no_data_pct,
        )

        # Cache metrics
        self.metrics = metrics
        return metrics

    def get_metrics(self) -> TerrainMetrics:
        """
        Get terrain metrics, computing if not already cached.

        Returns:
            TerrainMetrics object
        """
        if self.metrics is None:
            return self.compute_metrics()
        return self.metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert DEM data to dictionary (without elevation array)."""
        return {
            "metadata": self.metadata.to_dict(),
            "metrics": self.get_metrics().to_dict(),
            "shape": self.elevation.shape,
            "dtype": str(self.elevation.dtype),
        }


@dataclass
class DEMValidationResult:
    """
    Result of DEM validation checks.

    Attributes:
        is_valid: Overall validation status
        issues: List of validation issues found
        warnings: List of non-critical warnings
        metadata: DEM metadata that was validated
    """

    is_valid: bool
    issues: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metadata: Optional[DEMMetadata] = None

    def add_issue(self, issue: str) -> None:
        """Add a validation issue."""
        self.issues.append(issue)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        result = {
            "is_valid": self.is_valid,
            "issues": self.issues,
            "warnings": self.warnings,
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result

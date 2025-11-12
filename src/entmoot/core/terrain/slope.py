"""
Slope calculation and classification for terrain analysis.

This module implements multiple algorithms for calculating slope from Digital Elevation Models (DEMs):
- Horn's method (3x3 kernel, standard in GIS)
- Fleming and Hoffer method
- Zevenbergen and Thorne method

Slope is calculated as the rate of maximum elevation change and can be expressed
in degrees or percentage.
"""

from enum import Enum
from typing import Optional, Tuple, Dict, Any
import numpy as np
from numpy.typing import NDArray


class SlopeMethod(str, Enum):
    """Supported slope calculation methods."""

    HORN = "horn"
    FLEMING_HOFFER = "fleming_hoffer"
    ZEVENBERGEN_THORNE = "zevenbergen_thorne"


class SlopeClassification(str, Enum):
    """Standard slope classifications for buildability analysis."""

    FLAT = "flat"  # 0-5%: Easily buildable
    MODERATE = "moderate"  # 5-15%: Buildable with grading
    STEEP = "steep"  # 15-25%: Difficult, requires engineering
    VERY_STEEP = "very_steep"  # 25%+: Generally unbuildable


class SlopeCalculator:
    """
    Calculate slope from Digital Elevation Models using various algorithms.

    This class provides methods to compute slope in both degrees and percentage,
    with support for multiple calculation algorithms and configurable parameters.
    """

    def __init__(
        self,
        cell_size: float = 1.0,
        method: SlopeMethod = SlopeMethod.HORN,
        units: str = "degrees",
    ):
        """
        Initialize the slope calculator.

        Args:
            cell_size: Resolution of the DEM in meters (default: 1.0)
            method: Algorithm to use for slope calculation (default: Horn's method)
            units: Output units - 'degrees' or 'percent' (default: 'degrees')

        Raises:
            ValueError: If units is not 'degrees' or 'percent'
        """
        if units not in ["degrees", "percent"]:
            raise ValueError("units must be 'degrees' or 'percent'")

        self.cell_size = cell_size
        self.method = method
        self.units = units

    def calculate(
        self, dem: NDArray[np.floating[Any]], z_factor: float = 1.0
    ) -> NDArray[np.floating[Any]]:
        """
        Calculate slope from a DEM array.

        Args:
            dem: 2D numpy array representing the Digital Elevation Model
            z_factor: Vertical exaggeration factor (default: 1.0)

        Returns:
            2D numpy array of slope values in the specified units

        Raises:
            ValueError: If DEM is not a 2D array or has invalid dimensions
        """
        if dem.ndim != 2:
            raise ValueError("DEM must be a 2D array")
        if dem.shape[0] < 3 or dem.shape[1] < 3:
            raise ValueError("DEM must be at least 3x3 pixels")

        # Select calculation method
        if self.method == SlopeMethod.HORN:
            dzdx, dzdy = self._calculate_gradients_horn(dem, z_factor)
        elif self.method == SlopeMethod.FLEMING_HOFFER:
            dzdx, dzdy = self._calculate_gradients_fleming_hoffer(dem, z_factor)
        elif self.method == SlopeMethod.ZEVENBERGEN_THORNE:
            dzdx, dzdy = self._calculate_gradients_zevenbergen_thorne(dem, z_factor)
        else:
            raise ValueError(f"Unknown method: {self.method}")

        # Calculate slope from gradients
        slope_radians = np.arctan(np.sqrt(dzdx**2 + dzdy**2))

        # Convert to requested units
        if self.units == "degrees":
            return np.degrees(slope_radians)
        else:  # percent
            return np.tan(slope_radians) * 100.0

    def _calculate_gradients_horn(
        self, dem: NDArray[np.floating[Any]], z_factor: float
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]:
        """
        Calculate gradients using Horn's method (3x3 kernel).

        This is the standard method used in most GIS software (ArcGIS, QGIS).
        It uses a weighted kernel that gives more weight to closer cells.

        The method uses the following kernels:
        dz/dx:  [-1  0  1]       dz/dy:  [-1 -2 -1]
                [-2  0  2]               [ 0  0  0]
                [-1  0  1]               [ 1  2  1]

        Args:
            dem: 2D elevation array
            z_factor: Vertical exaggeration factor

        Returns:
            Tuple of (dz/dx, dz/dy) gradient arrays
        """
        # Pad the DEM to handle edges (replicate edge values)
        dem_padded = np.pad(dem, pad_width=1, mode="edge")

        # Apply z_factor
        dem_padded = dem_padded * z_factor

        # Extract the 8 neighboring cells for each pixel
        # Using array slicing for vectorization (no loops)
        a = dem_padded[0:-2, 0:-2]  # top-left
        b = dem_padded[0:-2, 1:-1]  # top
        c = dem_padded[0:-2, 2:]  # top-right
        d = dem_padded[1:-1, 0:-2]  # left
        # e = dem_padded[1:-1, 1:-1]  # center (not needed)
        f = dem_padded[1:-1, 2:]  # right
        g = dem_padded[2:, 0:-2]  # bottom-left
        h = dem_padded[2:, 1:-1]  # bottom
        i = dem_padded[2:, 2:]  # bottom-right

        # Calculate gradients using Horn's formula
        # dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cell_size)
        # dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cell_size)
        dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * self.cell_size)
        dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * self.cell_size)

        return dzdx, dzdy

    def _calculate_gradients_fleming_hoffer(
        self, dem: NDArray[np.floating[Any]], z_factor: float
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]:
        """
        Calculate gradients using Fleming and Hoffer method.

        This method uses simple unweighted finite differences.

        Args:
            dem: 2D elevation array
            z_factor: Vertical exaggeration factor

        Returns:
            Tuple of (dz/dx, dz/dy) gradient arrays
        """
        dem_padded = np.pad(dem, pad_width=1, mode="edge")
        dem_padded = dem_padded * z_factor

        # Simple finite differences
        # dz/dx = (right - left) / (2 * cell_size)
        # dz/dy = (bottom - top) / (2 * cell_size)
        dzdx = (dem_padded[1:-1, 2:] - dem_padded[1:-1, 0:-2]) / (2.0 * self.cell_size)
        dzdy = (dem_padded[2:, 1:-1] - dem_padded[0:-2, 1:-1]) / (2.0 * self.cell_size)

        return dzdx, dzdy

    def _calculate_gradients_zevenbergen_thorne(
        self, dem: NDArray[np.floating[Any]], z_factor: float
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]:
        """
        Calculate gradients using Zevenbergen and Thorne method.

        This method uses a fitted polynomial surface and is appropriate
        for smooth, continuous surfaces.

        Args:
            dem: 2D elevation array
            z_factor: Vertical exaggeration factor

        Returns:
            Tuple of (dz/dx, dz/dy) gradient arrays
        """
        dem_padded = np.pad(dem, pad_width=1, mode="edge")
        dem_padded = dem_padded * z_factor

        # Extract neighbors
        d = dem_padded[1:-1, 0:-2]  # left
        f = dem_padded[1:-1, 2:]  # right
        b = dem_padded[0:-2, 1:-1]  # top
        h = dem_padded[2:, 1:-1]  # bottom

        # Zevenbergen and Thorne formulas
        dzdx = (f - d) / (2.0 * self.cell_size)
        dzdy = (h - b) / (2.0 * self.cell_size)

        return dzdx, dzdy

    def calculate_with_metadata(
        self, dem: NDArray[np.floating[Any]], z_factor: float = 1.0
    ) -> Dict[str, Any]:
        """
        Calculate slope and return with statistics.

        Args:
            dem: 2D numpy array representing the Digital Elevation Model
            z_factor: Vertical exaggeration factor (default: 1.0)

        Returns:
            Dictionary containing:
                - slope: The slope array
                - min: Minimum slope value
                - max: Maximum slope value
                - mean: Mean slope value
                - std: Standard deviation of slope
                - method: Method used for calculation
                - units: Units of the result
        """
        slope = self.calculate(dem, z_factor)

        return {
            "slope": slope,
            "min": float(np.min(slope)),
            "max": float(np.max(slope)),
            "mean": float(np.mean(slope)),
            "std": float(np.std(slope)),
            "method": self.method.value,
            "units": self.units,
        }


def calculate_slope(
    dem: NDArray[np.floating[Any]],
    cell_size: float = 1.0,
    method: SlopeMethod = SlopeMethod.HORN,
    units: str = "degrees",
    z_factor: float = 1.0,
) -> NDArray[np.floating[Any]]:
    """
    Convenience function to calculate slope from a DEM.

    Args:
        dem: 2D numpy array representing the Digital Elevation Model
        cell_size: Resolution of the DEM in meters (default: 1.0)
        method: Algorithm to use (default: Horn's method)
        units: Output units - 'degrees' or 'percent' (default: 'degrees')
        z_factor: Vertical exaggeration factor (default: 1.0)

    Returns:
        2D numpy array of slope values

    Example:
        >>> import numpy as np
        >>> dem = np.array([[100, 101, 102],
        ...                 [100, 101, 102],
        ...                 [100, 101, 102]])
        >>> slope = calculate_slope(dem, cell_size=1.0, units='degrees')
    """
    calculator = SlopeCalculator(cell_size=cell_size, method=method, units=units)
    return calculator.calculate(dem, z_factor)


def classify_slope(
    slope_percent: NDArray[np.floating[Any]],
    thresholds: Optional[Tuple[float, float, float]] = None,
) -> NDArray[np.integer[Any]]:
    """
    Classify slope values into buildability categories.

    Args:
        slope_percent: Array of slope values in percent
        thresholds: Custom thresholds as (moderate, steep, very_steep) in percent.
                   Default: (5, 15, 25)

    Returns:
        Integer array with classification codes:
            0 = FLAT (0-5%)
            1 = MODERATE (5-15%)
            2 = STEEP (15-25%)
            3 = VERY_STEEP (25%+)

    Example:
        >>> slope_pct = np.array([[2, 8, 20], [10, 18, 30]])
        >>> classified = classify_slope(slope_pct)
        >>> # Result: [[0, 1, 2], [1, 2, 3]]
    """
    if thresholds is None:
        thresholds = (5.0, 15.0, 25.0)

    moderate_threshold, steep_threshold, very_steep_threshold = thresholds

    # Initialize with FLAT (0)
    classified = np.zeros_like(slope_percent, dtype=np.int32)

    # Classify into categories
    classified[slope_percent >= moderate_threshold] = 1  # MODERATE
    classified[slope_percent >= steep_threshold] = 2  # STEEP
    classified[slope_percent >= very_steep_threshold] = 3  # VERY_STEEP

    return classified


def get_classification_name(code: int) -> str:
    """
    Get the classification name for a numeric code.

    Args:
        code: Classification code (0-3)

    Returns:
        Classification name

    Raises:
        ValueError: If code is not in range 0-3
    """
    classifications = {
        0: SlopeClassification.FLAT.value,
        1: SlopeClassification.MODERATE.value,
        2: SlopeClassification.STEEP.value,
        3: SlopeClassification.VERY_STEEP.value,
    }

    if code not in classifications:
        raise ValueError(f"Invalid classification code: {code}")

    return classifications[code]


def calculate_slope_statistics(
    slope: NDArray[np.floating[Any]], classified: Optional[NDArray[np.integer[Any]]] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive statistics for a slope array.

    Args:
        slope: Array of slope values
        classified: Optional classified slope array

    Returns:
        Dictionary containing slope statistics and class distribution
    """
    stats = {
        "min": float(np.min(slope)),
        "max": float(np.max(slope)),
        "mean": float(np.mean(slope)),
        "median": float(np.median(slope)),
        "std": float(np.std(slope)),
        "percentile_25": float(np.percentile(slope, 25)),
        "percentile_75": float(np.percentile(slope, 75)),
        "percentile_90": float(np.percentile(slope, 90)),
        "percentile_95": float(np.percentile(slope, 95)),
    }

    if classified is not None:
        total_pixels = classified.size
        class_counts = {
            "flat": int(np.sum(classified == 0)),
            "moderate": int(np.sum(classified == 1)),
            "steep": int(np.sum(classified == 2)),
            "very_steep": int(np.sum(classified == 3)),
        }
        class_percentages = {
            key: (count / total_pixels) * 100 for key, count in class_counts.items()
        }

        stats["class_counts"] = class_counts
        stats["class_percentages"] = class_percentages

    return stats

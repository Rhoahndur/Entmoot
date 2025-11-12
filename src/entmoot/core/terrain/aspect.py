"""
Aspect calculation and analysis for terrain.

This module calculates aspect (the compass direction of maximum slope) from
Digital Elevation Models. Aspect is important for:
- Solar exposure analysis
- Wind exposure modeling
- Ecological and hydrological studies
- Building orientation planning
"""

from enum import Enum
from typing import Optional, Dict, Any, Tuple
import numpy as np
from numpy.typing import NDArray


class CardinalDirection(str, Enum):
    """Eight cardinal and intercardinal directions."""

    N = "N"  # North: 337.5° - 22.5°
    NE = "NE"  # Northeast: 22.5° - 67.5°
    E = "E"  # East: 67.5° - 112.5°
    SE = "SE"  # Southeast: 112.5° - 157.5°
    S = "S"  # South: 157.5° - 202.5°
    SW = "SW"  # Southwest: 202.5° - 247.5°
    W = "W"  # West: 247.5° - 292.5°
    NW = "NW"  # Northwest: 292.5° - 337.5°
    FLAT = "FLAT"  # Undefined (slope = 0)


class AspectCalculator:
    """
    Calculate aspect (direction of slope) from Digital Elevation Models.

    Aspect represents the compass direction that a slope faces, measured
    in degrees clockwise from North (0° = North, 90° = East, 180° = South, 270° = West).
    """

    def __init__(self, cell_size: float = 1.0):
        """
        Initialize the aspect calculator.

        Args:
            cell_size: Resolution of the DEM in meters (default: 1.0)
        """
        self.cell_size = cell_size

    def calculate(
        self, dem: NDArray[np.floating[Any]], slope_threshold: float = 0.1
    ) -> NDArray[np.floating[Any]]:
        """
        Calculate aspect from a DEM array.

        Args:
            dem: 2D numpy array representing the Digital Elevation Model
            slope_threshold: Minimum slope (in degrees) below which aspect is
                           set to -1 (undefined/flat). Default: 0.1

        Returns:
            2D numpy array of aspect values in degrees (0-360), with -1 for flat areas

        Raises:
            ValueError: If DEM is not a 2D array or has invalid dimensions
        """
        if dem.ndim != 2:
            raise ValueError("DEM must be a 2D array")
        if dem.shape[0] < 3 or dem.shape[1] < 3:
            raise ValueError("DEM must be at least 3x3 pixels")

        # Calculate gradients using Horn's method (same as slope calculation)
        dzdx, dzdy = self._calculate_gradients(dem)

        # Calculate aspect in radians using atan2
        # atan2(dy, dx) gives angle from positive x-axis
        # We need to convert to compass bearing (0° = North, clockwise)
        aspect_radians = np.arctan2(dzdy, -dzdx)

        # Convert to degrees (0-360, with 0° = East)
        aspect_degrees = np.degrees(aspect_radians)

        # Convert from math convention (0° = East, counter-clockwise)
        # to compass bearing (0° = North, clockwise)
        # Formula: aspect = 90° - atan2_result
        # Then normalize to 0-360 range
        aspect_compass = 90.0 - aspect_degrees

        # Normalize to 0-360 range
        aspect_compass = np.where(aspect_compass < 0, aspect_compass + 360, aspect_compass)
        aspect_compass = np.where(aspect_compass >= 360, aspect_compass - 360, aspect_compass)

        # Mark flat areas (low slope) as undefined (-1)
        if slope_threshold > 0:
            slope_radians = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
            slope_degrees = np.degrees(slope_radians)
            aspect_compass = np.where(slope_degrees < slope_threshold, -1.0, aspect_compass)

        return aspect_compass

    def _calculate_gradients(
        self, dem: NDArray[np.floating[Any]]
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]:
        """
        Calculate gradients using Horn's method.

        Args:
            dem: 2D elevation array

        Returns:
            Tuple of (dz/dx, dz/dy) gradient arrays
        """
        # Pad the DEM to handle edges
        dem_padded = np.pad(dem, pad_width=1, mode="edge")

        # Extract the 8 neighboring cells
        a = dem_padded[0:-2, 0:-2]  # top-left
        b = dem_padded[0:-2, 1:-1]  # top
        c = dem_padded[0:-2, 2:]  # top-right
        d = dem_padded[1:-1, 0:-2]  # left
        f = dem_padded[1:-1, 2:]  # right
        g = dem_padded[2:, 0:-2]  # bottom-left
        h = dem_padded[2:, 1:-1]  # bottom
        i = dem_padded[2:, 2:]  # bottom-right

        # Horn's formula for gradients
        dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * self.cell_size)
        dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * self.cell_size)

        return dzdx, dzdy

    def calculate_with_cardinal(
        self, dem: NDArray[np.floating[Any]], slope_threshold: float = 0.1
    ) -> Tuple[NDArray[np.floating[Any]], NDArray[np.integer[Any]]]:
        """
        Calculate aspect and convert to cardinal directions.

        Args:
            dem: 2D numpy array representing the Digital Elevation Model
            slope_threshold: Minimum slope for valid aspect (degrees)

        Returns:
            Tuple of (aspect_degrees, cardinal_codes) where cardinal_codes are integers:
                0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 8=FLAT
        """
        aspect = self.calculate(dem, slope_threshold)
        cardinal = aspect_to_cardinal_code(aspect)
        return aspect, cardinal

    def calculate_with_metadata(
        self, dem: NDArray[np.floating[Any]], slope_threshold: float = 0.1
    ) -> Dict[str, Any]:
        """
        Calculate aspect and return with statistics.

        Args:
            dem: 2D numpy array representing the Digital Elevation Model
            slope_threshold: Minimum slope for valid aspect (degrees)

        Returns:
            Dictionary containing aspect array and statistics
        """
        aspect = self.calculate(dem, slope_threshold)

        # Get statistics for defined aspects only (exclude -1)
        valid_aspect = aspect[aspect >= 0]

        stats = {
            "aspect": aspect,
            "undefined_pixels": int(np.sum(aspect < 0)),
            "defined_pixels": int(np.sum(aspect >= 0)),
        }

        if len(valid_aspect) > 0:
            stats.update(
                {
                    "mean": float(np.mean(valid_aspect)),
                    "median": float(np.median(valid_aspect)),
                    "std": float(np.std(valid_aspect)),
                }
            )

        return stats


def calculate_aspect(
    dem: NDArray[np.floating[Any]], cell_size: float = 1.0, slope_threshold: float = 0.1
) -> NDArray[np.floating[Any]]:
    """
    Convenience function to calculate aspect from a DEM.

    Args:
        dem: 2D numpy array representing the Digital Elevation Model
        cell_size: Resolution of the DEM in meters (default: 1.0)
        slope_threshold: Minimum slope for valid aspect in degrees (default: 0.1)

    Returns:
        2D numpy array of aspect values in degrees (0-360), with -1 for flat areas

    Example:
        >>> import numpy as np
        >>> dem = np.array([[100, 100, 100],
        ...                 [100, 105, 100],
        ...                 [100, 100, 100]])
        >>> aspect = calculate_aspect(dem, cell_size=1.0)
    """
    calculator = AspectCalculator(cell_size=cell_size)
    return calculator.calculate(dem, slope_threshold)


def aspect_to_cardinal(aspect_degrees: float) -> CardinalDirection:
    """
    Convert a single aspect value to cardinal direction.

    Args:
        aspect_degrees: Aspect in degrees (0-360) or -1 for flat

    Returns:
        CardinalDirection enum value

    Example:
        >>> direction = aspect_to_cardinal(45.0)
        >>> print(direction)  # CardinalDirection.NE
    """
    if aspect_degrees < 0:
        return CardinalDirection.FLAT

    # Normalize to 0-360
    aspect_degrees = aspect_degrees % 360

    # Map to cardinal directions (8 sectors of 45 degrees each)
    # N: 337.5-22.5, NE: 22.5-67.5, E: 67.5-112.5, etc.
    if aspect_degrees < 22.5 or aspect_degrees >= 337.5:
        return CardinalDirection.N
    elif aspect_degrees < 67.5:
        return CardinalDirection.NE
    elif aspect_degrees < 112.5:
        return CardinalDirection.E
    elif aspect_degrees < 157.5:
        return CardinalDirection.SE
    elif aspect_degrees < 202.5:
        return CardinalDirection.S
    elif aspect_degrees < 247.5:
        return CardinalDirection.SW
    elif aspect_degrees < 292.5:
        return CardinalDirection.W
    else:
        return CardinalDirection.NW


def aspect_to_cardinal_code(aspect: NDArray[np.floating[Any]]) -> NDArray[np.integer[Any]]:
    """
    Convert aspect array to cardinal direction codes.

    Args:
        aspect: Array of aspect values in degrees (0-360), with -1 for flat

    Returns:
        Integer array with direction codes:
            0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 8=FLAT

    Example:
        >>> aspect = np.array([0, 45, 90, 180, -1])
        >>> codes = aspect_to_cardinal_code(aspect)
        >>> # Result: [0, 1, 2, 4, 8]
    """
    # Initialize with FLAT (8)
    cardinal = np.full_like(aspect, 8, dtype=np.int32)

    # Create mask for defined aspects
    valid_mask = aspect >= 0

    # For valid aspects, determine cardinal direction
    valid_aspect = aspect[valid_mask]

    # Normalize to 0-360
    valid_aspect = valid_aspect % 360

    # Assign cardinal codes based on angle ranges
    cardinal[valid_mask] = np.where(
        (valid_aspect < 22.5) | (valid_aspect >= 337.5),
        0,  # N
        np.where(
            valid_aspect < 67.5,
            1,  # NE
            np.where(
                valid_aspect < 112.5,
                2,  # E
                np.where(
                    valid_aspect < 157.5,
                    3,  # SE
                    np.where(
                        valid_aspect < 202.5,
                        4,  # S
                        np.where(
                            valid_aspect < 247.5,
                            5,  # SW
                            np.where(valid_aspect < 292.5, 6, 7),  # W  # NW
                        ),
                    ),
                ),
            ),
        ),
    )

    return cardinal


def cardinal_code_to_name(code: int) -> str:
    """
    Get the cardinal direction name for a numeric code.

    Args:
        code: Cardinal direction code (0-8)

    Returns:
        Direction name (e.g., "N", "NE", "FLAT")

    Raises:
        ValueError: If code is not in range 0-8
    """
    directions = {
        0: CardinalDirection.N.value,
        1: CardinalDirection.NE.value,
        2: CardinalDirection.E.value,
        3: CardinalDirection.SE.value,
        4: CardinalDirection.S.value,
        5: CardinalDirection.SW.value,
        6: CardinalDirection.W.value,
        7: CardinalDirection.NW.value,
        8: CardinalDirection.FLAT.value,
    }

    if code not in directions:
        raise ValueError(f"Invalid cardinal code: {code}")

    return directions[code]


def calculate_aspect_distribution(
    aspect: NDArray[np.floating[Any]],
) -> Dict[str, Any]:
    """
    Calculate distribution statistics for aspect.

    Args:
        aspect: Array of aspect values in degrees

    Returns:
        Dictionary with cardinal direction counts and percentages
    """
    cardinal = aspect_to_cardinal_code(aspect)
    total_pixels = cardinal.size

    counts = {
        "N": int(np.sum(cardinal == 0)),
        "NE": int(np.sum(cardinal == 1)),
        "E": int(np.sum(cardinal == 2)),
        "SE": int(np.sum(cardinal == 3)),
        "S": int(np.sum(cardinal == 4)),
        "SW": int(np.sum(cardinal == 5)),
        "W": int(np.sum(cardinal == 6)),
        "NW": int(np.sum(cardinal == 7)),
        "FLAT": int(np.sum(cardinal == 8)),
    }

    percentages = {key: (count / total_pixels) * 100 for key, count in counts.items()}

    return {"counts": counts, "percentages": percentages}


def calculate_solar_exposure(
    aspect: NDArray[np.floating[Any]],
    slope: NDArray[np.floating[Any]],
    latitude: float = 40.0,
) -> NDArray[np.floating[Any]]:
    """
    Calculate solar exposure index based on aspect and slope.

    For northern hemisphere, south-facing slopes receive more solar radiation.
    The index considers both the direction and steepness of the slope.

    Args:
        aspect: Array of aspect values in degrees (0-360, -1 for flat)
        slope: Array of slope values in degrees
        latitude: Latitude in degrees (positive for N, negative for S). Default: 40°N

    Returns:
        Solar exposure index (0-1, where 1 is maximum exposure)

    Notes:
        - In northern hemisphere: South-facing (180°) is optimal
        - In southern hemisphere: North-facing (0°/360°) is optimal
        - Flat areas receive baseline exposure
        - Steeper slopes in optimal direction receive more exposure
    """
    # Optimal aspect depends on hemisphere
    if latitude >= 0:
        # Northern hemisphere: South is optimal (180°)
        optimal_aspect = 180.0
    else:
        # Southern hemisphere: North is optimal (0°)
        optimal_aspect = 0.0

    # Initialize exposure index
    exposure = np.ones_like(aspect, dtype=np.float64)

    # For defined aspects, calculate exposure
    valid_mask = aspect >= 0
    valid_aspect = aspect[valid_mask]
    valid_slope = slope[valid_mask]

    # Calculate aspect factor (0-1, where 1 is optimal direction)
    # Use cosine to get smooth transition
    aspect_diff = np.abs(valid_aspect - optimal_aspect)
    aspect_diff = np.minimum(aspect_diff, 360 - aspect_diff)  # Handle wrap-around
    aspect_factor = (np.cos(np.radians(aspect_diff)) + 1) / 2  # Normalize to 0-1

    # Calculate slope factor
    # Optimal slope depends on latitude (approximately equal to latitude angle)
    optimal_slope = np.abs(latitude)
    slope_diff = np.abs(valid_slope - optimal_slope)
    slope_factor = np.exp(-slope_diff / 30.0)  # Gaussian-like decay

    # Combine factors
    exposure[valid_mask] = aspect_factor * slope_factor

    # Flat areas get baseline exposure (0.5)
    exposure[aspect < 0] = 0.5

    return exposure


def calculate_wind_exposure(
    aspect: NDArray[np.floating[Any]],
    slope: NDArray[np.floating[Any]],
    prevailing_wind_direction: float = 270.0,
) -> NDArray[np.floating[Any]]:
    """
    Calculate wind exposure index based on aspect and slope.

    Slopes facing the prevailing wind direction have higher exposure.
    Steeper slopes in the wind direction have even higher exposure.

    Args:
        aspect: Array of aspect values in degrees (0-360, -1 for flat)
        slope: Array of slope values in degrees
        prevailing_wind_direction: Direction wind comes FROM in degrees (default: 270° = West)

    Returns:
        Wind exposure index (0-1, where 1 is maximum exposure)

    Example:
        >>> aspect = np.array([270, 90, 0, -1])  # W, E, N, FLAT
        >>> slope = np.array([20, 20, 5, 0])
        >>> exposure = calculate_wind_exposure(aspect, slope, prevailing_wind_direction=270)
        >>> # West-facing slope gets highest exposure
    """
    # Initialize exposure index
    exposure = np.zeros_like(aspect, dtype=np.float64)

    # For defined aspects, calculate exposure
    valid_mask = aspect >= 0
    valid_aspect = aspect[valid_mask]
    valid_slope = slope[valid_mask]

    # Calculate aspect alignment with wind direction
    # Maximum exposure when facing the wind
    aspect_diff = np.abs(valid_aspect - prevailing_wind_direction)
    aspect_diff = np.minimum(aspect_diff, 360 - aspect_diff)  # Handle wrap-around
    aspect_factor = (np.cos(np.radians(aspect_diff)) + 1) / 2  # 0-1

    # Slope amplification factor (steeper = more exposed)
    # Use tanh for smooth saturation
    slope_factor = np.tanh(valid_slope / 30.0)  # Normalizes steep slopes

    # Combine factors
    exposure[valid_mask] = aspect_factor * (0.7 + 0.3 * slope_factor)

    # Flat areas get minimal exposure (0.3)
    exposure[aspect < 0] = 0.3

    return exposure

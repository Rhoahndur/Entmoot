"""
Buildable area identification for site analysis.

This module identifies buildable areas based on terrain analysis (slope, elevation, aspect)
and provides comprehensive metrics for each buildable zone. It uses:
- Slope thresholds to determine buildability
- Elevation constraints to avoid flood-prone areas
- Connected components analysis to identify contiguous zones
- Polygonization to convert raster zones to vector geometries
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List
from enum import Enum

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from scipy.ndimage import label as scipy_label
import rasterio.features
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union


class BuildabilityClass(str, Enum):
    """Buildability classification based on slope."""

    EXCELLENT = "excellent"  # 0-5%: Ideal for building
    GOOD = "good"  # 5-15%: Buildable with minimal grading
    DIFFICULT = "difficult"  # 15-25%: Requires significant engineering
    UNSUITABLE = "unsuitable"  # 25%+: Generally unbuildable


@dataclass
class BuildabilityThresholds:
    """
    Configurable thresholds for buildability analysis.

    Attributes:
        excellent_slope_max: Maximum slope for excellent buildability (%)
        good_slope_max: Maximum slope for good buildability (%)
        difficult_slope_max: Maximum slope for difficult buildability (%)
        min_elevation: Minimum elevation (to avoid flood zones)
        max_elevation: Maximum elevation (practical limit)
        min_zone_area_sqm: Minimum contiguous buildable area (sq meters)
        aspect_preference: Optional preferred aspect (degrees, 0-360)
        aspect_tolerance: Tolerance for aspect preference (degrees)
    """

    excellent_slope_max: float = 5.0
    good_slope_max: float = 15.0
    difficult_slope_max: float = 25.0
    min_elevation: Optional[float] = None
    max_elevation: Optional[float] = None
    min_zone_area_sqm: float = 1000.0  # ~10,764 sq ft
    aspect_preference: Optional[float] = None
    aspect_tolerance: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate thresholds."""
        if self.excellent_slope_max >= self.good_slope_max:
            raise ValueError("excellent_slope_max must be less than good_slope_max")
        if self.good_slope_max >= self.difficult_slope_max:
            raise ValueError("good_slope_max must be less than difficult_slope_max")
        if self.min_zone_area_sqm <= 0:
            raise ValueError("min_zone_area_sqm must be positive")

        if self.min_elevation is not None and self.max_elevation is not None:
            if self.min_elevation >= self.max_elevation:
                raise ValueError("min_elevation must be less than max_elevation")


@dataclass
class BuildableZone:
    """
    Information about a single buildable zone.

    Attributes:
        zone_id: Unique identifier for the zone
        area_sqm: Area in square meters
        area_acres: Area in acres
        geometry: Shapely polygon geometry
        mean_slope: Average slope in the zone (%)
        min_elevation: Minimum elevation in the zone
        max_elevation: Maximum elevation in the zone
        mean_elevation: Average elevation in the zone
        compactness: Compactness score (0-1, 1 = perfect circle)
        quality_score: Overall quality score (0-100)
        buildability_class: Classification of buildability
        centroid: (x, y) centroid coordinates
    """

    zone_id: int
    area_sqm: float
    area_acres: float
    geometry: Polygon
    mean_slope: float
    min_elevation: float
    max_elevation: float
    mean_elevation: float
    compactness: float
    quality_score: float
    buildability_class: BuildabilityClass
    centroid: Tuple[float, float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert zone to dictionary."""
        return {
            "zone_id": self.zone_id,
            "area_sqm": float(self.area_sqm),
            "area_acres": float(self.area_acres),
            "mean_slope": float(self.mean_slope),
            "min_elevation": float(self.min_elevation),
            "max_elevation": float(self.max_elevation),
            "mean_elevation": float(self.mean_elevation),
            "compactness": float(self.compactness),
            "quality_score": float(self.quality_score),
            "buildability_class": self.buildability_class.value,
            "centroid": self.centroid,
            "geometry_wkt": self.geometry.wkt,
        }


@dataclass
class BuildabilityResult:
    """
    Complete buildability analysis results.

    Attributes:
        buildable_mask: Boolean array where True = buildable
        zones: List of buildable zones
        total_buildable_area_sqm: Total buildable area (sq m)
        total_buildable_area_acres: Total buildable area (acres)
        buildable_percentage: Percentage of property that's buildable
        num_zones: Number of distinct buildable zones
        largest_zone: The largest buildable zone
        overall_quality_score: Overall site buildability score (0-100)
        metrics: Additional metrics dictionary
    """

    buildable_mask: NDArray[np.bool_]
    zones: List[BuildableZone] = field(default_factory=list)
    total_buildable_area_sqm: float = 0.0
    total_buildable_area_acres: float = 0.0
    buildable_percentage: float = 0.0
    num_zones: int = 0
    largest_zone: Optional[BuildableZone] = None
    overall_quality_score: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary (without mask array)."""
        return {
            "total_buildable_area_sqm": float(self.total_buildable_area_sqm),
            "total_buildable_area_acres": float(self.total_buildable_area_acres),
            "buildable_percentage": float(self.buildable_percentage),
            "num_zones": int(self.num_zones),
            "largest_zone": self.largest_zone.to_dict() if self.largest_zone else None,
            "overall_quality_score": float(self.overall_quality_score),
            "zones": [zone.to_dict() for zone in self.zones],
            "metrics": self.metrics,
        }


class BuildabilityAnalyzer:
    """
    Analyze terrain to identify buildable areas.

    This class performs comprehensive buildability analysis including:
    - Applying slope and elevation constraints
    - Identifying contiguous buildable zones
    - Converting zones to vector polygons
    - Calculating quality scores and metrics
    """

    def __init__(
        self,
        cell_size: float = 1.0,
        thresholds: Optional[BuildabilityThresholds] = None,
    ):
        """
        Initialize the buildability analyzer.

        Args:
            cell_size: Resolution of the DEM in meters (default: 1.0)
            thresholds: Buildability thresholds (uses defaults if not provided)
        """
        self.cell_size = cell_size
        self.thresholds = thresholds or BuildabilityThresholds()

    def analyze(
        self,
        slope_percent: NDArray[np.floating[Any]],
        elevation: NDArray[np.floating[Any]],
        transform: Optional[Any] = None,
        aspect: Optional[NDArray[np.floating[Any]]] = None,
        property_mask: Optional[NDArray[np.bool_]] = None,
    ) -> BuildabilityResult:
        """
        Perform complete buildability analysis.

        Args:
            slope_percent: Array of slope values in percent
            elevation: Array of elevation values
            transform: Rasterio affine transform for coordinate conversion
            aspect: Optional array of aspect values (degrees)
            property_mask: Optional mask of property boundary (True = inside property)

        Returns:
            BuildabilityResult with comprehensive analysis

        Raises:
            ValueError: If arrays have mismatched shapes
        """
        if slope_percent.shape != elevation.shape:
            raise ValueError("Slope and elevation arrays must have same shape")

        if aspect is not None and aspect.shape != slope_percent.shape:
            raise ValueError("Aspect array must have same shape as slope/elevation")

        # Step 1: Create buildable mask
        buildable_mask = self.create_buildable_mask(
            slope_percent, elevation, aspect, property_mask
        )

        # Step 2: Calculate total area
        pixel_area_sqm = self.cell_size * self.cell_size
        total_pixels = buildable_mask.size
        buildable_pixels = np.sum(buildable_mask)
        total_buildable_area_sqm = buildable_pixels * pixel_area_sqm
        total_buildable_area_acres = total_buildable_area_sqm / 4046.86  # sqm to acres

        # Calculate percentage
        buildable_percentage = (buildable_pixels / total_pixels) * 100.0

        # Step 3: Identify contiguous zones
        labeled_zones, num_zones = self.identify_zones(buildable_mask)

        # Step 4: Analyze each zone
        zones = self.analyze_zones(
            labeled_zones,
            num_zones,
            slope_percent,
            elevation,
            transform,
        )

        # Step 5: Calculate overall quality score
        overall_quality = self.calculate_overall_quality(
            zones, buildable_percentage, slope_percent, buildable_mask
        )

        # Find largest zone
        largest_zone = max(zones, key=lambda z: z.area_sqm) if zones else None

        # Build result
        result = BuildabilityResult(
            buildable_mask=buildable_mask,
            zones=zones,
            total_buildable_area_sqm=total_buildable_area_sqm,
            total_buildable_area_acres=total_buildable_area_acres,
            buildable_percentage=buildable_percentage,
            num_zones=len(zones),
            largest_zone=largest_zone,
            overall_quality_score=overall_quality,
            metrics=self._calculate_additional_metrics(
                zones, slope_percent, elevation, buildable_mask
            ),
        )

        return result

    def create_buildable_mask(
        self,
        slope_percent: NDArray[np.floating[Any]],
        elevation: NDArray[np.floating[Any]],
        aspect: Optional[NDArray[np.floating[Any]]] = None,
        property_mask: Optional[NDArray[np.bool_]] = None,
    ) -> NDArray[np.bool_]:
        """
        Create boolean mask of buildable areas.

        Args:
            slope_percent: Array of slope values in percent
            elevation: Array of elevation values
            aspect: Optional array of aspect values
            property_mask: Optional property boundary mask

        Returns:
            Boolean array where True = buildable
        """
        # Start with all True
        mask = np.ones_like(slope_percent, dtype=bool)

        # Apply slope constraint (must be below difficult threshold)
        mask &= slope_percent <= self.thresholds.difficult_slope_max

        # Apply elevation constraints
        if self.thresholds.min_elevation is not None:
            mask &= elevation >= self.thresholds.min_elevation

        if self.thresholds.max_elevation is not None:
            mask &= elevation <= self.thresholds.max_elevation

        # Apply aspect preference if specified
        if aspect is not None and self.thresholds.aspect_preference is not None:
            aspect_pref = self.thresholds.aspect_preference
            aspect_tol = self.thresholds.aspect_tolerance or 45.0

            # Calculate angular difference (handle wrap-around at 0/360)
            aspect_diff = np.abs(aspect - aspect_pref)
            aspect_diff = np.minimum(aspect_diff, 360.0 - aspect_diff)

            # Keep only aspects within tolerance
            mask &= (aspect_diff <= aspect_tol) | (aspect < 0)  # -1 = flat (ok)

        # Apply property mask if provided
        if property_mask is not None:
            mask &= property_mask

        return mask

    def identify_zones(
        self, buildable_mask: NDArray[np.bool_]
    ) -> Tuple[NDArray[np.integer[Any]], int]:
        """
        Identify contiguous buildable zones using connected components.

        Args:
            buildable_mask: Boolean mask of buildable areas

        Returns:
            Tuple of (labeled_array, num_zones) where labeled_array has
            zone IDs (0 = not buildable, 1+ = zone ID)
        """
        # Define 8-connectivity structure (includes diagonals)
        structure = ndimage.generate_binary_structure(2, 2)

        # Label connected components
        labeled, num_zones = scipy_label(buildable_mask, structure=structure)

        return labeled, num_zones

    def analyze_zones(
        self,
        labeled_zones: NDArray[np.integer[Any]],
        num_zones: int,
        slope_percent: NDArray[np.floating[Any]],
        elevation: NDArray[np.floating[Any]],
        transform: Optional[Any] = None,
    ) -> List[BuildableZone]:
        """
        Analyze each buildable zone and create zone objects.

        Args:
            labeled_zones: Array with zone labels
            num_zones: Number of zones
            slope_percent: Slope array
            elevation: Elevation array
            transform: Optional rasterio transform

        Returns:
            List of BuildableZone objects, filtered by minimum area
        """
        zones = []
        pixel_area_sqm = self.cell_size * self.cell_size

        for zone_id in range(1, num_zones + 1):
            zone_mask = labeled_zones == zone_id

            # Calculate area
            zone_pixels = np.sum(zone_mask)
            area_sqm = zone_pixels * pixel_area_sqm

            # Filter by minimum area
            if area_sqm < self.thresholds.min_zone_area_sqm:
                continue

            # Extract zone statistics
            zone_slopes = slope_percent[zone_mask]
            zone_elevations = elevation[zone_mask]

            mean_slope = float(np.mean(zone_slopes))
            min_elevation = float(np.min(zone_elevations))
            max_elevation = float(np.max(zone_elevations))
            mean_elevation = float(np.mean(zone_elevations))

            # Convert to polygon
            geometry = self.zone_to_polygon(zone_mask, transform)

            if geometry is None or geometry.is_empty:
                continue

            # Calculate compactness (Polsby-Popper score)
            compactness = self._calculate_compactness(geometry)

            # Determine buildability class
            buildability_class = self._classify_zone(mean_slope)

            # Calculate centroid
            centroid = (geometry.centroid.x, geometry.centroid.y)

            # Calculate quality score
            quality_score = self._calculate_zone_quality(
                area_sqm, mean_slope, compactness, buildability_class
            )

            zone = BuildableZone(
                zone_id=zone_id,
                area_sqm=area_sqm,
                area_acres=area_sqm / 4046.86,
                geometry=geometry,
                mean_slope=mean_slope,
                min_elevation=min_elevation,
                max_elevation=max_elevation,
                mean_elevation=mean_elevation,
                compactness=compactness,
                quality_score=quality_score,
                buildability_class=buildability_class,
                centroid=centroid,
            )

            zones.append(zone)

        # Sort zones by area (largest first)
        zones.sort(key=lambda z: z.area_sqm, reverse=True)

        return zones

    def zone_to_polygon(
        self,
        zone_mask: NDArray[np.bool_],
        transform: Optional[Any] = None,
        simplify_tolerance: float = 1.0,
    ) -> Optional[Polygon]:
        """
        Convert a zone mask to a polygon geometry.

        Args:
            zone_mask: Boolean mask of the zone
            transform: Rasterio affine transform
            simplify_tolerance: Tolerance for polygon simplification (meters)

        Returns:
            Shapely Polygon or None if conversion fails
        """
        # Convert mask to uint8 for rasterio
        zone_uint8 = zone_mask.astype(np.uint8)

        # Create identity transform if none provided (pixel coordinates)
        if transform is None:
            from rasterio.transform import Affine
            transform = Affine.identity()

        # Extract shapes (polygons) from raster
        shapes_gen = rasterio.features.shapes(zone_uint8, transform=transform)

        # Filter for value=1 (the zone) and convert to shapely geometries
        polygons = []
        for geom_dict, value in shapes_gen:
            if value == 1:
                geom = shape(geom_dict)
                if geom.is_valid:
                    polygons.append(geom)

        if not polygons:
            return None

        # Union all polygons (handles multi-part geometries)
        if len(polygons) == 1:
            result = polygons[0]
        else:
            result = unary_union(polygons)

        # Convert MultiPolygon to Polygon (take largest)
        if isinstance(result, MultiPolygon):
            result = max(result.geoms, key=lambda p: p.area)

        # Simplify to reduce vertices
        if simplify_tolerance > 0:
            result = result.simplify(simplify_tolerance, preserve_topology=True)

        # Apply buffer of 0 to fix any geometry issues
        result = result.buffer(0)

        return result if isinstance(result, Polygon) else None

    def _calculate_compactness(self, polygon: Polygon) -> float:
        """
        Calculate Polsby-Popper compactness score.

        Compactness = 4 * pi * area / perimeter^2
        Score of 1.0 = perfect circle
        Score approaches 0 for elongated shapes

        Args:
            polygon: Shapely polygon

        Returns:
            Compactness score (0-1)
        """
        area = polygon.area
        perimeter = polygon.length

        if perimeter == 0:
            return 0.0

        compactness = (4.0 * np.pi * area) / (perimeter**2)
        return min(compactness, 1.0)  # Cap at 1.0 due to numerical errors

    def _classify_zone(self, mean_slope: float) -> BuildabilityClass:
        """
        Classify zone based on average slope.

        Args:
            mean_slope: Average slope in percent

        Returns:
            BuildabilityClass
        """
        if mean_slope <= self.thresholds.excellent_slope_max:
            return BuildabilityClass.EXCELLENT
        elif mean_slope <= self.thresholds.good_slope_max:
            return BuildabilityClass.GOOD
        elif mean_slope <= self.thresholds.difficult_slope_max:
            return BuildabilityClass.DIFFICULT
        else:
            return BuildabilityClass.UNSUITABLE

    def _calculate_zone_quality(
        self,
        area_sqm: float,
        mean_slope: float,
        compactness: float,
        buildability_class: BuildabilityClass,
    ) -> float:
        """
        Calculate overall quality score for a zone (0-100).

        Factors:
        - Size (larger = better)
        - Slope (flatter = better)
        - Compactness (square = better)
        - Buildability class

        Args:
            area_sqm: Zone area in square meters
            mean_slope: Average slope
            compactness: Compactness score
            buildability_class: Buildability classification

        Returns:
            Quality score (0-100)
        """
        # Size score (normalize to reasonable range, cap at 5000 sqm)
        size_score = min(area_sqm / 5000.0, 1.0) * 30.0

        # Slope score (linear from 0% = 40 points to 25% = 0 points)
        slope_score = max(0, (1 - mean_slope / 25.0)) * 40.0

        # Compactness score
        compactness_score = compactness * 20.0

        # Class bonus
        class_bonus = {
            BuildabilityClass.EXCELLENT: 10.0,
            BuildabilityClass.GOOD: 7.0,
            BuildabilityClass.DIFFICULT: 3.0,
            BuildabilityClass.UNSUITABLE: 0.0,
        }[buildability_class]

        total_score = size_score + slope_score + compactness_score + class_bonus
        return min(total_score, 100.0)

    def calculate_overall_quality(
        self,
        zones: List[BuildableZone],
        buildable_percentage: float,
        slope_percent: NDArray[np.floating[Any]],
        buildable_mask: NDArray[np.bool_],
    ) -> float:
        """
        Calculate overall site buildability score (0-100).

        Factors:
        - Total buildable percentage
        - Quality of buildable zones
        - Number of zones (consolidated is better)
        - Average slope in buildable areas

        Args:
            zones: List of buildable zones
            buildable_percentage: Percentage of site that's buildable
            slope_percent: Full slope array
            buildable_mask: Buildable mask

        Returns:
            Overall quality score (0-100)
        """
        if not zones:
            return 0.0

        # Percentage score (0-50% site buildable = 0-30 points)
        percentage_score = min(buildable_percentage / 50.0, 1.0) * 30.0

        # Best zone quality score (0-30 points)
        best_zone_quality = max(z.quality_score for z in zones)
        zone_quality_score = (best_zone_quality / 100.0) * 30.0

        # Consolidation score (fewer zones = better, 0-20 points)
        # 1 zone = 20 points, 5+ zones = 5 points
        num_zones = len(zones)
        consolidation_score = max(20.0 - (num_zones - 1) * 3.0, 5.0)

        # Average slope score (0-20 points)
        buildable_slopes = slope_percent[buildable_mask]
        avg_buildable_slope = float(np.mean(buildable_slopes))
        slope_score = max(0, (1 - avg_buildable_slope / 25.0)) * 20.0

        total_score = (
            percentage_score + zone_quality_score + consolidation_score + slope_score
        )
        return min(total_score, 100.0)

    def _calculate_additional_metrics(
        self,
        zones: List[BuildableZone],
        slope_percent: NDArray[np.floating[Any]],
        elevation: NDArray[np.floating[Any]],
        buildable_mask: NDArray[np.bool_],
    ) -> Dict[str, Any]:
        """
        Calculate additional metrics for the buildability analysis.

        Args:
            zones: List of buildable zones
            slope_percent: Slope array
            elevation: Elevation array
            buildable_mask: Buildable mask

        Returns:
            Dictionary of additional metrics
        """
        metrics = {}

        if zones:
            # Area statistics
            zone_areas = [z.area_sqm for z in zones]
            metrics["largest_zone_area_sqm"] = float(max(zone_areas))
            metrics["smallest_zone_area_sqm"] = float(min(zone_areas))
            metrics["mean_zone_area_sqm"] = float(np.mean(zone_areas))
            metrics["median_zone_area_sqm"] = float(np.median(zone_areas))

            # Slope statistics in buildable areas
            buildable_slopes = slope_percent[buildable_mask]
            metrics["buildable_slope_mean"] = float(np.mean(buildable_slopes))
            metrics["buildable_slope_median"] = float(np.median(buildable_slopes))
            metrics["buildable_slope_max"] = float(np.max(buildable_slopes))
            metrics["buildable_slope_min"] = float(np.min(buildable_slopes))

            # Elevation statistics in buildable areas
            buildable_elevations = elevation[buildable_mask]
            metrics["buildable_elevation_mean"] = float(np.mean(buildable_elevations))
            metrics["buildable_elevation_median"] = float(np.median(buildable_elevations))
            metrics["buildable_elevation_max"] = float(np.max(buildable_elevations))
            metrics["buildable_elevation_min"] = float(np.min(buildable_elevations))

            # Quality statistics
            zone_qualities = [z.quality_score for z in zones]
            metrics["mean_zone_quality"] = float(np.mean(zone_qualities))
            metrics["median_zone_quality"] = float(np.median(zone_qualities))

            # Compactness statistics
            zone_compactness = [z.compactness for z in zones]
            metrics["mean_compactness"] = float(np.mean(zone_compactness))
            metrics["median_compactness"] = float(np.median(zone_compactness))

            # Buildability class distribution
            class_counts = {
                BuildabilityClass.EXCELLENT.value: 0,
                BuildabilityClass.GOOD.value: 0,
                BuildabilityClass.DIFFICULT.value: 0,
                BuildabilityClass.UNSUITABLE.value: 0,
            }
            for zone in zones:
                class_counts[zone.buildability_class.value] += 1

            metrics["buildability_class_distribution"] = class_counts

        return metrics


def analyze_buildability(
    slope_percent: NDArray[np.floating[Any]],
    elevation: NDArray[np.floating[Any]],
    cell_size: float = 1.0,
    thresholds: Optional[BuildabilityThresholds] = None,
    transform: Optional[Any] = None,
    aspect: Optional[NDArray[np.floating[Any]]] = None,
    property_mask: Optional[NDArray[np.bool_]] = None,
) -> BuildabilityResult:
    """
    Convenience function to analyze buildability.

    Args:
        slope_percent: Array of slope values in percent
        elevation: Array of elevation values
        cell_size: Resolution in meters
        thresholds: Optional buildability thresholds
        transform: Optional rasterio transform
        aspect: Optional aspect array
        property_mask: Optional property boundary mask

    Returns:
        BuildabilityResult with comprehensive analysis

    Example:
        >>> import numpy as np
        >>> slope = np.random.uniform(0, 30, (100, 100))
        >>> elevation = np.random.uniform(100, 200, (100, 100))
        >>> result = analyze_buildability(slope, elevation, cell_size=10.0)
        >>> print(f"Buildable: {result.buildable_percentage:.1f}%")
        >>> print(f"Zones: {result.num_zones}")
    """
    analyzer = BuildabilityAnalyzer(cell_size=cell_size, thresholds=thresholds)
    return analyzer.analyze(slope_percent, elevation, transform, aspect, property_mask)

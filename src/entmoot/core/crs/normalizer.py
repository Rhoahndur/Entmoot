"""
CRS normalization service.

This module provides functionality for normalizing geospatial data to a
common coordinate reference system, handling mixed CRS inputs, and
preserving original CRS metadata.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from entmoot.models.crs import BoundingBox, CRSInfo
from entmoot.core.crs.transformer import CRSTransformer, TransformationError
from entmoot.core.crs.utm import get_utm_crs_info


class NormalizationError(Exception):
    """Raised when CRS normalization fails."""
    pass


@dataclass
class NormalizedData:
    """
    Container for normalized geospatial data.

    Attributes:
        coordinates: Normalized coordinates as (x, y) pairs
        target_crs: Target CRS that data was normalized to
        original_crs: Original CRS of the data
        metadata: Additional metadata about normalization
    """

    coordinates: List[Tuple[float, float]]
    target_crs: CRSInfo
    original_crs: CRSInfo
    metadata: Dict[str, any] = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class CRSNormalizer:
    """
    Service for normalizing geospatial data to a common CRS.

    This class handles mixed CRS inputs, determines appropriate target CRS,
    and performs transformations while preserving original metadata.
    """

    def __init__(self, target_crs: Optional[CRSInfo] = None, auto_detect_utm: bool = True):
        """
        Initialize normalizer.

        Args:
            target_crs: Target CRS to normalize to. If None, will be auto-detected.
            auto_detect_utm: If True, auto-detect appropriate UTM zone for accurate measurements
        """
        self.target_crs = target_crs
        self.auto_detect_utm = auto_detect_utm
        self._transformers: Dict[str, CRSTransformer] = {}

    def normalize_coordinates(
        self,
        coordinates: List[Tuple[float, float]],
        source_crs: CRSInfo,
    ) -> NormalizedData:
        """
        Normalize coordinates to target CRS.

        Args:
            coordinates: List of (x, y) coordinate pairs
            source_crs: Source CRS of coordinates

        Returns:
            NormalizedData with transformed coordinates

        Raises:
            NormalizationError: If normalization fails
        """
        if not coordinates:
            raise NormalizationError("No coordinates provided")

        # Determine target CRS if not set
        target = self._get_target_crs(coordinates, source_crs)

        # If source and target are the same, no transformation needed
        if self._are_crs_equal(source_crs, target):
            return NormalizedData(
                coordinates=coordinates,
                target_crs=target,
                original_crs=source_crs,
                metadata={"transformation_applied": False},
            )

        # Get or create transformer
        transformer = self._get_transformer(source_crs, target)

        # Transform coordinates
        try:
            x_coords = [coord[0] for coord in coordinates]
            y_coords = [coord[1] for coord in coordinates]

            x_transformed, y_transformed = transformer.transform_batch(x_coords, y_coords)

            normalized_coords = list(zip(x_transformed.tolist(), y_transformed.tolist()))

            return NormalizedData(
                coordinates=normalized_coords,
                target_crs=target,
                original_crs=source_crs,
                metadata={
                    "transformation_applied": True,
                    "point_count": len(coordinates),
                },
            )

        except TransformationError as e:
            raise NormalizationError(f"Failed to normalize coordinates: {e}")

    def normalize_mixed_inputs(
        self,
        datasets: List[Tuple[List[Tuple[float, float]], CRSInfo]],
    ) -> List[NormalizedData]:
        """
        Normalize multiple datasets with different CRS to common target.

        Args:
            datasets: List of (coordinates, source_crs) tuples

        Returns:
            List of NormalizedData, one per input dataset

        Raises:
            NormalizationError: If normalization fails
        """
        if not datasets:
            raise NormalizationError("No datasets provided")

        # Determine common target CRS if not set
        if self.target_crs is None:
            self._determine_target_from_datasets(datasets)

        # Normalize each dataset
        results = []
        for coordinates, source_crs in datasets:
            try:
                normalized = self.normalize_coordinates(coordinates, source_crs)
                results.append(normalized)
            except NormalizationError as e:
                raise NormalizationError(f"Failed to normalize dataset: {e}")

        return results

    def normalize_bounding_box(
        self,
        bbox: BoundingBox,
    ) -> BoundingBox:
        """
        Normalize a bounding box to target CRS.

        Args:
            bbox: Bounding box to normalize

        Returns:
            Normalized bounding box

        Raises:
            NormalizationError: If normalization fails
        """
        # Determine target CRS if not set
        if self.target_crs is None:
            # Use bounding box center to determine UTM zone
            center_x, center_y = bbox.center
            if self.auto_detect_utm and bbox.crs.is_geographic:
                self.target_crs = get_utm_crs_info(center_x, center_y)
            else:
                self.target_crs = bbox.crs

        # If source and target are the same, no transformation needed
        if self._are_crs_equal(bbox.crs, self.target_crs):
            return bbox

        # Transform bounding box
        transformer = self._get_transformer(bbox.crs, self.target_crs)

        try:
            return transformer.transform_bounds(bbox)
        except TransformationError as e:
            raise NormalizationError(f"Failed to normalize bounding box: {e}")

    def validate_and_normalize(
        self,
        coordinates: List[Tuple[float, float]],
        source_crs: CRSInfo,
        max_error_meters: float = 0.01,
    ) -> NormalizedData:
        """
        Normalize coordinates and validate transformation accuracy.

        Args:
            coordinates: List of (x, y) coordinate pairs
            source_crs: Source CRS
            max_error_meters: Maximum acceptable round-trip error

        Returns:
            NormalizedData with validated transformation

        Raises:
            NormalizationError: If validation fails
        """
        normalized = self.normalize_coordinates(coordinates, source_crs)

        if not normalized.metadata.get("transformation_applied"):
            # No transformation, validation not needed
            return normalized

        # Validate with round-trip transformation
        target = normalized.target_crs
        forward = self._get_transformer(source_crs, target)
        backward = self._get_transformer(target, source_crs)

        # Sample a few points for validation
        sample_size = min(10, len(coordinates))
        sample_indices = np.linspace(0, len(coordinates) - 1, sample_size, dtype=int)

        max_error = 0.0
        for idx in sample_indices:
            x, y = coordinates[idx]

            # Forward transform
            x_t, y_t = forward.transform(x, y)

            # Backward transform
            x_back, y_back = backward.transform(x_t, y_t)

            # Calculate error in meters
            if source_crs.is_geographic:
                error_x = abs(x - x_back) * 111319.9  # meters per degree
                error_y = abs(y - y_back) * 111319.9
            else:
                error_x = abs(x - x_back)
                error_y = abs(y - y_back)

            error = (error_x ** 2 + error_y ** 2) ** 0.5
            max_error = max(max_error, error)

        if max_error > max_error_meters:
            raise NormalizationError(
                f"Transformation accuracy check failed: "
                f"max error {max_error:.6f}m exceeds threshold {max_error_meters}m"
            )

        normalized.metadata["max_round_trip_error_meters"] = max_error
        normalized.metadata["validated"] = True

        return normalized

    def _get_target_crs(
        self,
        coordinates: List[Tuple[float, float]],
        source_crs: CRSInfo,
    ) -> CRSInfo:
        """Determine target CRS if not explicitly set."""
        if self.target_crs is not None:
            return self.target_crs

        # Auto-detect UTM zone if source is geographic
        if self.auto_detect_utm and source_crs.is_geographic:
            # Use first coordinate to determine zone
            if coordinates:
                lon, lat = coordinates[0]
                return get_utm_crs_info(lon, lat)

        # Default to source CRS
        return source_crs

    def _determine_target_from_datasets(
        self,
        datasets: List[Tuple[List[Tuple[float, float]], CRSInfo]],
    ) -> None:
        """Determine common target CRS from multiple datasets."""
        if not datasets:
            return

        # Get all unique CRS
        unique_crs = set()
        for _, crs in datasets:
            crs_key = (crs.epsg, crs.wkt)
            unique_crs.add(crs_key)

        # If all datasets use same CRS, use that
        if len(unique_crs) == 1:
            _, first_crs = datasets[0]
            if self.auto_detect_utm and first_crs.is_geographic:
                # Use first dataset's first coordinate for UTM
                coords, crs = datasets[0]
                if coords:
                    lon, lat = coords[0]
                    self.target_crs = get_utm_crs_info(lon, lat)
                else:
                    self.target_crs = first_crs
            else:
                self.target_crs = first_crs
            return

        # Mixed CRS - determine best target
        # Prefer projected CRS for accuracy
        for _, crs in datasets:
            if not crs.is_geographic:
                self.target_crs = crs
                return

        # All geographic - detect UTM from first dataset
        if self.auto_detect_utm:
            coords, crs = datasets[0]
            if coords:
                lon, lat = coords[0]
                self.target_crs = get_utm_crs_info(lon, lat)
                return

        # Fallback to first dataset's CRS
        _, self.target_crs = datasets[0]

    def _get_transformer(
        self,
        source_crs: CRSInfo,
        target_crs: CRSInfo,
    ) -> CRSTransformer:
        """Get or create transformer for CRS pair."""
        key = f"{source_crs.epsg or source_crs.wkt}_{target_crs.epsg or target_crs.wkt}"

        if key not in self._transformers:
            self._transformers[key] = CRSTransformer(source_crs, target_crs)

        return self._transformers[key]

    def _are_crs_equal(self, crs1: CRSInfo, crs2: CRSInfo) -> bool:
        """Check if two CRS are equivalent."""
        # First check EPSG codes
        if crs1.epsg is not None and crs2.epsg is not None:
            return crs1.epsg == crs2.epsg

        # Check authority and code
        if (
            crs1.authority is not None
            and crs2.authority is not None
            and crs1.code is not None
            and crs2.code is not None
        ):
            return crs1.authority == crs2.authority and crs1.code == crs2.code

        # Compare WKT if available
        if crs1.wkt is not None and crs2.wkt is not None:
            return crs1.wkt == crs2.wkt

        # Cannot determine, assume different
        return False

    def reset(self) -> None:
        """Reset normalizer state and clear cached transformers."""
        self._transformers.clear()


def normalize_to_utm(
    coordinates: List[Tuple[float, float]],
    source_crs: CRSInfo,
    utm_zone: Optional[int] = None,
) -> NormalizedData:
    """
    Normalize coordinates to UTM (convenience function).

    Args:
        coordinates: List of (x, y) coordinate pairs
        source_crs: Source CRS
        utm_zone: Specific UTM zone, or None to auto-detect

    Returns:
        NormalizedData in UTM

    Raises:
        NormalizationError: If normalization fails
    """
    if utm_zone is not None:
        # Use specified UTM zone
        from entmoot.core.crs.utm import get_utm_epsg

        # Assume northern hemisphere if coordinates are positive latitude
        is_northern = coordinates[0][1] >= 0 if coordinates else True
        epsg = get_utm_epsg(utm_zone, is_northern)
        target_crs = CRSInfo.from_epsg(epsg)

        normalizer = CRSNormalizer(target_crs=target_crs, auto_detect_utm=False)
    else:
        # Auto-detect UTM zone
        normalizer = CRSNormalizer(auto_detect_utm=True)

    return normalizer.normalize_coordinates(coordinates, source_crs)


def normalize_to_wgs84(
    coordinates: List[Tuple[float, float]],
    source_crs: CRSInfo,
) -> NormalizedData:
    """
    Normalize coordinates to WGS84 (convenience function).

    Args:
        coordinates: List of (x, y) coordinate pairs
        source_crs: Source CRS

    Returns:
        NormalizedData in WGS84

    Raises:
        NormalizationError: If normalization fails
    """
    wgs84 = CRSInfo.from_epsg(4326)
    normalizer = CRSNormalizer(target_crs=wgs84, auto_detect_utm=False)
    return normalizer.normalize_coordinates(coordinates, source_crs)

"""
Post-grading elevation model.

Generates target elevations for asset footprints including:
- Flat pads for buildings
- Sloped areas for drainage
- Transition slopes
- Road grading with crown and cross-slope
"""

import logging
from typing import List, Optional, Tuple, Any
import numpy as np
from numpy.typing import NDArray

try:
    import rasterio
    from rasterio.transform import Affine
    from rasterio.features import rasterize
    from shapely.geometry import Point, LineString, Polygon
    from shapely.ops import nearest_points
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False

from entmoot.models.earthwork import GradingZone, GradingZoneType
from entmoot.models.terrain import DEMMetadata
from entmoot.core.errors import ValidationError

logger = logging.getLogger(__name__)


class PostGradingModel:
    """
    Post-grading elevation model.

    Generates target elevations for various grading zones including
    building pads, roads, transitions, and drainage features.
    """

    def __init__(
        self,
        metadata: DEMMetadata,
        base_elevation: Optional[NDArray[np.floating[Any]]] = None
    ) -> None:
        """
        Initialize post-grading model.

        Args:
            metadata: DEM metadata for grid dimensions and resolution
            base_elevation: Optional base elevation array (from pre-grading)

        Raises:
            ValidationError: If metadata is invalid
        """
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError(
                "Required dependencies not available. "
                "Install with: pip install rasterio shapely"
            )

        self.metadata = metadata
        self.grading_zones: List[GradingZone] = []

        # Initialize post-grading elevation array
        if base_elevation is not None:
            self.elevation = base_elevation.copy()
        else:
            self.elevation = np.full(
                (metadata.height, metadata.width),
                np.nan,
                dtype=np.float32
            )

        # Track which cells have been graded
        self.graded_mask = np.zeros((metadata.height, metadata.width), dtype=bool)
        self.zone_priority = np.zeros((metadata.height, metadata.width), dtype=np.int32)

        logger.info(
            f"Initialized post-grading model: {metadata.width}x{metadata.height}"
        )

    def add_grading_zone(self, zone: GradingZone) -> None:
        """
        Add a grading zone to the model.

        Args:
            zone: GradingZone to add
        """
        self.grading_zones.append(zone)
        logger.debug(f"Added grading zone: {zone.zone_type.value}")

    def add_building_pad(
        self,
        geometry: Any,
        target_elevation: float,
        transition_slope: float = 3.0,
        priority: int = 10
    ) -> None:
        """
        Add a flat building pad.

        Args:
            geometry: Shapely geometry defining pad boundary
            target_elevation: Target elevation for pad
            transition_slope: Slope for transition to natural (e.g., 3.0 for 3:1)
            priority: Priority (higher wins in overlaps)
        """
        zone = GradingZone(
            zone_type=GradingZoneType.BUILDING_PAD,
            geometry=geometry,
            target_elevation=target_elevation,
            transition_slope=transition_slope,
            priority=priority
        )
        self.add_grading_zone(zone)

    def add_road_corridor(
        self,
        centerline: Any,
        width: float,
        crown_height: float = 0.5,
        cross_slope: float = 2.0,
        priority: int = 8
    ) -> None:
        """
        Add a road corridor with crown and cross-slope.

        Args:
            centerline: LineString defining road centerline
            width: Road width in feet
            crown_height: Crown height in feet
            cross_slope: Cross-slope percentage
            priority: Priority (higher wins in overlaps)
        """
        # Buffer centerline to create road polygon
        geometry = centerline.buffer(width / 2.0)

        zone = GradingZone(
            zone_type=GradingZoneType.ROAD_CORRIDOR,
            geometry=geometry,
            crown_height=crown_height,
            cross_slope=cross_slope,
            priority=priority
        )
        self.add_grading_zone(zone)

    def add_drainage_swale(
        self,
        centerline: Any,
        width: float,
        slope: float,
        direction: float,
        priority: int = 5
    ) -> None:
        """
        Add a drainage swale with positive drainage.

        Args:
            centerline: LineString defining swale centerline
            width: Swale width in feet
            slope: Longitudinal slope percentage
            direction: Flow direction in degrees (0=North)
            priority: Priority (higher wins in overlaps)
        """
        geometry = centerline.buffer(width / 2.0)

        zone = GradingZone(
            zone_type=GradingZoneType.DRAINAGE_SWALE,
            geometry=geometry,
            target_slope=slope,
            slope_direction=direction,
            priority=priority
        )
        self.add_grading_zone(zone)

    def generate_grading(self) -> NDArray[np.floating[Any]]:
        """
        Generate post-grading elevation surface.

        Processes all grading zones in priority order, handling overlaps.

        Returns:
            Post-grading elevation array
        """
        # Sort zones by priority (highest first)
        sorted_zones = sorted(self.grading_zones, key=lambda z: z.priority, reverse=True)

        logger.info(f"Generating grading for {len(sorted_zones)} zones")

        # Process each zone
        for zone in sorted_zones:
            self._apply_grading_zone(zone)

        # Fill any remaining ungraded cells with original elevation
        ungraded = ~self.graded_mask
        if np.any(ungraded) and not np.all(np.isnan(self.elevation)):
            logger.warning(
                f"{np.sum(ungraded)} cells remain ungraded. "
                "Using original elevation."
            )

        logger.info("Grading generation complete")
        return self.elevation

    def _apply_grading_zone(self, zone: GradingZone) -> None:
        """
        Apply a grading zone to the elevation model.

        Args:
            zone: GradingZone to apply
        """
        # Create mask for this zone
        mask = self._create_geometry_mask(zone.geometry)

        # Check priority - only grade if priority is higher or equal
        can_grade = (zone.priority >= self.zone_priority) & mask

        if not np.any(can_grade):
            return

        # Apply grading based on zone type
        if zone.zone_type == GradingZoneType.BUILDING_PAD:
            self._grade_building_pad(zone, can_grade)
        elif zone.zone_type == GradingZoneType.ROAD_CORRIDOR:
            self._grade_road_corridor(zone, can_grade)
        elif zone.zone_type == GradingZoneType.DRAINAGE_SWALE:
            self._grade_drainage_swale(zone, can_grade)
        elif zone.zone_type == GradingZoneType.TRANSITION:
            self._grade_transition(zone, can_grade)

        # Update masks
        self.graded_mask[can_grade] = True
        self.zone_priority[can_grade] = zone.priority

    def _grade_building_pad(
        self,
        zone: GradingZone,
        mask: NDArray[np.bool_]
    ) -> None:
        """
        Grade a flat building pad.

        Args:
            zone: GradingZone for building pad
            mask: Boolean mask of cells to grade
        """
        if zone.target_elevation is None:
            logger.warning("Building pad has no target elevation, skipping")
            return

        # Set elevation to target
        self.elevation[mask] = zone.target_elevation

        logger.debug(
            f"Graded building pad at {zone.target_elevation:.1f} ft, "
            f"{np.sum(mask)} cells"
        )

    def _grade_road_corridor(
        self,
        zone: GradingZone,
        mask: NDArray[np.bool_]
    ) -> None:
        """
        Grade a road corridor with crown and cross-slope.

        Args:
            zone: GradingZone for road
            mask: Boolean mask of cells to grade
        """
        # Get road centerline
        centerline = zone.geometry.centroid  # Simplified - use buffered geometry

        # For each cell in mask, calculate:
        # 1. Distance from centerline
        # 2. Elevation along centerline
        # 3. Cross-slope adjustment

        rows, cols = np.where(mask)

        for row, col in zip(rows, cols):
            # Get cell coordinates
            x, y = self._pixel_to_coords(col, row)
            point = Point(x, y)

            # Find nearest point on centerline (simplified)
            # In practice, would use actual centerline geometry
            # For now, use centroid elevation with cross-slope

            # Calculate distance from center
            center_x = (self.metadata.bounds[0] + self.metadata.bounds[2]) / 2
            center_y = (self.metadata.bounds[1] + self.metadata.bounds[3]) / 2
            dist_from_center = abs(x - center_x) * 3.28084  # Convert to feet

            # Apply crown (higher in center, lower at edges)
            if zone.crown_height > 0:
                # Parabolic crown
                road_width = 24.0  # Assume 24 ft width
                crown_factor = 1.0 - (dist_from_center / (road_width / 2.0)) ** 2
                crown_adjustment = zone.crown_height * max(0, crown_factor)
            else:
                crown_adjustment = 0.0

            # Apply cross-slope
            cross_slope_adjustment = dist_from_center * (zone.cross_slope / 100.0)

            # Base elevation (simplified - use mean of zone)
            base_elev = np.nanmean(self.elevation[mask])
            if np.isnan(base_elev):
                base_elev = 0.0

            # Calculate final elevation
            self.elevation[row, col] = (
                base_elev + crown_adjustment - cross_slope_adjustment
            )

        logger.debug(
            f"Graded road corridor with crown={zone.crown_height:.2f} ft, "
            f"cross-slope={zone.cross_slope:.1f}%, {np.sum(mask)} cells"
        )

    def _grade_drainage_swale(
        self,
        zone: GradingZone,
        mask: NDArray[np.bool_]
    ) -> None:
        """
        Grade a drainage swale with positive drainage.

        Args:
            zone: GradingZone for swale
            mask: Boolean mask of cells to grade
        """
        if zone.target_slope is None or zone.slope_direction is None:
            logger.warning("Drainage swale missing slope or direction, skipping")
            return

        # Get swale geometry
        rows, cols = np.where(mask)

        # Calculate slope direction vector
        slope_rad = np.deg2rad(zone.slope_direction)
        dx = np.sin(slope_rad)
        dy = np.cos(slope_rad)

        # Find reference point (start of swale)
        ref_x = self.metadata.bounds[0]
        ref_y = self.metadata.bounds[1]

        for row, col in zip(rows, cols):
            # Get cell coordinates
            x, y = self._pixel_to_coords(col, row)

            # Calculate distance along slope direction
            dist_along = (x - ref_x) * dx + (y - ref_y) * dy
            dist_along_ft = dist_along * 3.28084  # Convert to feet

            # Apply slope
            slope_drop = dist_along_ft * (zone.target_slope / 100.0)

            # Base elevation at reference point
            base_elev = 100.0  # Simplified - would use actual elevation

            # Calculate final elevation
            self.elevation[row, col] = base_elev - slope_drop

        logger.debug(
            f"Graded drainage swale with slope={zone.target_slope:.2f}%, "
            f"{np.sum(mask)} cells"
        )

    def _grade_transition(
        self,
        zone: GradingZone,
        mask: NDArray[np.bool_]
    ) -> None:
        """
        Grade a transition zone that blends to natural terrain.

        Args:
            zone: GradingZone for transition
            mask: Boolean mask of cells to grade
        """
        # Transition zones blend between graded and natural
        # This is a simplified implementation

        rows, cols = np.where(mask)

        for row, col in zip(rows, cols):
            # Find distance to nearest graded cell
            # Blend elevation based on distance and transition slope

            # Simplified: use average of surrounding graded cells
            neighbors = self._get_neighbors(row, col, 3)
            graded_neighbors = neighbors[self.graded_mask[neighbors[:, 0], neighbors[:, 1]]]

            if len(graded_neighbors) > 0:
                avg_elev = np.mean(
                    self.elevation[graded_neighbors[:, 0], graded_neighbors[:, 1]]
                )
                self.elevation[row, col] = avg_elev
            else:
                # No graded neighbors, skip
                continue

        logger.debug(f"Graded transition zone, {np.sum(mask)} cells")

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

    def _pixel_to_coords(self, col: int, row: int) -> Tuple[float, float]:
        """
        Convert pixel indices to coordinates.

        Args:
            col: Column index
            row: Row index

        Returns:
            Tuple of (x, y) coordinates
        """
        if self.metadata.transform:
            a, b, c, d, e, f = self.metadata.transform
            x = a * col + b * row + c
            y = d * col + e * row + f
        else:
            min_x, min_y, max_x, max_y = self.metadata.bounds
            x = min_x + col * self.metadata.resolution[0]
            y = max_y - row * self.metadata.resolution[1]

        return x, y

    def _get_neighbors(
        self,
        row: int,
        col: int,
        radius: int = 1
    ) -> NDArray[np.integer[Any]]:
        """
        Get neighboring cell indices.

        Args:
            row: Row index
            col: Column index
            radius: Neighborhood radius

        Returns:
            Array of (row, col) indices
        """
        neighbors = []
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if dr == 0 and dc == 0:
                    continue
                r = row + dr
                c = col + dc
                if 0 <= r < self.metadata.height and 0 <= c < self.metadata.width:
                    neighbors.append([r, c])

        return np.array(neighbors)

    def export_surface(self, output_path: str) -> None:
        """
        Export post-grading surface to GeoTIFF.

        Args:
            output_path: Path to output file
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

        logger.info(f"Exported post-grading surface to {output_path}")

    def get_statistics(self) -> dict:
        """
        Get statistics about the post-grading surface.

        Returns:
            Dictionary of statistics
        """
        valid_elevations = self.elevation[~np.isnan(self.elevation)]

        if len(valid_elevations) == 0:
            return {
                "min_elevation": np.nan,
                "max_elevation": np.nan,
                "mean_elevation": np.nan,
                "graded_cells": 0,
                "ungraded_cells": self.metadata.pixel_count,
            }

        return {
            "min_elevation": float(np.min(valid_elevations)),
            "max_elevation": float(np.max(valid_elevations)),
            "mean_elevation": float(np.mean(valid_elevations)),
            "graded_cells": int(np.sum(self.graded_mask)),
            "ungraded_cells": int(self.metadata.pixel_count - np.sum(self.graded_mask)),
            "num_zones": len(self.grading_zones),
        }

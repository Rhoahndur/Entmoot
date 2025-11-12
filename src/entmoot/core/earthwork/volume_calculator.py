"""
Volume calculator for earthwork analysis.

Calculates cut/fill volumes using grid-based methods with support for:
- Shrink/swell factors
- Earthwork balancing
- Cost estimation
- Cross-sections
- Heatmap visualization
"""

import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
from numpy.typing import NDArray

try:
    import rasterio
    from rasterio.transform import Affine
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from entmoot.models.earthwork import (
    VolumeResult,
    SoilProperties,
    SoilType,
    CostDatabase,
    EarthworkCost,
    CrossSection,
    BalancingResult,
)
from entmoot.models.terrain import DEMMetadata
from entmoot.core.errors import ValidationError

logger = logging.getLogger(__name__)


class VolumeCalculator:
    """
    Calculate earthwork volumes and costs.

    Implements grid-based volume calculation with:
    - Cut/fill volume computation
    - Shrink/swell factor application
    - Earthwork balancing optimization
    - Cost estimation
    - Cross-section generation
    - Heatmap visualization
    """

    def __init__(
        self,
        pre_elevation: NDArray[np.floating[Any]],
        post_elevation: NDArray[np.floating[Any]],
        metadata: DEMMetadata,
        soil_properties: Optional[SoilProperties] = None,
        cost_database: Optional[CostDatabase] = None,
    ) -> None:
        """
        Initialize volume calculator.

        Args:
            pre_elevation: Pre-grading elevation array
            post_elevation: Post-grading elevation array
            metadata: DEM metadata with resolution and bounds
            soil_properties: Soil properties for shrink/swell factors
            cost_database: Cost database for estimation

        Raises:
            ValidationError: If arrays are incompatible
        """
        # Rasterio is only needed for GeoTIFF export, not core calculations
        # PIL is only needed for PNG heatmaps

        if pre_elevation.shape != post_elevation.shape:
            raise ValidationError(
                f"Pre/post elevation shapes do not match: "
                f"{pre_elevation.shape} vs {post_elevation.shape}"
            )

        if pre_elevation.shape != (metadata.height, metadata.width):
            raise ValidationError(
                f"Elevation shape {pre_elevation.shape} does not match "
                f"metadata dimensions ({metadata.height}, {metadata.width})"
            )

        self.pre_elevation = pre_elevation
        self.post_elevation = post_elevation
        self.metadata = metadata

        # Soil properties
        if soil_properties is None:
            self.soil_properties = SoilProperties.get_default(SoilType.MIXED)
        else:
            self.soil_properties = soil_properties

        # Cost database
        if cost_database is None:
            self.cost_database = CostDatabase()
        else:
            self.cost_database = cost_database

        # Calculate cut/fill depth
        self.cut_fill_depth = self._calculate_cut_fill_depth()

        # Cell area in square feet
        cell_width_ft = metadata.resolution[0] * 3.28084
        cell_height_ft = metadata.resolution[1] * 3.28084
        self.cell_area_sf = cell_width_ft * cell_height_ft

        logger.info(
            f"Initialized volume calculator: {metadata.width}x{metadata.height}, "
            f"cell area: {self.cell_area_sf:.2f} sq ft"
        )

    def _calculate_cut_fill_depth(self) -> NDArray[np.floating[Any]]:
        """
        Calculate cut/fill depth.

        Positive values = cut (remove material)
        Negative values = fill (add material)

        Returns:
            Cut/fill depth array in feet
        """
        # Cut/fill = pre - post
        # If pre > post, we cut (remove material)
        # If post > pre, we fill (add material)
        cut_fill = self.pre_elevation - self.post_elevation

        # Handle NaN values
        cut_fill = np.where(
            np.isnan(self.pre_elevation) | np.isnan(self.post_elevation),
            0.0,
            cut_fill
        )

        return cut_fill.astype(np.float32)

    def calculate_volumes(
        self,
        apply_shrink_swell: bool = True
    ) -> VolumeResult:
        """
        Calculate cut and fill volumes.

        Args:
            apply_shrink_swell: Whether to apply shrink/swell factors

        Returns:
            VolumeResult with volume calculations
        """
        logger.info("Calculating earthwork volumes...")

        # Separate cut and fill
        cut_mask = self.cut_fill_depth > 0
        fill_mask = self.cut_fill_depth < 0

        # Calculate cut volume (bank cubic yards)
        cut_volume_cf = np.sum(self.cut_fill_depth[cut_mask] * self.cell_area_sf)
        cut_volume_cy = cut_volume_cf / 27.0  # Convert cubic feet to cubic yards

        # Calculate fill volume (loose cubic yards)
        fill_depth = np.abs(self.cut_fill_depth[fill_mask])
        fill_volume_cf = np.sum(fill_depth * self.cell_area_sf)
        fill_volume_cy = fill_volume_cf / 27.0

        # Apply shrink/swell factors if requested
        if apply_shrink_swell:
            # Cut swells when excavated
            cut_volume_loose_cy = cut_volume_cy * self.soil_properties.swell_factor

            # Fill shrinks when compacted
            fill_volume_compacted_cy = fill_volume_cy * self.soil_properties.shrink_factor

            logger.debug(
                f"Applied shrink/swell factors: "
                f"cut={self.soil_properties.swell_factor:.2f}, "
                f"fill={self.soil_properties.shrink_factor:.2f}"
            )
        else:
            cut_volume_loose_cy = cut_volume_cy
            fill_volume_compacted_cy = fill_volume_cy

        # Calculate net volume
        net_volume_cy = cut_volume_loose_cy - fill_volume_compacted_cy

        # Determine import/export
        if net_volume_cy > 0:
            # More cut than fill - export excess
            export_volume_cy = net_volume_cy
            import_volume_cy = 0.0
            balanced_volume_cy = fill_volume_compacted_cy
        else:
            # More fill than cut - import deficit
            import_volume_cy = abs(net_volume_cy)
            export_volume_cy = 0.0
            balanced_volume_cy = cut_volume_loose_cy

        # Calculate areas
        cut_area_sf = np.sum(cut_mask) * self.cell_area_sf
        fill_area_sf = np.sum(fill_mask) * self.cell_area_sf

        # Calculate average depths
        if np.any(cut_mask):
            average_cut_depth_ft = float(np.mean(self.cut_fill_depth[cut_mask]))
        else:
            average_cut_depth_ft = 0.0

        if np.any(fill_mask):
            average_fill_depth_ft = float(np.mean(np.abs(self.cut_fill_depth[fill_mask])))
        else:
            average_fill_depth_ft = 0.0

        result = VolumeResult(
            cut_volume_cy=float(cut_volume_cy),
            fill_volume_cy=float(fill_volume_cy),
            net_volume_cy=float(net_volume_cy),
            balanced_volume_cy=float(balanced_volume_cy),
            import_volume_cy=float(import_volume_cy),
            export_volume_cy=float(export_volume_cy),
            cut_area_sf=float(cut_area_sf),
            fill_area_sf=float(fill_area_sf),
            average_cut_depth_ft=average_cut_depth_ft,
            average_fill_depth_ft=average_fill_depth_ft,
        )

        logger.info(
            f"Volumes calculated: Cut={cut_volume_cy:.0f} CY, "
            f"Fill={fill_volume_cy:.0f} CY, Net={net_volume_cy:.0f} CY"
        )

        return result

    def calculate_costs(
        self,
        volume_result: VolumeResult,
        average_haul_distance_miles: float = 0.25
    ) -> EarthworkCost:
        """
        Calculate earthwork costs.

        Args:
            volume_result: VolumeResult from calculate_volumes()
            average_haul_distance_miles: Average haul distance in miles

        Returns:
            EarthworkCost with detailed breakdown
        """
        logger.info("Calculating earthwork costs...")

        # Excavation cost
        excavation_cost = (
            volume_result.cut_volume_cy * self.cost_database.excavation_cost_cy
        )

        # Fill placement cost
        fill_cost = (
            volume_result.fill_volume_cy * self.cost_database.fill_cost_cy
        )

        # Haul cost (for balanced volume)
        haul_cost = (
            volume_result.balanced_volume_cy *
            average_haul_distance_miles *
            self.cost_database.haul_cost_cy_mile
        )

        # Import cost
        import_cost = (
            volume_result.import_volume_cy * self.cost_database.import_cost_cy
        )

        # Export cost
        export_cost = (
            volume_result.export_volume_cy * self.cost_database.export_cost_cy
        )

        # Compaction cost
        compaction_cost = (
            volume_result.fill_volume_cy * self.cost_database.compaction_cost_cy
        )

        # Total cost
        total_cost = (
            excavation_cost +
            fill_cost +
            haul_cost +
            import_cost +
            export_cost +
            compaction_cost
        )

        # Cost breakdown
        cost_breakdown = {
            "excavation": excavation_cost,
            "fill_placement": fill_cost,
            "haul": haul_cost,
            "import": import_cost,
            "export": export_cost,
            "compaction": compaction_cost,
        }

        result = EarthworkCost(
            excavation_cost=excavation_cost,
            fill_cost=fill_cost,
            haul_cost=haul_cost,
            import_cost=import_cost,
            export_cost=export_cost,
            compaction_cost=compaction_cost,
            total_cost=total_cost,
            cost_breakdown=cost_breakdown,
        )

        logger.info(f"Total earthwork cost: ${total_cost:,.2f}")

        return result

    def calculate_balancing(self) -> BalancingResult:
        """
        Calculate earthwork balancing optimization.

        Returns:
            BalancingResult with balancing recommendations
        """
        logger.info("Calculating earthwork balancing...")

        # Calculate volumes
        volume_result = self.calculate_volumes(apply_shrink_swell=True)

        # Calculate balance ratio
        if volume_result.cut_volume_cy > 0:
            balance_ratio = volume_result.fill_volume_cy / volume_result.cut_volume_cy
        else:
            balance_ratio = 0.0

        # Determine if balanced (within 10%)
        is_balanced = 0.9 <= balance_ratio <= 1.1

        # Estimate optimal haul distance
        # This is simplified - in practice would use actual cut/fill zones
        cut_mask = self.cut_fill_depth > 0
        fill_mask = self.cut_fill_depth < 0

        if np.any(cut_mask) and np.any(fill_mask):
            # Find centroid of cut and fill zones
            cut_rows, cut_cols = np.where(cut_mask)
            fill_rows, fill_cols = np.where(fill_mask)

            cut_centroid = (np.mean(cut_rows), np.mean(cut_cols))
            fill_centroid = (np.mean(fill_rows), np.mean(fill_cols))

            # Calculate distance
            dr = cut_centroid[0] - fill_centroid[0]
            dc = cut_centroid[1] - fill_centroid[1]
            pixel_dist = np.sqrt(dr**2 + dc**2)

            # Convert to feet
            dist_ft = pixel_dist * self.metadata.resolution[0] * 3.28084
            optimal_haul_distance = dist_ft / 5280.0  # Convert to miles
        else:
            optimal_haul_distance = 0.0

        # Generate recommendations
        recommendations = []

        if not is_balanced:
            if balance_ratio < 0.9:
                deficit_cy = volume_result.import_volume_cy
                recommendations.append(
                    f"Import {deficit_cy:.0f} CY of material to balance earthwork"
                )
                recommendations.append(
                    "Consider raising finished grades to reduce fill requirement"
                )
            else:
                excess_cy = volume_result.export_volume_cy
                recommendations.append(
                    f"Export {excess_cy:.0f} CY of material or stockpile on-site"
                )
                recommendations.append(
                    "Consider lowering finished grades to reduce cut requirement"
                )
        else:
            recommendations.append("Earthwork is well-balanced")

        if optimal_haul_distance > 0.5:
            recommendations.append(
                f"Average haul distance is {optimal_haul_distance:.2f} miles. "
                "Consider relocating cut/fill zones to reduce haul costs."
            )

        result = BalancingResult(
            is_balanced=is_balanced,
            balance_ratio=balance_ratio,
            optimal_haul_distance=optimal_haul_distance,
            recommendations=recommendations,
        )

        logger.info(
            f"Balancing analysis complete: "
            f"ratio={balance_ratio:.2f}, balanced={is_balanced}"
        )

        return result

    def generate_cross_section(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        num_points: int = 100
    ) -> CrossSection:
        """
        Generate a cross-section through the terrain.

        Args:
            start: (x, y) starting coordinates
            end: (x, y) ending coordinates
            num_points: Number of sample points

        Returns:
            CrossSection object
        """
        logger.debug(f"Generating cross-section from {start} to {end}")

        # Create points along the line
        x_coords = np.linspace(start[0], end[0], num_points)
        y_coords = np.linspace(start[1], end[1], num_points)

        # Calculate distance from start
        dx = x_coords - start[0]
        dy = y_coords - start[1]
        distance = np.sqrt(dx**2 + dy**2) * 3.28084  # Convert to feet

        # Sample elevations
        pre_elevation = np.zeros(num_points)
        post_elevation = np.zeros(num_points)

        for i in range(num_points):
            col, row = self._coords_to_pixel(x_coords[i], y_coords[i])

            if 0 <= row < self.metadata.height and 0 <= col < self.metadata.width:
                pre_elevation[i] = self.pre_elevation[row, col]
                post_elevation[i] = self.post_elevation[row, col]
            else:
                pre_elevation[i] = np.nan
                post_elevation[i] = np.nan

        # Calculate cut/fill
        cut_fill = pre_elevation - post_elevation

        # Calculate section volume (simplified - use average end area)
        # In practice, would integrate along the section
        section_area = np.nanmean(np.abs(cut_fill)) * distance[-1]
        section_volume_cy = section_area / 27.0  # Rough estimate

        return CrossSection(
            start_point=start,
            end_point=end,
            distance=distance,
            pre_elevation=pre_elevation,
            post_elevation=post_elevation,
            cut_fill=cut_fill,
            section_volume_cy=section_volume_cy,
        )

    def generate_heatmap(
        self,
        output_path: str,
        format: str = "geotiff",
        color_range: Tuple[float, float] = (-10.0, 10.0)
    ) -> None:
        """
        Generate cut/fill heatmap.

        Args:
            output_path: Path to output file
            format: Output format ("geotiff" or "png")
            color_range: Range for color mapping (min_fill, max_cut) in feet
        """
        logger.info(f"Generating {format} heatmap: {output_path}")

        if format.lower() == "geotiff":
            self._generate_geotiff_heatmap(output_path)
        elif format.lower() == "png":
            self._generate_png_heatmap(output_path, color_range)
        else:
            raise ValidationError(f"Unsupported format: {format}")

    def _generate_geotiff_heatmap(self, output_path: str) -> None:
        """Generate GeoTIFF heatmap with cut/fill values."""
        if not RASTERIO_AVAILABLE:
            raise ImportError("rasterio is required for GeoTIFF export")

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
            dtype=np.float32,
            crs=self.metadata.crs.to_string() if self.metadata.crs else None,
            transform=transform,
            nodata=0.0,
        ) as dst:
            dst.write(self.cut_fill_depth, 1)

        logger.info(f"Exported GeoTIFF heatmap to {output_path}")

    def _generate_png_heatmap(
        self,
        output_path: str,
        color_range: Tuple[float, float]
    ) -> None:
        """Generate PNG heatmap with color visualization."""
        if not PIL_AVAILABLE:
            raise ImportError("Pillow is required for PNG export")

        min_val, max_val = color_range

        # Normalize cut/fill to 0-255
        normalized = np.clip(self.cut_fill_depth, min_val, max_val)
        normalized = ((normalized - min_val) / (max_val - min_val) * 255).astype(np.uint8)

        # Create RGB image
        # Red = cut, Blue = fill, Green = balanced
        rgb = np.zeros((self.metadata.height, self.metadata.width, 3), dtype=np.uint8)

        # Cut (positive) = Red
        cut_mask = self.cut_fill_depth > 0.5
        rgb[cut_mask, 0] = normalized[cut_mask]  # Red channel

        # Fill (negative) = Blue
        fill_mask = self.cut_fill_depth < -0.5
        rgb[fill_mask, 2] = 255 - normalized[fill_mask]  # Blue channel

        # Balanced (near zero) = Green
        balanced_mask = np.abs(self.cut_fill_depth) <= 0.5
        rgb[balanced_mask, 1] = 128  # Green channel

        # Create and save image
        img = Image.fromarray(rgb, mode='RGB')
        img.save(output_path)

        logger.info(f"Exported PNG heatmap to {output_path}")

    def _coords_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """Convert coordinates to pixel indices."""
        if self.metadata.transform:
            a, b, c, d, e, f = self.metadata.transform
            col = int((x - c) / a)
            row = int((y - f) / e)
        else:
            min_x, min_y, max_x, max_y = self.metadata.bounds
            col = int((x - min_x) / self.metadata.resolution[0])
            row = int((max_y - y) / self.metadata.resolution[1])

        return col, row

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of earthwork analysis.

        Returns:
            Dictionary with volumes, costs, and balancing info
        """
        volume_result = self.calculate_volumes(apply_shrink_swell=True)
        cost_result = self.calculate_costs(volume_result)
        balancing_result = self.calculate_balancing()

        return {
            "volumes": volume_result.to_dict(),
            "costs": cost_result.to_dict(),
            "balancing": balancing_result.to_dict(),
            "soil_type": self.soil_properties.soil_type.value,
        }

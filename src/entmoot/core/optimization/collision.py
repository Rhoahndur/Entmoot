"""
Collision detection for asset placement validation.

This module provides fast collision detection using bounding boxes and
spatial indexing (R-tree) for efficient queries on large sites.
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from shapely.geometry.base import BaseGeometry
from shapely.geometry import box, Point
from shapely import STRtree

from entmoot.models.asset import AssetType, PlacedAsset, get_required_spacing


class ViolationType(str, Enum):
    """Types of constraint violations."""

    COLLISION = "collision"  # Direct overlap between assets
    SPACING_VIOLATION = "spacing_violation"  # Insufficient spacing
    OUT_OF_BOUNDS = "out_of_bounds"  # Asset outside property boundary
    EXCLUSION_ZONE = "exclusion_zone"  # Asset in exclusion zone
    SLOPE_VIOLATION = "slope_violation"  # Asset on steep slope
    SETBACK_VIOLATION = "setback_violation"  # Asset violates setback


@dataclass
class Violation:
    """
    Represents a constraint or collision violation.

    Attributes:
        violation_type: Type of violation
        asset_id: ID of the asset with the violation
        description: Human-readable description
        severity: Severity level (blocking, warning, info)
        conflicting_asset_id: ID of conflicting asset (if applicable)
        distance_m: Actual distance (for spacing violations)
        required_distance_m: Required distance (for spacing violations)
    """

    violation_type: ViolationType
    asset_id: str
    description: str
    severity: str = "blocking"
    conflicting_asset_id: Optional[str] = None
    distance_m: Optional[float] = None
    required_distance_m: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert violation to dictionary."""
        result = {
            "violation_type": self.violation_type.value,
            "asset_id": self.asset_id,
            "description": self.description,
            "severity": self.severity,
        }
        if self.conflicting_asset_id:
            result["conflicting_asset_id"] = self.conflicting_asset_id
        if self.distance_m is not None:
            result["distance_m"] = self.distance_m
        if self.required_distance_m is not None:
            result["required_distance_m"] = self.required_distance_m
        return result


@dataclass
class ValidationResult:
    """
    Result of asset placement validation.

    Attributes:
        is_valid: Whether placement is valid
        violations: List of violations found
        warnings: List of non-blocking warnings
    """

    is_valid: bool
    violations: List[Violation]
    warnings: List[str]

    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return {
            "is_valid": self.is_valid,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
        }


class CollisionDetector:
    """
    Fast collision detection for asset placement validation.

    Uses bounding boxes for fast pre-checks and STRtree spatial indexing
    for O(log n) queries on large sites.

    Attributes:
        assets: Dictionary of placed assets by ID
        spatial_index: STRtree spatial index for fast queries
        spacing_rules: Custom spacing rules
    """

    def __init__(
        self,
        spacing_rules: Optional[Dict[Tuple[AssetType, AssetType], float]] = None
    ):
        """
        Initialize collision detector.

        Args:
            spacing_rules: Optional custom spacing rules
        """
        self.assets: Dict[str, PlacedAsset] = {}
        self.spatial_index: Optional[STRtree] = None
        self.spacing_rules = spacing_rules
        self._needs_rebuild = False
        self._indexed_geometries: List[BaseGeometry] = []  # Geometries in the index
        self._indexed_asset_ids: List[str] = []  # Corresponding asset IDs

    def add_asset(self, asset: PlacedAsset) -> None:
        """
        Add an asset to the collision detector.

        Args:
            asset: Asset to add
        """
        self.assets[asset.id] = asset
        self._needs_rebuild = True

    def remove_asset(self, asset_id: str) -> None:
        """
        Remove an asset from the collision detector.

        Args:
            asset_id: ID of asset to remove
        """
        if asset_id in self.assets:
            del self.assets[asset_id]
            self._needs_rebuild = True

    def clear(self) -> None:
        """Clear all assets from the detector."""
        self.assets.clear()
        self.spatial_index = None
        self._needs_rebuild = False

    def _rebuild_index(self) -> None:
        """Rebuild the spatial index."""
        if not self.assets:
            self.spatial_index = None
            self._indexed_geometries.clear()
            self._indexed_asset_ids.clear()
            self._needs_rebuild = False
            return

        if not self._needs_rebuild:
            return

        # Create list of geometries with their asset IDs
        self._indexed_geometries.clear()
        self._indexed_asset_ids.clear()

        for asset_id, asset in self.assets.items():
            geom = asset.get_geometry()
            self._indexed_geometries.append(geom)
            self._indexed_asset_ids.append(asset_id)

        # Build STRtree index
        if self._indexed_geometries:
            self.spatial_index = STRtree(self._indexed_geometries)
        else:
            self.spatial_index = None

        self._needs_rebuild = False

    def check_bounding_box_collision(
        self,
        asset1: PlacedAsset,
        asset2: PlacedAsset
    ) -> bool:
        """
        Fast bounding box collision check.

        Args:
            asset1: First asset
            asset2: Second asset

        Returns:
            True if bounding boxes intersect
        """
        bounds1 = asset1.get_bounds()
        bounds2 = asset2.get_bounds()

        # Check if bounding boxes intersect
        # bounds format: (minx, miny, maxx, maxy)
        # Use <= to handle touching edges as not colliding
        return not (
            bounds1[2] <= bounds2[0] or  # asset1 is left of asset2
            bounds1[0] >= bounds2[2] or  # asset1 is right of asset2
            bounds1[3] <= bounds2[1] or  # asset1 is below asset2
            bounds1[1] >= bounds2[3]     # asset1 is above asset2
        )

    def check_precise_collision(
        self,
        asset1: PlacedAsset,
        asset2: PlacedAsset
    ) -> bool:
        """
        Precise polygon-polygon collision check using Shapely.

        Args:
            asset1: First asset
            asset2: Second asset

        Returns:
            True if assets actually intersect
        """
        geom1 = asset1.get_geometry()
        geom2 = asset2.get_geometry()
        return geom1.intersects(geom2)

    def check_spacing(
        self,
        asset1: PlacedAsset,
        asset2: PlacedAsset
    ) -> Tuple[bool, float, float]:
        """
        Check if spacing between assets is sufficient.

        Args:
            asset1: First asset
            asset2: Second asset

        Returns:
            Tuple of (is_valid, actual_distance, required_distance)
        """
        # Get required spacing
        required_spacing = get_required_spacing(
            asset1.asset_type,
            asset2.asset_type,
            self.spacing_rules
        )

        # Also consider asset-specific minimum spacing
        required_spacing = max(
            required_spacing,
            asset1.min_spacing_m,
            asset2.min_spacing_m
        )

        if required_spacing == 0:
            return (True, 0.0, 0.0)

        # Calculate actual distance
        geom1 = asset1.get_geometry()
        geom2 = asset2.get_geometry()
        actual_distance = geom1.distance(geom2)

        is_valid = actual_distance >= required_spacing

        return (is_valid, actual_distance, required_spacing)

    def check_collision_with_asset(
        self,
        new_asset: PlacedAsset,
        existing_asset: PlacedAsset
    ) -> Optional[Violation]:
        """
        Check collision between new asset and existing asset.

        Args:
            new_asset: Asset being placed
            existing_asset: Existing asset to check against

        Returns:
            Violation if found, None otherwise
        """
        # Fast bounding box check for overlap
        if self.check_bounding_box_collision(new_asset, existing_asset):
            # Check precise collision if bounding boxes overlap
            if self.check_precise_collision(new_asset, existing_asset):
                return Violation(
                    violation_type=ViolationType.COLLISION,
                    asset_id=new_asset.id,
                    description=f"Asset collides with {existing_asset.name}",
                    severity="blocking",
                    conflicting_asset_id=existing_asset.id,
                )

        # Always check spacing requirements (even if no overlap)
        is_valid, actual_dist, required_dist = self.check_spacing(
            new_asset, existing_asset
        )

        if not is_valid:
            return Violation(
                violation_type=ViolationType.SPACING_VIOLATION,
                asset_id=new_asset.id,
                description=(
                    f"Insufficient spacing to {existing_asset.name}: "
                    f"{actual_dist:.2f}m (required: {required_dist:.2f}m)"
                ),
                severity="blocking",
                conflicting_asset_id=existing_asset.id,
                distance_m=actual_dist,
                required_distance_m=required_dist,
            )

        return None

    def find_potential_collisions(
        self,
        asset: PlacedAsset,
        buffer_distance: float = 0.0
    ) -> List[PlacedAsset]:
        """
        Find assets that potentially collide with given asset using spatial index.

        Args:
            asset: Asset to check
            buffer_distance: Optional buffer distance to expand search

        Returns:
            List of potentially colliding assets
        """
        # Rebuild index if needed
        if self._needs_rebuild:
            self._rebuild_index()

        # If no spatial index, check all assets
        if self.spatial_index is None:
            return [a for a in self.assets.values() if a.id != asset.id]

        # Query spatial index
        query_geom = asset.get_buffered_geometry(buffer_distance)

        # Find candidates using spatial index
        # STRtree.query() returns array of indices
        candidates = []
        result_indices = self.spatial_index.query(query_geom)

        # Map indices back to assets
        for idx in result_indices:
            asset_id = self._indexed_asset_ids[idx]
            if asset_id != asset.id:
                candidate = self.assets.get(asset_id)
                if candidate:
                    candidates.append(candidate)

        return candidates

    def check_collisions(
        self,
        asset: PlacedAsset,
        exclude_ids: Optional[Set[str]] = None
    ) -> List[Violation]:
        """
        Check for collisions between asset and all existing assets.

        Args:
            asset: Asset to check
            exclude_ids: Optional set of asset IDs to exclude from checks

        Returns:
            List of violations found
        """
        violations = []
        exclude_ids = exclude_ids or set()

        # Get maximum spacing requirement to determine search buffer
        max_spacing = max(
            [
                get_required_spacing(asset.asset_type, other.asset_type, self.spacing_rules)
                for other in self.assets.values()
                if other.id not in exclude_ids and other.id != asset.id
            ] + [asset.min_spacing_m, 0.0]
        )

        # Find potential collisions using spatial index
        candidates = self.find_potential_collisions(asset, buffer_distance=max_spacing)

        # Check each candidate
        for candidate in candidates:
            if candidate.id in exclude_ids or candidate.id == asset.id:
                continue

            violation = self.check_collision_with_asset(asset, candidate)
            if violation:
                violations.append(violation)

        return violations

    def validate_placement(
        self,
        asset: PlacedAsset,
        site_boundary: Optional[BaseGeometry] = None,
        exclusion_zones: Optional[List[BaseGeometry]] = None,
        buildable_area: Optional[BaseGeometry] = None,
        max_slope: Optional[float] = None,
        slope_raster: Optional[any] = None,
    ) -> ValidationResult:
        """
        Comprehensive validation of asset placement.

        Args:
            asset: Asset to validate
            site_boundary: Optional site boundary polygon
            exclusion_zones: Optional list of exclusion zone polygons
            buildable_area: Optional buildable area polygon
            max_slope: Optional maximum allowed slope in degrees
            slope_raster: Optional slope raster for slope validation

        Returns:
            ValidationResult with all violations and warnings
        """
        violations = []
        warnings = []

        # Check within property boundary
        if site_boundary is not None:
            asset_geom = asset.get_geometry()
            if not site_boundary.contains(asset_geom):
                if not asset_geom.intersects(site_boundary):
                    violations.append(
                        Violation(
                            violation_type=ViolationType.OUT_OF_BOUNDS,
                            asset_id=asset.id,
                            description="Asset is completely outside property boundary",
                            severity="blocking",
                        )
                    )
                else:
                    # Partially outside
                    intersection = asset_geom.intersection(site_boundary)
                    overlap_pct = (intersection.area / asset_geom.area) * 100
                    if overlap_pct < 90:
                        violations.append(
                            Violation(
                                violation_type=ViolationType.OUT_OF_BOUNDS,
                                asset_id=asset.id,
                                description=f"Asset extends outside boundary ({100-overlap_pct:.1f}% outside)",
                                severity="blocking",
                            )
                        )
                    else:
                        warnings.append(
                            f"Asset slightly extends outside boundary ({100-overlap_pct:.1f}% outside)"
                        )

        # Check buildable area
        if buildable_area is not None:
            asset_geom = asset.get_geometry()
            if not buildable_area.contains(asset_geom):
                violations.append(
                    Violation(
                        violation_type=ViolationType.SETBACK_VIOLATION,
                        asset_id=asset.id,
                        description="Asset is not within buildable area",
                        severity="blocking",
                    )
                )

        # Check exclusion zones
        if exclusion_zones:
            asset_geom = asset.get_geometry()
            for i, zone in enumerate(exclusion_zones):
                if zone.intersects(asset_geom):
                    violations.append(
                        Violation(
                            violation_type=ViolationType.EXCLUSION_ZONE,
                            asset_id=asset.id,
                            description=f"Asset intersects exclusion zone {i+1}",
                            severity="blocking",
                        )
                    )

        # Check slope constraints
        if max_slope is not None and slope_raster is not None:
            # Sample slope at asset location
            # This is simplified - real implementation would sample the raster
            warnings.append("Slope validation not fully implemented")

        # Check collisions with other assets
        collision_violations = self.check_collisions(asset)
        violations.extend(collision_violations)

        # Determine overall validity
        is_valid = len(violations) == 0

        return ValidationResult(
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
        )

    def validate_multiple_placements(
        self,
        assets: List[PlacedAsset],
        site_boundary: Optional[BaseGeometry] = None,
        exclusion_zones: Optional[List[BaseGeometry]] = None,
        buildable_area: Optional[BaseGeometry] = None,
    ) -> Dict[str, ValidationResult]:
        """
        Validate multiple asset placements.

        Args:
            assets: List of assets to validate
            site_boundary: Optional site boundary polygon
            exclusion_zones: Optional list of exclusion zone polygons
            buildable_area: Optional buildable area polygon

        Returns:
            Dictionary mapping asset IDs to validation results
        """
        results = {}

        # Add all assets to the detector
        for asset in assets:
            if asset.id not in self.assets:
                self.add_asset(asset)

        # Validate each asset
        for asset in assets:
            result = self.validate_placement(
                asset=asset,
                site_boundary=site_boundary,
                exclusion_zones=exclusion_zones,
                buildable_area=buildable_area,
            )
            results[asset.id] = result

        return results

    def get_clearance_zone(
        self,
        asset: PlacedAsset,
        clearance_distance: float
    ) -> BaseGeometry:
        """
        Get clearance zone around an asset.

        Args:
            asset: Asset to get clearance zone for
            clearance_distance: Distance to buffer

        Returns:
            Buffered geometry representing clearance zone
        """
        return asset.get_buffered_geometry(clearance_distance)

    def check_minimum_spacing_violations(self) -> List[Violation]:
        """
        Check all assets for minimum spacing violations.

        Returns:
            List of spacing violations found
        """
        violations = []
        asset_list = list(self.assets.values())

        # Check each pair of assets
        for i, asset1 in enumerate(asset_list):
            for asset2 in asset_list[i + 1:]:
                is_valid, actual_dist, required_dist = self.check_spacing(
                    asset1, asset2
                )

                if not is_valid:
                    violations.append(
                        Violation(
                            violation_type=ViolationType.SPACING_VIOLATION,
                            asset_id=asset1.id,
                            description=(
                                f"Insufficient spacing between {asset1.name} and "
                                f"{asset2.name}: {actual_dist:.2f}m "
                                f"(required: {required_dist:.2f}m)"
                            ),
                            severity="blocking",
                            conflicting_asset_id=asset2.id,
                            distance_m=actual_dist,
                            required_distance_m=required_dist,
                        )
                    )

        return violations

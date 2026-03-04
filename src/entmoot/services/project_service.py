"""
Project service — business logic for project results and validation.

Extracted from api/projects.py to keep route handlers thin.
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from shapely.geometry import Polygon as ShapelyPolygon, Point

from entmoot.models.project import (
    Bounds,
    BuildableArea,
    Coordinate,
    ConstraintViolation,
    CostBreakdown,
    EarthworkVolumes,
    LayoutAlternative,
    LayoutMetrics,
    LayoutResults,
    OptimizationResults,
    RoadNetwork,
)

logger = logging.getLogger(__name__)

# Approximate conversions (mid-latitude US)
LAT_PER_FOOT = 1 / 364000
LNG_PER_FOOT = 1 / 288200


class ProjectService:
    """Stateless helpers for project result assembly and validation."""

    # ------------------------------------------------------------------
    # Weight validation (was duplicated in create_project / reoptimize)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_weights(
        cost: float,
        buildable_area: float,
        accessibility: float,
        environmental_impact: float,
        aesthetics: float,
    ) -> Optional[str]:
        """Return an error message if weights do not sum to 100, else ``None``."""
        total = cost + buildable_area + accessibility + environmental_impact + aesthetics
        if abs(total - 100) > 0.01:
            return f"Optimization weights must sum to 100%, got {total}%"
        return None

    # ------------------------------------------------------------------
    # Result assembly (was the 230-line body of get_layout_results)
    # ------------------------------------------------------------------

    @staticmethod
    def build_optimization_results(
        project: Dict[str, Any],
        layout_results: LayoutResults,
        project_id: str,
    ) -> OptimizationResults:
        """Assemble the full ``OptimizationResults`` response from stored data."""

        property_boundary_coords: List[Dict[str, float]] = project.get(
            "property_boundary", []
        )
        bounds_data: Dict[str, float] = project.get("bounds", {})

        # Road network
        total_road_length = sum(seg.length for seg in layout_results.road_network)
        intersections = ProjectService._compute_road_intersections(
            layout_results.road_network
        )
        road_network = RoadNetwork(
            segments=layout_results.road_network,
            total_length=total_road_length,
            intersections=intersections,
        )

        # Constraint violations
        violations = ProjectService._detect_constraint_violations(
            layout_results.placed_assets, property_boundary_coords
        )

        # Constraint / buildable zones
        constraint_zones = ProjectService._compute_constraint_zones(
            property_boundary_coords,
            setback_ft=project.get("config", {})
            .get("constraints", {})
            .get("setback_distance", 20),
        )
        buildable_areas = ProjectService._compute_buildable_areas(
            property_boundary_coords,
            setback_ft=project.get("config", {})
            .get("constraints", {})
            .get("setback_distance", 20),
        )

        # Metrics
        earthwork_cost = layout_results.earthwork.estimated_cost
        road_cost = total_road_length * 100
        base_cost = layout_results.total_cost / 1.1
        asset_cost = max(0.0, base_cost - earthwork_cost - road_cost)
        contingency_cost = layout_results.total_cost * 0.1

        metrics = LayoutMetrics(
            property_area=project.get("property_area", 0.0),
            buildable_area=project.get("buildable_area", 0.0),
            buildable_percentage=layout_results.buildable_area_used,
            assets_placed=len(layout_results.placed_assets),
            total_road_length=total_road_length,
            earthwork_volumes=EarthworkVolumes(
                cut=layout_results.earthwork.total_cut_volume,
                fill=layout_results.earthwork.total_fill_volume,
                net=layout_results.earthwork.net_volume,
                balance_ratio=(
                    layout_results.earthwork.total_cut_volume
                    / layout_results.earthwork.total_fill_volume
                    if layout_results.earthwork.total_fill_volume > 0
                    else 0.0
                ),
            ),
            estimated_cost=CostBreakdown(
                earthwork=earthwork_cost,
                roads=road_cost,
                utilities=asset_cost,
                drainage=0.0,
                landscaping=0.0,
                contingency=contingency_cost,
                total=layout_results.total_cost,
            ),
            constraint_violations=0 if layout_results.constraints_satisfied else 1,
            optimization_score=layout_results.fitness_score * 100,
        )

        alternative = LayoutAlternative(
            id="alt-1",
            name="Optimized Layout",
            description="AI-generated optimized site layout",
            metrics=metrics,
            assets=layout_results.placed_assets,
            road_network=road_network,
            constraint_zones=constraint_zones,
            buildable_areas=buildable_areas,
            earthwork_zones=[],
            violations=violations,
            created_at=project.get("created_at", datetime.utcnow().isoformat()),
        )

        return OptimizationResults(
            project_id=project_id,
            project_name=project.get("project_name", "Unnamed Project"),
            property_boundary=property_boundary_coords,
            bounds=(
                Bounds(**bounds_data)
                if bounds_data
                else Bounds(north=0, south=0, east=0, west=0)
            ),
            alternatives=[alternative],
            selected_alternative_id="alt-1",
            created_at=project.get("created_at", datetime.utcnow().isoformat()),
            updated_at=project.get("updated_at", datetime.utcnow().isoformat()),
        )

    # ------------------------------------------------------------------
    # Constraint violation detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_constraint_violations(
        placed_assets: list,
        property_boundary_coords: List[Dict[str, float]],
    ) -> List[ConstraintViolation]:
        """Check every asset for overlaps and boundary breaches."""
        violations: List[ConstraintViolation] = []

        asset_polys = []
        for asset in placed_assets:
            poly = ProjectService._asset_polygon(asset)
            asset_polys.append((asset, poly))

        for i, (asset, asset_poly) in enumerate(asset_polys):
            # Check overlaps with subsequent assets
            for j in range(i + 1, len(asset_polys)):
                other_asset, other_poly = asset_polys[j]
                if asset_poly.intersects(other_poly):
                    overlap_area = asset_poly.intersection(other_poly).area
                    overlap_sqft = overlap_area / (LAT_PER_FOOT * LNG_PER_FOOT)
                    violations.append(
                        ConstraintViolation(
                            asset_id=asset.id,
                            constraint_type="setback",
                            severity="error",
                            message=(
                                f"Asset overlaps with another asset "
                                f"(overlap: {overlap_sqft:.0f} sq ft)"
                            ),
                        )
                    )

            # Check site boundary
            if property_boundary_coords:
                try:
                    boundary_poly = ShapelyPolygon(
                        [
                            (p["longitude"], p["latitude"])
                            for p in property_boundary_coords
                        ]
                    )
                    if not boundary_poly.contains(asset_poly):
                        if asset_poly.intersects(boundary_poly):
                            outside_area = asset_poly.difference(boundary_poly).area
                            outside_sqft = outside_area / (LAT_PER_FOOT * LNG_PER_FOOT)
                            violations.append(
                                ConstraintViolation(
                                    asset_id=asset.id,
                                    constraint_type="property_line",
                                    severity="error",
                                    message=(
                                        f"Asset extends {outside_sqft:.0f} sq ft "
                                        f"beyond property boundary"
                                    ),
                                )
                            )
                        else:
                            violations.append(
                                ConstraintViolation(
                                    asset_id=asset.id,
                                    constraint_type="property_line",
                                    severity="error",
                                    message="Asset is completely outside property boundary",
                                )
                            )
                except Exception as e:
                    logger.warning(f"Could not check boundary violation: {e}")

        logger.info(f"Detected {len(violations)} constraint violations")
        return violations

    # ------------------------------------------------------------------
    # Road intersections (resolves TODO: intersections=[])
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_road_intersections(
        road_segments: list,
    ) -> List[Coordinate]:
        """Find coordinates shared by 2+ road segment endpoints."""
        from collections import Counter

        endpoint_counts: Counter[tuple[float, float]] = Counter()
        for seg in road_segments:
            for pt in seg.points:
                key = (round(pt.longitude, 8), round(pt.latitude, 8))
                endpoint_counts[key] += 1

        return [
            Coordinate(longitude=lon, latitude=lat)
            for (lon, lat), count in endpoint_counts.items()
            if count >= 2
        ]

    # ------------------------------------------------------------------
    # Constraint zones (resolves TODO: constraint_zones=[])
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_constraint_zones(
        property_boundary_coords: List[Dict[str, float]],
        setback_ft: float = 20,
    ) -> list:
        """Generate setback zone as an inward buffer of the property boundary."""
        if not property_boundary_coords or len(property_boundary_coords) < 3:
            return []

        try:
            boundary_poly = ShapelyPolygon(
                [(p["longitude"], p["latitude"]) for p in property_boundary_coords]
            )
            # Approximate setback in degrees
            setback_deg = setback_ft * LNG_PER_FOOT
            setback_zone = boundary_poly.difference(
                boundary_poly.buffer(-setback_deg)
            )
            if setback_zone.is_empty:
                return []

            coords = [
                {"latitude": y, "longitude": x}
                for x, y in setback_zone.exterior.coords[:-1]
            ]
            return [
                {
                    "type": "setback",
                    "label": f"{setback_ft}ft setback zone",
                    "coordinates": coords,
                }
            ]
        except Exception as e:
            logger.warning(f"Could not compute constraint zones: {e}")
            return []

    # ------------------------------------------------------------------
    # Buildable areas (resolves TODO: buildable_areas=[])
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_buildable_areas(
        property_boundary_coords: List[Dict[str, float]],
        setback_ft: float = 20,
    ) -> list:
        """Property boundary minus setback buffer."""
        if not property_boundary_coords or len(property_boundary_coords) < 3:
            return []

        try:
            boundary_poly = ShapelyPolygon(
                [(p["longitude"], p["latitude"]) for p in property_boundary_coords]
            )
            setback_deg = setback_ft * LNG_PER_FOOT
            buildable = boundary_poly.buffer(-setback_deg)
            if buildable.is_empty:
                return []

            coords = [
                {"latitude": y, "longitude": x}
                for x, y in buildable.exterior.coords[:-1]
            ]
            return [
                BuildableArea(
                    id="buildable-1",
                    name="Primary buildable area",
                    coordinates=coords,
                    area_sqft=buildable.area / (LAT_PER_FOOT * LNG_PER_FOOT),
                ).model_dump()
            ]
        except Exception as e:
            logger.warning(f"Could not compute buildable areas: {e}")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _asset_polygon(asset: Any) -> ShapelyPolygon:
        """Build a Shapely polygon for an asset's rotated footprint."""
        half_width = (asset.width / 2) * LNG_PER_FOOT
        half_length = (asset.length / 2) * LAT_PER_FOOT

        rot_rad = math.radians(asset.rotation)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        corners = [
            (-half_width, -half_length),
            (half_width, -half_length),
            (half_width, half_length),
            (-half_width, half_length),
        ]

        rotated = []
        for x, y in corners:
            rot_x = x * cos_r - y * sin_r
            rot_y = x * sin_r + y * cos_r
            rotated.append(
                (asset.position.longitude + rot_x, asset.position.latitude + rot_y)
            )

        return ShapelyPolygon(rotated)

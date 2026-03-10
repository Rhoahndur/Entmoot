"""
Project service — business logic for project results and validation.

Extracted from api/projects.py to keep route handlers thin.
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from shapely.geometry import Polygon as ShapelyPolygon

from entmoot.models.project import (
    Bounds,
    BuildableArea,
    ConstraintType,
    ConstraintViolation,
    ConstraintZone,
    Coordinate,
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
        property_boundary_coords: List[Dict[str, float]] = project.get("property_boundary", [])
        bounds_data: Dict[str, float] = project.get("bounds", {})

        # Road network
        total_road_length = sum(seg.length for seg in layout_results.road_network)
        intersections = ProjectService._compute_road_intersections(layout_results.road_network)
        road_network = RoadNetwork(
            segments=layout_results.road_network,
            total_length=total_road_length,
            intersections=intersections,
        )

        # Constraint / buildable zones (must be computed before violations)
        constraint_zones = ProjectService._compute_constraint_zones(
            property_boundary_coords,
            setback_ft=project.get("config", {}).get("constraints", {}).get("setback_distance", 20),
        )

        # Append existing conditions zones (from OSM data)
        for ec_data in project.get("existing_conditions", []):
            try:
                constraint_zones.append(ConstraintZone(**ec_data))
            except (TypeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Skipping existing condition zone {ec_data.get('id', 'unknown')}: {e}"
                )

        # Constraint violations (now checked against zones too)
        violations = ProjectService._detect_constraint_violations(
            layout_results.placed_assets,
            property_boundary_coords,
            constraint_zones,
            utm_data=project.get("utm_data"),
        )
        buildable_areas = ProjectService._compute_buildable_areas(
            property_boundary_coords,
            setback_ft=project.get("config", {}).get("constraints", {}).get("setback_distance", 20),
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
            constraint_violations=len(violations),
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

        boundary_as_coords = [
            Coordinate(latitude=p["latitude"], longitude=p["longitude"])
            for p in property_boundary_coords
        ]

        return OptimizationResults(
            project_id=project_id,
            project_name=project.get("project_name", "Unnamed Project"),
            property_boundary=boundary_as_coords,
            bounds=(
                Bounds(**bounds_data) if bounds_data else Bounds(north=0, south=0, east=0, west=0)
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
        constraint_zones: Optional[List[ConstraintZone]] = None,
        utm_data: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        """Check every asset for overlaps, boundary breaches, and zone violations.

        When ``utm_data`` is available (stored after optimization) all geometry
        checks are done in UTM metre-space for accuracy.  Falls back to the
        original WGS84-degree approximation when UTM data is absent.
        """
        violations: List[ConstraintViolation] = []

        # ----- Try UTM-based checks first (accurate) -----
        if utm_data is not None:
            try:
                utm_violations = ProjectService._detect_violations_utm(placed_assets, utm_data)
                logger.info(f"Detected {len(utm_violations)} constraint violations (UTM)")
                return utm_violations
            except Exception as e:
                logger.warning(f"UTM violation detection failed, falling back to WGS84: {e}")

        # ----- Fallback: original WGS84-degree checks -----
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
                            constraint_type=ConstraintType.SETBACK,
                            severity="error",
                            message=(
                                f"Asset overlaps with another asset "
                                f"(overlap: {overlap_sqft:.0f} sq ft)"
                            ),
                            location=None,
                        )
                    )

            # Check site boundary
            if property_boundary_coords:
                try:
                    boundary_poly = ShapelyPolygon(
                        [(p["longitude"], p["latitude"]) for p in property_boundary_coords]
                    )
                    if not boundary_poly.contains(asset_poly):
                        if asset_poly.intersects(boundary_poly):
                            outside_area = asset_poly.difference(boundary_poly).area
                            outside_sqft = outside_area / (LAT_PER_FOOT * LNG_PER_FOOT)
                            violations.append(
                                ConstraintViolation(
                                    asset_id=asset.id,
                                    constraint_type=ConstraintType.PROPERTY_LINE,
                                    severity="error",
                                    message=(
                                        f"Asset extends {outside_sqft:.0f} sq ft "
                                        f"beyond property boundary"
                                    ),
                                    location=None,
                                )
                            )
                        else:
                            violations.append(
                                ConstraintViolation(
                                    asset_id=asset.id,
                                    constraint_type=ConstraintType.PROPERTY_LINE,
                                    severity="error",
                                    message="Asset is completely outside property boundary",
                                    location=None,
                                )
                            )
                except Exception as e:
                    logger.warning(f"Could not check boundary violation: {e}")

            # Check constraint zones (setback, exclusion, existing conditions)
            if constraint_zones:
                for zone in constraint_zones:
                    try:
                        zone_poly = ShapelyPolygon(
                            [(c.longitude, c.latitude) for c in zone.polygon]
                        )
                        if asset_poly.intersects(zone_poly):
                            intersection_area = asset_poly.intersection(zone_poly).area
                            if intersection_area > 0:
                                severity = "error" if zone.severity == "high" else "warning"
                                violations.append(
                                    ConstraintViolation(
                                        asset_id=asset.id,
                                        constraint_type=zone.type,
                                        severity=severity,
                                        message=(
                                            f"Asset intersects {zone.type.value} zone"
                                            f"{': ' + zone.description if zone.description else ''}"
                                        ),
                                        location=None,
                                    )
                                )
                    except Exception as e:
                        logger.warning(f"Could not check zone {zone.id} violation: {e}")

        logger.info(f"Detected {len(violations)} constraint violations")
        return violations

    # ------------------------------------------------------------------
    # UTM-based violation detection (accurate metre-space geometry)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_violations_utm(
        placed_assets: list,
        utm_data: Dict[str, Any],
    ) -> List[ConstraintViolation]:
        """Run violation checks in UTM metre-space using stored optimization geometry."""
        from pyproj import Transformer
        from shapely import wkt
        from shapely.ops import transform as shapely_transform

        violations: List[ConstraintViolation] = []

        crs_epsg = utm_data["crs_epsg"]
        buildable_area = wkt.loads(utm_data["buildable_area_wkt"])
        exclusion_zones = [wkt.loads(w) for w in utm_data.get("exclusion_zones_wkt", [])]

        # WGS84 → UTM transformer
        proj_transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{crs_epsg}", always_xy=True)

        def to_utm(x: float, y: float) -> tuple:
            return proj_transformer.transform(x, y)  # type: ignore[no-any-return]

        # Build UTM polygons for each asset
        asset_utm_polys = []
        for asset in placed_assets:
            wgs_poly = ProjectService._asset_polygon(asset)
            utm_poly = shapely_transform(to_utm, wgs_poly)
            asset_utm_polys.append((asset, utm_poly))

        for i, (asset, asset_utm) in enumerate(asset_utm_polys):
            # Check overlaps with subsequent assets
            for j in range(i + 1, len(asset_utm_polys)):
                other_asset, other_utm = asset_utm_polys[j]
                if asset_utm.intersects(other_utm):
                    overlap_area_sqm = asset_utm.intersection(other_utm).area
                    overlap_sqft = overlap_area_sqm * 10.7639
                    violations.append(
                        ConstraintViolation(
                            asset_id=asset.id,
                            constraint_type=ConstraintType.SETBACK,
                            severity="error",
                            message=(
                                f"Asset overlaps with another asset "
                                f"(overlap: {overlap_sqft:.0f} sq ft)"
                            ),
                            location=None,
                        )
                    )

            # Check against buildable area (includes setback, exclusions, etc.)
            if not buildable_area.contains(asset_utm):
                if asset_utm.intersects(buildable_area):
                    outside_area_sqm = asset_utm.difference(buildable_area).area
                    outside_sqft = outside_area_sqm * 10.7639
                    violations.append(
                        ConstraintViolation(
                            asset_id=asset.id,
                            constraint_type=ConstraintType.SETBACK,
                            severity="error",
                            message=(
                                f"Asset extends {outside_sqft:.0f} sq ft " f"beyond buildable area"
                            ),
                            location=None,
                        )
                    )
                else:
                    violations.append(
                        ConstraintViolation(
                            asset_id=asset.id,
                            constraint_type=ConstraintType.PROPERTY_LINE,
                            severity="error",
                            message="Asset is completely outside buildable area",
                            location=None,
                        )
                    )

            # Check exclusion zones
            for ez in exclusion_zones:
                if asset_utm.intersects(ez):
                    intersection_sqm = asset_utm.intersection(ez).area
                    if intersection_sqm > 0.1:  # > ~1 sq ft
                        violations.append(
                            ConstraintViolation(
                                asset_id=asset.id,
                                constraint_type=ConstraintType.EXCLUSION,
                                severity="error",
                                message=(
                                    f"Asset intersects exclusion zone "
                                    f"({intersection_sqm * 10.7639:.0f} sq ft)"
                                ),
                                location=None,
                            )
                        )

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
    ) -> List[ConstraintZone]:
        """Generate setback zone as an inward buffer of the property boundary."""
        if not property_boundary_coords or len(property_boundary_coords) < 3:
            return []

        try:
            boundary_poly = ShapelyPolygon(
                [(p["longitude"], p["latitude"]) for p in property_boundary_coords]
            )
            # Approximate setback in degrees with latitude correction
            center_lat = boundary_poly.centroid.y
            cos_lat = math.cos(math.radians(center_lat))
            setback_deg = setback_ft * LAT_PER_FOOT / (cos_lat or 1)
            setback_zone = boundary_poly.difference(boundary_poly.buffer(-setback_deg))
            if setback_zone.is_empty:
                return []

            coords = [
                Coordinate(latitude=y, longitude=x) for x, y in setback_zone.exterior.coords[:-1]
            ]
            return [
                ConstraintZone(
                    id="setback-zone-1",
                    type=ConstraintType.SETBACK,
                    polygon=coords,
                    severity="medium",
                    description=f"{setback_ft}ft setback zone",
                )
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
    ) -> List[BuildableArea]:
        """Property boundary minus setback buffer."""
        if not property_boundary_coords or len(property_boundary_coords) < 3:
            return []

        try:
            boundary_poly = ShapelyPolygon(
                [(p["longitude"], p["latitude"]) for p in property_boundary_coords]
            )
            center_lat = boundary_poly.centroid.y
            cos_lat = math.cos(math.radians(center_lat))
            setback_deg = setback_ft * LAT_PER_FOOT / (cos_lat or 1)
            buildable = boundary_poly.buffer(-setback_deg)
            if buildable.is_empty:
                return []

            coords = [
                Coordinate(latitude=y, longitude=x) for x, y in buildable.exterior.coords[:-1]
            ]
            return [
                BuildableArea(
                    polygon=coords,
                    area=buildable.area / (LAT_PER_FOOT * LNG_PER_FOOT),
                    usable=True,
                )
            ]
        except Exception as e:
            logger.warning(f"Could not compute buildable areas: {e}")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _asset_polygon(asset: Any) -> ShapelyPolygon:
        """Build a Shapely polygon for an asset's footprint.

        Uses backend-computed polygon (accurate UTM→WGS84) when available;
        falls back to local approximation with cos(lat) correction.
        """
        # Prefer backend-computed polygon
        if hasattr(asset, "polygon") and asset.polygon and len(asset.polygon) >= 3:
            return ShapelyPolygon([(c.longitude, c.latitude) for c in asset.polygon])

        # Fallback: local approximation with latitude correction
        cos_lat = math.cos(math.radians(asset.position.latitude))
        lng_per_foot = LAT_PER_FOOT / (cos_lat or 1)
        half_width = (asset.width / 2) * lng_per_foot
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
            rotated.append((asset.position.longitude + rot_x, asset.position.latitude + rot_y))

        return ShapelyPolygon(rotated)

    # ------------------------------------------------------------------
    # Single-asset placement validation (for drag-and-drop)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_single_asset_placement(
        asset_id: str,
        lat: float,
        lng: float,
        rotation: float,
        width_ft: float,
        length_ft: float,
        other_assets: list,
        utm_data: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        """Validate a single asset's placement against constraints.

        Builds the asset footprint from the given parameters, transforms to
        UTM when possible, and checks against the buildable area, exclusion
        zones, and other placed assets.
        """
        violations: List[ConstraintViolation] = []

        # Build WGS84 footprint
        width_m = width_ft * 0.3048
        length_m = length_ft * 0.3048
        half_w_deg = (width_ft / 2) * LAT_PER_FOOT / (math.cos(math.radians(lat)) or 1)
        half_l_deg = (length_ft / 2) * LAT_PER_FOOT

        rot_rad = math.radians(rotation)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        corners_deg = [
            (-half_w_deg, -half_l_deg),
            (half_w_deg, -half_l_deg),
            (half_w_deg, half_l_deg),
            (-half_w_deg, half_l_deg),
        ]
        wgs_coords = []
        for dx, dy in corners_deg:
            rx = dx * cos_r - dy * sin_r
            ry = dx * sin_r + dy * cos_r
            wgs_coords.append((lng + rx, lat + ry))
        wgs_poly = ShapelyPolygon(wgs_coords)

        if utm_data is not None:
            try:
                from pyproj import Transformer
                from shapely import wkt
                from shapely.ops import transform as shapely_transform

                crs_epsg = utm_data["crs_epsg"]
                buildable_area = wkt.loads(utm_data["buildable_area_wkt"])
                exclusion_zones = [wkt.loads(w) for w in utm_data.get("exclusion_zones_wkt", [])]

                proj = Transformer.from_crs("EPSG:4326", f"EPSG:{crs_epsg}", always_xy=True)

                def to_utm(x: float, y: float) -> tuple:
                    return proj.transform(x, y)  # type: ignore[no-any-return]

                asset_utm = shapely_transform(to_utm, wgs_poly)

                # Check buildable area
                if not buildable_area.contains(asset_utm):
                    if asset_utm.intersects(buildable_area):
                        outside_sqft = asset_utm.difference(buildable_area).area * 10.7639
                        violations.append(
                            ConstraintViolation(
                                asset_id=asset_id,
                                constraint_type=ConstraintType.SETBACK,
                                severity="error",
                                message=(
                                    f"Asset extends {outside_sqft:.0f} sq ft "
                                    f"beyond buildable area"
                                ),
                                location=None,
                            )
                        )
                    else:
                        violations.append(
                            ConstraintViolation(
                                asset_id=asset_id,
                                constraint_type=ConstraintType.PROPERTY_LINE,
                                severity="error",
                                message="Asset is completely outside buildable area",
                                location=None,
                            )
                        )

                # Check exclusion zones
                for ez in exclusion_zones:
                    if asset_utm.intersects(ez):
                        isect_sqm = asset_utm.intersection(ez).area
                        if isect_sqm > 0.1:
                            violations.append(
                                ConstraintViolation(
                                    asset_id=asset_id,
                                    constraint_type=ConstraintType.EXCLUSION,
                                    severity="error",
                                    message=(
                                        f"Asset intersects exclusion zone "
                                        f"({isect_sqm * 10.7639:.0f} sq ft)"
                                    ),
                                    location=None,
                                )
                            )

                # Check overlaps with other placed assets
                for other in other_assets:
                    if other.id == asset_id:
                        continue
                    other_wgs = ProjectService._asset_polygon(other)
                    other_utm = shapely_transform(to_utm, other_wgs)
                    if asset_utm.intersects(other_utm):
                        overlap_sqft = asset_utm.intersection(other_utm).area * 10.7639
                        violations.append(
                            ConstraintViolation(
                                asset_id=asset_id,
                                constraint_type=ConstraintType.SETBACK,
                                severity="error",
                                message=(
                                    f"Asset overlaps with {other.id} " f"({overlap_sqft:.0f} sq ft)"
                                ),
                                location=None,
                            )
                        )

                return violations
            except Exception as e:
                logger.warning(f"UTM validate failed, falling back to WGS84: {e}")
                violations = []

        # Fallback: WGS84-only checks (no utm_data or UTM failed)
        # Just check overlaps with other assets
        for other in other_assets:
            if other.id == asset_id:
                continue
            other_poly = ProjectService._asset_polygon(other)
            if wgs_poly.intersects(other_poly):
                violations.append(
                    ConstraintViolation(
                        asset_id=asset_id,
                        constraint_type=ConstraintType.SETBACK,
                        severity="error",
                        message=f"Asset overlaps with {other.id}",
                        location=None,
                    )
                )

        return violations

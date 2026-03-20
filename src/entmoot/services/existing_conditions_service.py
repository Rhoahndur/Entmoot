"""Service bridging OSM existing conditions data into exclusion zones."""

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from shapely import wkt
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from entmoot.core.constraints.buffers import (
    ROAD_SETBACK,
    UTILITY_SETBACK,
    WATER_FEATURE_SETBACK,
    BufferConfig,
    BufferGenerator,
    RoadType,
    WaterFeatureType,
)
from entmoot.core.crs.transformer import CRSTransformer
from entmoot.integrations.osm.client import OSMClient, OSMClientConfig
from entmoot.models.existing_conditions import (
    OSMFeature,
    OSMRoadClass,
    OSMUtilityType,
    OSMWaterType,
)
from entmoot.models.project import ConstraintType, ConstraintZone, Coordinate

logger = logging.getLogger(__name__)

# Building footprint buffer (no predefined constant — 3m ≈ 10ft)
BUILDING_BUFFER_M = 3.0

# Mapping from OSM road class to buffers.py RoadType
_ROAD_CLASS_TO_ROAD_TYPE = {
    OSMRoadClass.MOTORWAY: RoadType.MAJOR,
    OSMRoadClass.PRIMARY: RoadType.MAJOR,
    OSMRoadClass.SECONDARY: RoadType.COLLECTOR,
    OSMRoadClass.TERTIARY: RoadType.COLLECTOR,
    OSMRoadClass.RESIDENTIAL: RoadType.LOCAL,
    OSMRoadClass.SERVICE: RoadType.DRIVEWAY,
    OSMRoadClass.OTHER: RoadType.LOCAL,
}

# Mapping from OSM water type to buffers.py WaterFeatureType
_WATER_TYPE_MAP = {
    OSMWaterType.STREAM: WaterFeatureType.STREAM,
    OSMWaterType.RIVER: WaterFeatureType.RIVER,
    OSMWaterType.POND: WaterFeatureType.POND,
    OSMWaterType.LAKE: WaterFeatureType.LAKE,
    OSMWaterType.WETLAND: WaterFeatureType.WETLAND,
}

# Mapping from OSM utility type to utility_setback key
_UTILITY_TYPE_KEY = {
    OSMUtilityType.POWER_LINE: "power_line",
    OSMUtilityType.HIGH_VOLTAGE: "high_voltage",
    OSMUtilityType.PIPELINE: "pipeline",
    OSMUtilityType.GAS_LINE: "gas_line",
    OSMUtilityType.DEFAULT: "default",
}


@dataclass
class ExistingConditionsResult:
    """Result of processing OSM data into optimizer-ready structures."""

    exclusion_zones: List[ShapelyPolygon] = field(default_factory=list)
    display_features: List[ConstraintZone] = field(default_factory=list)
    road_entry_point: Optional[Tuple[float, float]] = None  # (x, y) in UTM
    feature_count: int = 0


class ExistingConditionsService:
    """Fetches OSM data and converts it into exclusion zones for the optimizer."""

    def __init__(self, osm_config: Optional[OSMClientConfig] = None) -> None:
        """Initialize service with optional OSM client configuration."""
        self._osm_config = osm_config

    async def fetch_and_process(
        self,
        site_boundary_wgs84: ShapelyPolygon,
        transformer: CRSTransformer,
        inverse_transformer: CRSTransformer,
        site_boundary_utm: ShapelyPolygon,
    ) -> ExistingConditionsResult:
        """
        Fetch existing conditions from OSM and produce exclusion zones.

        Args:
            site_boundary_wgs84: Site boundary in WGS84 (lon/lat).
            transformer: WGS84 → UTM transformer.
            inverse_transformer: UTM → WGS84 transformer (for display features).
            site_boundary_utm: Site boundary in UTM (for clipping).

        Returns:
            ExistingConditionsResult with exclusion zones and display data.
        """
        # 1. Compute bbox with small buffer
        bounds = site_boundary_wgs84.bounds  # (minx, miny, maxx, maxy) = (min_lon, min_lat, …)
        buf = 0.002  # ~200m buffer in degrees
        min_lon = bounds[0] - buf
        min_lat = bounds[1] - buf
        max_lon = bounds[2] + buf
        max_lat = bounds[3] + buf

        # 2. Query OSM
        async with OSMClient(self._osm_config) as client:
            osm_data = await client.query_existing_conditions(min_lon, min_lat, max_lon, max_lat)

        if osm_data.feature_count == 0:
            logger.info("No existing conditions found from OSM")
            return ExistingConditionsResult()

        logger.info(f"Processing {osm_data.feature_count} OSM features into exclusion zones")

        buf_gen = BufferGenerator()
        exclusion_zones: List[ShapelyPolygon] = []
        display_features: List[ConstraintZone] = []
        road_entry_point: Optional[Tuple[float, float]] = None
        nearest_road_dist = float("inf")
        zone_counter = 0

        # 3. Process buildings
        for feat in osm_data.buildings:
            zone = self._process_building(feat, transformer, site_boundary_utm, buf_gen)
            if zone is not None:
                exclusion_zones.append(zone)
                zone_counter += 1
                display_features.append(
                    self._make_display_zone(
                        f"existing-building-{zone_counter}",
                        ConstraintType.EXISTING_BUILDING,
                        zone,
                        inverse_transformer,
                        "Existing building",
                    )
                )

        # 4. Process roads (also find entry point)
        for feat in osm_data.roads:
            zone = self._process_road(feat, transformer, site_boundary_utm, buf_gen)
            if zone is not None:
                exclusion_zones.append(zone)
                zone_counter += 1
                display_features.append(
                    self._make_display_zone(
                        f"existing-road-{zone_counter}",
                        ConstraintType.EXISTING_ROAD,
                        zone,
                        inverse_transformer,
                        f"Existing road ({feat.road_class.value if feat.road_class else 'unknown'})",
                    )
                )

            # Find nearest road point to site boundary for entry
            entry = self._find_road_entry(feat, transformer, site_boundary_utm)
            if entry is not None:
                dist, pt = entry
                if dist < nearest_road_dist:
                    nearest_road_dist = dist
                    road_entry_point = pt

        # 5. Process utilities
        for feat in osm_data.utilities:
            zone = self._process_utility(feat, transformer, site_boundary_utm, buf_gen)
            if zone is not None:
                exclusion_zones.append(zone)
                zone_counter += 1
                display_features.append(
                    self._make_display_zone(
                        f"existing-utility-{zone_counter}",
                        ConstraintType.EXISTING_UTILITY,
                        zone,
                        inverse_transformer,
                        f"Existing utility ({feat.utility_type.value if feat.utility_type else 'unknown'})",
                    )
                )

        # 6. Process water features
        for feat in osm_data.water_features:
            zone = self._process_water(feat, transformer, site_boundary_utm, buf_gen)
            if zone is not None:
                exclusion_zones.append(zone)
                zone_counter += 1
                display_features.append(
                    self._make_display_zone(
                        f"existing-water-{zone_counter}",
                        ConstraintType.EXISTING_WATER,
                        zone,
                        inverse_transformer,
                        f"Water feature ({feat.water_type.value if feat.water_type else 'unknown'})",
                    )
                )

        # 7. Fallback entry point: centroid
        if road_entry_point is None:
            road_entry_point = (site_boundary_utm.centroid.x, site_boundary_utm.centroid.y)

        logger.info(
            f"Created {len(exclusion_zones)} exclusion zones from existing conditions, "
            f"road entry at ({road_entry_point[0]:.1f}, {road_entry_point[1]:.1f})"
        )

        return ExistingConditionsResult(
            exclusion_zones=exclusion_zones,
            display_features=display_features,
            road_entry_point=road_entry_point,
            feature_count=osm_data.feature_count,
        )

    # ------------------------------------------------------------------
    # Feature processors
    # ------------------------------------------------------------------

    def _transform_geometry(
        self,
        feat: OSMFeature,
        transformer: CRSTransformer,
    ) -> BaseGeometry:
        """Load WKT geometry and transform from WGS84 to UTM."""
        from shapely.ops import transform as shapely_transform

        geom = wkt.loads(feat.geometry_wkt)

        def _xform(x: Any, y: Any, z: Any = None) -> Tuple[Any, Any]:
            tx, ty = transformer.transform(x, y)
            return tx, ty

        return shapely_transform(_xform, geom)

    def _clip_to_site(
        self, geom: BaseGeometry, site_boundary_utm: ShapelyPolygon
    ) -> Optional[ShapelyPolygon]:
        """Clip geometry to site boundary, return None if empty."""
        clipped = geom.intersection(site_boundary_utm)
        if clipped.is_empty or clipped.area < 0.1:
            return None
        # Ensure polygon type
        if clipped.geom_type == "MultiPolygon":
            # Return the largest part
            parts = sorted(clipped.geoms, key=lambda g: g.area, reverse=True)
            return parts[0] if parts[0].area > 0.1 else None
        if clipped.geom_type == "Polygon":
            return clipped
        return None

    def _process_building(
        self,
        feat: OSMFeature,
        transformer: CRSTransformer,
        site_boundary_utm: ShapelyPolygon,
        buf_gen: BufferGenerator,
    ) -> Optional[ShapelyPolygon]:
        try:
            geom_utm = self._transform_geometry(feat, transformer)
            config = BufferConfig(distance_m=BUILDING_BUFFER_M)
            buffered = buf_gen.create_buffer(geom_utm, config)
            return self._clip_to_site(buffered, site_boundary_utm)
        except Exception as e:
            logger.debug(f"Skipping building {feat.osm_id}: {e}")
            return None

    def _process_road(
        self,
        feat: OSMFeature,
        transformer: CRSTransformer,
        site_boundary_utm: ShapelyPolygon,
        buf_gen: BufferGenerator,
    ) -> Optional[ShapelyPolygon]:
        try:
            geom_utm = self._transform_geometry(feat, transformer)
            road_type = _ROAD_CLASS_TO_ROAD_TYPE.get(
                feat.road_class or OSMRoadClass.OTHER, RoadType.LOCAL
            )
            distance = ROAD_SETBACK[road_type]
            config = BufferConfig(distance_m=distance)
            buffered = buf_gen.create_buffer(geom_utm, config)
            return self._clip_to_site(buffered, site_boundary_utm)
        except Exception as e:
            logger.debug(f"Skipping road {feat.osm_id}: {e}")
            return None

    def _process_utility(
        self,
        feat: OSMFeature,
        transformer: CRSTransformer,
        site_boundary_utm: ShapelyPolygon,
        buf_gen: BufferGenerator,
    ) -> Optional[ShapelyPolygon]:
        try:
            geom_utm = self._transform_geometry(feat, transformer)
            key = _UTILITY_TYPE_KEY.get(feat.utility_type or OSMUtilityType.DEFAULT, "default")
            distance = UTILITY_SETBACK.get(key, UTILITY_SETBACK["default"])
            config = BufferConfig(distance_m=distance)
            buffered = buf_gen.create_buffer(geom_utm, config)
            return self._clip_to_site(buffered, site_boundary_utm)
        except Exception as e:
            logger.debug(f"Skipping utility {feat.osm_id}: {e}")
            return None

    def _process_water(
        self,
        feat: OSMFeature,
        transformer: CRSTransformer,
        site_boundary_utm: ShapelyPolygon,
        buf_gen: BufferGenerator,
    ) -> Optional[ShapelyPolygon]:
        try:
            geom_utm = self._transform_geometry(feat, transformer)
            wf_type = _WATER_TYPE_MAP.get(
                feat.water_type or OSMWaterType.POND, WaterFeatureType.POND
            )
            distance = WATER_FEATURE_SETBACK[wf_type]
            config = BufferConfig(distance_m=distance)
            buffered = buf_gen.create_buffer(geom_utm, config)
            return self._clip_to_site(buffered, site_boundary_utm)
        except Exception as e:
            logger.debug(f"Skipping water feature {feat.osm_id}: {e}")
            return None

    def _find_road_entry(
        self,
        feat: OSMFeature,
        transformer: CRSTransformer,
        site_boundary_utm: ShapelyPolygon,
    ) -> Optional[Tuple[float, Tuple[float, float]]]:
        """Find nearest point on road to site boundary. Returns (distance, (x,y))."""
        try:
            geom_utm = self._transform_geometry(feat, transformer)
            boundary_line = site_boundary_utm.boundary
            p1, _ = nearest_points(geom_utm, boundary_line)
            dist = geom_utm.distance(boundary_line)
            return (dist, (p1.x, p1.y))
        except Exception:
            return None

    @staticmethod
    def _make_display_zone(
        zone_id: str,
        constraint_type: ConstraintType,
        polygon_utm: ShapelyPolygon,
        inverse_transformer: CRSTransformer,
        description: str,
    ) -> ConstraintZone:
        """Convert a UTM polygon to a WGS84 ConstraintZone for frontend display."""
        from shapely.ops import transform as shapely_transform

        def _inv(x: Any, y: Any, z: Any = None) -> Tuple[Any, Any]:
            tx, ty = inverse_transformer.transform(x, y)
            return tx, ty

        poly_wgs84 = shapely_transform(_inv, polygon_utm)
        coords = [Coordinate(latitude=y, longitude=x) for x, y in poly_wgs84.exterior.coords[:-1]]

        return ConstraintZone(
            id=zone_id,
            type=constraint_type,
            polygon=coords,
            severity="high",
            description=description,
        )

"""Parser for OpenStreetMap Overpass API responses."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import LineString, Polygon

from entmoot.models.existing_conditions import (
    ExistingConditionsData,
    OSMFeature,
    OSMFeatureType,
    OSMRoadClass,
    OSMUtilityType,
    OSMWaterType,
)

logger = logging.getLogger(__name__)

# OSM highway tag → road class mapping
_HIGHWAY_TO_ROAD_CLASS: Dict[str, OSMRoadClass] = {
    "motorway": OSMRoadClass.MOTORWAY,
    "motorway_link": OSMRoadClass.MOTORWAY,
    "trunk": OSMRoadClass.PRIMARY,
    "trunk_link": OSMRoadClass.PRIMARY,
    "primary": OSMRoadClass.PRIMARY,
    "primary_link": OSMRoadClass.PRIMARY,
    "secondary": OSMRoadClass.SECONDARY,
    "secondary_link": OSMRoadClass.SECONDARY,
    "tertiary": OSMRoadClass.TERTIARY,
    "tertiary_link": OSMRoadClass.TERTIARY,
    "residential": OSMRoadClass.RESIDENTIAL,
    "unclassified": OSMRoadClass.RESIDENTIAL,
    "living_street": OSMRoadClass.RESIDENTIAL,
    "service": OSMRoadClass.SERVICE,
    "track": OSMRoadClass.SERVICE,
}


class OSMResponseParser:
    """Parses raw Overpass JSON into ExistingConditionsData."""

    def parse_response(
        self,
        data: Dict[str, Any],
        bbox: Optional[Dict[str, float]] = None,
    ) -> ExistingConditionsData:
        """
        Parse an Overpass API JSON response into typed features.

        Args:
            data: Raw JSON response from Overpass API.
            bbox: Bounding box used for the query.

        Returns:
            ExistingConditionsData with categorised features.
        """
        elements = data.get("elements", [])
        if not elements:
            logger.info("Overpass response contains no elements")
            return ExistingConditionsData(bbox=bbox, query_timestamp=datetime.now(timezone.utc))

        # Build node index: id → (lon, lat)
        node_index: Dict[int, Tuple[float, float]] = {}
        for el in elements:
            if el.get("type") == "node":
                node_index[el["id"]] = (el["lon"], el["lat"])

        buildings: List[OSMFeature] = []
        roads: List[OSMFeature] = []
        utilities: List[OSMFeature] = []
        water_features: List[OSMFeature] = []

        for el in elements:
            if el.get("type") not in ("way", "relation"):
                continue

            tags = el.get("tags", {})
            node_refs = el.get("nodes", [])

            # Build geometry from node references
            coords = self._resolve_coords(node_refs, node_index)
            if len(coords) < 2:
                continue

            # Classify the element
            if "building" in tags:
                geom = self._make_polygon(coords)
                if geom is None:
                    continue
                buildings.append(
                    OSMFeature(
                        osm_id=el["id"],
                        feature_type=OSMFeatureType.BUILDING,
                        geometry_wkt=geom.wkt,
                        tags=tags,
                    )
                )
            elif "highway" in tags:
                highway_val = tags["highway"]
                road_class = _HIGHWAY_TO_ROAD_CLASS.get(highway_val, OSMRoadClass.OTHER)
                geom = LineString(coords)
                if geom.is_empty:
                    continue
                roads.append(
                    OSMFeature(
                        osm_id=el["id"],
                        feature_type=OSMFeatureType.ROAD,
                        geometry_wkt=geom.wkt,
                        tags=tags,
                        road_class=road_class,
                    )
                )
            elif tags.get("power") == "line" or tags.get("man_made") == "pipeline":
                ut = self._classify_utility(tags)
                geom = LineString(coords)
                if geom.is_empty:
                    continue
                utilities.append(
                    OSMFeature(
                        osm_id=el["id"],
                        feature_type=OSMFeatureType.UTILITY,
                        geometry_wkt=geom.wkt,
                        tags=tags,
                        utility_type=ut,
                    )
                )
            elif tags.get("natural") in ("water", "wetland") or "waterway" in tags:
                wt = self._classify_water(tags)
                # Water can be polygon or line
                if len(coords) >= 4 and coords[0] == coords[-1]:
                    geom = self._make_polygon(coords)
                else:
                    geom = LineString(coords)
                if geom is None or geom.is_empty:
                    continue
                water_features.append(
                    OSMFeature(
                        osm_id=el["id"],
                        feature_type=OSMFeatureType.WATER,
                        geometry_wkt=geom.wkt,
                        tags=tags,
                        water_type=wt,
                    )
                )

        logger.info(
            f"Parsed OSM response: {len(buildings)} buildings, {len(roads)} roads, "
            f"{len(utilities)} utilities, {len(water_features)} water features"
        )

        return ExistingConditionsData(
            buildings=buildings,
            roads=roads,
            utilities=utilities,
            water_features=water_features,
            bbox=bbox,
            query_timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_coords(
        node_refs: List[int],
        node_index: Dict[int, Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """Resolve node IDs to (lon, lat) coordinate tuples."""
        coords = []
        for nid in node_refs:
            if nid in node_index:
                coords.append(node_index[nid])
        return coords

    @staticmethod
    def _make_polygon(coords: List[Tuple[float, float]]) -> Optional[Polygon]:
        """Create a valid polygon, closing the ring if needed."""
        if len(coords) < 3:
            return None
        # Close ring if not already closed
        if coords[0] != coords[-1]:
            coords = list(coords) + [coords[0]]
        try:
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                return None
            return poly
        except Exception:
            return None

    @staticmethod
    def _classify_utility(tags: Dict[str, str]) -> OSMUtilityType:
        """Classify a utility feature from its OSM tags."""
        if tags.get("power") == "line":
            voltage_str = tags.get("voltage", "")
            try:
                voltage = int(voltage_str)
                if voltage >= 100_000:
                    return OSMUtilityType.HIGH_VOLTAGE
            except (ValueError, TypeError):
                pass
            return OSMUtilityType.POWER_LINE

        if tags.get("man_made") == "pipeline":
            substance = tags.get("substance", "").lower()
            if substance in ("gas", "natural_gas"):
                return OSMUtilityType.GAS_LINE
            return OSMUtilityType.PIPELINE

        return OSMUtilityType.DEFAULT

    @staticmethod
    def _classify_water(tags: Dict[str, str]) -> OSMWaterType:
        """Classify a water feature from its OSM tags."""
        if tags.get("natural") == "wetland":
            return OSMWaterType.WETLAND

        waterway = tags.get("waterway", "")
        if waterway in ("stream", "creek", "ditch", "drain"):
            return OSMWaterType.STREAM
        if waterway == "river":
            return OSMWaterType.RIVER

        # natural=water — distinguish pond/lake by area tag or default to pond
        water_tag = tags.get("water", "")
        if water_tag == "lake" or water_tag == "reservoir":
            return OSMWaterType.LAKE

        return OSMWaterType.POND

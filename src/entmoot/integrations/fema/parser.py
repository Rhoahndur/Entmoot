"""
FEMA National Flood Hazard Layer response parser.

Parses FEMA ArcGIS REST API responses and converts them to FloodplainData models.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from shapely.geometry import Polygon as ShapelyPolygon, shape
from shapely.ops import unary_union

from entmoot.models.regulatory import (
    FloodplainData,
    FloodZone,
    FloodZoneType,
    RegulatoryDataSource,
)

logger = logging.getLogger(__name__)


class FEMAResponseParser:
    """Parser for FEMA NFHL ArcGIS REST API responses."""

    # Mapping from FEMA zone codes to FloodZoneType enum
    ZONE_TYPE_MAPPING = {
        "A": FloodZoneType.A,
        "AE": FloodZoneType.AE,
        "AH": FloodZoneType.AH,
        "AO": FloodZoneType.AO,
        "AR": FloodZoneType.AR,
        "A99": FloodZoneType.A99,
        "V": FloodZoneType.V,
        "VE": FloodZoneType.VE,
        "B": FloodZoneType.B,
        "C": FloodZoneType.C,
        "X": FloodZoneType.X,
        "D": FloodZoneType.D,
        "AREA NOT INCLUDED": FloodZoneType.X,
        "OPEN WATER": FloodZoneType.OPEN_WATER,
    }

    def __init__(self) -> None:
        """Initialize FEMA response parser."""
        pass

    def _parse_zone_type(self, fld_zone: Optional[str]) -> FloodZoneType:
        """
        Parse FEMA zone code to FloodZoneType.

        Args:
            fld_zone: Raw FEMA zone code

        Returns:
            FloodZoneType enum value
        """
        if not fld_zone:
            return FloodZoneType.UNKNOWN

        # Clean and normalize zone code
        zone_clean = fld_zone.strip().upper()

        # Direct mapping
        if zone_clean in self.ZONE_TYPE_MAPPING:
            return self.ZONE_TYPE_MAPPING[zone_clean]

        # Handle variations
        if "FLOODWAY" in zone_clean:
            return FloodZoneType.AE  # Floodways are typically in AE zones

        # Check for X zone variations
        if zone_clean.startswith("X "):
            if "PROTECTED" in zone_clean or "LEVEE" in zone_clean:
                return FloodZoneType.X_PROTECTED
            return FloodZoneType.X

        # Default to unknown
        logger.warning(f"Unknown flood zone type: {fld_zone}")
        return FloodZoneType.UNKNOWN

    def _parse_geometry(self, geometry_dict: Dict[str, Any]) -> Optional[str]:
        """
        Parse ArcGIS geometry to WKT.

        Args:
            geometry_dict: ArcGIS geometry dictionary

        Returns:
            WKT string or None
        """
        try:
            # ArcGIS uses "rings" for polygons
            if "rings" in geometry_dict:
                rings = geometry_dict["rings"]
                if not rings:
                    return None

                # Create polygon from rings
                exterior = rings[0]
                holes = rings[1:] if len(rings) > 1 else []

                from shapely.geometry import Polygon
                geom = Polygon(exterior, holes)

                # Validate geometry
                if not geom.is_valid:
                    logger.warning("Invalid geometry detected, attempting to fix")
                    geom = geom.buffer(0)

                return geom.wkt

            # Try GeoJSON format as fallback
            geom = shape(geometry_dict)

            # Validate geometry
            if not geom.is_valid:
                logger.warning("Invalid geometry detected, attempting to fix")
                geom = geom.buffer(0)

            return geom.wkt

        except Exception as e:
            logger.error(f"Failed to parse geometry: {e}")
            return None

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """
        Parse FEMA date field (typically UNIX timestamp in milliseconds).

        Args:
            date_value: Date value from FEMA API

        Returns:
            Datetime object or None
        """
        if not date_value:
            return None

        try:
            # FEMA uses UNIX timestamp in milliseconds
            if isinstance(date_value, (int, float)):
                timestamp_seconds = date_value / 1000.0
                return datetime.utcfromtimestamp(timestamp_seconds)

            # Try parsing string
            if isinstance(date_value, str):
                # Try common date formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        return datetime.strptime(date_value, fmt)
                    except ValueError:
                        continue

        except Exception as e:
            logger.warning(f"Failed to parse date {date_value}: {e}")

        return None

    def _parse_bfe(self, bfe_value: Any) -> Optional[float]:
        """
        Parse Base Flood Elevation value.

        Args:
            bfe_value: BFE value from FEMA API

        Returns:
            Float BFE or None
        """
        if bfe_value is None or bfe_value == "":
            return None

        try:
            # Handle numeric values
            if isinstance(bfe_value, (int, float)):
                return float(bfe_value)

            # Handle string values
            if isinstance(bfe_value, str):
                # Remove common non-numeric characters
                clean_value = bfe_value.strip().replace("+", "").replace(" ", "")

                # Skip if empty or placeholder
                if not clean_value or clean_value in ["-", "N/A", "NA", "UNKNOWN"]:
                    return None

                return float(clean_value)

        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse BFE value '{bfe_value}': {e}")

        return None

    def _parse_feature(self, feature: Dict[str, Any]) -> Optional[FloodZone]:
        """
        Parse a single feature from FEMA response to FloodZone.

        Args:
            feature: Feature dictionary from FEMA API

        Returns:
            FloodZone or None if parsing fails
        """
        try:
            attributes = feature.get("attributes", {})
            geometry = feature.get("geometry")

            if not geometry:
                logger.warning("Feature has no geometry")
                return None

            # Parse geometry to WKT
            geometry_wkt = self._parse_geometry(geometry)
            if not geometry_wkt:
                return None

            # Extract key fields (field names may vary)
            fld_zone = attributes.get("FLD_ZONE") or attributes.get("ZONE_SUBTY")
            zone_type = self._parse_zone_type(fld_zone)

            # Parse BFE (Base Flood Elevation)
            bfe = self._parse_bfe(
                attributes.get("STATIC_BFE") or attributes.get("BFE_REVERT") or attributes.get("V_DATUM")
            )

            # Parse depth (for AO zones)
            depth = self._parse_bfe(attributes.get("DEPTH"))

            # Parse velocity
            velocity = self._parse_bfe(attributes.get("VELOCITY"))

            # Floodway indicator
            floodway = attributes.get("FLOODWAY") == "FLOODWAY"

            # Coastal zone indicator (V zones)
            coastal_zone = zone_type in {FloodZoneType.V, FloodZoneType.VE}

            # Effective date
            effective_date = self._parse_date(
                attributes.get("EFF_DATE") or attributes.get("EFFECTIVE_DATE")
            )

            # Study type
            study_type = attributes.get("STUDY_TYP") or attributes.get("STUDY_TYPE")

            # Source citation
            source_citation = (
                attributes.get("SOURCE_CIT") or attributes.get("FIRM_PAN") or attributes.get("DFIRM_ID")
            )

            # Vertical datum
            vertical_datum = attributes.get("V_DATUM") or attributes.get("VERT_DATUM")

            # Calculate area if possible
            area_sqm = None
            try:
                from shapely import wkt
                geom = wkt.loads(geometry_wkt)
                if isinstance(geom, ShapelyPolygon):
                    # Convert to appropriate projection for area calculation
                    # For now, approximate using geodesic
                    area_sqm = geom.area * 111320 * 111320  # Rough conversion
            except Exception as e:
                logger.debug(f"Could not calculate area: {e}")

            return FloodZone(
                zone_type=zone_type,
                zone_subtype=attributes.get("ZONE_SUBTY"),
                geometry_wkt=geometry_wkt,
                base_flood_elevation=bfe,
                static_bfe=bfe,
                depth=depth,
                velocity=velocity,
                floodway=floodway,
                coastal_zone=coastal_zone,
                effective_date=effective_date,
                study_type=study_type,
                source_citation=source_citation,
                area_sqm=area_sqm,
                vertical_datum=vertical_datum,
            )

        except Exception as e:
            logger.error(f"Failed to parse feature: {e}")
            return None

    def _determine_highest_risk_zone(self, zones: List[FloodZone]) -> Optional[FloodZoneType]:
        """
        Determine the highest risk zone from a list of zones.

        Args:
            zones: List of FloodZone objects

        Returns:
            Highest risk FloodZoneType
        """
        if not zones:
            return None

        # Priority order (highest to lowest risk)
        risk_priority = [
            FloodZoneType.VE,
            FloodZoneType.V,
            FloodZoneType.AE,
            FloodZoneType.AH,
            FloodZoneType.AO,
            FloodZoneType.A,
            FloodZoneType.AR,
            FloodZoneType.A99,
            FloodZoneType.X_PROTECTED,
            FloodZoneType.B,
            FloodZoneType.C,
            FloodZoneType.X,
            FloodZoneType.D,
            FloodZoneType.OPEN_WATER,
            FloodZoneType.UNKNOWN,
        ]

        zone_types = [z.zone_type for z in zones]

        for priority_zone in risk_priority:
            if priority_zone in zone_types:
                return priority_zone

        return zone_types[0] if zone_types else None

    def parse_query_response(
        self,
        response_data: Dict[str, Any],
        longitude: Optional[float] = None,
        latitude: Optional[float] = None,
        bbox_min_lon: Optional[float] = None,
        bbox_min_lat: Optional[float] = None,
        bbox_max_lon: Optional[float] = None,
        bbox_max_lat: Optional[float] = None,
    ) -> FloodplainData:
        """
        Parse FEMA query response to FloodplainData.

        Args:
            response_data: Raw JSON response from FEMA API
            longitude: Query point longitude
            latitude: Query point latitude
            bbox_min_lon: Bounding box minimum longitude
            bbox_min_lat: Bounding box minimum latitude
            bbox_max_lon: Bounding box maximum longitude
            bbox_max_lat: Bounding box maximum latitude

        Returns:
            FloodplainData object
        """
        try:
            features = response_data.get("features", [])
            logger.info(f"Parsing {len(features)} features from FEMA response")

            # Parse all features to FloodZone objects
            zones: List[FloodZone] = []
            for feature in features:
                zone = self._parse_feature(feature)
                if zone:
                    zones.append(zone)

            logger.info(f"Successfully parsed {len(zones)} flood zones")

            # Determine highest risk zone
            highest_risk = self._determine_highest_risk_zone(zones)

            # Check if in SFHA (Special Flood Hazard Area)
            in_sfha = any(z.is_high_risk() for z in zones)

            # Flood insurance required if in SFHA
            insurance_required = in_sfha

            # Extract community information (if available from first zone)
            community_name = None
            community_id = None
            panel_id = None

            if zones:
                # Try to get from first zone's attributes
                first_zone = zones[0]
                if first_zone.source_citation:
                    panel_id = first_zone.source_citation

            return FloodplainData(
                zones=zones,
                location_lon=longitude,
                location_lat=latitude,
                bbox_min_lon=bbox_min_lon,
                bbox_min_lat=bbox_min_lat,
                bbox_max_lon=bbox_max_lon,
                bbox_max_lat=bbox_max_lat,
                community_name=community_name,
                community_id=community_id,
                panel_id=panel_id,
                highest_risk_zone=highest_risk,
                in_sfha=in_sfha,
                insurance_required=insurance_required,
                query_date=datetime.utcnow(),
                data_source=RegulatoryDataSource.FEMA_NFHL,
                cache_hit=False,
            )

        except Exception as e:
            logger.error(f"Failed to parse FEMA response: {e}")
            # Return empty FloodplainData on parse failure
            return FloodplainData(
                location_lon=longitude,
                location_lat=latitude,
                bbox_min_lon=bbox_min_lon,
                bbox_min_lat=bbox_min_lat,
                bbox_max_lon=bbox_max_lon,
                bbox_max_lat=bbox_max_lat,
                data_source=RegulatoryDataSource.FEMA_NFHL,
            )

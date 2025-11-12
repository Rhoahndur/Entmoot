"""
Property Boundary Extraction Service.

This module provides functionality to identify and validate property boundaries
from parsed KML/KMZ data, with multiple identification strategies and comprehensive
geometry validation.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

from ..core.parsers.kml_parser import ParsedKML, Placemark
from ..models.boundary import (
    BoundaryExtractionResult,
    BoundaryMetadata,
    BoundaryMetrics,
    BoundarySource,
    GeometryIssue,
    PropertyBoundary,
    SubParcel,
)

logger = logging.getLogger(__name__)

# Constants for unit conversions
SQM_TO_ACRES = 0.000247105  # 1 square meter = 0.000247105 acres
METERS_TO_FEET = 3.28084  # 1 meter = 3.28084 feet


class BoundaryExtractionService:
    """
    Service for extracting and validating property boundaries from parsed KML/KMZ data.

    Supports multiple identification strategies:
    - Name pattern matching (property, parcel, boundary, site, lot)
    - Layer/folder name analysis
    - Metadata/extended data examination
    - Largest polygon heuristic (fallback)
    """

    # Name patterns that indicate a property boundary
    BOUNDARY_NAME_PATTERNS = [
        r"property\s*boundary",
        r"property\s*line",
        r"parcel\s*boundary",
        r"parcel\s*line",
        r"site\s*boundary",
        r"boundary",
        r"parcel",
        r"property",
        r"site",
        r"lot\s*line",
        r"lot\s*boundary",
        r"lot\s*\d+",
    ]

    # Folder names that indicate boundaries
    BOUNDARY_FOLDER_PATTERNS = [
        r"boundar(?:y|ies)",
        r"parcel",
        r"property",
        r"site",
        r"lot",
    ]

    # Metadata keys that indicate boundaries
    BOUNDARY_METADATA_KEYS = [
        "boundary",
        "parcel",
        "property",
        "apn",
        "parcel_id",
        "lot",
    ]

    def __init__(self, auto_repair: bool = True, min_area_sqm: float = 1.0):
        """
        Initialize boundary extraction service.

        Args:
            auto_repair: Whether to attempt automatic repair of invalid geometries
            min_area_sqm: Minimum area in square meters for valid boundaries
        """
        self.auto_repair = auto_repair
        self.min_area_sqm = min_area_sqm

    def extract_boundaries(
        self, parsed_kml: ParsedKML, strategy: Optional[BoundarySource] = None
    ) -> BoundaryExtractionResult:
        """
        Extract property boundaries from parsed KML data.

        Args:
            parsed_kml: Parsed KML data containing placemarks
            strategy: Optional specific strategy to use (None = auto-detect)

        Returns:
            BoundaryExtractionResult with extracted boundaries and metadata
        """
        result = BoundaryExtractionResult(
            success=False,
            total_placemarks=parsed_kml.placemark_count,
            total_polygons=len(parsed_kml.get_property_boundaries()),
        )

        try:
            # Get polygon placemarks (excluding contours)
            polygon_placemarks = parsed_kml.get_property_boundaries()

            if not polygon_placemarks:
                result.errors.append("No polygon placemarks found in KML")
                return result

            # Try identification strategies in order
            boundaries = []
            used_strategy = None

            if strategy:
                # Use specific strategy
                boundaries = self._apply_strategy(polygon_placemarks, strategy)
                used_strategy = strategy
            else:
                # Try strategies in priority order
                strategies = [
                    BoundarySource.NAME_PATTERN,
                    BoundarySource.METADATA,
                    BoundarySource.LAYER_NAME,
                    BoundarySource.LARGEST_POLYGON,
                ]

                for strat in strategies:
                    boundaries = self._apply_strategy(polygon_placemarks, strat)
                    if boundaries:
                        used_strategy = strat
                        break

            if not boundaries:
                result.errors.append("No property boundaries could be identified")
                return result

            # Process each identified boundary
            property_boundaries = []
            for placemark in boundaries:
                try:
                    boundary = self._process_boundary(placemark, used_strategy)
                    if boundary:
                        property_boundaries.append(boundary)
                except Exception as e:
                    error_msg = f"Failed to process boundary '{placemark.name}': {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            if not property_boundaries:
                result.errors.append("No valid boundaries could be extracted")
                return result

            result.success = True
            result.boundaries = property_boundaries
            result.extraction_strategy = used_strategy

            # Add warnings for small or suspicious polygons
            for boundary in property_boundaries:
                if boundary.metrics.area_sqm < self.min_area_sqm:
                    result.warnings.append(
                        f"Boundary '{boundary.metadata.name}' has very small area: "
                        f"{boundary.metrics.area_sqm:.2f} sqm"
                    )

            return result

        except Exception as e:
            error_msg = f"Boundary extraction failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            return result

    def _apply_strategy(
        self, placemarks: List[Placemark], strategy: BoundarySource
    ) -> List[Placemark]:
        """
        Apply a specific identification strategy to find boundaries.

        Args:
            placemarks: List of polygon placemarks
            strategy: Strategy to apply

        Returns:
            List of placemarks identified as boundaries
        """
        if strategy == BoundarySource.NAME_PATTERN:
            return self._identify_by_name(placemarks)
        elif strategy == BoundarySource.LAYER_NAME:
            return self._identify_by_folder(placemarks)
        elif strategy == BoundarySource.METADATA:
            return self._identify_by_metadata(placemarks)
        elif strategy == BoundarySource.LARGEST_POLYGON:
            return self._identify_by_size(placemarks)
        else:
            return []

    def _identify_by_name(self, placemarks: List[Placemark]) -> List[Placemark]:
        """Identify boundaries by name pattern matching."""
        matches = []
        for placemark in placemarks:
            if not placemark.name:
                continue

            name_lower = placemark.name.lower()
            for pattern in self.BOUNDARY_NAME_PATTERNS:
                if re.search(pattern, name_lower):
                    matches.append(placemark)
                    break

        return matches

    def _identify_by_folder(self, placemarks: List[Placemark]) -> List[Placemark]:
        """Identify boundaries by folder/layer name."""
        matches = []
        for placemark in placemarks:
            if not placemark.folder_path:
                continue

            folder_text = " ".join(placemark.folder_path).lower()
            for pattern in self.BOUNDARY_FOLDER_PATTERNS:
                if re.search(pattern, folder_text):
                    matches.append(placemark)
                    break

        return matches

    def _identify_by_metadata(self, placemarks: List[Placemark]) -> List[Placemark]:
        """Identify boundaries by metadata/extended data."""
        matches = []
        for placemark in placemarks:
            if not placemark.properties:
                continue

            property_keys = [k.lower() for k in placemark.properties.keys()]
            for key in self.BOUNDARY_METADATA_KEYS:
                if key in property_keys:
                    matches.append(placemark)
                    break

        return matches

    def _identify_by_size(self, placemarks: List[Placemark]) -> List[Placemark]:
        """Identify boundaries by selecting largest polygon(s)."""
        if not placemarks:
            return []

        # Calculate areas
        placemark_areas = []
        for placemark in placemarks:
            if placemark.geometry and isinstance(placemark.geometry, Polygon):
                area = placemark.geometry.area
                placemark_areas.append((placemark, area))

        if not placemark_areas:
            return []

        # Sort by area descending
        placemark_areas.sort(key=lambda x: x[1], reverse=True)

        # Return largest polygon (could be extended to return multiple if needed)
        return [placemark_areas[0][0]]

    def _process_boundary(
        self, placemark: Placemark, source: Optional[BoundarySource]
    ) -> Optional[PropertyBoundary]:
        """
        Process a placemark into a PropertyBoundary with validation and metrics.

        Args:
            placemark: Placemark to process
            source: Identification source

        Returns:
            PropertyBoundary or None if processing fails
        """
        if not placemark.geometry:
            return None

        # Accept both Polygon and MultiPolygon
        if not isinstance(placemark.geometry, (Polygon, MultiPolygon)):
            return None

        geometry = placemark.geometry
        repaired = False

        # Handle multi-polygon properties
        is_multi_parcel = isinstance(geometry, MultiPolygon)
        sub_parcels = []

        if is_multi_parcel:
            # For MultiPolygon, extract sub-parcels first
            sub_parcels = self._extract_sub_parcels(geometry)
            # Use the whole MultiPolygon for validation and metrics
            is_valid = True  # Assume valid if all sub-polygons are valid
            validation_issues = []

            # Validate each sub-polygon
            for poly in geometry.geoms:
                poly_valid, poly_issues = self._validate_geometry(poly)
                if not poly_valid:
                    is_valid = False
                    validation_issues.extend(poly_issues)

            # Calculate metrics for the entire MultiPolygon
            metrics = self._calculate_metrics_multipolygon(geometry)
        else:
            # Single polygon processing
            # Validate geometry
            is_valid, validation_issues = self._validate_geometry(geometry)

            # Attempt repair if invalid and auto_repair is enabled
            if not is_valid and self.auto_repair:
                repaired_geom = self._repair_geometry(geometry)
                if repaired_geom and repaired_geom.is_valid:
                    geometry = repaired_geom
                    is_valid = True
                    validation_issues = []
                    repaired = True
                    logger.info(f"Successfully repaired geometry for '{placemark.name}'")

            # Calculate metrics
            metrics = self._calculate_metrics(geometry)

        # Extract metadata
        metadata = self._extract_metadata(placemark, source or BoundarySource.MANUAL)

        # Create PropertyBoundary
        boundary = PropertyBoundary(
            geometry_wkt=geometry.wkt,
            metrics=metrics,
            metadata=metadata,
            is_valid=is_valid,
            validation_issues=validation_issues,
            is_multi_parcel=is_multi_parcel,
            sub_parcels=sub_parcels,
            repaired=repaired,
        )

        return boundary

    def _validate_geometry(self, geometry: BaseGeometry) -> Tuple[bool, List[GeometryIssue]]:
        """
        Validate polygon geometry.

        Args:
            geometry: Geometry to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check if geometry is valid
        if not geometry.is_valid:
            reason = explain_validity(geometry)
            logger.warning(f"Invalid geometry: {reason}")

            # Classify the issue
            if "self-intersection" in reason.lower():
                issues.append(GeometryIssue.SELF_INTERSECTION)
            elif "ring" in reason.lower():
                issues.append(GeometryIssue.UNCLOSED_RING)
            else:
                issues.append(GeometryIssue.INVALID_GEOMETRY)

        if isinstance(geometry, Polygon):
            # Check exterior ring
            exterior = geometry.exterior
            coords = list(exterior.coords)

            # Check if ring is closed
            if coords[0] != coords[-1]:
                issues.append(GeometryIssue.UNCLOSED_RING)

            # Check minimum vertices
            unique_coords = len(set(coords[:-1]))  # Exclude closing point
            if unique_coords < 3:
                issues.append(GeometryIssue.INSUFFICIENT_VERTICES)

            # Check coordinate validity
            for lon, lat in coords:
                if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                    issues.append(GeometryIssue.INVALID_COORDINATES)
                    break

        return len(issues) == 0, issues

    def _repair_geometry(self, geometry: BaseGeometry) -> Optional[BaseGeometry]:
        """
        Attempt to repair invalid geometry.

        Uses Shapely's buffer(0) trick which can fix many common issues.

        Args:
            geometry: Geometry to repair

        Returns:
            Repaired geometry or None if repair failed
        """
        try:
            # buffer(0) is a common trick to fix self-intersections and other issues
            repaired = geometry.buffer(0)

            if repaired.is_valid and not repaired.is_empty:
                return repaired

            return None

        except Exception as e:
            logger.error(f"Failed to repair geometry: {e}")
            return None

    def _calculate_metrics(self, geometry: Polygon) -> BoundaryMetrics:
        """
        Calculate boundary metrics.

        Args:
            geometry: Polygon geometry

        Returns:
            BoundaryMetrics with calculated values
        """
        # Area (in square degrees, needs to be converted to square meters for accurate results)
        # Note: For accurate area calculation, would need to project to appropriate CRS
        # For now, using simple approximation
        area_sqm = self._calculate_area_sqm(geometry)
        area_acres = area_sqm * SQM_TO_ACRES

        # Perimeter
        perimeter_m = self._calculate_perimeter_m(geometry)
        perimeter_ft = perimeter_m * METERS_TO_FEET

        # Centroid
        centroid = geometry.centroid
        centroid_lon = centroid.x
        centroid_lat = centroid.y

        # Bounding box
        bbox = geometry.bounds  # (minx, miny, maxx, maxy)
        bbox_min_lon = bbox[0]
        bbox_min_lat = bbox[1]
        bbox_max_lon = bbox[2]
        bbox_max_lat = bbox[3]

        # Holes
        has_holes = len(geometry.interiors) > 0
        hole_count = len(geometry.interiors)

        # Vertices
        vertex_count = len(geometry.exterior.coords) - 1  # Exclude closing point

        return BoundaryMetrics(
            area_sqm=area_sqm,
            area_acres=area_acres,
            perimeter_m=perimeter_m,
            perimeter_ft=perimeter_ft,
            centroid_lon=centroid_lon,
            centroid_lat=centroid_lat,
            bbox_min_lon=bbox_min_lon,
            bbox_min_lat=bbox_min_lat,
            bbox_max_lon=bbox_max_lon,
            bbox_max_lat=bbox_max_lat,
            has_holes=has_holes,
            hole_count=hole_count,
            vertex_count=vertex_count,
        )

    def _calculate_metrics_multipolygon(self, geometry: MultiPolygon) -> BoundaryMetrics:
        """
        Calculate boundary metrics for a MultiPolygon.

        Args:
            geometry: MultiPolygon geometry

        Returns:
            BoundaryMetrics with calculated values for the entire MultiPolygon
        """
        # Calculate total area across all polygons
        total_area_sqm = 0.0
        total_perimeter_m = 0.0
        total_holes = 0
        total_vertices = 0

        for polygon in geometry.geoms:
            total_area_sqm += self._calculate_area_sqm(polygon)
            total_perimeter_m += self._calculate_perimeter_m(polygon)
            total_holes += len(polygon.interiors)
            total_vertices += len(polygon.exterior.coords) - 1

        total_area_acres = total_area_sqm * SQM_TO_ACRES
        total_perimeter_ft = total_perimeter_m * METERS_TO_FEET

        # Centroid of the entire MultiPolygon
        centroid = geometry.centroid
        centroid_lon = centroid.x
        centroid_lat = centroid.y

        # Bounding box of the entire MultiPolygon
        bbox = geometry.bounds
        bbox_min_lon = bbox[0]
        bbox_min_lat = bbox[1]
        bbox_max_lon = bbox[2]
        bbox_max_lat = bbox[3]

        # Check if any polygon has holes
        has_holes = total_holes > 0

        return BoundaryMetrics(
            area_sqm=total_area_sqm,
            area_acres=total_area_acres,
            perimeter_m=total_perimeter_m,
            perimeter_ft=total_perimeter_ft,
            centroid_lon=centroid_lon,
            centroid_lat=centroid_lat,
            bbox_min_lon=bbox_min_lon,
            bbox_min_lat=bbox_min_lat,
            bbox_max_lon=bbox_max_lon,
            bbox_max_lat=bbox_max_lat,
            has_holes=has_holes,
            hole_count=total_holes,
            vertex_count=total_vertices,
        )

    def _calculate_area_sqm(self, geometry: Polygon) -> float:
        """
        Calculate area in square meters.

        Uses approximate conversion from square degrees.
        For accurate results, would need to project to appropriate CRS.

        Args:
            geometry: Polygon geometry

        Returns:
            Area in square meters (approximate)
        """
        # Get centroid for latitude-based conversion
        centroid = geometry.centroid
        lat = centroid.y

        # Area in square degrees
        area_deg2 = geometry.area

        # Approximate conversion to square meters
        # At equator: 1 degree longitude ≈ 111,320 meters
        # 1 degree latitude ≈ 110,574 meters (constant)
        # Longitude varies by latitude: cos(lat) * 111,320
        import math

        lat_rad = math.radians(lat)
        meters_per_deg_lon = math.cos(lat_rad) * 111320
        meters_per_deg_lat = 110574

        # Average for rough approximation
        meters_per_deg = (meters_per_deg_lon + meters_per_deg_lat) / 2
        area_sqm = area_deg2 * (meters_per_deg**2)

        return area_sqm

    def _calculate_perimeter_m(self, geometry: Polygon) -> float:
        """
        Calculate perimeter in meters.

        Uses approximate conversion from degrees.

        Args:
            geometry: Polygon geometry

        Returns:
            Perimeter in meters (approximate)
        """
        import math

        # Get centroid for latitude-based conversion
        centroid = geometry.centroid
        lat = centroid.y

        lat_rad = math.radians(lat)
        meters_per_deg_lon = math.cos(lat_rad) * 111320
        meters_per_deg_lat = 110574

        # Calculate perimeter
        coords = list(geometry.exterior.coords)
        perimeter_deg = 0.0

        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]

            # Convert to meters
            dlon = abs(lon2 - lon1) * meters_per_deg_lon
            dlat = abs(lat2 - lat1) * meters_per_deg_lat

            # Euclidean distance
            segment_length = math.sqrt(dlon**2 + dlat**2)
            perimeter_deg += segment_length

        return perimeter_deg

    def _extract_metadata(
        self, placemark: Placemark, source: BoundarySource
    ) -> BoundaryMetadata:
        """
        Extract boundary metadata from placemark.

        Args:
            placemark: Placemark to extract from
            source: Identification source

        Returns:
            BoundaryMetadata
        """
        # Extract potential address from properties or description
        address = None
        parcel_id = None

        # Check properties for address and parcel ID
        if placemark.properties:
            for key, value in placemark.properties.items():
                key_lower = key.lower()
                if "address" in key_lower or "location" in key_lower:
                    address = str(value)
                elif any(
                    k in key_lower for k in ["apn", "parcel_id", "parcel", "lot_number"]
                ):
                    parcel_id = str(value)

        # Try to extract from description
        if not address and placemark.description:
            address_match = re.search(
                r"\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct|boulevard|blvd)",
                placemark.description,
                re.IGNORECASE,
            )
            if address_match:
                address = address_match.group(0)

        return BoundaryMetadata(
            name=placemark.name,
            description=placemark.description,
            address=address,
            parcel_id=parcel_id,
            properties=placemark.properties.copy(),
            folder_path=placemark.folder_path.copy(),
            source=source,
        )

    def _extract_sub_parcels(self, geometry: MultiPolygon) -> List[SubParcel]:
        """
        Extract sub-parcels from a MultiPolygon.

        Args:
            geometry: MultiPolygon geometry

        Returns:
            List of SubParcel objects
        """
        sub_parcels = []

        for i, polygon in enumerate(geometry.geoms):
            # Calculate metrics for this sub-parcel
            area_sqm = self._calculate_area_sqm(polygon)
            area_acres = area_sqm * SQM_TO_ACRES

            centroid = polygon.centroid

            sub_parcel = SubParcel(
                parcel_id=f"parcel_{i + 1}",
                geometry_wkt=polygon.wkt,
                area_sqm=area_sqm,
                area_acres=area_acres,
                centroid_lon=centroid.x,
                centroid_lat=centroid.y,
            )
            sub_parcels.append(sub_parcel)

        return sub_parcels


def extract_boundaries_from_kml(
    parsed_kml: ParsedKML,
    strategy: Optional[BoundarySource] = None,
    auto_repair: bool = True,
    min_area_sqm: float = 1.0,
) -> BoundaryExtractionResult:
    """
    Convenience function to extract boundaries from parsed KML.

    Args:
        parsed_kml: Parsed KML data
        strategy: Optional specific strategy to use
        auto_repair: Whether to attempt automatic repair
        min_area_sqm: Minimum area for valid boundaries

    Returns:
        BoundaryExtractionResult
    """
    service = BoundaryExtractionService(auto_repair=auto_repair, min_area_sqm=min_area_sqm)
    return service.extract_boundaries(parsed_kml, strategy=strategy)

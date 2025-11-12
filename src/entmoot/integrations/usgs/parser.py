"""
USGS API response parser.

Parses JSON responses from USGS Elevation Point Query Service (EPQS)
and extracts elevation data, metadata, and error information.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from entmoot.models.elevation import (
    ElevationDataSource,
    ElevationDatum,
    ElevationPoint,
    ElevationUnit,
)

logger = logging.getLogger(__name__)


class USGSResponseParser:
    """
    Parser for USGS API responses.

    Handles:
    - Elevation Point Query Service (EPQS) responses
    - Error responses
    - Metadata extraction
    """

    def parse_epqs_response(
        self,
        data: Dict[str, Any],
        longitude: float,
        latitude: float,
        unit: ElevationUnit = ElevationUnit.METERS,
    ) -> ElevationPoint:
        """
        Parse EPQS JSON response for a single point.

        Expected response format:
        {
            "value": 123.45,
            "resolution": 1.0,
            "units": "Meters",
            "data_source": "3DEP 1 arc-second"
        }

        Args:
            data: JSON response data
            longitude: Longitude coordinate
            latitude: Latitude coordinate
            unit: Elevation unit

        Returns:
            ElevationPoint with parsed data
        """
        try:
            # Extract elevation value
            elevation = None
            if "value" in data and data["value"] is not None:
                try:
                    elevation = float(data["value"])
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to parse elevation value: {data['value']}, error: {e}")

            # Extract resolution
            resolution = None
            if "resolution" in data:
                try:
                    resolution = float(data["resolution"])
                except (ValueError, TypeError):
                    pass

            # Determine data source from resolution or metadata
            data_source = self._determine_data_source(data, resolution)

            # Extract datum
            datum = self._extract_datum(data)

            # Extract units (to verify match)
            response_unit = data.get("units", "").lower()
            if "meter" in response_unit and unit == ElevationUnit.FEET:
                logger.warning(f"Unit mismatch: requested {unit.value}, got {response_unit}")
            elif "feet" in response_unit or "foot" in response_unit:
                if unit == ElevationUnit.METERS and elevation is not None:
                    # Convert feet to meters
                    elevation = elevation * 0.3048
                    logger.debug(f"Converted elevation from feet to meters: {elevation}")

            # Extract coordinates from response if available
            x_coord = data.get("x")
            y_coord = data.get("y")

            point = ElevationPoint(
                longitude=longitude,
                latitude=latitude,
                elevation=elevation,
                unit=unit,
                datum=datum,
                resolution=resolution,
                data_source=data_source,
                query_timestamp=datetime.utcnow(),
                x_coord=x_coord,
                y_coord=y_coord,
            )

            return point

        except Exception as e:
            logger.error(f"Failed to parse EPQS response: {e}, data: {data}")
            return ElevationPoint(
                longitude=longitude,
                latitude=latitude,
                elevation=None,
                unit=unit,
                data_source=ElevationDataSource.UNKNOWN,
            )

    def parse_batch_response(
        self,
        responses: List[Dict[str, Any]],
        coordinates: List[tuple[float, float]],
        unit: ElevationUnit = ElevationUnit.METERS,
    ) -> List[ElevationPoint]:
        """
        Parse batch EPQS responses.

        Args:
            responses: List of JSON response data
            coordinates: List of (longitude, latitude) tuples
            unit: Elevation unit

        Returns:
            List of ElevationPoints
        """
        if len(responses) != len(coordinates):
            logger.error(
                f"Response count ({len(responses)}) does not match "
                f"coordinate count ({len(coordinates)})"
            )
            # Pad with None responses if needed
            while len(responses) < len(coordinates):
                responses.append({})

        points = []
        for data, (lon, lat) in zip(responses, coordinates):
            point = self.parse_epqs_response(data, lon, lat, unit)
            points.append(point)

        return points

    def _determine_data_source(
        self, data: Dict[str, Any], resolution: Optional[float]
    ) -> ElevationDataSource:
        """
        Determine data source from response metadata.

        Args:
            data: Response data
            resolution: Resolution in arc-seconds

        Returns:
            ElevationDataSource enum
        """
        # Check explicit data source field
        if "data_source" in data:
            source_str = str(data["data_source"]).lower()
            if "1-meter" in source_str or "1 meter" in source_str:
                return ElevationDataSource.USGS_3DEP_1M
            elif "1/3" in source_str or "0.33" in source_str:
                return ElevationDataSource.USGS_3DEP_1_3M
            elif "1 arc" in source_str or "1-arc" in source_str:
                return ElevationDataSource.USGS_3DEP_1ARC
            elif "2 arc" in source_str or "2-arc" in source_str:
                return ElevationDataSource.USGS_3DEP_2ARC
            elif "3dep" in source_str:
                return ElevationDataSource.USGS_3DEP_1ARC
            elif "ned" in source_str:
                return ElevationDataSource.NED
            elif "srtm" in source_str:
                return ElevationDataSource.SRTM

        # Infer from resolution
        if resolution is not None:
            if resolution < 0.01:  # ~1 meter
                return ElevationDataSource.USGS_3DEP_1M
            elif resolution <= 0.33:  # 1/3 arc-second
                return ElevationDataSource.USGS_3DEP_1_3M
            elif resolution <= 1.0:  # 1 arc-second
                return ElevationDataSource.USGS_3DEP_1ARC
            elif resolution <= 2.0:  # 2 arc-second
                return ElevationDataSource.USGS_3DEP_2ARC
            else:
                return ElevationDataSource.NED

        return ElevationDataSource.USGS_3DEP_1ARC  # Default

    def _extract_datum(self, data: Dict[str, Any]) -> ElevationDatum:
        """
        Extract vertical datum from response.

        Args:
            data: Response data

        Returns:
            ElevationDatum enum
        """
        # Check explicit datum field
        if "datum" in data:
            datum_str = str(data["datum"]).upper()
            if "NAVD88" in datum_str or "NAVD 88" in datum_str:
                return ElevationDatum.NAVD88
            elif "NGVD29" in datum_str or "NGVD 29" in datum_str:
                return ElevationDatum.NGVD29
            elif "WGS84" in datum_str or "WGS 84" in datum_str:
                return ElevationDatum.WGS84
            elif "MSL" in datum_str:
                return ElevationDatum.MSL

        # Check vertical_datum field
        if "vertical_datum" in data:
            datum_str = str(data["vertical_datum"]).upper()
            if "NAVD88" in datum_str:
                return ElevationDatum.NAVD88
            elif "NGVD29" in datum_str:
                return ElevationDatum.NGVD29

        # Default to NAVD88 (most common for USGS data)
        return ElevationDatum.NAVD88

    def parse_error_response(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Parse error response from USGS API.

        Args:
            data: Response data

        Returns:
            Error message if present, None otherwise
        """
        # Check for explicit error field
        if "error" in data:
            error = data["error"]
            if isinstance(error, dict):
                return error.get("message", str(error))
            return str(error)

        # Check for error message field
        if "error_message" in data:
            return str(data["error_message"])

        # Check for status field
        if "status" in data:
            status = str(data["status"]).lower()
            if "error" in status or "fail" in status:
                return data.get("message", f"Query failed with status: {status}")

        # Check if value is explicitly null with a reason
        if "value" in data and data["value"] is None:
            if "message" in data:
                return str(data["message"])
            return "No elevation data available for this location"

        return None

    def validate_response(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate USGS API response.

        Args:
            data: Response data

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for error response
        error_msg = self.parse_error_response(data)
        if error_msg:
            return False, error_msg

        # Check for required fields
        if "value" not in data:
            return False, "Missing 'value' field in response"

        # Check if value is a valid number
        if data["value"] is not None:
            try:
                float(data["value"])
            except (ValueError, TypeError):
                return False, f"Invalid elevation value: {data['value']}"

        return True, None

    def extract_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from response.

        Args:
            data: Response data

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        # Extract available fields
        fields = [
            "resolution",
            "units",
            "datum",
            "vertical_datum",
            "data_source",
            "x",
            "y",
            "wkid",
            "includeDate",
            "date",
        ]

        for field in fields:
            if field in data:
                metadata[field] = data[field]

        return metadata

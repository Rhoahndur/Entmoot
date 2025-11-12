"""
CRS detection from various geospatial file formats.

This module provides functionality to detect Coordinate Reference Systems
from KML, GeoTIFF, GeoJSON, and other geospatial file formats.
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Union

try:
    from osgeo import gdal, osr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

from pyproj import CRS

from entmoot.models.crs import CRSInfo, CoordinateOrder, DistanceUnit


class CRSDetectionError(Exception):
    """Raised when CRS cannot be detected from a file."""
    pass


def detect_crs_from_file(file_path: Union[str, Path]) -> CRSInfo:
    """
    Detect CRS from a geospatial file.

    Automatically determines file type and uses appropriate detection method.

    Args:
        file_path: Path to geospatial file

    Returns:
        Detected CRSInfo

    Raises:
        CRSDetectionError: If CRS cannot be detected
        FileNotFoundError: If file does not exist
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Determine file type by extension
    suffix = file_path.suffix.lower()

    if suffix in ['.kml', '.kmz']:
        return detect_crs_from_kml(file_path)
    elif suffix in ['.tif', '.tiff', '.geotiff']:
        return detect_crs_from_geotiff(file_path)
    elif suffix in ['.json', '.geojson']:
        return detect_crs_from_geojson(file_path)
    elif suffix in ['.shp', '.gpkg']:
        return detect_crs_from_ogr(file_path)
    else:
        raise CRSDetectionError(f"Unsupported file format: {suffix}")


def detect_crs_from_kml(file_path: Union[str, Path]) -> CRSInfo:
    """
    Detect CRS from KML file.

    KML files typically use WGS84 (EPSG:4326) by default, but may specify
    a different CRS in the XML.

    Args:
        file_path: Path to KML file

    Returns:
        Detected CRSInfo (usually WGS84)

    Raises:
        CRSDetectionError: If CRS cannot be detected
    """
    file_path = Path(file_path)

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Check for namespace
        namespace = {'kml': 'http://www.opengis.net/kml/2.2'}

        # Look for SRS or CRS elements (non-standard but sometimes present)
        srs_elem = root.find('.//kml:srs', namespace)
        if srs_elem is not None and srs_elem.text:
            return parse_crs_string(srs_elem.text)

        crs_elem = root.find('.//kml:crs', namespace)
        if crs_elem is not None and crs_elem.text:
            return parse_crs_string(crs_elem.text)

        # KML standard specifies WGS84 as default
        return CRSInfo(
            epsg=4326,
            name="WGS 84",
            units=DistanceUnit.DEGREES,
            is_geographic=True,
            coordinate_order=CoordinateOrder.LON_LAT,
            authority="EPSG",
            code="4326",
        )

    except ET.ParseError as e:
        raise CRSDetectionError(f"Failed to parse KML file: {e}")
    except Exception as e:
        raise CRSDetectionError(f"Error detecting CRS from KML: {e}")


def detect_crs_from_geotiff(file_path: Union[str, Path]) -> CRSInfo:
    """
    Detect CRS from GeoTIFF file metadata.

    Args:
        file_path: Path to GeoTIFF file

    Returns:
        Detected CRSInfo

    Raises:
        CRSDetectionError: If CRS cannot be detected
        ImportError: If GDAL is not available
    """
    if not GDAL_AVAILABLE:
        raise ImportError("GDAL is required for GeoTIFF CRS detection")

    file_path = Path(file_path)

    try:
        dataset = gdal.Open(str(file_path), gdal.GA_ReadOnly)
        if dataset is None:
            raise CRSDetectionError(f"Failed to open GeoTIFF: {file_path}")

        # Get spatial reference
        wkt = dataset.GetProjection()
        if not wkt:
            raise CRSDetectionError("No CRS information in GeoTIFF")

        # Parse with pyproj
        crs = CRS.from_wkt(wkt)
        return crs_to_info(crs)

    except Exception as e:
        raise CRSDetectionError(f"Error detecting CRS from GeoTIFF: {e}")


def detect_crs_from_geojson(file_path: Union[str, Path]) -> CRSInfo:
    """
    Detect CRS from GeoJSON file.

    GeoJSON RFC 7946 specifies WGS84 as the default CRS, but older files
    may include a "crs" property.

    Args:
        file_path: Path to GeoJSON file

    Returns:
        Detected CRSInfo

    Raises:
        CRSDetectionError: If CRS cannot be detected
    """
    file_path = Path(file_path)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check for explicit CRS property (legacy)
        if 'crs' in data:
            crs_obj = data['crs']

            # Named CRS
            if crs_obj.get('type') == 'name':
                crs_name = crs_obj.get('properties', {}).get('name', '')
                return parse_crs_string(crs_name)

            # Linked CRS
            elif crs_obj.get('type') == 'link':
                href = crs_obj.get('properties', {}).get('href', '')
                return parse_crs_string(href)

        # RFC 7946 default: WGS84
        return CRSInfo(
            epsg=4326,
            name="WGS 84",
            units=DistanceUnit.DEGREES,
            is_geographic=True,
            coordinate_order=CoordinateOrder.LON_LAT,
            authority="EPSG",
            code="4326",
        )

    except json.JSONDecodeError as e:
        raise CRSDetectionError(f"Invalid GeoJSON: {e}")
    except Exception as e:
        raise CRSDetectionError(f"Error detecting CRS from GeoJSON: {e}")


def detect_crs_from_ogr(file_path: Union[str, Path]) -> CRSInfo:
    """
    Detect CRS from OGR-supported formats (Shapefile, GeoPackage, etc.).

    Args:
        file_path: Path to file

    Returns:
        Detected CRSInfo

    Raises:
        CRSDetectionError: If CRS cannot be detected
        ImportError: If GDAL is not available
    """
    if not GDAL_AVAILABLE:
        raise ImportError("GDAL is required for Shapefile/GeoPackage CRS detection")

    file_path = Path(file_path)

    try:
        from osgeo import ogr

        driver = ogr.GetDriverByName('ESRI Shapefile' if file_path.suffix == '.shp' else 'GPKG')
        dataset = driver.Open(str(file_path), 0)

        if dataset is None:
            raise CRSDetectionError(f"Failed to open file: {file_path}")

        layer = dataset.GetLayer()
        srs = layer.GetSpatialRef()

        if srs is None:
            raise CRSDetectionError("No CRS information in file")

        # Export to WKT
        wkt = srs.ExportToWkt()
        crs = CRS.from_wkt(wkt)
        return crs_to_info(crs)

    except Exception as e:
        raise CRSDetectionError(f"Error detecting CRS from OGR format: {e}")


def parse_crs_string(crs_string: str) -> CRSInfo:
    """
    Parse a CRS from various string representations.

    Supports:
    - EPSG codes: "EPSG:4326", "epsg:4326", "4326"
    - URN format: "urn:ogc:def:crs:EPSG::4326"
    - URL format: "http://www.opengis.net/def/crs/EPSG/0/4326"
    - PROJ4 strings: "+proj=longlat +datum=WGS84..."
    - WKT strings

    Args:
        crs_string: String representation of CRS

    Returns:
        CRSInfo object

    Raises:
        CRSDetectionError: If string cannot be parsed
    """
    crs_string = crs_string.strip()

    try:
        # Try EPSG code patterns
        epsg_match = re.search(r'EPSG[:\s]*(\d+)', crs_string, re.IGNORECASE)
        if epsg_match:
            epsg = int(epsg_match.group(1))
            crs = CRS.from_epsg(epsg)
            return crs_to_info(crs)

        # Try URN format
        urn_match = re.search(r'urn:ogc:def:crs:(\w+)::(\d+)', crs_string, re.IGNORECASE)
        if urn_match:
            authority = urn_match.group(1).upper()
            code = urn_match.group(2)
            if authority == 'EPSG':
                crs = CRS.from_epsg(int(code))
                return crs_to_info(crs)

        # Try URL format
        url_match = re.search(r'/crs/(\w+)/\d+/(\d+)', crs_string, re.IGNORECASE)
        if url_match:
            authority = url_match.group(1).upper()
            code = url_match.group(2)
            if authority == 'EPSG':
                crs = CRS.from_epsg(int(code))
                return crs_to_info(crs)

        # Try as pure number (assume EPSG)
        if crs_string.isdigit():
            crs = CRS.from_epsg(int(crs_string))
            return crs_to_info(crs)

        # Try PROJ4 string
        if crs_string.startswith('+proj'):
            crs = CRS.from_proj4(crs_string)
            return crs_to_info(crs)

        # Try WKT
        if 'PROJCS' in crs_string or 'GEOGCS' in crs_string:
            crs = CRS.from_wkt(crs_string)
            return crs_to_info(crs)

        # Try general pyproj parser as last resort
        crs = CRS.from_string(crs_string)
        return crs_to_info(crs)

    except Exception as e:
        raise CRSDetectionError(f"Failed to parse CRS string '{crs_string}': {e}")


def crs_to_info(crs: CRS) -> CRSInfo:
    """
    Convert pyproj CRS to CRSInfo.

    Args:
        crs: pyproj CRS object

    Returns:
        CRSInfo object
    """
    # Extract EPSG code if available
    epsg = None
    authority = None
    code = None

    if crs.to_epsg():
        epsg = crs.to_epsg()
        authority = "EPSG"
        code = str(epsg)
    elif crs.to_authority():
        auth_tuple = crs.to_authority()
        if auth_tuple:
            authority, code = auth_tuple
            if authority == "EPSG":
                try:
                    epsg = int(code)
                except ValueError:
                    pass

    # Determine units
    units = DistanceUnit.METERS
    if crs.is_geographic:
        units = DistanceUnit.DEGREES
    elif crs.axis_info:
        unit_name = crs.axis_info[0].unit_name.lower()
        if 'foot' in unit_name or 'feet' in unit_name:
            units = DistanceUnit.FEET
        elif 'meter' in unit_name or 'metre' in unit_name:
            units = DistanceUnit.METERS

    # Determine coordinate order
    coord_order = CoordinateOrder.LON_LAT
    if crs.is_geographic:
        # Check if lat comes first
        if crs.axis_info and len(crs.axis_info) >= 2:
            first_axis = crs.axis_info[0].direction.lower()
            if 'north' in first_axis or 'south' in first_axis:
                coord_order = CoordinateOrder.LAT_LON
    else:
        coord_order = CoordinateOrder.XY

    return CRSInfo(
        epsg=epsg,
        wkt=crs.to_wkt(),
        proj4=crs.to_proj4(),
        name=crs.name,
        units=units,
        is_geographic=crs.is_geographic,
        coordinate_order=coord_order,
        authority=authority,
        code=code,
    )


def detect_crs_from_prj(file_path: Union[str, Path]) -> CRSInfo:
    """
    Detect CRS from .prj file (Shapefile projection file).

    Args:
        file_path: Path to .prj file

    Returns:
        Detected CRSInfo

    Raises:
        CRSDetectionError: If CRS cannot be detected
    """
    file_path = Path(file_path)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            wkt = f.read().strip()

        crs = CRS.from_wkt(wkt)
        return crs_to_info(crs)

    except Exception as e:
        raise CRSDetectionError(f"Error detecting CRS from .prj file: {e}")

"""
Tests for CRS detection from various file formats.
"""

import json
import tempfile
from pathlib import Path

import pytest
from pyproj import CRS

from entmoot.core.crs import detector
from entmoot.models.crs import CoordinateOrder, DistanceUnit


class TestParseCRSString:
    """Tests for parsing CRS strings."""

    def test_parse_epsg_with_prefix(self) -> None:
        """Test parsing EPSG code with prefix."""
        crs_info = detector.parse_crs_string("EPSG:4326")
        assert crs_info.epsg == 4326
        assert crs_info.is_geographic is True

    def test_parse_epsg_lowercase(self) -> None:
        """Test parsing lowercase EPSG code."""
        crs_info = detector.parse_crs_string("epsg:4326")
        assert crs_info.epsg == 4326

    def test_parse_epsg_number_only(self) -> None:
        """Test parsing plain number as EPSG."""
        crs_info = detector.parse_crs_string("4326")
        assert crs_info.epsg == 4326

    def test_parse_epsg_urn_format(self) -> None:
        """Test parsing URN format."""
        crs_info = detector.parse_crs_string("urn:ogc:def:crs:EPSG::4326")
        assert crs_info.epsg == 4326

    def test_parse_epsg_url_format(self) -> None:
        """Test parsing URL format."""
        crs_info = detector.parse_crs_string(
            "http://www.opengis.net/def/crs/EPSG/0/4326"
        )
        assert crs_info.epsg == 4326

    def test_parse_proj4_string(self) -> None:
        """Test parsing PROJ4 string."""
        proj4 = "+proj=longlat +datum=WGS84 +no_defs"
        crs_info = detector.parse_crs_string(proj4)
        assert crs_info.is_geographic is True

    def test_parse_invalid_string(self) -> None:
        """Test error handling for invalid CRS string."""
        with pytest.raises(detector.CRSDetectionError):
            detector.parse_crs_string("invalid_crs_string")


class TestCRSToInfo:
    """Tests for converting pyproj CRS to CRSInfo."""

    def test_crs_to_info_wgs84(self) -> None:
        """Test conversion of WGS84."""
        crs = CRS.from_epsg(4326)
        crs_info = detector.crs_to_info(crs)

        assert crs_info.epsg == 4326
        assert crs_info.is_geographic is True
        assert crs_info.units == DistanceUnit.DEGREES
        assert crs_info.authority == "EPSG"
        assert crs_info.code == "4326"

    def test_crs_to_info_utm(self) -> None:
        """Test conversion of UTM zone."""
        crs = CRS.from_epsg(32631)  # UTM Zone 31N
        crs_info = detector.crs_to_info(crs)

        assert crs_info.epsg == 32631
        assert crs_info.is_geographic is False
        assert crs_info.units == DistanceUnit.METERS

    def test_crs_to_info_web_mercator(self) -> None:
        """Test conversion of Web Mercator."""
        crs = CRS.from_epsg(3857)
        crs_info = detector.crs_to_info(crs)

        assert crs_info.epsg == 3857
        assert crs_info.is_geographic is False


class TestDetectCRSFromKML:
    """Tests for detecting CRS from KML files."""

    def test_detect_crs_from_kml_default(self) -> None:
        """Test detection of default WGS84 from KML."""
        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <Point>
      <coordinates>-122.0822035425683,37.42228990140251,0</coordinates>
    </Point>
  </Placemark>
</kml>"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
            f.write(kml_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            crs_info = detector.detect_crs_from_kml(temp_path)
            assert crs_info.epsg == 4326
            assert crs_info.is_geographic is True
            assert crs_info.coordinate_order == CoordinateOrder.LON_LAT
        finally:
            temp_path.unlink()

    def test_detect_crs_from_kml_invalid_xml(self) -> None:
        """Test error handling for invalid KML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
            f.write("invalid xml content")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(detector.CRSDetectionError, match="Failed to parse KML"):
                detector.detect_crs_from_kml(temp_path)
        finally:
            temp_path.unlink()


class TestDetectCRSFromGeoJSON:
    """Tests for detecting CRS from GeoJSON files."""

    def test_detect_crs_from_geojson_default(self) -> None:
        """Test detection of default WGS84 from GeoJSON."""
        geojson_content = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.08, 37.42]
                    },
                    "properties": {}
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(geojson_content, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            crs_info = detector.detect_crs_from_geojson(temp_path)
            assert crs_info.epsg == 4326
            assert crs_info.is_geographic is True
        finally:
            temp_path.unlink()

    def test_detect_crs_from_geojson_with_named_crs(self) -> None:
        """Test detection of explicitly specified CRS in GeoJSON."""
        geojson_content = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:EPSG::32631"
                }
            },
            "features": []
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(geojson_content, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            crs_info = detector.detect_crs_from_geojson(temp_path)
            assert crs_info.epsg == 32631
        finally:
            temp_path.unlink()

    def test_detect_crs_from_geojson_invalid_json(self) -> None:
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            f.write("invalid json")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(detector.CRSDetectionError, match="Invalid GeoJSON"):
                detector.detect_crs_from_geojson(temp_path)
        finally:
            temp_path.unlink()


class TestDetectCRSFromFile:
    """Tests for automatic file type detection."""

    def test_detect_crs_from_kml_file(self) -> None:
        """Test automatic detection from .kml file."""
        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <Point>
      <coordinates>0,0,0</coordinates>
    </Point>
  </Placemark>
</kml>"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
            f.write(kml_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            crs_info = detector.detect_crs_from_file(temp_path)
            assert crs_info.epsg == 4326
        finally:
            temp_path.unlink()

    def test_detect_crs_from_geojson_file(self) -> None:
        """Test automatic detection from .geojson file."""
        geojson_content = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(geojson_content, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            crs_info = detector.detect_crs_from_file(temp_path)
            assert crs_info.epsg == 4326
        finally:
            temp_path.unlink()

    def test_detect_crs_from_file_not_found(self) -> None:
        """Test error handling for non-existent file."""
        with pytest.raises(FileNotFoundError):
            detector.detect_crs_from_file(Path("/nonexistent/file.kml"))

    def test_detect_crs_from_file_unsupported_format(self) -> None:
        """Test error handling for unsupported file format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(detector.CRSDetectionError, match="Unsupported file format"):
                detector.detect_crs_from_file(temp_path)
        finally:
            temp_path.unlink()


class TestDetectCRSFromPRJ:
    """Tests for detecting CRS from .prj files."""

    def test_detect_crs_from_prj_wgs84(self) -> None:
        """Test detection from .prj file with WGS84."""
        wkt = """GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.prj', delete=False) as f:
            f.write(wkt)
            f.flush()
            temp_path = Path(f.name)

        try:
            crs_info = detector.detect_crs_from_prj(temp_path)
            assert crs_info.epsg == 4326
        finally:
            temp_path.unlink()

    def test_detect_crs_from_prj_invalid_wkt(self) -> None:
        """Test error handling for invalid WKT."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.prj', delete=False) as f:
            f.write("invalid wkt")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(detector.CRSDetectionError):
                detector.detect_crs_from_prj(temp_path)
        finally:
            temp_path.unlink()


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_parse_crs_string_empty(self) -> None:
        """Test parsing empty string."""
        with pytest.raises(detector.CRSDetectionError):
            detector.parse_crs_string("")

    def test_parse_crs_string_whitespace(self) -> None:
        """Test parsing whitespace-only string."""
        with pytest.raises(detector.CRSDetectionError):
            detector.parse_crs_string("   ")

    def test_crs_to_info_without_epsg(self) -> None:
        """Test conversion of CRS without EPSG code."""
        # Create CRS from PROJ4 string without EPSG
        proj4 = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +no_defs"
        crs = CRS.from_proj4(proj4)
        crs_info = detector.crs_to_info(crs)

        # Should still create valid CRSInfo even without EPSG
        assert crs_info.wkt is not None
        assert crs_info.is_geographic is False

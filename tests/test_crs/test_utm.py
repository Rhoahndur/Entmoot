"""
Tests for UTM zone detection and utilities.
"""

import pytest
from entmoot.core.crs import utm
from entmoot.models.crs import CoordinateOrder, DistanceUnit


class TestUTMZoneDetection:
    """Tests for UTM zone detection."""

    def test_detect_utm_zone_london(self) -> None:
        """Test UTM zone detection for London, UK."""
        # London: 51.5074°N, 0.1278°W (zone 30)
        zone, is_northern = utm.detect_utm_zone(-0.1278, 51.5074)
        assert zone == 30
        assert is_northern is True

    def test_detect_utm_zone_new_york(self) -> None:
        """Test UTM zone detection for New York, USA."""
        # New York: 40.7128°N, 74.0060°W
        zone, is_northern = utm.detect_utm_zone(-74.0060, 40.7128)
        assert zone == 18
        assert is_northern is True

    def test_detect_utm_zone_sydney(self) -> None:
        """Test UTM zone detection for Sydney, Australia."""
        # Sydney: 33.8688°S, 151.2093°E
        zone, is_northern = utm.detect_utm_zone(151.2093, -33.8688)
        assert zone == 56
        assert is_northern is False

    def test_detect_utm_zone_tokyo(self) -> None:
        """Test UTM zone detection for Tokyo, Japan."""
        # Tokyo: 35.6762°N, 139.6503°E
        zone, is_northern = utm.detect_utm_zone(139.6503, 35.6762)
        assert zone == 54
        assert is_northern is True

    def test_detect_utm_zone_rio(self) -> None:
        """Test UTM zone detection for Rio de Janeiro, Brazil."""
        # Rio: 22.9068°S, 43.1729°W
        zone, is_northern = utm.detect_utm_zone(-43.1729, -22.9068)
        assert zone == 23
        assert is_northern is False

    def test_detect_utm_zone_equator(self) -> None:
        """Test UTM zone detection at equator."""
        # Exactly at equator
        zone, is_northern = utm.detect_utm_zone(0.0, 0.0)
        assert zone == 31
        assert is_northern is True  # 0° latitude is northern

    def test_detect_utm_zone_south_of_equator(self) -> None:
        """Test UTM zone detection just south of equator."""
        zone, is_northern = utm.detect_utm_zone(0.0, -0.1)
        assert zone == 31
        assert is_northern is False

    def test_detect_utm_zone_norway_special_case(self) -> None:
        """Test special case handling for Norway."""
        # Norway between 56-64°N, 3-12°E should use zone 32
        zone, is_northern = utm.detect_utm_zone(6.0, 60.0)
        assert zone == 32
        assert is_northern is True

    def test_detect_utm_zone_svalbard_special_case(self) -> None:
        """Test special case handling for Svalbard."""
        # Svalbard 72-84°N has special zones
        # 0-9°E should use zone 31
        zone, is_northern = utm.detect_utm_zone(5.0, 78.0)
        assert zone == 31
        assert is_northern is True

        # 9-21°E should use zone 33
        zone, is_northern = utm.detect_utm_zone(15.0, 78.0)
        assert zone == 33
        assert is_northern is True

    def test_detect_utm_zone_at_180_degrees(self) -> None:
        """Test UTM zone detection at 180° longitude."""
        zone, is_northern = utm.detect_utm_zone(180.0, 10.0)
        assert zone == 1
        assert is_northern is True

    def test_detect_utm_zone_invalid_longitude(self) -> None:
        """Test error handling for invalid longitude."""
        with pytest.raises(ValueError, match="Longitude must be between"):
            utm.detect_utm_zone(200.0, 0.0)

    def test_detect_utm_zone_invalid_latitude(self) -> None:
        """Test error handling for invalid latitude."""
        with pytest.raises(ValueError, match="Latitude must be between"):
            utm.detect_utm_zone(0.0, 100.0)


class TestUTMEPSG:
    """Tests for UTM EPSG code generation."""

    def test_get_utm_epsg_northern(self) -> None:
        """Test EPSG code for northern hemisphere UTM zones."""
        # Zone 31N should be EPSG:32631
        assert utm.get_utm_epsg(31, True) == 32631
        # Zone 1N should be EPSG:32601
        assert utm.get_utm_epsg(1, True) == 32601
        # Zone 60N should be EPSG:32660
        assert utm.get_utm_epsg(60, True) == 32660

    def test_get_utm_epsg_southern(self) -> None:
        """Test EPSG code for southern hemisphere UTM zones."""
        # Zone 31S should be EPSG:32731
        assert utm.get_utm_epsg(31, False) == 32731
        # Zone 1S should be EPSG:32701
        assert utm.get_utm_epsg(1, False) == 32701
        # Zone 60S should be EPSG:32760
        assert utm.get_utm_epsg(60, False) == 32760

    def test_get_utm_epsg_invalid_zone(self) -> None:
        """Test error handling for invalid zone numbers."""
        with pytest.raises(ValueError, match="UTM zone must be between"):
            utm.get_utm_epsg(0, True)

        with pytest.raises(ValueError, match="UTM zone must be between"):
            utm.get_utm_epsg(61, True)


class TestUTMCRSInfo:
    """Tests for UTM CRS info generation."""

    def test_get_utm_crs_info_northern(self) -> None:
        """Test CRS info for northern hemisphere."""
        # Paris coordinates (2.3522°E, 48.8566°N) - in zone 31N
        crs_info = utm.get_utm_crs_info(2.3522, 48.8566)

        assert crs_info.epsg == 32631  # Zone 31N
        assert crs_info.name == "WGS 84 / UTM zone 31N"
        assert crs_info.units == DistanceUnit.METERS
        assert crs_info.is_geographic is False
        assert crs_info.coordinate_order == CoordinateOrder.XY
        assert crs_info.authority == "EPSG"
        assert crs_info.code == "32631"

    def test_get_utm_crs_info_southern(self) -> None:
        """Test CRS info for southern hemisphere."""
        # Sydney coordinates
        crs_info = utm.get_utm_crs_info(151.2093, -33.8688)

        assert crs_info.epsg == 32756  # Zone 56S
        assert crs_info.name == "WGS 84 / UTM zone 56S"
        assert crs_info.units == DistanceUnit.METERS
        assert crs_info.is_geographic is False


class TestUTMZoneBounds:
    """Tests for UTM zone bounds."""

    def test_get_utm_zone_bounds_zone_1(self) -> None:
        """Test bounds for zone 1."""
        min_lon, max_lon = utm.get_utm_zone_bounds(1)
        assert min_lon == -180.0
        assert max_lon == -174.0

    def test_get_utm_zone_bounds_zone_31(self) -> None:
        """Test bounds for zone 31."""
        min_lon, max_lon = utm.get_utm_zone_bounds(31)
        assert min_lon == 0.0
        assert max_lon == 6.0

    def test_get_utm_zone_bounds_zone_60(self) -> None:
        """Test bounds for zone 60."""
        min_lon, max_lon = utm.get_utm_zone_bounds(60)
        assert min_lon == 174.0
        assert max_lon == 180.0

    def test_get_utm_zone_bounds_invalid(self) -> None:
        """Test error handling for invalid zone."""
        with pytest.raises(ValueError):
            utm.get_utm_zone_bounds(0)


class TestUTMCentralMeridian:
    """Tests for UTM central meridian calculation."""

    def test_calculate_utm_central_meridian_zone_1(self) -> None:
        """Test central meridian for zone 1."""
        cm = utm.calculate_utm_central_meridian(1)
        assert cm == -177.0

    def test_calculate_utm_central_meridian_zone_31(self) -> None:
        """Test central meridian for zone 31."""
        cm = utm.calculate_utm_central_meridian(31)
        assert cm == 3.0

    def test_calculate_utm_central_meridian_zone_60(self) -> None:
        """Test central meridian for zone 60."""
        cm = utm.calculate_utm_central_meridian(60)
        assert cm == 177.0

    def test_calculate_utm_central_meridian_invalid(self) -> None:
        """Test error handling for invalid zone."""
        with pytest.raises(ValueError):
            utm.calculate_utm_central_meridian(61)


class TestIsInUTMZone:
    """Tests for checking if coordinates are in a UTM zone."""

    def test_is_in_utm_zone_true(self) -> None:
        """Test coordinates that are in specified zone."""
        # London is in zone 30
        assert utm.is_in_utm_zone(-0.1278, 51.5074, 30) is True

    def test_is_in_utm_zone_false(self) -> None:
        """Test coordinates that are not in specified zone."""
        # London is not in zone 31
        assert utm.is_in_utm_zone(-0.1278, 51.5074, 31) is False

    def test_is_in_utm_zone_invalid_coordinates(self) -> None:
        """Test handling of invalid coordinates."""
        assert utm.is_in_utm_zone(200.0, 0.0, 31) is False


class TestScaleFactor:
    """Tests for UTM scale factor calculation."""

    def test_calculate_scale_factor_at_central_meridian(self) -> None:
        """Test scale factor at central meridian."""
        # At central meridian, scale factor should be close to 0.9996
        scale = utm.calculate_scale_factor(3.0, 51.0, 31)
        assert 0.9995 < scale < 0.9997

    def test_calculate_scale_factor_at_zone_edge(self) -> None:
        """Test scale factor at zone edge."""
        # At zone edge, scale factor should be slightly above 1.0
        scale = utm.calculate_scale_factor(6.0, 51.0, 31)
        assert scale > 1.0


class TestUTMLetterDesignator:
    """Tests for UTM letter designator."""

    def test_get_utm_letter_designator_various_latitudes(self) -> None:
        """Test letter designators for various latitudes."""
        # C band: -80 to -72
        assert utm.get_utm_letter_designator(-75.0) == "C"

        # N band: 0 to 8
        assert utm.get_utm_letter_designator(4.0) == "N"

        # R band: 24 to 32
        assert utm.get_utm_letter_designator(28.0) == "R"

        # S band: 32 to 40
        assert utm.get_utm_letter_designator(36.0) == "S"

        # X band: 72 to 84
        assert utm.get_utm_letter_designator(75.0) == "X"
        assert utm.get_utm_letter_designator(83.0) == "X"

    def test_get_utm_letter_designator_invalid_latitude(self) -> None:
        """Test error handling for invalid latitudes."""
        with pytest.raises(ValueError, match="UTM is only defined"):
            utm.get_utm_letter_designator(-85.0)

        with pytest.raises(ValueError, match="UTM is only defined"):
            utm.get_utm_letter_designator(85.0)


class TestFormatUTMZone:
    """Tests for UTM zone formatting."""

    def test_format_utm_zone_simple(self) -> None:
        """Test simple zone formatting without band."""
        assert utm.format_utm_zone(31, True) == "31N"
        assert utm.format_utm_zone(31, False) == "31S"

    def test_format_utm_zone_with_band(self) -> None:
        """Test zone formatting with latitude band."""
        # Zone 31 at 51°N should be in U band (48-56)
        assert utm.format_utm_zone(31, True, include_band=True, latitude=51.0) == "31U"

        # Zone 31 at 36°N should be in S band (32-40)
        assert utm.format_utm_zone(31, True, include_band=True, latitude=36.0) == "31S"

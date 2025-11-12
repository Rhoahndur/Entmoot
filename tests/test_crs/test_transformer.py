"""
Tests for CRS transformation service.
"""

import numpy as np
import pytest

from entmoot.core.crs import transformer
from entmoot.models.crs import BoundingBox, CRSInfo


class TestCRSTransformer:
    """Tests for CRSTransformer class."""

    def test_transform_wgs84_to_utm(self) -> None:
        """Test transformation from WGS84 to UTM."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # Transform Paris coordinates (2.3522°E, 48.8566°N)
        lon, lat = 2.3522, 48.8566
        easting, northing = trans.transform(lon, lat)

        # Paris in UTM 31N should be approximately:
        # Easting: ~450000, Northing: ~5400000
        assert 440000 < easting < 460000
        assert 5400000 < northing < 5420000

    def test_transform_utm_to_wgs84(self) -> None:
        """Test transformation from UTM to WGS84."""
        utm_31n = CRSInfo.from_epsg(32631)
        wgs84 = CRSInfo.from_epsg(4326)

        trans = transformer.CRSTransformer(utm_31n, wgs84)

        # Transform UTM coordinates back to WGS84 (Paris coordinates)
        easting, northing = 452000, 5411000
        lon, lat = trans.transform(easting, northing)

        # Should be close to Paris coordinates
        assert 2.0 < lon < 2.5
        assert 48.5 < lat < 49.0

    def test_transform_roundtrip(self) -> None:
        """Test round-trip transformation accuracy."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        # Original coordinates
        lon_orig, lat_orig = -0.1278, 51.5074

        # Forward transformation
        forward = transformer.CRSTransformer(wgs84, utm_31n)
        easting, northing = forward.transform(lon_orig, lat_orig)

        # Backward transformation
        backward = transformer.CRSTransformer(utm_31n, wgs84)
        lon_back, lat_back = backward.transform(easting, northing)

        # Should match original within tolerance
        assert abs(lon_orig - lon_back) < 1e-9
        assert abs(lat_orig - lat_back) < 1e-9

    def test_transform_with_elevation(self) -> None:
        """Test transformation with elevation/z coordinate."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        lon, lat, elev = -0.1278, 51.5074, 100.0
        x, y, z = trans.transform(lon, lat, elev)

        # Elevation should be preserved (approximately)
        assert abs(z - elev) < 0.01

    def test_transform_batch(self) -> None:
        """Test batch transformation of multiple coordinates."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # Multiple coordinates
        lons = [-0.1278, 0.0, 0.5]
        lats = [51.5074, 51.5, 51.6]

        eastings, northings = trans.transform_batch(lons, lats)

        # Should return numpy arrays
        assert isinstance(eastings, np.ndarray)
        assert isinstance(northings, np.ndarray)
        assert len(eastings) == 3
        assert len(northings) == 3

    def test_transform_batch_with_elevation(self) -> None:
        """Test batch transformation with elevation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        lons = [-0.1278, 0.0]
        lats = [51.5074, 51.5]
        elevs = [100.0, 200.0]

        eastings, northings, elevations = trans.transform_batch(lons, lats, elevs)

        assert len(eastings) == 2
        assert len(northings) == 2
        assert len(elevations) == 2

    def test_transform_batch_mismatched_lengths(self) -> None:
        """Test error handling for mismatched coordinate arrays."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        with pytest.raises(transformer.TransformationError, match="must have same length"):
            trans.transform_batch([0.0, 1.0], [0.0])

    def test_transform_bounds(self) -> None:
        """Test bounding box transformation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # Bounding box around London
        bbox = BoundingBox(
            min_x=-0.5,
            min_y=51.3,
            max_x=0.3,
            max_y=51.7,
            crs=wgs84,
        )

        transformed_bbox = trans.transform_bounds(bbox)

        # Should have different coordinates
        assert transformed_bbox.crs.epsg == 32631
        assert transformed_bbox.min_x != bbox.min_x
        assert transformed_bbox.max_x > transformed_bbox.min_x
        assert transformed_bbox.max_y > transformed_bbox.min_y

    def test_inverse_transform(self) -> None:
        """Test inverse transformation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # Forward transformation
        lon, lat = -0.1278, 51.5074
        x, y = trans.transform(lon, lat)

        # Inverse transformation
        lon_back, lat_back = trans.inverse_transform(x, y)

        assert abs(lon - lon_back) < 1e-9
        assert abs(lat - lat_back) < 1e-9

    def test_get_transformation_info(self) -> None:
        """Test getting transformation metadata."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)
        info = trans.get_transformation_info()

        assert info.source_crs.epsg == 4326
        assert info.target_crs.epsg == 32631
        assert info.always_xy is True

    def test_transformer_creation_error(self) -> None:
        """Test error handling when transformer cannot be created."""
        # CRS without sufficient information
        invalid_crs = CRSInfo()

        with pytest.raises(transformer.TransformationError):
            transformer.CRSTransformer(invalid_crs, CRSInfo.from_epsg(4326))


class TestTransformCoordinates:
    """Tests for transform_coordinates convenience function."""

    def test_transform_coordinates_simple(self) -> None:
        """Test simple coordinate transformation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        x, y = transformer.transform_coordinates(
            2.3522, 48.8566, wgs84, utm_31n
        )

        assert 440000 < x < 460000
        assert 5400000 < y < 5420000

    def test_transform_coordinates_with_z(self) -> None:
        """Test coordinate transformation with elevation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        x, y, z = transformer.transform_coordinates(
            -0.1278, 51.5074, wgs84, utm_31n, z=100.0
        )

        assert abs(z - 100.0) < 0.01


class TestWGS84ToUTM:
    """Tests for WGS84 to UTM transformation."""

    def test_transform_wgs84_to_utm_auto_detect(self) -> None:
        """Test WGS84 to UTM with auto-detected zone."""
        lon, lat = 2.3522, 48.8566

        easting, northing, crs_info = transformer.transform_wgs84_to_utm(lon, lat)

        # Should auto-detect zone 31N
        assert crs_info.epsg == 32631
        assert 440000 < easting < 460000
        assert 5400000 < northing < 5420000

    def test_transform_wgs84_to_utm_specified_zone(self) -> None:
        """Test WGS84 to UTM with specified zone."""
        lon, lat = -0.1278, 51.5074

        easting, northing, crs_info = transformer.transform_wgs84_to_utm(
            lon, lat, utm_zone=31
        )

        assert crs_info.epsg == 32631

    def test_transform_wgs84_to_utm_southern_hemisphere(self) -> None:
        """Test WGS84 to UTM in southern hemisphere."""
        # Sydney coordinates
        lon, lat = 151.2093, -33.8688

        easting, northing, crs_info = transformer.transform_wgs84_to_utm(lon, lat)

        # Should auto-detect zone 56S
        assert crs_info.epsg == 32756


class TestUTMToWGS84:
    """Tests for UTM to WGS84 transformation."""

    def test_transform_utm_to_wgs84_northern(self) -> None:
        """Test UTM to WGS84 in northern hemisphere."""
        # Paris in UTM 31N
        easting, northing = 452000, 5411000

        lon, lat = transformer.transform_utm_to_wgs84(
            easting, northing, utm_zone=31, is_northern=True
        )

        # Should be close to Paris
        assert 2.0 < lon < 2.5
        assert 48.5 < lat < 49.0

    def test_transform_utm_to_wgs84_southern(self) -> None:
        """Test UTM to WGS84 in southern hemisphere."""
        # Sydney approximate UTM coordinates
        easting, northing = 334800, 6252200

        lon, lat = transformer.transform_utm_to_wgs84(
            easting, northing, utm_zone=56, is_northern=False
        )

        # Should be close to Sydney
        assert 150.0 < lon < 152.0
        assert -35.0 < lat < -33.0


class TestWebMercator:
    """Tests for Web Mercator transformations."""

    def test_transform_to_web_mercator(self) -> None:
        """Test transformation to Web Mercator."""
        lon, lat = -122.4194, 37.7749  # San Francisco

        x, y = transformer.transform_to_web_mercator(lon, lat)

        # Web Mercator uses meters
        assert x != lon
        assert y != lat
        # San Francisco should be in western hemisphere (negative x)
        assert x < 0

    def test_transform_to_web_mercator_from_utm(self) -> None:
        """Test transformation to Web Mercator from UTM."""
        easting, northing = 699329, 5710164

        x, y = transformer.transform_to_web_mercator(
            easting, northing, source_epsg=32631
        )

        # Should produce valid Web Mercator coordinates
        assert isinstance(x, float)
        assert isinstance(y, float)


class TestValidateTransformationAccuracy:
    """Tests for transformation accuracy validation."""

    def test_validate_transformation_accuracy_pass(self) -> None:
        """Test validation with accurate transformation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        # Should pass for WGS84 <-> UTM transformation
        is_valid = transformer.validate_transformation_accuracy(
            -0.1278, 51.5074, wgs84, utm_31n, max_error_meters=0.01
        )

        assert is_valid is True

    def test_validate_transformation_accuracy_tolerance(self) -> None:
        """Test validation with different tolerances."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        # Should pass with large tolerance
        is_valid = transformer.validate_transformation_accuracy(
            -0.1278, 51.5074, wgs84, utm_31n, max_error_meters=1.0
        )
        assert is_valid is True

        # Should still pass with reasonable tolerance
        is_valid = transformer.validate_transformation_accuracy(
            -0.1278, 51.5074, wgs84, utm_31n, max_error_meters=0.001
        )
        assert is_valid is True


class TestKnownReferencePoints:
    """Tests with known reference points for accuracy."""

    def test_greenwich_meridian(self) -> None:
        """Test transformation at Greenwich meridian."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # Point at 3°E (central meridian of zone 31), 51°N
        lon, lat = 3.0, 51.0
        easting, northing = trans.transform(lon, lat)

        # At central meridian of zone 31, easting should be around 500km
        assert 490000 < easting < 510000
        assert 5640000 < northing < 5660000

    def test_equator_crossing(self) -> None:
        """Test transformation near equator."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # Point near equator in zone 31
        lon, lat = 3.0, 0.1
        easting, northing = trans.transform(lon, lat)

        # At central meridian, easting should be around 500km
        assert 400000 < easting < 600000
        # Just north of equator, northing should be small
        assert 0 < northing < 100000


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_transform_at_pole(self) -> None:
        """Test transformation near poles."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        # UTM is not defined at poles, but transformation should not crash
        try:
            trans.transform(0.0, 89.0)
        except transformer.TransformationError:
            # Expected behavior - transformation may fail near poles
            pass

    def test_transform_across_date_line(self) -> None:
        """Test transformation across international date line."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_1n = CRSInfo.from_epsg(32601)  # Zone 1N

        trans = transformer.CRSTransformer(wgs84, utm_1n)

        # Point near date line
        lon, lat = 179.0, 10.0
        x, y = trans.transform(lon, lat)

        # Should produce valid coordinates
        assert isinstance(x, float)
        assert isinstance(y, float)

    def test_transform_empty_batch(self) -> None:
        """Test batch transformation with empty arrays."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        trans = transformer.CRSTransformer(wgs84, utm_31n)

        x, y = trans.transform_batch([], [])

        assert len(x) == 0
        assert len(y) == 0

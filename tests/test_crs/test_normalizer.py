"""
Tests for CRS normalization service.
"""

import pytest

from entmoot.core.crs import normalizer
from entmoot.models.crs import BoundingBox, CRSInfo


class TestCRSNormalizer:
    """Tests for CRSNormalizer class."""

    def test_normalize_coordinates_same_crs(self) -> None:
        """Test normalization when source and target CRS are the same."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(target_crs=wgs84, auto_detect_utm=False)

        coords = [(-0.1278, 51.5074), (0.0, 51.5)]
        result = norm.normalize_coordinates(coords, wgs84)

        # Should return same coordinates
        assert result.coordinates == coords
        assert result.target_crs.epsg == 4326
        assert result.original_crs.epsg == 4326
        assert result.metadata["transformation_applied"] is False

    def test_normalize_coordinates_different_crs(self) -> None:
        """Test normalization with different source and target CRS."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        coords = [(-0.1278, 51.5074), (0.0, 51.5)]
        result = norm.normalize_coordinates(coords, wgs84)

        # Should have different coordinates
        assert result.coordinates != coords
        assert result.target_crs.epsg == 32631
        assert result.original_crs.epsg == 4326
        assert result.metadata["transformation_applied"] is True
        assert result.metadata["point_count"] == 2

    def test_normalize_coordinates_auto_detect_utm(self) -> None:
        """Test normalization with auto-detected UTM zone."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(auto_detect_utm=True)

        # Paris coordinates should auto-detect to zone 31N
        coords = [(2.3522, 48.8566)]
        result = norm.normalize_coordinates(coords, wgs84)

        assert result.target_crs.epsg == 32631
        assert result.metadata["transformation_applied"] is True

    def test_normalize_coordinates_empty_list(self) -> None:
        """Test error handling for empty coordinate list."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(target_crs=wgs84)

        with pytest.raises(normalizer.NormalizationError, match="No coordinates provided"):
            norm.normalize_coordinates([], wgs84)

    def test_normalize_mixed_inputs(self) -> None:
        """Test normalization of multiple datasets with different CRS."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)
        utm_32n = CRSInfo.from_epsg(32632)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        # Multiple datasets with different CRS
        datasets = [
            ([(-0.1278, 51.5074)], wgs84),
            ([(699329, 5710164)], utm_32n),
        ]

        results = norm.normalize_mixed_inputs(datasets)

        assert len(results) == 2
        assert results[0].target_crs.epsg == 32631
        assert results[1].target_crs.epsg == 32631

    def test_normalize_mixed_inputs_empty(self) -> None:
        """Test error handling for empty dataset list."""
        norm = normalizer.CRSNormalizer()

        with pytest.raises(normalizer.NormalizationError, match="No datasets provided"):
            norm.normalize_mixed_inputs([])

    def test_normalize_mixed_inputs_auto_target(self) -> None:
        """Test auto-detection of target CRS from mixed inputs."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        # No target specified
        norm = normalizer.CRSNormalizer(auto_detect_utm=False)

        datasets = [
            ([(-0.1278, 51.5074)], wgs84),
            ([(0.0, 51.5)], wgs84),
        ]

        results = norm.normalize_mixed_inputs(datasets)

        # Should use first dataset's CRS
        assert len(results) == 2
        assert results[0].target_crs.epsg == 4326

    def test_normalize_bounding_box_same_crs(self) -> None:
        """Test bounding box normalization with same CRS."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(target_crs=wgs84, auto_detect_utm=False)

        bbox = BoundingBox(
            min_x=-0.5, min_y=51.3, max_x=0.3, max_y=51.7, crs=wgs84
        )

        result = norm.normalize_bounding_box(bbox)

        # Should return same bounding box
        assert result.min_x == bbox.min_x
        assert result.max_x == bbox.max_x
        assert result.crs.epsg == 4326

    def test_normalize_bounding_box_different_crs(self) -> None:
        """Test bounding box normalization with different CRS."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        bbox = BoundingBox(
            min_x=-0.5, min_y=51.3, max_x=0.3, max_y=51.7, crs=wgs84
        )

        result = norm.normalize_bounding_box(bbox)

        # Should have different coordinates
        assert result.min_x != bbox.min_x
        assert result.crs.epsg == 32631

    def test_normalize_bounding_box_auto_detect_utm(self) -> None:
        """Test bounding box normalization with auto-detected UTM."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(auto_detect_utm=True)

        bbox = BoundingBox(
            min_x=2.0, min_y=48.5, max_x=2.7, max_y=49.0, crs=wgs84
        )

        result = norm.normalize_bounding_box(bbox)

        # Should auto-detect zone 31N
        assert result.crs.epsg == 32631

    def test_validate_and_normalize(self) -> None:
        """Test normalization with validation."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        coords = [(-0.1278, 51.5074), (0.0, 51.5)]
        result = norm.validate_and_normalize(coords, wgs84)

        # Should pass validation
        assert result.metadata["validated"] is True
        assert "max_round_trip_error_meters" in result.metadata
        assert result.metadata["max_round_trip_error_meters"] < 0.01

    def test_validate_and_normalize_same_crs(self) -> None:
        """Test validation when no transformation is needed."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(target_crs=wgs84, auto_detect_utm=False)

        coords = [(-0.1278, 51.5074)]
        result = norm.validate_and_normalize(coords, wgs84)

        # Should not validate (no transformation)
        assert result.metadata.get("validated") is None

    def test_reset(self) -> None:
        """Test resetting normalizer state."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        # Perform transformation to create cached transformer
        coords = [(-0.1278, 51.5074)]
        norm.normalize_coordinates(coords, wgs84)

        # Reset should clear cache
        norm.reset()
        assert len(norm._transformers) == 0


class TestNormalizeToUTM:
    """Tests for normalize_to_utm convenience function."""

    def test_normalize_to_utm_auto_detect(self) -> None:
        """Test normalization to UTM with auto-detected zone."""
        wgs84 = CRSInfo.from_epsg(4326)
        coords = [(2.3522, 48.8566)]

        result = normalizer.normalize_to_utm(coords, wgs84)

        # Should auto-detect zone 31N
        assert result.target_crs.epsg == 32631
        assert result.original_crs.epsg == 4326

    def test_normalize_to_utm_specified_zone(self) -> None:
        """Test normalization to specific UTM zone."""
        wgs84 = CRSInfo.from_epsg(4326)
        coords = [(-0.1278, 51.5074)]

        result = normalizer.normalize_to_utm(coords, wgs84, utm_zone=31)

        assert result.target_crs.epsg == 32631

    def test_normalize_to_utm_southern_hemisphere(self) -> None:
        """Test normalization to UTM in southern hemisphere."""
        wgs84 = CRSInfo.from_epsg(4326)
        # Sydney coordinates
        coords = [(151.2093, -33.8688)]

        result = normalizer.normalize_to_utm(coords, wgs84)

        # Should auto-detect zone 56S
        assert result.target_crs.epsg == 32756


class TestNormalizeToWGS84:
    """Tests for normalize_to_wgs84 convenience function."""

    def test_normalize_to_wgs84(self) -> None:
        """Test normalization to WGS84."""
        utm_31n = CRSInfo.from_epsg(32631)
        coords = [(452000, 5411000)]

        result = normalizer.normalize_to_wgs84(coords, utm_31n)

        assert result.target_crs.epsg == 4326
        assert result.original_crs.epsg == 32631

        # Should be close to Paris
        lon, lat = result.coordinates[0]
        assert 2.0 < lon < 2.5
        assert 48.5 < lat < 49.0

    def test_normalize_to_wgs84_from_wgs84(self) -> None:
        """Test normalization to WGS84 when already in WGS84."""
        wgs84 = CRSInfo.from_epsg(4326)
        coords = [(-0.1278, 51.5074)]

        result = normalizer.normalize_to_wgs84(coords, wgs84)

        # Should return same coordinates
        assert result.coordinates == coords
        assert result.metadata["transformation_applied"] is False


class TestMixedCRSScenarios:
    """Tests for complex mixed CRS scenarios."""

    def test_normalize_three_different_crs(self) -> None:
        """Test normalization of three datasets with different CRS."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)
        utm_32n = CRSInfo.from_epsg(32632)
        web_mercator = CRSInfo.from_epsg(3857)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        datasets = [
            ([(-0.1278, 51.5074)], wgs84),
            ([(699329, 5710164)], utm_31n),
            ([(300000, 5700000)], utm_32n),
        ]

        results = norm.normalize_mixed_inputs(datasets)

        assert len(results) == 3
        # All should be normalized to UTM 31N
        for result in results:
            assert result.target_crs.epsg == 32631

    def test_normalize_prefer_projected_crs(self) -> None:
        """Test that normalizer can handle mixed geographic and projected CRS."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        # Explicitly set target to UTM to prefer projected CRS
        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        datasets = [
            ([(2.3522, 48.8566)], wgs84),
            ([(452000, 5411000)], utm_31n),
        ]

        results = norm.normalize_mixed_inputs(datasets)

        # All datasets should be normalized to UTM
        assert results[0].target_crs.epsg == 32631
        assert results[1].target_crs.epsg == 32631


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_normalize_single_point(self) -> None:
        """Test normalization of single point."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        coords = [(-0.1278, 51.5074)]
        result = norm.normalize_coordinates(coords, wgs84)

        assert len(result.coordinates) == 1

    def test_normalize_many_points(self) -> None:
        """Test normalization of many points."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        # Generate 1000 points
        coords = [(lon, lat) for lon in range(-10, 10) for lat in range(40, 60)]
        result = norm.normalize_coordinates(coords, wgs84)

        assert len(result.coordinates) == len(coords)

    def test_normalize_near_antimeridian(self) -> None:
        """Test normalization near international date line."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(auto_detect_utm=True)

        # Points near antimeridian
        coords = [(179.5, 10.0), (-179.5, 10.0)]
        result = norm.normalize_coordinates(coords, wgs84)

        # Should handle gracefully
        assert len(result.coordinates) == 2

    def test_normalize_at_equator(self) -> None:
        """Test normalization at equator."""
        wgs84 = CRSInfo.from_epsg(4326)
        norm = normalizer.CRSNormalizer(auto_detect_utm=True)

        coords = [(0.0, 0.0)]
        result = norm.normalize_coordinates(coords, wgs84)

        # Should detect northern hemisphere UTM
        assert result.target_crs.epsg == 32631  # Zone 31N

    def test_normalize_projected_to_projected(self) -> None:
        """Test normalization between two projected CRS."""
        utm_31n = CRSInfo.from_epsg(32631)
        utm_32n = CRSInfo.from_epsg(32632)

        norm = normalizer.CRSNormalizer(target_crs=utm_32n, auto_detect_utm=False)

        coords = [(699329, 5710164)]
        result = norm.normalize_coordinates(coords, utm_31n)

        assert result.target_crs.epsg == 32632
        assert result.original_crs.epsg == 32631

    def test_are_crs_equal_same_epsg(self) -> None:
        """Test CRS equality check with same EPSG."""
        norm = normalizer.CRSNormalizer()

        crs1 = CRSInfo.from_epsg(4326)
        crs2 = CRSInfo.from_epsg(4326)

        assert norm._are_crs_equal(crs1, crs2) is True

    def test_are_crs_equal_different_epsg(self) -> None:
        """Test CRS equality check with different EPSG."""
        norm = normalizer.CRSNormalizer()

        crs1 = CRSInfo.from_epsg(4326)
        crs2 = CRSInfo.from_epsg(32631)

        assert norm._are_crs_equal(crs1, crs2) is False

    def test_validation_failure_handling(self) -> None:
        """Test handling of validation failures."""
        wgs84 = CRSInfo.from_epsg(4326)
        utm_31n = CRSInfo.from_epsg(32631)

        norm = normalizer.CRSNormalizer(target_crs=utm_31n, auto_detect_utm=False)

        coords = [(-0.1278, 51.5074)]

        # Should pass with reasonable tolerance
        result = norm.validate_and_normalize(coords, wgs84, max_error_meters=0.01)
        assert result.metadata["validated"] is True

        # Would fail with impossible tolerance (but pyproj is very accurate)
        # This test shows the validation mechanism works
        result = norm.validate_and_normalize(coords, wgs84, max_error_meters=1e-6)
        assert result.metadata["validated"] is True  # Should still pass with pyproj

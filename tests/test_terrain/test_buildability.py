"""
Tests for buildability analysis module.

This module tests the identification of buildable areas based on terrain analysis,
including zone detection, polygonization, and quality scoring.
"""

import pytest
import numpy as np
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

from entmoot.core.terrain.buildability import (
    BuildabilityAnalyzer,
    BuildabilityThresholds,
    BuildabilityClass,
    BuildableZone,
    BuildabilityResult,
    analyze_buildability,
)


class TestBuildabilityThresholds:
    """Test BuildabilityThresholds configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = BuildabilityThresholds()

        assert thresholds.excellent_slope_max == 5.0
        assert thresholds.good_slope_max == 15.0
        assert thresholds.difficult_slope_max == 25.0
        assert thresholds.min_zone_area_sqm == 1000.0
        assert thresholds.min_elevation is None
        assert thresholds.max_elevation is None

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = BuildabilityThresholds(
            excellent_slope_max=3.0,
            good_slope_max=10.0,
            difficult_slope_max=20.0,
            min_elevation=100.0,
            max_elevation=500.0,
            min_zone_area_sqm=2000.0,
        )

        assert thresholds.excellent_slope_max == 3.0
        assert thresholds.good_slope_max == 10.0
        assert thresholds.min_elevation == 100.0

    def test_invalid_slope_progression(self):
        """Test that slope thresholds must be in ascending order."""
        with pytest.raises(ValueError, match="excellent_slope_max must be less"):
            BuildabilityThresholds(
                excellent_slope_max=15.0,
                good_slope_max=10.0,
                difficult_slope_max=25.0,
            )

        with pytest.raises(ValueError, match="good_slope_max must be less"):
            BuildabilityThresholds(
                excellent_slope_max=5.0,
                good_slope_max=30.0,
                difficult_slope_max=25.0,
            )

    def test_invalid_elevation_range(self):
        """Test that min_elevation must be less than max_elevation."""
        with pytest.raises(ValueError, match="min_elevation must be less"):
            BuildabilityThresholds(
                min_elevation=500.0,
                max_elevation=100.0,
            )

    def test_invalid_min_zone_area(self):
        """Test that min_zone_area_sqm must be positive."""
        with pytest.raises(ValueError, match="min_zone_area_sqm must be positive"):
            BuildabilityThresholds(min_zone_area_sqm=-100.0)


class TestBuildableZone:
    """Test BuildableZone dataclass."""

    def test_zone_creation(self):
        """Test creating a BuildableZone."""
        polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])

        zone = BuildableZone(
            zone_id=1,
            area_sqm=100.0,
            area_acres=0.0247,
            geometry=polygon,
            mean_slope=5.0,
            min_elevation=100.0,
            max_elevation=105.0,
            mean_elevation=102.5,
            compactness=0.85,
            quality_score=80.0,
            buildability_class=BuildabilityClass.EXCELLENT,
            centroid=(5.0, 5.0),
        )

        assert zone.zone_id == 1
        assert zone.area_sqm == 100.0
        assert zone.buildability_class == BuildabilityClass.EXCELLENT

    def test_zone_to_dict(self):
        """Test converting zone to dictionary."""
        polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])

        zone = BuildableZone(
            zone_id=1,
            area_sqm=100.0,
            area_acres=0.0247,
            geometry=polygon,
            mean_slope=5.0,
            min_elevation=100.0,
            max_elevation=105.0,
            mean_elevation=102.5,
            compactness=0.85,
            quality_score=80.0,
            buildability_class=BuildabilityClass.EXCELLENT,
            centroid=(5.0, 5.0),
        )

        zone_dict = zone.to_dict()

        assert zone_dict["zone_id"] == 1
        assert zone_dict["area_sqm"] == 100.0
        assert zone_dict["buildability_class"] == "excellent"
        assert "geometry_wkt" in zone_dict
        assert zone_dict["centroid"] == (5.0, 5.0)


class TestBuildabilityAnalyzer:
    """Test BuildabilityAnalyzer class."""

    @pytest.fixture
    def flat_terrain(self):
        """Create a flat terrain for testing."""
        size = 50
        slope = np.zeros((size, size), dtype=np.float32)  # 0% slope
        elevation = np.full((size, size), 100.0, dtype=np.float32)
        return slope, elevation

    @pytest.fixture
    def mixed_terrain(self):
        """Create terrain with mixed slopes."""
        size = 100
        slope = np.zeros((size, size), dtype=np.float32)

        # Create regions with different slopes
        slope[0:25, 0:25] = 3.0  # Excellent (0-5%)
        slope[0:25, 25:50] = 10.0  # Good (5-15%)
        slope[0:25, 50:75] = 20.0  # Difficult (15-25%)
        slope[0:25, 75:100] = 30.0  # Unsuitable (25%+)

        elevation = np.random.uniform(100, 120, (size, size)).astype(np.float32)

        return slope, elevation

    @pytest.fixture
    def steep_terrain(self):
        """Create steep unbuildable terrain."""
        size = 50
        slope = np.full((size, size), 35.0, dtype=np.float32)  # 35% slope
        elevation = np.random.uniform(100, 200, (size, size)).astype(np.float32)
        return slope, elevation

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = BuildabilityAnalyzer(cell_size=10.0)
        assert analyzer.cell_size == 10.0
        assert analyzer.thresholds.excellent_slope_max == 5.0

        custom_thresholds = BuildabilityThresholds(excellent_slope_max=3.0)
        analyzer2 = BuildabilityAnalyzer(cell_size=5.0, thresholds=custom_thresholds)
        assert analyzer2.thresholds.excellent_slope_max == 3.0

    def test_create_buildable_mask_flat(self, flat_terrain):
        """Test creating buildable mask for flat terrain."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        mask = analyzer.create_buildable_mask(slope, elevation)

        # All flat terrain should be buildable
        assert np.all(mask)
        assert mask.shape == slope.shape

    def test_create_buildable_mask_with_slope_threshold(self, mixed_terrain):
        """Test buildable mask respects slope threshold."""
        slope, elevation = mixed_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        mask = analyzer.create_buildable_mask(slope, elevation)

        # Only areas with slope <= 25% should be buildable
        expected_buildable = slope <= 25.0
        np.testing.assert_array_equal(mask, expected_buildable)

    def test_create_buildable_mask_with_elevation_constraints(self, flat_terrain):
        """Test buildable mask with elevation constraints."""
        slope, elevation = flat_terrain
        elevation[0:25, 0:25] = 50.0  # Low area
        elevation[25:50, 25:50] = 600.0  # High area

        thresholds = BuildabilityThresholds(
            min_elevation=80.0,
            max_elevation=500.0,
        )
        analyzer = BuildabilityAnalyzer(cell_size=1.0, thresholds=thresholds)

        mask = analyzer.create_buildable_mask(slope, elevation)

        # Low and high areas should not be buildable
        assert not np.any(mask[0:25, 0:25])  # Too low
        assert not np.any(mask[25:50, 25:50])  # Too high
        assert np.all(mask[0:25, 25:50])  # Within range

    def test_create_buildable_mask_with_property_mask(self, flat_terrain):
        """Test buildable mask respects property boundary."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        # Create property mask (only left half is property)
        property_mask = np.zeros_like(slope, dtype=bool)
        property_mask[:, 0:25] = True

        mask = analyzer.create_buildable_mask(slope, elevation, property_mask=property_mask)

        # Only left half should be buildable
        assert np.all(mask[:, 0:25])
        assert not np.any(mask[:, 25:50])

    def test_create_buildable_mask_with_aspect_preference(self, flat_terrain):
        """Test buildable mask with aspect preference."""
        slope, elevation = flat_terrain

        # Create aspect array (different directions)
        aspect = np.zeros_like(slope)
        aspect[:, 0:25] = 180.0  # South-facing (preferred)
        aspect[:, 25:50] = 0.0  # North-facing

        thresholds = BuildabilityThresholds(
            aspect_preference=180.0,  # Prefer south-facing
            aspect_tolerance=30.0,
        )
        analyzer = BuildabilityAnalyzer(cell_size=1.0, thresholds=thresholds)

        mask = analyzer.create_buildable_mask(slope, elevation, aspect=aspect)

        # South-facing should be buildable, north-facing should not
        assert np.all(mask[:, 0:25])
        assert not np.any(mask[:, 25:50])

    def test_identify_zones_single_zone(self, flat_terrain):
        """Test identifying a single contiguous zone."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        mask = analyzer.create_buildable_mask(slope, elevation)
        labeled, num_zones = analyzer.identify_zones(mask)

        assert num_zones == 1
        assert labeled.shape == mask.shape
        assert np.all(labeled[mask] > 0)  # All buildable pixels labeled
        assert np.all(labeled[~mask] == 0)  # Non-buildable pixels are 0

    def test_identify_zones_multiple_zones(self):
        """Test identifying multiple separate zones."""
        size = 100
        slope = np.full((size, size), 3.0, dtype=np.float32)
        elevation = np.full((size, size), 100.0, dtype=np.float32)

        # Create non-buildable barrier
        slope[45:55, :] = 30.0  # Steep strip in middle

        analyzer = BuildabilityAnalyzer(cell_size=1.0)
        mask = analyzer.create_buildable_mask(slope, elevation)
        labeled, num_zones = analyzer.identify_zones(mask)

        # Should have 2 zones (top and bottom)
        assert num_zones == 2

    def test_identify_zones_no_buildable_areas(self, steep_terrain):
        """Test identifying zones when no buildable areas exist."""
        slope, elevation = steep_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        mask = analyzer.create_buildable_mask(slope, elevation)
        labeled, num_zones = analyzer.identify_zones(mask)

        assert num_zones == 0
        assert np.all(labeled == 0)

    def test_analyze_zones_filters_small_zones(self, flat_terrain):
        """Test that small zones are filtered out."""
        slope, elevation = flat_terrain

        # Create small buildable patch
        slope[:, :] = 30.0  # Make most unbuildable
        slope[0:5, 0:5] = 3.0  # Small buildable area (25 sq m at 1m resolution)

        thresholds = BuildabilityThresholds(
            min_zone_area_sqm=100.0  # Minimum 100 sq m
        )
        analyzer = BuildabilityAnalyzer(cell_size=1.0, thresholds=thresholds)

        mask = analyzer.create_buildable_mask(slope, elevation)
        labeled, num_zones = analyzer.identify_zones(mask)
        zones = analyzer.analyze_zones(labeled, num_zones, slope, elevation)

        # Small zone should be filtered out
        assert len(zones) == 0

    def test_analyze_zones_calculates_statistics(self, flat_terrain):
        """Test that zone analysis calculates correct statistics."""
        slope, elevation = flat_terrain

        # Set known values for testing
        slope[:, :] = 7.5  # Good buildability
        elevation[:, :] = 150.0

        analyzer = BuildabilityAnalyzer(cell_size=10.0)  # 10m resolution

        mask = analyzer.create_buildable_mask(slope, elevation)
        labeled, num_zones = analyzer.identify_zones(mask)
        zones = analyzer.analyze_zones(labeled, num_zones, slope, elevation)

        assert len(zones) == 1
        zone = zones[0]

        # Check statistics
        assert zone.mean_slope == pytest.approx(7.5, rel=1e-5)
        assert zone.min_elevation == pytest.approx(150.0, rel=1e-5)
        assert zone.max_elevation == pytest.approx(150.0, rel=1e-5)
        assert zone.mean_elevation == pytest.approx(150.0, rel=1e-5)
        assert zone.area_sqm == pytest.approx(50 * 50 * 100, rel=1e-2)  # 50x50 pixels * 100 sqm/pixel

    def test_zone_classification(self, mixed_terrain):
        """Test zone buildability classification."""
        slope, elevation = mixed_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        # Test each classification
        test_cases = [
            (3.0, BuildabilityClass.EXCELLENT),
            (10.0, BuildabilityClass.GOOD),
            (20.0, BuildabilityClass.DIFFICULT),
            (30.0, BuildabilityClass.UNSUITABLE),
        ]

        for mean_slope, expected_class in test_cases:
            result = analyzer._classify_zone(mean_slope)
            assert result == expected_class

    def test_zone_compactness_calculation(self):
        """Test compactness calculation."""
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        # Perfect square (should be close to circle)
        square = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        compactness_square = analyzer._calculate_compactness(square)
        assert 0.7 < compactness_square <= 1.0

        # Elongated rectangle (lower compactness)
        rectangle = Polygon([(0, 0), (50, 0), (50, 5), (0, 5), (0, 0)])
        compactness_rect = analyzer._calculate_compactness(rectangle)
        assert 0 < compactness_rect < 0.5
        assert compactness_rect < compactness_square

    def test_zone_quality_score(self):
        """Test quality score calculation."""
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        # Excellent zone: large, flat, compact
        score1 = analyzer._calculate_zone_quality(
            area_sqm=5000.0,
            mean_slope=2.0,
            compactness=0.9,
            buildability_class=BuildabilityClass.EXCELLENT,
        )
        assert 80 < score1 <= 100

        # Poor zone: small, steep, not compact
        score2 = analyzer._calculate_zone_quality(
            area_sqm=500.0,
            mean_slope=22.0,
            compactness=0.3,
            buildability_class=BuildabilityClass.DIFFICULT,
        )
        assert 0 <= score2 < 30
        assert score2 < score1

    def test_analyze_complete(self, flat_terrain):
        """Test complete buildability analysis."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=10.0)

        result = analyzer.analyze(slope, elevation)

        assert isinstance(result, BuildabilityResult)
        assert result.buildable_mask.shape == slope.shape
        assert result.total_buildable_area_sqm > 0
        assert result.total_buildable_area_acres > 0
        assert result.buildable_percentage > 0
        assert result.num_zones >= 1
        assert result.largest_zone is not None
        assert 0 <= result.overall_quality_score <= 100

    def test_analyze_with_transform(self, flat_terrain):
        """Test analysis with rasterio transform."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=10.0)

        # Create transform for 50x50 grid with 10m resolution
        transform = from_bounds(0, 0, 500, 500, 50, 50)

        result = analyzer.analyze(slope, elevation, transform=transform)

        assert result.num_zones >= 1
        assert result.largest_zone is not None

        # Check that geometry has real coordinates (not pixel coordinates)
        zone = result.largest_zone
        bounds = zone.geometry.bounds
        assert bounds[0] >= 0  # min_x
        assert bounds[2] <= 500  # max_x

    def test_analyze_no_buildable_areas(self, steep_terrain):
        """Test analysis when no buildable areas exist."""
        slope, elevation = steep_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        result = analyzer.analyze(slope, elevation)

        assert result.total_buildable_area_sqm == 0
        assert result.total_buildable_area_acres == 0
        assert result.buildable_percentage == 0
        assert result.num_zones == 0
        assert result.largest_zone is None
        assert result.overall_quality_score == 0

    def test_analyze_mismatched_shapes(self):
        """Test that analysis fails with mismatched array shapes."""
        slope = np.zeros((50, 50), dtype=np.float32)
        elevation = np.zeros((60, 60), dtype=np.float32)

        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        with pytest.raises(ValueError, match="must have same shape"):
            analyzer.analyze(slope, elevation)

    def test_analyze_with_aspect_mismatched_shape(self, flat_terrain):
        """Test that analysis fails with mismatched aspect shape."""
        slope, elevation = flat_terrain
        aspect = np.zeros((30, 30), dtype=np.float32)

        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        with pytest.raises(ValueError, match="Aspect array must have same shape"):
            analyzer.analyze(slope, elevation, aspect=aspect)

    def test_zone_to_polygon(self, flat_terrain):
        """Test converting zone mask to polygon."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=10.0)

        # Create simple square mask
        mask = np.zeros((20, 20), dtype=bool)
        mask[5:15, 5:15] = True

        transform = from_bounds(0, 0, 200, 200, 20, 20)
        polygon = analyzer.zone_to_polygon(mask, transform, simplify_tolerance=0.5)

        assert polygon is not None
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert polygon.area > 0

    def test_zone_to_polygon_empty_mask(self):
        """Test converting empty mask returns None."""
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        mask = np.zeros((20, 20), dtype=bool)
        polygon = analyzer.zone_to_polygon(mask)

        assert polygon is None

    def test_overall_quality_score_excellent_site(self, flat_terrain):
        """Test overall quality score for excellent site."""
        slope, elevation = flat_terrain
        slope[:, :] = 2.0  # Very flat

        analyzer = BuildabilityAnalyzer(cell_size=10.0)
        result = analyzer.analyze(slope, elevation)

        # Excellent flat site should score high
        assert result.overall_quality_score > 70

    def test_overall_quality_score_fragmented_site(self):
        """Test overall quality score for fragmented site."""
        size = 100
        slope = np.full((size, size), 30.0, dtype=np.float32)  # Start with all unbuildable
        elevation = np.full((size, size), 100.0, dtype=np.float32)

        # Create multiple small buildable patches separated by unbuildable strips
        # This ensures they are truly separate zones
        patch_size = 8
        gap_size = 4  # Gap to ensure no 8-connectivity between patches

        for i in range(0, size, patch_size + gap_size):
            for j in range(0, size, patch_size + gap_size):
                if i + patch_size <= size and j + patch_size <= size:
                    slope[i : i + patch_size, j : j + patch_size] = 3.0  # Buildable

        thresholds = BuildabilityThresholds(min_zone_area_sqm=100.0)  # Allow smaller zones
        analyzer = BuildabilityAnalyzer(cell_size=10.0, thresholds=thresholds)
        result = analyzer.analyze(slope, elevation)

        # Fragmented site should have multiple zones and score lower than excellent sites
        assert result.num_zones > 5
        assert result.overall_quality_score < 80  # Multiple zones reduce overall score

    def test_additional_metrics_calculation(self, mixed_terrain):
        """Test calculation of additional metrics."""
        slope, elevation = mixed_terrain
        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        result = analyzer.analyze(slope, elevation)

        # Check that metrics are present
        assert "largest_zone_area_sqm" in result.metrics
        assert "buildable_slope_mean" in result.metrics
        assert "buildable_elevation_mean" in result.metrics
        assert "mean_zone_quality" in result.metrics
        assert "buildability_class_distribution" in result.metrics

        # Check metric types
        assert isinstance(result.metrics["largest_zone_area_sqm"], float)
        assert isinstance(result.metrics["buildability_class_distribution"], dict)

    def test_result_to_dict(self, flat_terrain):
        """Test converting result to dictionary."""
        slope, elevation = flat_terrain
        analyzer = BuildabilityAnalyzer(cell_size=10.0)

        result = analyzer.analyze(slope, elevation)
        result_dict = result.to_dict()

        assert "total_buildable_area_sqm" in result_dict
        assert "total_buildable_area_acres" in result_dict
        assert "buildable_percentage" in result_dict
        assert "num_zones" in result_dict
        assert "largest_zone" in result_dict
        assert "overall_quality_score" in result_dict
        assert "zones" in result_dict
        assert "metrics" in result_dict

        # Check that zones are dicts
        assert isinstance(result_dict["zones"], list)
        if result_dict["zones"]:
            assert isinstance(result_dict["zones"][0], dict)


class TestConvenienceFunction:
    """Test the convenience function."""

    def test_analyze_buildability_function(self):
        """Test the analyze_buildability convenience function."""
        slope = np.random.uniform(0, 10, (50, 50)).astype(np.float32)
        elevation = np.random.uniform(100, 150, (50, 50)).astype(np.float32)

        result = analyze_buildability(slope, elevation, cell_size=5.0)

        assert isinstance(result, BuildabilityResult)
        assert result.buildable_percentage > 0
        assert result.num_zones >= 1

    def test_analyze_buildability_with_custom_thresholds(self):
        """Test convenience function with custom thresholds."""
        slope = np.random.uniform(0, 8, (50, 50)).astype(np.float32)
        elevation = np.random.uniform(100, 150, (50, 50)).astype(np.float32)

        thresholds = BuildabilityThresholds(
            excellent_slope_max=3.0,
            good_slope_max=8.0,
            difficult_slope_max=15.0,
        )

        result = analyze_buildability(
            slope,
            elevation,
            cell_size=5.0,
            thresholds=thresholds,
        )

        assert isinstance(result, BuildabilityResult)

    def test_analyze_buildability_with_all_parameters(self):
        """Test convenience function with all parameters."""
        slope = np.random.uniform(0, 10, (50, 50)).astype(np.float32)
        elevation = np.random.uniform(100, 150, (50, 50)).astype(np.float32)
        aspect = np.random.uniform(0, 360, (50, 50)).astype(np.float32)

        property_mask = np.ones((50, 50), dtype=bool)
        transform = from_bounds(0, 0, 500, 500, 50, 50)

        thresholds = BuildabilityThresholds(min_elevation=110.0, max_elevation=140.0)

        result = analyze_buildability(
            slope,
            elevation,
            cell_size=10.0,
            thresholds=thresholds,
            transform=transform,
            aspect=aspect,
            property_mask=property_mask,
        )

        assert isinstance(result, BuildabilityResult)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_single_pixel_zone(self):
        """Test handling of single-pixel zones."""
        slope = np.full((10, 10), 30.0, dtype=np.float32)
        elevation = np.full((10, 10), 100.0, dtype=np.float32)

        # Single buildable pixel
        slope[5, 5] = 3.0

        thresholds = BuildabilityThresholds(
            min_zone_area_sqm=0.5  # Allow very small zones
        )
        analyzer = BuildabilityAnalyzer(cell_size=1.0, thresholds=thresholds)

        result = analyzer.analyze(slope, elevation)

        # Should have one tiny zone
        assert result.num_zones == 1
        assert result.total_buildable_area_sqm == pytest.approx(1.0, rel=1e-2)

    def test_all_nan_elevation(self):
        """Test handling of NaN values in elevation."""
        slope = np.zeros((20, 20), dtype=np.float32)
        elevation = np.full((20, 20), np.nan, dtype=np.float32)

        analyzer = BuildabilityAnalyzer(cell_size=1.0)

        # NaN comparisons will make everything False
        result = analyzer.analyze(slope, elevation)

        # Should have no buildable areas (NaN fails all comparisons)
        assert result.num_zones == 0

    def test_very_small_cell_size(self):
        """Test with very small cell size."""
        slope = np.random.uniform(0, 5, (100, 100)).astype(np.float32)
        elevation = np.random.uniform(100, 120, (100, 100)).astype(np.float32)

        analyzer = BuildabilityAnalyzer(cell_size=0.1)  # 10cm resolution

        result = analyzer.analyze(slope, elevation)

        assert result.total_buildable_area_sqm > 0
        # Areas should be small due to small cell size
        assert result.total_buildable_area_sqm < 1000  # 100x100 * 0.1^2 = 1000 sqm max

    def test_very_large_cell_size(self):
        """Test with very large cell size."""
        slope = np.random.uniform(0, 5, (50, 50)).astype(np.float32)
        elevation = np.random.uniform(100, 120, (50, 50)).astype(np.float32)

        analyzer = BuildabilityAnalyzer(cell_size=100.0)  # 100m resolution

        result = analyzer.analyze(slope, elevation)

        assert result.total_buildable_area_sqm > 0
        # Areas should be large due to large cell size
        assert result.total_buildable_area_sqm > 100000  # 50x50 * 100^2 = 25,000,000 sqm max

    def test_diagonal_zones(self):
        """Test detection of diagonally connected zones."""
        size = 20
        slope = np.full((size, size), 30.0, dtype=np.float32)
        elevation = np.full((size, size), 100.0, dtype=np.float32)

        # Create diagonal buildable pixels
        for i in range(10):
            slope[i, i] = 3.0
            slope[i, i + 1] = 3.0

        thresholds = BuildabilityThresholds(min_zone_area_sqm=0.1)
        analyzer = BuildabilityAnalyzer(cell_size=1.0, thresholds=thresholds)

        result = analyzer.analyze(slope, elevation)

        # Should be one zone due to 8-connectivity
        assert result.num_zones == 1

    def test_buildability_percentage_bounds(self):
        """Test that buildable percentage is always 0-100."""
        test_cases = [
            (np.zeros((50, 50)), 100.0),  # All flat
            (np.full((50, 50), 30.0), 0.0),  # All steep
            (np.random.uniform(0, 10, (50, 50)), None),  # Mixed (between 0-100)
        ]

        for slope, expected_pct in test_cases:
            elevation = np.full((50, 50), 100.0, dtype=np.float32)
            result = analyze_buildability(slope.astype(np.float32), elevation, cell_size=1.0)

            if expected_pct is not None:
                assert result.buildable_percentage == pytest.approx(expected_pct, rel=1e-2)
            else:
                assert 0 <= result.buildable_percentage <= 100

    def test_area_unit_conversions(self):
        """Test that area conversions are correct."""
        # Create 100x100m buildable area (10,000 sqm = 2.47 acres)
        slope = np.zeros((100, 100), dtype=np.float32)
        elevation = np.full((100, 100), 100.0, dtype=np.float32)

        analyzer = BuildabilityAnalyzer(cell_size=1.0)
        result = analyzer.analyze(slope, elevation)

        expected_sqm = 10000.0
        expected_acres = expected_sqm / 4046.86

        assert result.total_buildable_area_sqm == pytest.approx(expected_sqm, rel=1e-2)
        assert result.total_buildable_area_acres == pytest.approx(expected_acres, rel=1e-2)


class TestRealWorldScenarios:
    """Test realistic scenarios."""

    def test_valley_terrain(self):
        """Test valley with buildable floor and steep sides."""
        size = 100
        x = np.arange(size)
        y = np.arange(size)
        xx, yy = np.meshgrid(x, y)

        # Create valley: steep sides, flat bottom
        elevation = np.abs(xx - 50) * 2 + 100  # V-shaped valley

        # Calculate slope manually based on elevation gradient
        slope = np.zeros_like(elevation, dtype=np.float32)
        # Center is flat
        slope[:, 45:55] = 1.0
        # Sides are steep
        slope[:, :45] = 35.0
        slope[:, 55:] = 35.0

        analyzer = BuildabilityAnalyzer(cell_size=10.0)
        result = analyzer.analyze(slope.astype(np.float32), elevation.astype(np.float32))

        # Valley floor should be buildable
        assert result.num_zones >= 1
        assert result.buildable_percentage < 50  # Only the floor

    def test_hilltop_plateau(self):
        """Test hilltop with buildable plateau and steep slopes."""
        size = 100
        x = np.arange(size)
        y = np.arange(size)
        xx, yy = np.meshgrid(x, y)

        # Create hill: flat top, steep sides
        dist_from_center = np.sqrt((xx - 50) ** 2 + (yy - 50) ** 2)
        elevation = 200 - dist_from_center * 3  # Cone shape

        slope = np.zeros_like(elevation, dtype=np.float32)
        # Center plateau is flat
        slope[dist_from_center < 15] = 2.0
        # Sides are steep
        slope[dist_from_center >= 15] = 35.0

        analyzer = BuildabilityAnalyzer(cell_size=5.0)
        result = analyzer.analyze(slope.astype(np.float32), elevation.astype(np.float32))

        # Plateau should be buildable
        assert result.num_zones >= 1
        assert result.largest_zone is not None
        assert result.largest_zone.buildability_class == BuildabilityClass.EXCELLENT

    def test_multiple_terraces(self):
        """Test terrain with multiple buildable terraces."""
        size = 100
        slope = np.full((size, size), 30.0, dtype=np.float32)
        elevation = np.zeros((size, size), dtype=np.float32)

        # Create three flat terraces at different elevations
        slope[10:20, 10:40] = 3.0
        elevation[10:20, 10:40] = 100.0

        slope[40:50, 30:70] = 4.0
        elevation[40:50, 30:70] = 150.0

        slope[70:80, 50:90] = 5.0
        elevation[70:80, 50:90] = 200.0

        thresholds = BuildabilityThresholds(min_zone_area_sqm=100.0)
        analyzer = BuildabilityAnalyzer(cell_size=10.0, thresholds=thresholds)

        result = analyzer.analyze(slope, elevation)

        # Should detect three separate zones
        assert result.num_zones == 3
        assert all(
            z.buildability_class == BuildabilityClass.EXCELLENT for z in result.zones
        )

    def test_coastal_property_with_flood_constraint(self):
        """Test coastal property with low-elevation flood zones."""
        size = 100
        x = np.arange(size)
        y = np.arange(size)
        xx, yy = np.meshgrid(x, y)

        # Elevation increases away from coast (left side)
        elevation = xx * 0.5 + 95  # Range from 95m to 145m

        # Mostly flat terrain
        slope = np.random.uniform(0, 5, (size, size)).astype(np.float32)

        # Avoid flood-prone areas below 100m
        thresholds = BuildabilityThresholds(min_elevation=100.0)
        analyzer = BuildabilityAnalyzer(cell_size=10.0, thresholds=thresholds)

        result = analyzer.analyze(slope, elevation.astype(np.float32))

        # Coastal area should not be buildable
        assert result.buildable_percentage < 100
        # Higher elevations should be buildable
        assert result.num_zones >= 1

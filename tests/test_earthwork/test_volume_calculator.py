"""
Tests for volume calculator.

Tests cut/fill calculations, cost estimation, and accuracy validation.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from entmoot.core.earthwork.volume_calculator import VolumeCalculator, PIL_AVAILABLE
from entmoot.models.terrain import DEMMetadata, ElevationUnit
from entmoot.models.earthwork import (
    SoilProperties,
    SoilType,
    CostDatabase,
)
from pyproj import CRS


@pytest.fixture
def metadata():
    """Create test DEM metadata."""
    return DEMMetadata(
        width=100,
        height=100,
        resolution=(1.0, 1.0),  # 1 meter cells
        bounds=(0.0, 0.0, 100.0, 100.0),
        crs=CRS.from_epsg(32610),  # UTM Zone 10N
        no_data_value=np.nan,
        elevation_unit=ElevationUnit.FEET,
    )


@pytest.fixture
def flat_terrain(metadata):
    """Create flat terrain at elevation 100."""
    return np.full((metadata.height, metadata.width), 100.0, dtype=np.float32)


@pytest.fixture
def sloped_terrain(metadata):
    """Create terrain sloping from 100 to 110."""
    terrain = np.zeros((metadata.height, metadata.width), dtype=np.float32)
    for i in range(metadata.height):
        terrain[i, :] = 100.0 + (i / metadata.height) * 10.0
    return terrain


class TestVolumeCalculator:
    """Test VolumeCalculator class."""

    def test_initialization(self, flat_terrain, metadata):
        """Test calculator initialization."""
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 95.0  # 5 ft cut

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        assert calc.pre_elevation.shape == (100, 100)
        assert calc.post_elevation.shape == (100, 100)
        assert calc.cut_fill_depth.shape == (100, 100)

    def test_shape_mismatch(self, flat_terrain, metadata):
        """Test error on shape mismatch."""
        wrong_shape = np.zeros((50, 50), dtype=np.float32)

        with pytest.raises(Exception):  # ValidationError
            VolumeCalculator(
                pre_elevation=flat_terrain,
                post_elevation=wrong_shape,
                metadata=metadata,
            )

    def test_simple_cut_volume(self, flat_terrain, metadata):
        """Test simple cut volume calculation."""
        # Create a 20x20 area with 5 ft cut
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 95.0  # 5 ft cut

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        # Expected cut volume:
        # Area: 20x20 cells = 400 cells
        # Cell size: 1m x 1m = 3.28084 ft x 3.28084 ft = 10.764 sq ft
        # Depth: 5 ft
        # Volume: 400 * 10.764 * 5 / 27 = 796.4 CY
        expected_cut_cy = 400 * 10.764 * 5 / 27

        assert result.cut_volume_cy > 0
        assert result.fill_volume_cy == 0
        assert abs(result.cut_volume_cy - expected_cut_cy) / expected_cut_cy < 0.01  # Within 1%

    def test_simple_fill_volume(self, flat_terrain, metadata):
        """Test simple fill volume calculation."""
        # Create a 20x20 area with 5 ft fill
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 105.0  # 5 ft fill

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        # Expected fill volume: same calculation as cut
        expected_fill_cy = 400 * 10.764 * 5 / 27

        assert result.fill_volume_cy > 0
        assert result.cut_volume_cy == 0
        assert abs(result.fill_volume_cy - expected_fill_cy) / expected_fill_cy < 0.01

    def test_mixed_cut_fill(self, flat_terrain, metadata):
        """Test mixed cut and fill."""
        post_terrain = flat_terrain.copy()
        post_terrain[20:40, 20:40] = 95.0  # Cut area
        post_terrain[60:80, 60:80] = 105.0  # Fill area

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        assert result.cut_volume_cy > 0
        assert result.fill_volume_cy > 0
        # Should be balanced
        assert abs(result.cut_volume_cy - result.fill_volume_cy) / result.cut_volume_cy < 0.01

    def test_shrink_swell_factors(self, flat_terrain, metadata):
        """Test shrink/swell factor application."""
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 95.0  # 5 ft cut

        # Clay has shrink=1.25, swell=1.30
        soil_props = SoilProperties.get_default(SoilType.CLAY)

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
            soil_properties=soil_props,
        )

        result_no_factor = calc.calculate_volumes(apply_shrink_swell=False)
        result_with_factor = calc.calculate_volumes(apply_shrink_swell=True)

        # With swell factor, export volume should increase (loose volume)
        # The cut_volume_cy stays the same (bank volume)
        # But export volume includes swell factor
        assert result_with_factor.export_volume_cy > result_no_factor.export_volume_cy
        # Ratio should match swell factor
        ratio = result_with_factor.export_volume_cy / result_no_factor.export_volume_cy
        assert abs(ratio - soil_props.swell_factor) < 0.01

    def test_balanced_earthwork(self, flat_terrain, metadata):
        """Test balanced earthwork detection."""
        post_terrain = flat_terrain.copy()
        post_terrain[20:40, 20:40] = 95.0  # Cut
        post_terrain[60:80, 60:80] = 105.0  # Equal fill

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        balancing = calc.calculate_balancing()
        volume_result = calc.calculate_volumes(apply_shrink_swell=False)

        assert balancing.is_balanced
        assert 0.9 <= balancing.balance_ratio <= 1.1
        assert volume_result.import_volume_cy == 0
        assert volume_result.export_volume_cy == 0

    def test_import_required(self, flat_terrain, metadata):
        """Test import volume calculation."""
        post_terrain = flat_terrain.copy()
        post_terrain[20:60, 20:60] = 105.0  # Large fill area

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        assert result.import_volume_cy > 0
        assert result.export_volume_cy == 0
        assert result.import_volume_cy == result.fill_volume_cy

    def test_export_required(self, flat_terrain, metadata):
        """Test export volume calculation."""
        post_terrain = flat_terrain.copy()
        post_terrain[20:60, 20:60] = 95.0  # Large cut area

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        assert result.export_volume_cy > 0
        assert result.import_volume_cy == 0
        assert result.export_volume_cy == result.cut_volume_cy

    def test_cost_calculation(self, flat_terrain, metadata):
        """Test cost calculation."""
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 95.0  # Cut

        cost_db = CostDatabase(
            excavation_cost_cy=5.00,
            fill_cost_cy=8.00,
            haul_cost_cy_mile=2.50,
            import_cost_cy=25.00,
            export_cost_cy=15.00,
        )

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
            cost_database=cost_db,
        )

        volume_result = calc.calculate_volumes(apply_shrink_swell=False)
        cost_result = calc.calculate_costs(volume_result, average_haul_distance_miles=0.25)

        # Verify cost components
        assert cost_result.excavation_cost > 0
        assert cost_result.export_cost > 0
        assert cost_result.total_cost > 0

        # Check calculation
        expected_excavation = volume_result.cut_volume_cy * cost_db.excavation_cost_cy
        assert abs(cost_result.excavation_cost - expected_excavation) < 0.01

        expected_export = volume_result.export_volume_cy * cost_db.export_cost_cy
        assert abs(cost_result.export_cost - expected_export) < 0.01

    def test_cross_section(self, sloped_terrain, metadata):
        """Test cross-section generation."""
        post_terrain = sloped_terrain.copy()
        post_terrain[:, :] = 105.0  # Flat at 105

        calc = VolumeCalculator(
            pre_elevation=sloped_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        # Cross-section from corner to corner
        section = calc.generate_cross_section(
            start=(10.0, 10.0),
            end=(90.0, 90.0),
            num_points=50
        )

        assert len(section.distance) == 50
        assert len(section.pre_elevation) == 50
        assert len(section.post_elevation) == 50
        assert len(section.cut_fill) == 50

        # Pre-elevation should vary (sloped)
        assert np.std(section.pre_elevation[~np.isnan(section.pre_elevation)]) > 0

        # Post-elevation should be constant
        post_valid = section.post_elevation[~np.isnan(section.post_elevation)]
        if len(post_valid) > 0:
            assert np.std(post_valid) < 1.0  # Should be nearly flat

    def test_heatmap_geotiff(self, flat_terrain, metadata):
        """Test GeoTIFF heatmap generation."""
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 95.0  # Cut area

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "heatmap.tif"
            calc.generate_heatmap(str(output_path), format="geotiff")

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    @pytest.mark.skipif(not PIL_AVAILABLE, reason="Pillow not available")
    def test_heatmap_png(self, flat_terrain, metadata):
        """Test PNG heatmap generation."""
        post_terrain = flat_terrain.copy()
        post_terrain[20:40, 20:40] = 95.0  # Cut (red)
        post_terrain[60:80, 60:80] = 105.0  # Fill (blue)

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "heatmap.png"
            calc.generate_heatmap(str(output_path), format="png")

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_nan_handling(self, flat_terrain, metadata):
        """Test handling of NaN values."""
        post_terrain = flat_terrain.copy()
        post_terrain[40:60, 40:60] = 95.0

        # Add some NaN values
        flat_terrain[0:10, 0:10] = np.nan
        post_terrain[90:100, 90:100] = np.nan

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        # Should still calculate volumes for valid cells
        assert result.cut_volume_cy > 0
        assert not np.isnan(result.cut_volume_cy)
        assert not np.isnan(result.net_volume_cy)

    def test_accuracy_tolerance(self, flat_terrain, metadata):
        """Test that calculations meet ±5% accuracy requirement."""
        # Create known volume scenario
        # 10x10 area, 10 ft cut
        post_terrain = flat_terrain.copy()
        post_terrain[45:55, 45:55] = 90.0  # 10 ft cut

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=False)

        # Calculate expected volume manually
        # Area: 10x10 cells = 100 cells
        # Cell area: 10.764 sq ft
        # Depth: 10 ft
        # Volume: 100 * 10.764 * 10 / 27 = 398.67 CY
        expected_cy = 100 * 10.764 * 10 / 27

        # Check accuracy is within ±5%
        error_percent = abs(result.cut_volume_cy - expected_cy) / expected_cy * 100
        assert error_percent < 5.0, f"Error {error_percent:.2f}% exceeds 5% tolerance"

    def test_summary(self, flat_terrain, metadata):
        """Test comprehensive summary generation."""
        post_terrain = flat_terrain.copy()
        post_terrain[20:40, 20:40] = 95.0  # Cut
        post_terrain[60:80, 60:80] = 105.0  # Fill

        calc = VolumeCalculator(
            pre_elevation=flat_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        summary = calc.get_summary()

        # Verify summary structure
        assert "volumes" in summary
        assert "costs" in summary
        assert "balancing" in summary
        assert "soil_type" in summary

        # Verify volume data
        assert summary["volumes"]["cut_volume_cy"] > 0
        assert summary["volumes"]["fill_volume_cy"] > 0

        # Verify cost data
        assert summary["costs"]["total_cost"] > 0

        # Verify balancing data
        assert "balance_ratio" in summary["balancing"]
        assert "is_balanced" in summary["balancing"]


class TestSoilProperties:
    """Test soil properties."""

    def test_clay_properties(self):
        """Test clay soil properties."""
        clay = SoilProperties.get_default(SoilType.CLAY)

        assert clay.soil_type == SoilType.CLAY
        assert clay.shrink_factor == 1.25
        assert clay.swell_factor == 1.30
        assert clay.density_pcf == 110.0

    def test_sand_properties(self):
        """Test sand soil properties."""
        sand = SoilProperties.get_default(SoilType.SAND)

        assert sand.soil_type == SoilType.SAND
        assert sand.shrink_factor == 1.10
        assert sand.swell_factor == 1.15

    def test_rock_properties(self):
        """Test rock soil properties."""
        rock = SoilProperties.get_default(SoilType.ROCK)

        assert rock.soil_type == SoilType.ROCK
        assert rock.shrink_factor == 1.50
        assert rock.swell_factor == 1.60


class TestCostDatabase:
    """Test cost database."""

    def test_default_costs(self):
        """Test default cost values."""
        costs = CostDatabase()

        assert costs.excavation_cost_cy == 5.00
        assert costs.fill_cost_cy == 8.00
        assert costs.haul_cost_cy_mile == 2.50
        assert costs.import_cost_cy == 25.00
        assert costs.export_cost_cy == 15.00

    def test_custom_costs(self):
        """Test custom cost values."""
        costs = CostDatabase(
            excavation_cost_cy=10.00,
            fill_cost_cy=12.00,
        )

        assert costs.excavation_cost_cy == 10.00
        assert costs.fill_cost_cy == 12.00


@pytest.mark.integration
class TestVolumeCalculatorIntegration:
    """Integration tests with realistic scenarios."""

    def test_building_pad_scenario(self, metadata):
        """Test realistic building pad scenario."""
        # Create sloped terrain
        pre_terrain = np.zeros((100, 100), dtype=np.float32)
        for i in range(100):
            pre_terrain[i, :] = 100.0 + (i / 100.0) * 20.0  # 20 ft slope

        # Create flat building pad at elevation 110
        post_terrain = pre_terrain.copy()
        post_terrain[40:60, 40:60] = 110.0

        calc = VolumeCalculator(
            pre_elevation=pre_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=True)
        cost_result = calc.calculate_costs(result)
        balancing = calc.calculate_balancing()

        # Verify results
        assert result.cut_volume_cy > 0 or result.fill_volume_cy > 0
        assert cost_result.total_cost > 0
        assert len(balancing.recommendations) > 0

    def test_road_corridor_scenario(self, metadata):
        """Test road corridor grading scenario."""
        # Create terrain with varying elevations
        pre_terrain = np.random.uniform(100, 120, (100, 100)).astype(np.float32)

        # Create road corridor (flat strip)
        post_terrain = pre_terrain.copy()
        post_terrain[45:55, :] = 110.0  # Flat road at 110 ft

        calc = VolumeCalculator(
            pre_elevation=pre_terrain,
            post_elevation=post_terrain,
            metadata=metadata,
        )

        result = calc.calculate_volumes(apply_shrink_swell=True)

        # Should have both cut and fill
        assert result.cut_volume_cy > 0
        assert result.fill_volume_cy > 0

        # Generate cross-section
        section = calc.generate_cross_section(
            start=(50.0, 10.0),
            end=(50.0, 90.0),
            num_points=80
        )

        assert section.section_volume_cy > 0

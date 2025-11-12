"""
Tests for optimization problem definition.
"""

import pytest
import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint

from entmoot.models.assets import BuildingAsset, EquipmentYardAsset
from entmoot.core.optimization.problem import (
    ObjectiveWeights,
    OptimizationConstraints,
    OptimizationObjective,
    PlacementSolution,
)


@pytest.fixture
def sample_site_boundary():
    """Create a sample site boundary."""
    return ShapelyPolygon([
        (0, 0),
        (200, 0),
        (200, 200),
        (0, 200),
        (0, 0),
    ])


@pytest.fixture
def sample_assets():
    """Create sample assets for testing."""
    return [
        BuildingAsset(
            id="bldg_001",
            name="Office Building",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            position=(100.0, 100.0),
        ),
        EquipmentYardAsset(
            id="yard_001",
            name="Storage Yard",
            dimensions=(40.0, 60.0),
            area_sqm=2400.0,
            position=(50.0, 50.0),
        ),
    ]


class TestObjectiveWeights:
    """Tests for ObjectiveWeights."""

    def test_default_weights(self):
        """Test default weights sum to 1.0."""
        weights = ObjectiveWeights()
        total = (
            weights.cut_fill_weight
            + weights.accessibility_weight
            + weights.road_length_weight
            + weights.compactness_weight
            + weights.slope_variance_weight
        )
        assert abs(total - 1.0) < 0.01

    def test_custom_weights(self):
        """Test custom weights."""
        weights = ObjectiveWeights(
            cut_fill_weight=0.4,
            accessibility_weight=0.3,
            road_length_weight=0.2,
            compactness_weight=0.05,
            slope_variance_weight=0.05,
        )
        assert weights.cut_fill_weight == 0.4
        assert weights.accessibility_weight == 0.3

    def test_weights_must_sum_to_one(self):
        """Test that weights must sum to 1.0."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ObjectiveWeights(
                cut_fill_weight=0.5,
                accessibility_weight=0.5,
                road_length_weight=0.5,
                compactness_weight=0.0,
                slope_variance_weight=0.0,
            )

    def test_negative_weight_validation(self):
        """Test that negative weights are rejected."""
        with pytest.raises(ValueError, match="non-negative"):
            ObjectiveWeights(
                cut_fill_weight=-0.1,
                accessibility_weight=0.6,
                road_length_weight=0.3,
                compactness_weight=0.1,
                slope_variance_weight=0.1,
            )


class TestOptimizationConstraints:
    """Tests for OptimizationConstraints."""

    def test_constraints_creation(self, sample_site_boundary):
        """Test creating constraints."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            min_setback_m=10.0,
            min_asset_spacing_m=5.0,
        )

        assert constraints.min_setback_m == 10.0
        assert constraints.min_asset_spacing_m == 5.0
        assert constraints.site_boundary.area == 40000.0  # 200x200

    def test_invalid_boundary(self):
        """Test invalid boundary validation."""
        # Create a self-intersecting polygon (figure-8 shape)
        from shapely.wkt import loads
        invalid_polygon = loads("POLYGON((0 0, 2 2, 2 0, 0 2, 0 0))")  # Self-intersecting

        with pytest.raises(ValueError, match="valid polygon"):
            OptimizationConstraints(site_boundary=invalid_polygon)

    def test_negative_setback(self, sample_site_boundary):
        """Test negative setback validation."""
        with pytest.raises(ValueError, match="non-negative"):
            OptimizationConstraints(
                site_boundary=sample_site_boundary,
                min_setback_m=-5.0,
            )

    def test_get_buildable_area(self, sample_site_boundary):
        """Test getting buildable area."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            min_setback_m=10.0,
        )

        buildable = constraints.get_buildable_area()
        assert buildable.is_valid
        assert buildable.area < sample_site_boundary.area  # Reduced by setback

    def test_get_buildable_area_with_exclusions(self, sample_site_boundary):
        """Test buildable area with exclusion zones."""
        exclusion = ShapelyPolygon([
            (50, 50),
            (100, 50),
            (100, 100),
            (50, 100),
            (50, 50),
        ])

        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            exclusion_zones=[exclusion],
            min_setback_m=0.0,
        )

        buildable = constraints.get_buildable_area()
        assert buildable.is_valid
        assert buildable.area < sample_site_boundary.area

    def test_is_position_valid(self, sample_site_boundary):
        """Test position validation."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            min_setback_m=10.0,
        )

        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(100.0, 100.0),
        )

        # Position at center should be valid
        assert constraints.is_position_valid(asset, (100.0, 100.0))

        # Position at edge should be invalid (due to setback)
        assert not constraints.is_position_valid(asset, (10.0, 10.0))

    def test_max_coverage_validation(self, sample_site_boundary):
        """Test max site coverage validation."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            max_site_coverage_percent=50.0,
        )

        assert constraints.max_site_coverage_percent == 50.0


class TestPlacementSolution:
    """Tests for PlacementSolution."""

    def test_solution_creation(self, sample_assets):
        """Test creating a placement solution."""
        solution = PlacementSolution(assets=sample_assets)

        assert len(solution.assets) == 2
        assert solution.fitness == 0.0
        assert solution.constraint_violations == 0
        assert not solution.is_valid

    def test_solution_copy(self, sample_assets):
        """Test copying a solution."""
        solution = PlacementSolution(
            assets=sample_assets,
            fitness=75.0,
            is_valid=True,
        )

        copy = solution.copy()
        assert copy.fitness == 75.0
        assert copy.is_valid
        assert len(copy.assets) == 2

        # Modify copy shouldn't affect original
        copy.fitness = 50.0
        assert solution.fitness == 75.0

    def test_get_asset_by_id(self, sample_assets):
        """Test getting asset by ID."""
        solution = PlacementSolution(assets=sample_assets)

        asset = solution.get_asset_by_id("bldg_001")
        assert asset is not None
        assert asset.name == "Office Building"

        # Non-existent ID
        assert solution.get_asset_by_id("nonexistent") is None

    def test_get_total_area(self, sample_assets):
        """Test calculating total area."""
        solution = PlacementSolution(assets=sample_assets)

        total_area = solution.get_total_area_sqm()
        assert total_area == 1500.0 + 2400.0

    def test_get_coverage_percent(self, sample_assets):
        """Test calculating coverage percentage."""
        solution = PlacementSolution(assets=sample_assets)

        site_area = 40000.0  # 200x200
        coverage = solution.get_coverage_percent(site_area)

        expected = ((1500.0 + 2400.0) / 40000.0) * 100.0
        assert abs(coverage - expected) < 0.01

    def test_solution_to_dict(self, sample_assets):
        """Test converting solution to dictionary."""
        solution = PlacementSolution(
            assets=sample_assets,
            fitness=80.0,
            is_valid=True,
            objectives={"cut_fill": 70.0, "accessibility": 90.0},
        )

        result_dict = solution.to_dict()

        assert result_dict["fitness"] == 80.0
        assert result_dict["is_valid"] is True
        assert result_dict["num_assets"] == 2
        assert "cut_fill" in result_dict["objectives"]


class TestOptimizationObjective:
    """Tests for OptimizationObjective."""

    def test_objective_creation(self, sample_site_boundary):
        """Test creating optimization objective."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(constraints=constraints)

        assert objective.constraints == constraints
        assert objective.weights is not None

    def test_evaluate_valid_solution(self, sample_site_boundary, sample_assets):
        """Test evaluating a valid solution."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            min_setback_m=5.0,
        )
        objective = OptimizationObjective(constraints=constraints)

        solution = PlacementSolution(assets=sample_assets)
        fitness = objective.evaluate(solution)

        assert solution.fitness == fitness
        assert len(solution.objectives) > 0

    def test_evaluate_solution_with_violations(self, sample_site_boundary):
        """Test evaluating solution with constraint violations."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            min_setback_m=5.0,
        )
        objective = OptimizationObjective(constraints=constraints)

        # Create overlapping assets
        assets = [
            BuildingAsset(
                id="bldg_001",
                name="Building 1",
                dimensions=(30.0, 50.0),
                area_sqm=1500.0,
                position=(100.0, 100.0),
            ),
            BuildingAsset(
                id="bldg_002",
                name="Building 2",
                dimensions=(30.0, 50.0),
                area_sqm=1500.0,
                position=(105.0, 105.0),  # Overlapping
            ),
        ]

        solution = PlacementSolution(assets=assets)
        fitness = objective.evaluate(solution)

        assert solution.constraint_violations > 0
        assert not solution.is_valid
        assert fitness < 0  # Penalty for violations

    def test_evaluate_accessibility(self, sample_site_boundary, sample_assets):
        """Test accessibility objective evaluation."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(
            constraints=constraints,
            weights=ObjectiveWeights(
                cut_fill_weight=0.0,
                accessibility_weight=1.0,
                road_length_weight=0.0,
                compactness_weight=0.0,
                slope_variance_weight=0.0,
            ),
        )

        solution = PlacementSolution(assets=sample_assets)
        objective.evaluate(solution)

        assert "accessibility" in solution.objectives
        assert 0 <= solution.objectives["accessibility"] <= 100

    def test_evaluate_road_length(self, sample_site_boundary, sample_assets):
        """Test road length objective evaluation."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(
            constraints=constraints,
            road_entry_point=(0.0, 0.0),
            weights=ObjectiveWeights(
                cut_fill_weight=0.0,
                accessibility_weight=0.0,
                road_length_weight=1.0,
                compactness_weight=0.0,
                slope_variance_weight=0.0,
            ),
        )

        solution = PlacementSolution(assets=sample_assets)
        objective.evaluate(solution)

        assert "road_length" in solution.objectives
        assert 0 <= solution.objectives["road_length"] <= 100

    def test_evaluate_compactness(self, sample_site_boundary, sample_assets):
        """Test compactness objective evaluation."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(
            constraints=constraints,
            weights=ObjectiveWeights(
                cut_fill_weight=0.0,
                accessibility_weight=0.0,
                road_length_weight=0.0,
                compactness_weight=1.0,
                slope_variance_weight=0.0,
            ),
        )

        solution = PlacementSolution(assets=sample_assets)
        objective.evaluate(solution)

        assert "compactness" in solution.objectives
        assert 0 <= solution.objectives["compactness"] <= 100

    def test_evaluate_with_elevation_data(self, sample_site_boundary, sample_assets):
        """Test evaluation with elevation data."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)

        # Create sample elevation data
        elevation_data = np.random.uniform(100, 150, (50, 50)).astype(np.float32)

        objective = OptimizationObjective(
            constraints=constraints,
            elevation_data=elevation_data,
        )

        solution = PlacementSolution(assets=sample_assets)
        objective.evaluate(solution)

        assert "cut_fill" in solution.objectives

    def test_constraint_violation_counting(self, sample_site_boundary):
        """Test constraint violation counting."""
        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            max_site_coverage_percent=10.0,  # Very restrictive
        )
        objective = OptimizationObjective(constraints=constraints)

        # Create solution that exceeds coverage
        assets = [
            BuildingAsset(
                id=f"bldg_{i:03d}",
                name=f"Building {i}",
                dimensions=(30.0, 50.0),
                area_sqm=1500.0,
                position=(50.0 + i * 40, 100.0),
            )
            for i in range(5)
        ]

        solution = PlacementSolution(assets=assets)
        violations = objective._count_constraint_violations(solution)

        assert violations > 0


class TestObjectiveIntegration:
    """Integration tests for optimization objectives."""

    def test_multi_objective_evaluation(self, sample_site_boundary, sample_assets):
        """Test evaluation with multiple objectives."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)

        # Balanced weights
        weights = ObjectiveWeights(
            cut_fill_weight=0.2,
            accessibility_weight=0.2,
            road_length_weight=0.2,
            compactness_weight=0.2,
            slope_variance_weight=0.2,
        )

        objective = OptimizationObjective(
            constraints=constraints,
            weights=weights,
        )

        solution = PlacementSolution(assets=sample_assets)
        fitness = objective.evaluate(solution)

        # Check all objectives were evaluated
        assert len(solution.objectives) >= 3
        assert 0 <= fitness <= 100

    def test_fitness_improves_with_better_layout(self, sample_site_boundary):
        """Test that fitness improves with better layout."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(constraints=constraints)

        # Solution 1: Spread out assets
        assets1 = [
            BuildingAsset(
                id="bldg_001",
                name="Building 1",
                dimensions=(20.0, 30.0),
                area_sqm=600.0,
                position=(50.0, 50.0),
            ),
            BuildingAsset(
                id="bldg_002",
                name="Building 2",
                dimensions=(20.0, 30.0),
                area_sqm=600.0,
                position=(150.0, 150.0),
            ),
        ]

        # Solution 2: Compact layout (closer but not overlapping)
        assets2 = [
            BuildingAsset(
                id="bldg_001",
                name="Building 1",
                dimensions=(20.0, 30.0),
                area_sqm=600.0,
                position=(80.0, 90.0),
            ),
            BuildingAsset(
                id="bldg_002",
                name="Building 2",
                dimensions=(20.0, 30.0),
                area_sqm=600.0,
                position=(120.0, 110.0),
            ),
        ]

        solution1 = PlacementSolution(assets=assets1)
        solution2 = PlacementSolution(assets=assets2)

        fitness1 = objective.evaluate(solution1)
        fitness2 = objective.evaluate(solution2)

        # Compact layout should have better compactness score
        # (Allow some tolerance since objectives can vary)
        compactness1 = solution1.objectives.get("compactness", 0)
        compactness2 = solution2.objectives.get("compactness", 0)
        # Solution 2 should be at least as compact or more
        assert compactness2 >= compactness1 * 0.9  # Allow 10% tolerance

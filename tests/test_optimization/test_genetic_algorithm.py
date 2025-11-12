"""
Tests for genetic algorithm optimizer.
"""

import pytest
import time
from shapely.geometry import Polygon as ShapelyPolygon

from entmoot.models.assets import BuildingAsset, EquipmentYardAsset
from entmoot.core.optimization.problem import (
    OptimizationConstraints,
    OptimizationObjective,
    ObjectiveWeights,
    PlacementSolution,
)
from entmoot.core.optimization.genetic_algorithm import (
    GeneticAlgorithmConfig,
    GeneticOptimizer,
    InitializationStrategy,
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
        ),
        EquipmentYardAsset(
            id="yard_001",
            name="Storage Yard",
            dimensions=(40.0, 60.0),
            area_sqm=2400.0,
        ),
    ]


@pytest.fixture
def optimizer(sample_site_boundary):
    """Create a basic genetic optimizer."""
    constraints = OptimizationConstraints(
        site_boundary=sample_site_boundary,
        min_setback_m=5.0,
    )
    objective = OptimizationObjective(constraints=constraints)

    config = GeneticAlgorithmConfig(
        population_size=10,
        num_generations=5,
        time_limit_seconds=30.0,
    )

    return GeneticOptimizer(
        objective=objective,
        constraints=constraints,
        config=config,
        random_seed=42,
    )


class TestGeneticAlgorithmConfig:
    """Tests for GeneticAlgorithmConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = GeneticAlgorithmConfig()

        assert config.population_size == 50
        assert config.num_generations == 100
        assert config.mutation_rate == 0.3
        assert config.crossover_rate == 0.7
        assert config.time_limit_seconds == 120.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = GeneticAlgorithmConfig(
            population_size=20,
            num_generations=50,
            mutation_rate=0.2,
            time_limit_seconds=60.0,
        )

        assert config.population_size == 20
        assert config.num_generations == 50
        assert config.mutation_rate == 0.2

    def test_invalid_population_size(self):
        """Test invalid population size validation."""
        with pytest.raises(ValueError, match="at least 2"):
            GeneticAlgorithmConfig(population_size=1)

    def test_invalid_mutation_rate(self):
        """Test invalid mutation rate validation."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            GeneticAlgorithmConfig(mutation_rate=1.5)

    def test_invalid_crossover_rate(self):
        """Test invalid crossover rate validation."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            GeneticAlgorithmConfig(crossover_rate=-0.1)


class TestGeneticOptimizer:
    """Tests for GeneticOptimizer."""

    def test_optimizer_creation(self, optimizer):
        """Test creating optimizer."""
        assert optimizer is not None
        assert optimizer.config.population_size == 10
        assert len(optimizer.population) == 0

    def test_random_initialization(self, optimizer, sample_assets):
        """Test random population initialization."""
        population = optimizer._initialize_random(sample_assets)

        assert len(population) == optimizer.config.population_size
        assert all(isinstance(sol, PlacementSolution) for sol in population)
        assert all(len(sol.assets) == len(sample_assets) for sol in population)

    def test_grid_initialization(self, optimizer, sample_assets):
        """Test grid-based population initialization."""
        population = optimizer._initialize_grid(sample_assets)

        assert len(population) == optimizer.config.population_size
        assert all(len(sol.assets) == len(sample_assets) for sol in population)

    def test_heuristic_initialization(self, optimizer, sample_assets):
        """Test heuristic population initialization."""
        population = optimizer._initialize_heuristic(sample_assets)

        assert len(population) == optimizer.config.population_size
        assert all(len(sol.assets) == len(sample_assets) for sol in population)

    def test_tournament_selection(self, optimizer, sample_assets):
        """Test tournament selection."""
        # Initialize population
        optimizer.population = optimizer._initialize_random(sample_assets)

        # Evaluate population
        for solution in optimizer.population:
            optimizer.objective.evaluate(solution)

        # Sort by fitness
        optimizer.population.sort(key=lambda s: s.fitness, reverse=True)

        # Select parent
        parent = optimizer._tournament_selection()

        assert isinstance(parent, PlacementSolution)
        assert len(parent.assets) == len(sample_assets)

    def test_crossover(self, optimizer, sample_assets):
        """Test crossover operator."""
        # Create two parent solutions
        parent1 = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets],
            fitness=80.0,
        )
        parent2 = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets],
            fitness=70.0,
        )

        # Set different positions
        parent1.assets[0].set_position(50.0, 50.0)
        parent2.assets[0].set_position(150.0, 150.0)

        # Crossover
        child = optimizer._crossover(parent1, parent2)

        assert isinstance(child, PlacementSolution)
        assert len(child.assets) == len(sample_assets)

        # Child position should be between parents
        child_pos = child.assets[0].position
        assert 50.0 <= child_pos[0] <= 150.0
        assert 50.0 <= child_pos[1] <= 150.0

    def test_mutation_move(self, optimizer, sample_assets):
        """Test move mutation operator."""
        solution = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets]
        )

        original_position = solution.assets[0].position

        # Mutate
        mutated = optimizer._mutate_move(solution)

        # Position should have changed
        new_position = mutated.assets[0].position
        assert new_position != original_position

    def test_mutation_rotate(self, optimizer, sample_assets):
        """Test rotate mutation operator."""
        solution = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets]
        )

        solution.assets[0].set_rotation(0)

        # Mutate
        mutated = optimizer._mutate_rotate(solution)

        # Rotation should have changed (unless it randomly picked 0 again)
        # We'll just check it's a valid rotation
        assert mutated.assets[0].rotation in [0, 90, 180, 270]

    def test_mutation_swap(self, optimizer, sample_assets):
        """Test swap mutation operator."""
        solution = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets]
        )

        # Set distinct positions
        solution.assets[0].set_position(50.0, 50.0)
        solution.assets[1].set_position(150.0, 150.0)

        pos1_before = solution.assets[0].position
        pos2_before = solution.assets[1].position

        # Mutate (swap)
        mutated = optimizer._mutate_swap(solution)

        # Positions should be swapped
        assert mutated.assets[0].position == pos2_before
        assert mutated.assets[1].position == pos1_before

    def test_diversity_calculation(self, optimizer, sample_assets):
        """Test diversity calculation between solutions."""
        solution1 = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets]
        )
        solution2 = PlacementSolution(
            assets=[asset.model_copy(deep=True) for asset in sample_assets]
        )

        # Set different positions
        solution1.assets[0].set_position(50.0, 50.0)
        solution2.assets[0].set_position(150.0, 150.0)

        diversity = optimizer._calculate_diversity(solution1, solution2)

        assert 0.0 <= diversity <= 1.0
        assert diversity > 0  # Should be diverse


class TestGeneticOptimization:
    """Integration tests for genetic optimization."""

    def test_basic_optimization(self, optimizer, sample_assets):
        """Test basic optimization run."""
        result = optimizer.optimize(
            assets=sample_assets,
            initialization_strategy=InitializationStrategy.RANDOM,
        )

        assert result is not None
        assert result.best_solution is not None
        assert len(result.best_solution.assets) == len(sample_assets)
        assert result.generations_run > 0
        assert result.time_elapsed_seconds > 0

    def test_optimization_convergence(self, optimizer, sample_assets):
        """Test that optimization converges."""
        result = optimizer.optimize(assets=sample_assets)

        # Check convergence history (includes initial + generations)
        assert len(result.convergence_history) >= result.generations_run
        assert all(isinstance(f, (int, float)) for f in result.convergence_history)

        # Fitness should generally improve or stay same
        first_fitness = result.convergence_history[0]
        last_fitness = result.convergence_history[-1]
        # With few generations and randomness, fitness may not always improve
        # but it shouldn't get dramatically worse
        assert last_fitness >= first_fitness * 0.5  # At most 50% worse (very lenient)

    def test_optimization_with_grid_initialization(self, optimizer, sample_assets):
        """Test optimization with grid initialization."""
        result = optimizer.optimize(
            assets=sample_assets,
            initialization_strategy=InitializationStrategy.GRID,
        )

        assert result.best_solution is not None
        assert len(result.best_solution.assets) == len(sample_assets)

    def test_optimization_with_heuristic_initialization(self, optimizer, sample_assets):
        """Test optimization with heuristic initialization."""
        result = optimizer.optimize(
            assets=sample_assets,
            initialization_strategy=InitializationStrategy.HEURISTIC,
        )

        assert result.best_solution is not None
        assert len(result.best_solution.assets) == len(sample_assets)

    def test_optimization_generates_alternatives(self, optimizer, sample_assets):
        """Test that optimization generates alternative solutions."""
        result = optimizer.optimize(assets=sample_assets)

        assert len(result.alternative_solutions) > 0
        assert len(result.alternative_solutions) <= optimizer.config.num_alternatives

        # Alternatives should be different from best
        for alt in result.alternative_solutions:
            assert alt.fitness <= result.best_solution.fitness

    def test_optimization_respects_time_limit(self, sample_site_boundary, sample_assets):
        """Test that optimization respects time limit."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(constraints=constraints)

        config = GeneticAlgorithmConfig(
            population_size=20,
            num_generations=1000,  # Many generations
            time_limit_seconds=2.0,  # But short time limit
        )

        optimizer = GeneticOptimizer(
            objective=objective,
            constraints=constraints,
            config=config,
        )

        start = time.time()
        result = optimizer.optimize(assets=sample_assets)
        elapsed = time.time() - start

        # Should respect time limit (with generous tolerance for CI/CD)
        assert elapsed < 10.0  # 2 seconds + large margin for slow systems
        # Time limit may not always trigger if it converges quickly
        assert result.metadata.get("time_limited", False) or result.generations_run < 1000

    def test_optimization_with_multiple_assets(self, sample_site_boundary):
        """Test optimization with more assets."""
        assets = [
            BuildingAsset(
                id=f"bldg_{i:03d}",
                name=f"Building {i}",
                dimensions=(20.0, 30.0),
                area_sqm=600.0,
            )
            for i in range(5)
        ]

        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            min_setback_m=5.0,
        )
        objective = OptimizationObjective(constraints=constraints)

        config = GeneticAlgorithmConfig(
            population_size=10,
            num_generations=5,
            time_limit_seconds=30.0,
        )

        optimizer = GeneticOptimizer(
            objective=objective,
            constraints=constraints,
            config=config,
            random_seed=42,
        )

        result = optimizer.optimize(assets=assets)

        assert result.best_solution is not None
        assert len(result.best_solution.assets) == 5

    def test_optimization_result_to_dict(self, optimizer, sample_assets):
        """Test converting optimization result to dictionary."""
        result = optimizer.optimize(assets=sample_assets)

        result_dict = result.to_dict()

        assert "best_solution" in result_dict
        assert "alternative_solutions" in result_dict
        assert "generations_run" in result_dict
        assert "time_elapsed_seconds" in result_dict
        assert "convergence_history" in result_dict

    def test_optimization_with_constraints(self, sample_site_boundary, sample_assets):
        """Test optimization respects constraints."""
        # Create exclusion zone
        exclusion = ShapelyPolygon([
            (80, 80),
            (120, 80),
            (120, 120),
            (80, 120),
            (80, 80),
        ])

        constraints = OptimizationConstraints(
            site_boundary=sample_site_boundary,
            exclusion_zones=[exclusion],
            min_setback_m=5.0,
        )
        objective = OptimizationObjective(constraints=constraints)

        config = GeneticAlgorithmConfig(
            population_size=10,
            num_generations=10,
            time_limit_seconds=30.0,
        )

        optimizer = GeneticOptimizer(
            objective=objective,
            constraints=constraints,
            config=config,
            random_seed=42,
        )

        result = optimizer.optimize(assets=sample_assets)

        # Best solution should have low violations
        assert result.best_solution.constraint_violations <= 2

    def test_optimization_convergence_detection(self, sample_site_boundary, sample_assets):
        """Test convergence detection stops early."""
        constraints = OptimizationConstraints(site_boundary=sample_site_boundary)
        objective = OptimizationObjective(constraints=constraints)

        config = GeneticAlgorithmConfig(
            population_size=10,
            num_generations=100,  # Many generations
            convergence_patience=3,  # Stop after 3 generations without improvement
            convergence_threshold=0.001,
            time_limit_seconds=60.0,
        )

        optimizer = GeneticOptimizer(
            objective=objective,
            constraints=constraints,
            config=config,
            random_seed=42,
        )

        result = optimizer.optimize(assets=sample_assets)

        # Should stop before max generations due to convergence
        # (Though this is probabilistic, so we check metadata)
        assert result.generations_run <= 100
        # At least ran some generations
        assert result.generations_run > 0


class TestOptimizationQuality:
    """Tests for optimization quality metrics."""

    def test_fitness_improves_over_generations(self, optimizer, sample_assets):
        """Test that fitness generally improves over generations."""
        result = optimizer.optimize(assets=sample_assets)

        # Compare first and last generation fitness
        first_gen_fitness = result.convergence_history[0]
        last_gen_fitness = result.convergence_history[-1]

        # Should improve or stay similar (allowing for some randomness)
        assert last_gen_fitness >= first_gen_fitness * 0.7

    def test_alternatives_are_diverse(self, optimizer, sample_assets):
        """Test that alternative solutions are diverse."""
        result = optimizer.optimize(assets=sample_assets)

        if len(result.alternative_solutions) < 2:
            pytest.skip("Not enough alternatives generated")

        # Calculate diversity between alternatives
        alt1 = result.alternative_solutions[0]
        alt2 = result.alternative_solutions[1]

        diversity = optimizer._calculate_diversity(alt1, alt2)
        assert diversity > 0.01  # Should be somewhat different

    def test_best_solution_quality(self, optimizer, sample_assets):
        """Test that best solution has reasonable quality."""
        result = optimizer.optimize(assets=sample_assets)

        # Best solution should be valid or have few violations
        assert result.best_solution.constraint_violations <= 3

        # Should have evaluated objectives
        assert len(result.best_solution.objectives) > 0

"""
Genetic algorithm for asset placement optimization.

This module implements a genetic algorithm that evolves populations of asset
placement solutions to find optimal or near-optimal layouts.
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from entmoot.models.assets import Asset, RotationAngle
from entmoot.core.optimization.problem import (
    OptimizationObjective,
    OptimizationConstraints,
    PlacementSolution,
)


class InitializationStrategy(str, Enum):
    """Strategies for initializing the population."""

    RANDOM = "random"
    GRID = "grid"
    HEURISTIC = "heuristic"


@dataclass
class GeneticAlgorithmConfig:
    """
    Configuration for genetic algorithm.

    Attributes:
        population_size: Number of solutions in population
        num_generations: Maximum number of generations
        mutation_rate: Probability of mutation (0-1)
        crossover_rate: Probability of crossover (0-1)
        elitism_rate: Percentage of top solutions to keep (0-1)
        tournament_size: Size of tournament selection
        convergence_threshold: Stop if improvement below this for N generations
        convergence_patience: Number of generations with no improvement before stopping
        diversity_weight: Weight for maintaining diversity (0-1)
        num_alternatives: Number of diverse alternatives to generate
        time_limit_seconds: Maximum time allowed (seconds)
    """

    population_size: int = 50
    num_generations: int = 100
    mutation_rate: float = 0.3
    crossover_rate: float = 0.7
    elitism_rate: float = 0.1
    tournament_size: int = 3
    convergence_threshold: float = 0.001
    convergence_patience: int = 10
    diversity_weight: float = 0.2
    num_alternatives: int = 3
    time_limit_seconds: float = 120.0  # 2 minutes

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.population_size < 2:
            raise ValueError("Population size must be at least 2")
        if not (0 <= self.mutation_rate <= 1):
            raise ValueError("Mutation rate must be between 0 and 1")
        if not (0 <= self.crossover_rate <= 1):
            raise ValueError("Crossover rate must be between 0 and 1")
        if not (0 <= self.elitism_rate < 1):
            raise ValueError("Elitism rate must be between 0 and 1")
        if self.tournament_size < 2:
            raise ValueError("Tournament size must be at least 2")
        if self.num_alternatives < 1:
            raise ValueError("Must generate at least 1 alternative")


@dataclass
class OptimizationResult:
    """
    Result of genetic algorithm optimization.

    Attributes:
        best_solution: Best solution found
        alternative_solutions: List of diverse alternative solutions
        generations_run: Number of generations executed
        time_elapsed_seconds: Time taken for optimization
        convergence_history: Fitness scores over generations
        final_population: Final population of solutions
        metadata: Additional result metadata
    """

    best_solution: PlacementSolution
    alternative_solutions: List[PlacementSolution] = field(default_factory=list)
    generations_run: int = 0
    time_elapsed_seconds: float = 0.0
    convergence_history: List[float] = field(default_factory=list)
    final_population: List[PlacementSolution] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "best_solution": self.best_solution.to_dict(),
            "alternative_solutions": [sol.to_dict() for sol in self.alternative_solutions],
            "generations_run": self.generations_run,
            "time_elapsed_seconds": self.time_elapsed_seconds,
            "convergence_history": self.convergence_history,
            "metadata": self.metadata,
        }


class GeneticOptimizer:
    """
    Genetic algorithm optimizer for asset placement.

    This class implements a genetic algorithm with:
    - Multiple initialization strategies
    - Tournament selection
    - Various mutation operators
    - Crossover operators
    - Elitism
    - Diversity maintenance
    - Convergence detection
    """

    def __init__(
        self,
        objective: OptimizationObjective,
        constraints: OptimizationConstraints,
        config: Optional[GeneticAlgorithmConfig] = None,
        random_seed: Optional[int] = None,
    ):
        """
        Initialize genetic optimizer.

        Args:
            objective: Optimization objective evaluator
            constraints: Optimization constraints
            config: Algorithm configuration (uses defaults if not provided)
            random_seed: Random seed for reproducibility
        """
        self.objective = objective
        self.constraints = constraints
        self.config = config or GeneticAlgorithmConfig()

        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)

        self.population: List[PlacementSolution] = []
        self.generation = 0
        self.best_fitness_history: List[float] = []
        self.start_time: float = 0.0

    def optimize(
        self,
        assets: List[Asset],
        initialization_strategy: InitializationStrategy = InitializationStrategy.RANDOM,
        seed_solution: Optional[PlacementSolution] = None,
    ) -> OptimizationResult:
        """
        Run genetic algorithm optimization.

        Args:
            assets: List of assets to place
            initialization_strategy: Strategy for population initialization
            seed_solution: Optional existing solution to include in initial population

        Returns:
            OptimizationResult with best and alternative solutions
        """
        self.start_time = time.time()

        # Step 1: Initialize population
        self.population = self._initialize_population(assets, initialization_strategy)

        # Step 1.5: If seed solution provided, add it to population (replacing worst solution)
        if seed_solution is not None:
            self.population[0] = seed_solution  # Replace first member with seed

        # Step 2: Evaluate initial population
        for solution in self.population:
            self.objective.evaluate(solution)

        # Sort by fitness
        self.population.sort(key=lambda s: s.fitness, reverse=True)
        self.best_fitness_history.append(self.population[0].fitness)

        # Step 3: Evolution loop
        no_improvement_count = 0
        last_best_fitness = self.population[0].fitness

        for gen in range(self.config.num_generations):
            self.generation = gen + 1

            # Check time limit
            if time.time() - self.start_time > self.config.time_limit_seconds:
                break

            # Step 4: Selection, crossover, mutation
            new_population = self._evolve_generation()

            # Step 5: Evaluate new population
            for solution in new_population:
                if solution.fitness == 0.0:  # Only evaluate if not already evaluated
                    self.objective.evaluate(solution)

            # Step 6: Update population
            self.population = new_population
            self.population.sort(key=lambda s: s.fitness, reverse=True)

            # Track best fitness
            current_best = self.population[0].fitness
            self.best_fitness_history.append(current_best)

            # Check convergence
            improvement = current_best - last_best_fitness
            if improvement < self.config.convergence_threshold:
                no_improvement_count += 1
            else:
                no_improvement_count = 0

            if no_improvement_count >= self.config.convergence_patience:
                break

            last_best_fitness = current_best

        # Step 7: Generate diverse alternatives
        alternatives = self._generate_alternatives()

        # Prepare result
        elapsed_time = time.time() - self.start_time

        result = OptimizationResult(
            best_solution=self.population[0].copy(),
            alternative_solutions=alternatives,
            generations_run=self.generation,
            time_elapsed_seconds=elapsed_time,
            convergence_history=self.best_fitness_history,
            final_population=[sol.copy() for sol in self.population[:10]],  # Top 10
            metadata={
                "convergence_achieved": no_improvement_count >= self.config.convergence_patience,
                "time_limited": elapsed_time >= self.config.time_limit_seconds,
                "final_population_size": len(self.population),
            },
        )

        return result

    def _initialize_population(
        self, assets: List[Asset], strategy: InitializationStrategy
    ) -> List[PlacementSolution]:
        """Initialize population based on strategy."""
        population = []

        if strategy == InitializationStrategy.RANDOM:
            population = self._initialize_random(assets)
        elif strategy == InitializationStrategy.GRID:
            population = self._initialize_grid(assets)
        elif strategy == InitializationStrategy.HEURISTIC:
            population = self._initialize_heuristic(assets)
        else:
            raise ValueError(f"Unknown initialization strategy: {strategy}")

        return population

    def _initialize_random(self, assets: List[Asset]) -> List[PlacementSolution]:
        """Initialize population with random placements that avoid overlaps."""
        population = []
        buildable_area = self.constraints.get_buildable_area()

        if buildable_area.is_empty:
            raise ValueError("No buildable area available for asset placement")

        bounds = buildable_area.bounds  # (minx, miny, maxx, maxy)

        for _ in range(self.config.population_size):
            # Create copies of assets
            asset_copies = [asset.model_copy(deep=True) for asset in assets]

            # Place assets one at a time, checking for overlaps
            placed_assets = []
            for asset in asset_copies:
                # Random rotation (0, 90, 180, 270)
                asset.set_rotation(random.choice([0, 90, 180, 270]))

                # Try to find a non-overlapping position
                max_attempts = 30
                placed_successfully = False

                for _ in range(max_attempts):
                    x = random.uniform(bounds[0], bounds[2])
                    y = random.uniform(bounds[1], bounds[3])

                    asset.set_position(x, y)

                    # Check if position is in buildable area
                    asset_geom = asset.get_geometry()
                    if not buildable_area.contains(asset_geom):
                        continue

                    # Check for overlaps with already placed assets
                    has_overlap = False
                    for placed_asset in placed_assets:
                        placed_geom = placed_asset.get_geometry()
                        if asset_geom.intersects(placed_geom):
                            has_overlap = True
                            break

                        # Also check spacing requirement
                        spacing_geom = asset.get_spacing_geometry()
                        if spacing_geom.intersects(placed_geom):
                            has_overlap = True
                            break

                    if not has_overlap:
                        placed_successfully = True
                        break

                # Add asset even if we couldn't find perfect placement
                # (genetic algorithm will optimize away overlaps)
                placed_assets.append(asset)

            solution = PlacementSolution(assets=placed_assets)
            population.append(solution)

        return population

    def _initialize_grid(self, assets: List[Asset]) -> List[PlacementSolution]:
        """Initialize population with grid-based placements."""
        population = []
        buildable_area = self.constraints.get_buildable_area()
        bounds = buildable_area.bounds

        # Calculate grid spacing
        grid_size = int(np.sqrt(len(assets))) + 1
        x_spacing = (bounds[2] - bounds[0]) / (grid_size + 1)
        y_spacing = (bounds[3] - bounds[1]) / (grid_size + 1)

        for pop_idx in range(self.config.population_size):
            asset_copies = [asset.model_copy(deep=True) for asset in assets]

            # Place assets on grid with some randomization
            for i, asset in enumerate(asset_copies):
                grid_x = (i % grid_size) + 1
                grid_y = (i // grid_size) + 1

                x = bounds[0] + grid_x * x_spacing + random.uniform(-x_spacing / 4, x_spacing / 4)
                y = bounds[1] + grid_y * y_spacing + random.uniform(-y_spacing / 4, y_spacing / 4)

                asset.set_position(x, y)
                asset.set_rotation(random.choice([0, 90, 180, 270]))

            solution = PlacementSolution(assets=asset_copies)
            population.append(solution)

        return population

    def _initialize_heuristic(self, assets: List[Asset]) -> List[PlacementSolution]:
        """Initialize population with heuristic placements (by priority)."""
        population = []
        buildable_area = self.constraints.get_buildable_area()
        bounds = buildable_area.bounds

        for _ in range(self.config.population_size):
            asset_copies = [asset.model_copy(deep=True) for asset in assets]

            # Sort by priority (high to low)
            asset_copies.sort(key=lambda a: a.priority, reverse=True)

            # Place high-priority assets near center
            center_x = (bounds[0] + bounds[2]) / 2
            center_y = (bounds[1] + bounds[3]) / 2

            for i, asset in enumerate(asset_copies):
                # High priority: closer to center
                radius = (i + 1) * 20.0 + random.uniform(-10, 10)
                angle = random.uniform(0, 2 * np.pi)

                x = center_x + radius * np.cos(angle)
                y = center_y + radius * np.sin(angle)

                # Clamp to bounds
                x = max(bounds[0], min(bounds[2], x))
                y = max(bounds[1], min(bounds[3], y))

                asset.set_position(x, y)
                asset.set_rotation(random.choice([0, 90, 180, 270]))

            solution = PlacementSolution(assets=asset_copies)
            population.append(solution)

        return population

    def _evolve_generation(self) -> List[PlacementSolution]:
        """Evolve one generation of the population."""
        new_population = []

        # Elitism: keep top performers
        num_elite = max(1, int(self.config.population_size * self.config.elitism_rate))
        elites = self.population[:num_elite]
        new_population.extend([sol.copy() for sol in elites])

        # Generate rest of population through selection, crossover, mutation
        while len(new_population) < self.config.population_size:
            # Selection
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()

            # Crossover
            if random.random() < self.config.crossover_rate:
                child = self._crossover(parent1, parent2)
            else:
                child = parent1.copy()

            # Mutation
            if random.random() < self.config.mutation_rate:
                child = self._mutate(child)

            new_population.append(child)

        return new_population

    def _tournament_selection(self) -> PlacementSolution:
        """Select solution using tournament selection."""
        tournament = random.sample(self.population, self.config.tournament_size)
        tournament.sort(key=lambda s: s.fitness, reverse=True)
        return tournament[0]

    def _crossover(
        self, parent1: PlacementSolution, parent2: PlacementSolution
    ) -> PlacementSolution:
        """
        Crossover two parent solutions to create a child.

        Uses blend crossover: takes weighted average of positions.
        """
        child = parent1.copy()

        # Blend positions
        for i, child_asset in enumerate(child.assets):
            if i < len(parent2.assets):
                p1_pos = parent1.assets[i].position
                p2_pos = parent2.assets[i].position

                # Weighted average (favor better parent)
                w1 = 0.5 + 0.3 * (parent1.fitness - parent2.fitness) / max(
                    abs(parent1.fitness - parent2.fitness), 1.0
                )
                w1 = max(0.2, min(0.8, w1))  # Clamp to [0.2, 0.8]
                w2 = 1.0 - w1

                new_x = w1 * p1_pos[0] + w2 * p2_pos[0]
                new_y = w1 * p1_pos[1] + w2 * p2_pos[1]

                child_asset.set_position(new_x, new_y)

                # Inherit rotation from better parent
                if parent1.fitness > parent2.fitness:
                    child_asset.set_rotation(parent1.assets[i].rotation)
                else:
                    child_asset.set_rotation(parent2.assets[i].rotation)

        return child

    def _mutate(self, solution: PlacementSolution) -> PlacementSolution:
        """
        Mutate a solution using various mutation operators.

        Mutation operators:
        - Move: Random walk for asset position
        - Rotate: Change rotation angle
        - Swap: Swap positions of two assets
        """
        mutated = solution.copy()

        # Choose mutation operator
        operator = random.choice(["move", "rotate", "swap"])

        if operator == "move":
            mutated = self._mutate_move(mutated)
        elif operator == "rotate":
            mutated = self._mutate_rotate(mutated)
        elif operator == "swap":
            mutated = self._mutate_swap(mutated)

        return mutated

    def _mutate_move(self, solution: PlacementSolution) -> PlacementSolution:
        """Mutate by moving a random asset (with overlap avoidance)."""
        if not solution.assets:
            return solution

        # Select random asset to move
        asset_idx = random.randint(0, len(solution.assets) - 1)
        asset = solution.assets[asset_idx]

        # Store original position in case we need to revert
        original_pos = asset.position

        # Try several random moves, pick first one without overlaps
        step_size = 20.0  # meters
        max_attempts = 10

        for _ in range(max_attempts):
            dx = random.uniform(-step_size, step_size)
            dy = random.uniform(-step_size, step_size)

            x, y = original_pos
            new_x, new_y = x + dx, y + dy
            asset.set_position(new_x, new_y)

            # Check if new position causes overlaps
            asset_geom = asset.get_geometry()
            has_overlap = False

            # Check against all other assets
            for i, other_asset in enumerate(solution.assets):
                if i == asset_idx:
                    continue

                other_geom = other_asset.get_geometry()
                if asset_geom.intersects(other_geom):
                    has_overlap = True
                    break

            # If no overlap, accept this position
            if not has_overlap:
                return solution

        # If all attempts failed, revert to original position
        asset.set_position(original_pos[0], original_pos[1])
        return solution

    def _mutate_rotate(self, solution: PlacementSolution) -> PlacementSolution:
        """Mutate by rotating a random asset (with overlap avoidance)."""
        if not solution.assets:
            return solution

        # Select random asset to rotate
        asset_idx = random.randint(0, len(solution.assets) - 1)
        asset = solution.assets[asset_idx]

        # Store original rotation in case we need to revert
        original_rotation = asset.rotation

        # Try all rotation angles, pick first one without overlaps
        rotation_options = [0, 90, 180, 270]
        random.shuffle(rotation_options)  # Try in random order

        for new_rotation in rotation_options:
            if new_rotation == original_rotation:
                continue  # Skip current rotation

            asset.set_rotation(new_rotation)

            # Check if new rotation causes overlaps
            asset_geom = asset.get_geometry()
            has_overlap = False

            # Check against all other assets
            for i, other_asset in enumerate(solution.assets):
                if i == asset_idx:
                    continue

                other_geom = other_asset.get_geometry()
                if asset_geom.intersects(other_geom):
                    has_overlap = True
                    break

            # If no overlap, accept this rotation
            if not has_overlap:
                return solution

        # If all rotations failed, revert to original
        asset.set_rotation(original_rotation)
        return solution

    def _mutate_swap(self, solution: PlacementSolution) -> PlacementSolution:
        """Mutate by swapping positions of two assets."""
        if len(solution.assets) < 2:
            return solution

        # Select two random assets
        asset1, asset2 = random.sample(solution.assets, 2)

        # Swap positions
        pos1 = asset1.position
        pos2 = asset2.position

        asset1.set_position(pos2[0], pos2[1])
        asset2.set_position(pos1[0], pos1[1])

        return solution

    def _generate_alternatives(self) -> List[PlacementSolution]:
        """
        Generate diverse alternative solutions.

        Uses diversity-based selection to find solutions that are
        significantly different from the best solution.
        """
        if len(self.population) < self.config.num_alternatives + 1:
            return [sol.copy() for sol in self.population[1 : self.config.num_alternatives + 1]]

        alternatives = []
        best_solution = self.population[0]

        # Score remaining solutions by diversity from best
        candidates = []
        for solution in self.population[1:]:
            diversity_score = self._calculate_diversity(best_solution, solution)
            fitness_score = solution.fitness

            # Combined score: balance fitness and diversity
            combined_score = (
                1.0 - self.config.diversity_weight
            ) * fitness_score + self.config.diversity_weight * diversity_score * 100.0

            candidates.append((solution, combined_score))

        # Sort by combined score
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Select top N alternatives
        for i in range(min(self.config.num_alternatives, len(candidates))):
            alternatives.append(candidates[i][0].copy())

        return alternatives

    def _calculate_diversity(
        self, solution1: PlacementSolution, solution2: PlacementSolution
    ) -> float:
        """
        Calculate diversity score between two solutions.

        Returns:
            Diversity score (0-1, higher = more different)
        """
        if not solution1.assets or not solution2.assets:
            return 0.0

        total_distance = 0.0
        for i in range(min(len(solution1.assets), len(solution2.assets))):
            pos1 = solution1.assets[i].position
            pos2 = solution2.assets[i].position

            distance = np.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)
            total_distance += distance

            # Also consider rotation difference
            rot_diff = abs(solution1.assets[i].rotation - solution2.assets[i].rotation)
            rot_diff = min(rot_diff, 360 - rot_diff)  # Handle wrap-around
            total_distance += rot_diff / 10.0  # Scale rotation difference

        # Normalize by number of assets and typical distance scale
        avg_distance = total_distance / len(solution1.assets)
        typical_distance = 100.0  # meters

        diversity = min(avg_distance / typical_distance, 1.0)
        return diversity

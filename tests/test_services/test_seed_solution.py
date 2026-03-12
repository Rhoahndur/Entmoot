"""Tests for PlacementSolution import and instantiation in seed solution path."""

from unittest.mock import MagicMock

import pytest


def test_placement_solution_import_resolves():
    """Verify the import path used in optimization_service.py resolves correctly."""
    from entmoot.core.optimization.problem import PlacementSolution

    assert PlacementSolution is not None


def test_placement_solution_instantiation_with_mock_assets():
    """Verify PlacementSolution can be instantiated with a list of assets."""
    from entmoot.core.optimization.problem import PlacementSolution

    mock_asset_1 = MagicMock()
    mock_asset_1.position = (10.0, 20.0)
    mock_asset_2 = MagicMock()
    mock_asset_2.position = (30.0, 40.0)

    solution = PlacementSolution(assets=[mock_asset_1, mock_asset_2])

    assert len(solution.assets) == 2
    assert solution.fitness == 0.0
    assert solution.constraint_violations == 0
    assert solution.is_valid is False


def test_placement_solution_not_importable_from_old_path():
    """Verify the old (broken) import path does not exist."""
    with pytest.raises(ModuleNotFoundError):
        from entmoot.core.optimization.solution import PlacementSolution  # noqa: F401

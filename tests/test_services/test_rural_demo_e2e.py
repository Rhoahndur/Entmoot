"""End-to-end integration test for the rural_demo.kml fixture.

Runs the full optimization pipeline and verifies zero constraint violations
are reported to the user.
"""

import asyncio
import uuid
from pathlib import Path

import pytest

from entmoot.core.redis_storage import get_storage
from entmoot.core.storage import storage_service
from entmoot.models.project import (
    AssetConfig,
    AssetType,
    ConstraintConfig,
    LayoutResults,
    OptimizationWeights,
    ProjectConfig,
    RoadConfig,
)
from entmoot.services.optimization_service import run_optimization_sync
from entmoot.services.project_service import ProjectService

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture()
def upload_id():
    """Save rural_demo.kml into StorageService and return its upload_id."""
    kml_path = FIXTURE_DIR / "rural_demo.kml"
    content = kml_path.read_bytes()

    metadata = asyncio.run(
        storage_service.save_file(
            file_content=content,
            filename="rural_demo.kml",
            content_type="application/vnd.google-earth.kml+xml",
            file_type="kml",
        )
    )

    return str(metadata.upload_id)


def _make_config(upload_id: str) -> ProjectConfig:
    """Build a minimal ProjectConfig matching the frontend defaults."""
    return ProjectConfig(
        project_name="Rural Demo E2E Test",
        upload_id=upload_id,
        assets=[
            AssetConfig(type=AssetType.BUILDINGS, quantity=3, width=60, length=80),
        ],
        constraints=ConstraintConfig(
            setback_distance=20,
            min_distance_between_assets=10,
            use_existing_conditions=False,  # skip OSM/FEMA for deterministic test
        ),
        road_design=RoadConfig(),
        optimization_weights=OptimizationWeights(
            cost=40,
            buildable_area=30,
            accessibility=15,
            environmental_impact=10,
            aesthetics=5,
        ),
    )


@pytest.fixture()
def rural_demo_project(upload_id):
    """Set up a project in storage and return (storage, project_id, config)."""
    storage = get_storage()
    project_id = f"e2e-rural-demo-{uuid.uuid4().hex[:8]}"
    config = _make_config(upload_id)

    project_data = {
        "project_id": project_id,
        "config": config.model_dump(),
        "project_name": config.project_name,
        "status": "created",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "progress": 0,
        "error": None,
    }
    storage.set_project(project_id, project_data)

    return storage, project_id, config


def test_rural_demo_zero_violations(rural_demo_project):
    """Full pipeline: parse, optimize, build results, assert zero violations.

    Runs the GA once and checks both raw GA validity and the results
    endpoint's violation report.  Catches the double-counting bug where
    _check_constraint_zones ran on top of UTM-based checks, producing
    phantom setback violations.
    """
    storage, project_id, config = rural_demo_project

    # Run the optimizer synchronously (single invocation for all assertions)
    layout_results: LayoutResults = run_optimization_sync(project_id, config)

    # --- GA-level checks ---
    assert layout_results.constraints_satisfied, (
        "GA should produce a valid solution for a 40-acre rural parcel "
        f"with only 3 buildings (fitness_score={layout_results.fitness_score:.2f})"
    )
    assert layout_results.fitness_score > 0, (
        f"Fitness should be positive for valid solution, " f"got {layout_results.fitness_score}"
    )
    assert len(layout_results.placed_assets) == 3

    # --- Results-endpoint checks ---
    # Persist results (as the async wrapper does)
    storage.set_results(project_id, layout_results.model_dump())

    # Re-read project (optimization_service stores utm_data, etc.)
    project = storage.get_project(project_id)
    assert project is not None

    # Build the OptimizationResults exactly as the GET /results endpoint does
    opt_results = ProjectService.build_optimization_results(project, layout_results, project_id)

    # Extract violations from the response
    assert len(opt_results.alternatives) > 0
    alt = opt_results.alternatives[0]

    if alt.violations:
        msgs = [f"  [{v.severity}] {v.asset_id}: {v.message}" for v in alt.violations]
        detail = "\n".join(msgs)
        pytest.fail(f"Expected 0 violations but got {len(alt.violations)}:\n{detail}")

    assert alt.metrics.constraint_violations == 0

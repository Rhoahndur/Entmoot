"""
Shared test fixtures and configuration.
"""

import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from entmoot.api.main import app


def pytest_configure(config):
    """Generate binary fixture files (e.g., KMZ) that cannot be checked in as text."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    _generate_kmz_fixtures(fixtures_dir)


def _generate_kmz_fixtures(fixtures_dir: Path) -> None:
    """Create KMZ fixture files from existing KML fixtures.

    KMZ files are ZIP archives containing KML. Since they are binary, we
    generate them from the KML source files so we don't need to commit
    binary blobs to the repository.
    """
    simple_kml_path = fixtures_dir / "simple.kml"
    simple_kmz_path = fixtures_dir / "simple.kmz"

    if simple_kml_path.exists():
        kml_content = simple_kml_path.read_text()
        with zipfile.ZipFile(simple_kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc.kml", kml_content)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-assign markers based on test file path.

    - Files under ``test_integrations/`` or containing 'integration' get ``@pytest.mark.integration``
    - All other tests get ``@pytest.mark.unit``
    """
    for item in items:
        # Skip items that already have explicit markers
        existing = {m.name for m in item.iter_markers()}

        path_str = str(item.fspath)

        if "integration" in existing or "unit" in existing:
            continue

        if "test_integrations" in path_str or "integration" in path_str:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

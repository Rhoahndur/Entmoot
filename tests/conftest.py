"""
Shared test fixtures and configuration.
"""

import pytest
from fastapi.testclient import TestClient

from entmoot.api.main import app


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

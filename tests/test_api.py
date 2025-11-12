"""
Tests for the FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient

from entmoot.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_root_endpoint(client: TestClient) -> None:
    """Test the root endpoint returns correct information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Entmoot API"
    assert data["version"] == "0.1.0"
    assert "description" in data


def test_health_check(client: TestClient) -> None:
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint_returns_dict(client: TestClient) -> None:
    """Test root endpoint returns dictionary with expected keys."""
    response = client.get("/")
    data = response.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"name", "version", "description"}

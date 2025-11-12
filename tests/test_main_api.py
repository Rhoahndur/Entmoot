"""
Tests for main API endpoints and application lifecycle.
"""

import pytest
from fastapi.testclient import TestClient

from entmoot.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestMainEndpoints:
    """Tests for main API endpoints."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Entmoot API"
        assert "version" in data
        assert data["description"] == "AI-driven site layout automation"

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"


class TestLifespan:
    """Tests for application lifespan management."""

    def test_app_starts_and_stops(self) -> None:
        """Test that app can start and stop without errors."""
        # Using TestClient handles lifespan automatically
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

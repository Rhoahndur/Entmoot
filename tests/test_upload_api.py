"""
Integration tests for upload API endpoint.
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from entmoot.api.main import app
from entmoot.core.config import settings


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def temp_upload_dir(tmp_path: Path, monkeypatch) -> Path:  # type: ignore
    """Create and configure a temporary upload directory."""
    upload_dir = tmp_path / "test_uploads"
    upload_dir.mkdir()

    # Mock the settings to use temp directory
    monkeypatch.setattr(settings, "uploads_dir", upload_dir)

    # Replace the global storage service instance
    from entmoot.core import storage
    from entmoot.api import upload as upload_module

    new_storage = storage.FileStorageService(base_dir=upload_dir)
    monkeypatch.setattr(storage, "storage_service", new_storage)
    monkeypatch.setattr(upload_module, "storage_service", new_storage)

    return upload_dir


class TestUploadEndpoint:
    """Tests for POST /api/v1/upload endpoint."""

    @pytest.mark.integration
    def test_upload_kmz_file_success(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test successful upload of a KMZ file."""
        # Create a valid KMZ file (ZIP format)
        file_content = b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test"
        files = {"file": ("test.kmz", io.BytesIO(file_content), "application/zip")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 201
        data = response.json()

        assert "upload_id" in data
        assert data["filename"] == "test.kmz"
        assert data["file_size"] == len(file_content)
        assert data["message"] == "File uploaded successfully"

    @pytest.mark.integration
    def test_upload_kml_file_success(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test successful upload of a KML file."""
        file_content = b'<?xml version="1.0"?><kml>test</kml>'
        files = {"file": ("test.kml", io.BytesIO(file_content), "application/xml")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.kml"

    @pytest.mark.integration
    def test_upload_geojson_file_success(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test successful upload of a GeoJSON file."""
        file_content = b'{"type": "FeatureCollection", "features": []}'
        files = {
            "file": ("test.geojson", io.BytesIO(file_content), "application/geo+json")
        }

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.geojson"

    @pytest.mark.integration
    def test_upload_tif_file_success(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test successful upload of a TIFF file."""
        # TIFF magic number (little-endian)
        file_content = b"II\x2a\x00\x08\x00\x00\x00test"
        files = {"file": ("test.tif", io.BytesIO(file_content), "image/tiff")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.tif"

    @pytest.mark.integration
    def test_upload_invalid_extension(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test that invalid file extensions are rejected."""
        file_content = b"test content"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error_code" in data["detail"]
        assert data["detail"]["error_code"] == "VALIDATION_ERROR"

    @pytest.mark.integration
    def test_upload_mismatched_mime_type(
        self, client: TestClient, temp_upload_dir: Path
    ) -> None:
        """Test that mismatched MIME types are rejected."""
        # KMZ file with wrong MIME type
        file_content = b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test"
        files = {"file": ("test.kmz", io.BytesIO(file_content), "text/plain")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "VALIDATION_ERROR"
        assert "MIME type" in data["detail"]["message"]

    @pytest.mark.integration
    def test_upload_wrong_magic_number(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test that files with wrong magic numbers are rejected."""
        # File claims to be KMZ but has wrong content
        file_content = b"This is not a ZIP file"
        files = {"file": ("test.kmz", io.BytesIO(file_content), "application/zip")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "VALIDATION_ERROR"
        assert "does not match" in data["detail"]["message"]

    @pytest.mark.integration
    def test_upload_file_too_large(
        self, client: TestClient, temp_upload_dir: Path, monkeypatch  # type: ignore
    ) -> None:
        """Test that files exceeding size limit are rejected."""
        # Set a small max size for testing
        monkeypatch.setattr(settings, "max_upload_size_mb", 0)  # 0 MB limit

        file_content = b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test"
        files = {"file": ("test.kmz", io.BytesIO(file_content), "application/zip")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 413
        data = response.json()
        assert data["detail"]["error_code"] == "FILE_TOO_LARGE"

    @pytest.mark.integration
    def test_upload_empty_file(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test that empty files are rejected."""
        file_content = b""
        files = {"file": ("test.kmz", io.BytesIO(file_content), "application/zip")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 413
        data = response.json()
        assert data["detail"]["error_code"] == "FILE_TOO_LARGE"
        assert "empty" in data["detail"]["message"].lower()

    @pytest.mark.integration
    def test_upload_no_filename(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test that uploads without filename are rejected."""
        file_content = b"test"
        # Don't provide filename - FastAPI returns 422 for this
        files = {"file": ("", io.BytesIO(file_content), "application/zip")}

        response = client.post("/api/v1/upload", files=files)

        # FastAPI returns 422 for empty filename (validation error)
        assert response.status_code in [400, 422]

    @pytest.mark.integration
    def test_upload_file_stored_correctly(
        self, client: TestClient, temp_upload_dir: Path
    ) -> None:
        """Test that uploaded file is stored in correct location."""
        file_content = b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test data"
        files = {"file": ("test.kmz", io.BytesIO(file_content), "application/zip")}

        response = client.post("/api/v1/upload", files=files)

        assert response.status_code == 201
        upload_id = response.json()["upload_id"]

        # Verify file exists on disk
        upload_dir = temp_upload_dir / upload_id
        assert upload_dir.exists()

        stored_file = upload_dir / "test.kmz"
        assert stored_file.exists()
        assert stored_file.read_bytes() == file_content

        # Verify metadata exists
        metadata_file = upload_dir / "metadata.json"
        assert metadata_file.exists()

    @pytest.mark.integration
    def test_multiple_uploads(self, client: TestClient, temp_upload_dir: Path) -> None:
        """Test multiple file uploads create separate entries."""
        files1 = {
            "file": (
                "test1.kmz",
                io.BytesIO(b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test1"),
                "application/zip",
            )
        }
        files2 = {
            "file": (
                "test2.kmz",
                io.BytesIO(b"PK\x03\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00test2"),
                "application/zip",
            )
        }

        response1 = client.post("/api/v1/upload", files=files1)
        response2 = client.post("/api/v1/upload", files=files2)

        assert response1.status_code == 201
        assert response2.status_code == 201

        upload_id1 = response1.json()["upload_id"]
        upload_id2 = response2.json()["upload_id"]

        # Verify they have different IDs
        assert upload_id1 != upload_id2

        # Verify both files exist
        assert (temp_upload_dir / upload_id1 / "test1.kmz").exists()
        assert (temp_upload_dir / upload_id2 / "test2.kmz").exists()


class TestUploadHealthCheck:
    """Tests for upload service health check endpoint."""

    @pytest.mark.integration
    def test_upload_health_check(self, client: TestClient) -> None:
        """Test upload service health check."""
        response = client.get("/api/v1/upload/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "upload"
        assert "max_upload_size_mb" in data
        assert "allowed_extensions" in data
        assert "virus_scan_enabled" in data


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation."""

    def test_openapi_schema_includes_upload_endpoint(self, client: TestClient) -> None:
        """Test that OpenAPI schema includes upload endpoint."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        # Check that upload endpoint is documented
        assert "/api/v1/upload" in schema["paths"]

        upload_endpoint = schema["paths"]["/api/v1/upload"]["post"]
        assert "summary" in upload_endpoint
        assert "description" in upload_endpoint
        assert "responses" in upload_endpoint

        # Check response codes are documented
        responses = upload_endpoint["responses"]
        assert "201" in responses  # Success
        assert "400" in responses  # Validation error
        assert "413" in responses  # File too large

    def test_docs_accessible(self, client: TestClient) -> None:
        """Test that Swagger docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

"""Integration tests for RCM API endpoints."""
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


class TestHealth:
    """Test health endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuth:
    """Test authentication endpoints."""

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": "pass"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "Incorrect username or password" in data["detail"]


class TestProtectedEndpoints:
    """Test protected endpoints require authentication."""

    def test_validation_without_auth(self, client):
        """Test validation endpoint requires auth."""
        response = client.post("/api/v1/validation/run")
        assert response.status_code == 403

    def test_validation_results_without_auth(self, client):
        """Test validation results endpoint requires auth."""
        response = client.get("/api/v1/validation/results")
        assert response.status_code == 403

    def test_validation_claims_without_auth(self, client):
        """Test validation claims endpoint requires auth."""
        response = client.get("/api/v1/validation/claims-validated")
        assert response.status_code == 403


class TestValidation:
    """Test validation endpoints with auth."""

    def get_token(self, client):
        """Helper to get auth token."""
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": "pass"}
        )
        return response.json()["access_token"]

    def test_validation_results_endpoint(self, client):
        """Test validation results endpoint."""
        token = self.get_token(client)
        response = client.get(
            "/api/v1/validation/results",
            headers={"Authorization": f"Bearer {token}"}
        )
        # May return data or empty metrics
        assert response.status_code in [200, 404]

    def test_validation_claims_endpoint(self, client):
        """Test validation claims endpoint."""
        token = self.get_token(client)
        response = client.get(
            "/api/v1/validation/claims-validated",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert "pagination" in data
        assert "filters" in data
        assert isinstance(data["claims"], list)

    def test_validation_run_endpoint(self, client):
        """Test validation run endpoint."""
        token = self.get_token(client)
        response = client.post(
            "/api/v1/validation/run",
            headers={"Authorization": f"Bearer {token}"}
        )
        # May return success, task_id, or "No claims to validate"
        assert response.status_code in [200, 400]
        data = response.json()
        assert "message" in data

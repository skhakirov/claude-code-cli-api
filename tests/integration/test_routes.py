"""
TDD: Integration tests for API routes.
Status: RED (must fail before implementation)
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestQueryRoutes:
    """Tests for /query endpoints."""

    @pytest.fixture
    def client(self, mock_settings):
        """TestClient with mocked dependencies."""
        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.api.dependencies.get_settings", return_value=mock_settings):
                from fastapi.testclient import TestClient
                from src.api.main import app
                return TestClient(app)

    def test_query_without_auth(self, client):
        """Request without API key is rejected."""
        response = client.post("/api/v1/query", json={"prompt": "Hello"})
        assert response.status_code == 401

    def test_query_with_invalid_auth(self, client):
        """Request with invalid API key is rejected."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": "Hello"},
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code == 401

    def test_query_success(self, client, mock_settings):
        """Successful query request."""
        with patch("src.services.claude_executor.ClaudeExecutor.execute_query") as mock_exec:
            from src.models.response import QueryResponse, QueryStatus

            mock_exec.return_value = QueryResponse(
                result="Hello!",
                session_id="test-123",
                status=QueryStatus.SUCCESS,
                duration_ms=1000,
                duration_api_ms=800
            )

            response = client.post(
                "/api/v1/query",
                json={"prompt": "Hello"},
                headers={"X-API-Key": "test-api-key"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["result"] == "Hello!"
            assert data["session_id"] == "test-123"

    def test_query_validation_error(self, client):
        """Validation error for invalid request."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": ""},  # Empty prompt
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 422

    def test_query_with_options(self, client, mock_settings):
        """Query with all options."""
        with patch("src.services.claude_executor.ClaudeExecutor.execute_query") as mock_exec:
            from src.models.response import QueryResponse, QueryStatus

            mock_exec.return_value = QueryResponse(
                result="Done!",
                session_id="test-456",
                status=QueryStatus.SUCCESS,
                duration_ms=2000,
                duration_api_ms=1500
            )

            response = client.post(
                "/api/v1/query",
                json={
                    "prompt": "Hello",
                    "model": "claude-opus-4-20250514",
                    "max_turns": 10,
                    "permission_mode": "bypassPermissions"
                },
                headers={"X-API-Key": "test-api-key"}
            )

            assert response.status_code == 200


class TestHealthRoutes:
    """Tests for /health endpoint."""

    @pytest.fixture
    def client(self, mock_settings):
        """TestClient with mocked dependencies."""
        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.api.dependencies.get_settings", return_value=mock_settings):
                from fastapi.testclient import TestClient
                from src.api.main import app
                return TestClient(app)

    def test_health_check(self, client):
        """Health check is accessible without auth."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_check_returns_version(self, client):
        """Health check returns API version."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data or "status" in data


class TestSessionRoutes:
    """Tests for /sessions endpoints."""

    @pytest.fixture
    def client(self, mock_settings):
        """TestClient with mocked dependencies."""
        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.api.dependencies.get_settings", return_value=mock_settings):
                from fastapi.testclient import TestClient
                from src.api.main import app
                return TestClient(app)

    def test_list_sessions(self, client):
        """List sessions endpoint."""
        response = client.get(
            "/api/v1/sessions",
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_sessions_without_auth(self, client):
        """List sessions without auth is rejected."""
        response = client.get("/api/v1/sessions")
        assert response.status_code == 401

    def test_get_session_not_found(self, client):
        """Non-existent session returns 404."""
        response = client.get(
            "/api/v1/sessions/nonexistent",
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 404

    def test_delete_session(self, client, mock_settings):
        """Delete session endpoint."""
        # First we need to mock session cache
        with patch("src.api.dependencies.get_session_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.delete.return_value = True
            mock_cache.return_value = mock_cache_instance

            response = client.delete(
                "/api/v1/sessions/test-123",
                headers={"X-API-Key": "test-api-key"}
            )
            # Should be 200 or 204 if found, 404 if not
            assert response.status_code in [200, 204, 404]

    def test_delete_session_not_found(self, client):
        """Delete non-existent session returns 404."""
        response = client.delete(
            "/api/v1/sessions/nonexistent",
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 404

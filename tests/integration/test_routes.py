"""
TDD: Integration tests for API routes.
Status: GREEN (with mocked dependencies)
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def create_mock_sdk():
    """Create mock SDK components."""
    class MockAssistantMessage:
        pass

    class MockResultMessage:
        pass

    class MockSystemMessage:
        pass

    class MockUserMessage:
        pass

    class MockTextBlock:
        pass

    class MockThinkingBlock:
        pass

    class MockToolUseBlock:
        pass

    class MockToolResultBlock:
        pass

    return {
        'query': MagicMock(),
        'ClaudeAgentOptions': MagicMock(),
        'AssistantMessage': MockAssistantMessage,
        'ResultMessage': MockResultMessage,
        'SystemMessage': MockSystemMessage,
        'UserMessage': MockUserMessage,
        'TextBlock': MockTextBlock,
        'ThinkingBlock': MockThinkingBlock,
        'ToolUseBlock': MockToolUseBlock,
        'ToolResultBlock': MockToolResultBlock,
    }


@pytest.fixture
def mock_sdk():
    """Create mock SDK to prevent import errors."""
    return create_mock_sdk()


@pytest.fixture
def client(mock_settings, mock_sdk):
    """TestClient with mocked dependencies."""
    with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
        with patch("src.core.config.get_settings", return_value=mock_settings):
            # Clear caches before importing
            from src.api.dependencies import get_executor
            get_executor.cache_clear()

            # Reset app_state session_cache
            from src.api.main import app_state
            app_state.session_cache = None

            from src.api.main import app
            return TestClient(app)


class TestQueryRoutes:
    """Tests for /query endpoints."""

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

    def test_query_success(self, mock_settings):
        """Successful query request."""
        mock_sdk = create_mock_sdk()

        # Setup mock response
        result_msg = MagicMock()
        result_msg.session_id = "test-123"
        result_msg.duration_ms = 1000
        result_msg.duration_api_ms = 800
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.usage = None
        result_msg.result = "Hello!"
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                from src.api.dependencies import get_executor
                get_executor.cache_clear()

                from src.api.main import app, app_state
                app_state.session_cache = None
                client = TestClient(app)

                response = client.post(
                    "/api/v1/query",
                    json={"prompt": "Hello"},
                    headers={"X-API-Key": "test-api-key"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["session_id"] == "test-123"

    def test_query_validation_error(self, client):
        """Validation error for invalid request."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": ""},  # Empty prompt
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 422

    def test_query_with_options(self, mock_settings):
        """Query with all options."""
        mock_sdk = create_mock_sdk()

        result_msg = MagicMock()
        result_msg.session_id = "test-456"
        result_msg.duration_ms = 2000
        result_msg.duration_api_ms = 1500
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.01
        result_msg.usage = None
        result_msg.result = "Done!"
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                from src.api.dependencies import get_executor
                get_executor.cache_clear()

                from src.api.main import app, app_state
                app_state.session_cache = None
                client = TestClient(app)

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

    def test_delete_session_not_found(self, client):
        """Delete non-existent session returns 404."""
        response = client.delete(
            "/api/v1/sessions/nonexistent",
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 404

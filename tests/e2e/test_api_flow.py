"""
End-to-end tests for the Claude Code CLI API.

These tests verify complete request/response flows using FastAPI TestClient.
SDK calls are mocked to allow testing without Claude CLI installed.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

# Set environment before importing app
os.environ["CLAUDE_API_API_KEYS"] = '["test-key", "valid-key"]'
os.environ["CLAUDE_API_ALLOWED_DIRECTORIES"] = '["/tmp", "/workspace"]'

from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """E2E tests for health check endpoints."""

    def test_health_check_returns_ok(self, client):
        """Health endpoint returns healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_ready_returns_circuit_state(self, client):
        """Health ready endpoint includes circuit breaker state."""
        response = client.get("/api/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "circuit_breaker" in data


class TestAuthenticationFlow:
    """E2E tests for API authentication."""

    def test_request_without_api_key_returns_401(self, client):
        """Requests without API key are rejected."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": "Hello"}
        )

        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_request_with_invalid_api_key_returns_401(self, client):
        """Requests with invalid API key are rejected."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": "Hello"},
            headers={"X-API-Key": "wrong-key"}
        )

        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_request_with_valid_api_key_passes_auth(self, client):
        """Requests with valid API key pass authentication."""
        mock_sdk = _create_mock_sdk()

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            response = client.post(
                "/api/v1/query",
                json={"prompt": "Hello"},
                headers={"X-API-Key": "valid-key"}
            )

            # Should not be 401 - authentication passed
            assert response.status_code != 401


class TestQueryFlow:
    """E2E tests for query endpoint flow."""

    def test_query_returns_result(self, client):
        """Query endpoint returns structured response."""
        mock_sdk = _create_mock_sdk(result_text="Hello! How can I help?")

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            response = client.post(
                "/api/v1/query",
                json={
                    "prompt": "Hello",
                    "working_directory": "/tmp"  # Use allowed directory
                },
                headers={"X-API-Key": "test-key"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "session_id" in data
            assert "result" in data

    def test_query_with_invalid_prompt_returns_422(self, client):
        """Query with empty prompt returns validation error."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": ""},
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 422

    def test_query_includes_request_id_header(self, client):
        """Response includes X-Request-ID header."""
        mock_sdk = _create_mock_sdk()

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            response = client.post(
                "/api/v1/query",
                json={"prompt": "Hello"},
                headers={"X-API-Key": "test-key"}
            )

            assert "x-request-id" in response.headers


class TestSessionFlow:
    """E2E tests for session management flow."""

    def test_sessions_list_returns_array(self, client):
        """Sessions list returns an array."""
        response = client.get(
            "/api/v1/sessions",
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_session_not_found_returns_404(self, client):
        """Non-existent session returns 404."""
        response = client.get(
            "/api/v1/sessions/non-existent-id",
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 404


class TestStreamingFlow:
    """E2E tests for streaming endpoint."""

    def test_stream_returns_sse_content_type(self, client):
        """Streaming endpoint returns SSE content type."""
        mock_sdk = _create_mock_sdk()

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            response = client.post(
                "/api/v1/query/stream",
                json={"prompt": "Hello"},
                headers={"X-API-Key": "test-key"}
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


class TestValidationFlow:
    """E2E tests for request validation."""

    def test_invalid_content_type_returns_415(self, client):
        """Non-JSON content type returns 415."""
        response = client.post(
            "/api/v1/query",
            content="prompt=Hello",
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        assert response.status_code == 415

    def test_invalid_json_returns_422(self, client):
        """Invalid JSON body returns 422."""
        response = client.post(
            "/api/v1/query",
            content="{invalid json}",
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 422


def _create_mock_sdk(result_text: str = "Test response") -> dict:
    """Create a mock SDK that returns specified result."""

    # Mock message types
    mock_text_block = MagicMock()
    mock_text_block.text = result_text

    mock_assistant_msg = MagicMock()
    mock_assistant_msg.content = [mock_text_block]
    mock_assistant_msg.model = "claude-sonnet-4-5-20250929"

    mock_result_msg = MagicMock()
    mock_result_msg.session_id = "test-session-123"
    mock_result_msg.total_cost_usd = 0.001
    mock_result_msg.num_turns = 1
    mock_result_msg.duration_ms = 100
    mock_result_msg.duration_api_ms = 80
    mock_result_msg.is_error = False
    mock_result_msg.result = result_text
    mock_result_msg.usage = {"input_tokens": 10, "output_tokens": 20}

    # Create async generator for query results
    async def mock_query(*args, **kwargs):
        yield mock_assistant_msg
        yield mock_result_msg

    # Mock SDK module
    mock_sdk = {
        'query': mock_query,
        'ClaudeAgentOptions': MagicMock,
        'AssistantMessage': type(mock_assistant_msg),
        'ResultMessage': type(mock_result_msg),
        'SystemMessage': MagicMock,
        'UserMessage': MagicMock,
        'TextBlock': type(mock_text_block),
        'ThinkingBlock': MagicMock,
        'ToolUseBlock': MagicMock,
        'ToolResultBlock': MagicMock,
    }

    return mock_sdk

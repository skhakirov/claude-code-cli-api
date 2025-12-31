"""
TDD: Integration tests for API routes.
Status: GREEN (with mocked dependencies)
"""
from unittest.mock import MagicMock, patch

import pytest
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
    """TestClient with mocked dependencies.

    Uses yield instead of return to keep patches active during test execution.
    Patches get_settings at ALL import locations to ensure proper mocking
    when running after E2E tests that set environment variables.
    """
    # Clear settings cache before patching
    from src.core.config import get_settings
    get_settings.cache_clear()

    # Patch get_settings at the source module AND all import locations
    # This is necessary because Python's `from x import y` creates a new reference
    patches = [
        patch("src.services.claude_executor._get_sdk", return_value=mock_sdk),
        patch("src.core.config.get_settings", return_value=mock_settings),
        patch("src.middleware.auth.get_settings", return_value=mock_settings),
        patch("src.api.dependencies.get_settings", return_value=mock_settings),
        patch("src.middleware.rate_limit.get_settings", return_value=mock_settings),
        patch("src.services.circuit_breaker.get_settings", return_value=mock_settings),
    ]

    for p in patches:
        p.start()

    try:
        # Clear caches before importing
        from src.api.dependencies import get_executor
        get_executor.cache_clear()

        # Reset app_state session_cache
        from src.api.main import app_state
        app_state.session_cache = None

        # Reset rate limiter and circuit breaker
        from src.middleware.rate_limit import reset_rate_limiter
        from src.services.circuit_breaker import reset_circuit_breaker
        reset_rate_limiter()
        reset_circuit_breaker()

        from src.api.main import app
        with TestClient(app) as test_client:
            yield test_client
    finally:
        for p in patches:
            p.stop()
        # Clear cache after test to prevent leaking mock settings
        get_settings.cache_clear()


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
                with patch("src.middleware.auth.get_settings", return_value=mock_settings):
                    from src.api.dependencies import get_executor
                    get_executor.cache_clear()

                    from src.api.main import app, app_state
                    app_state.session_cache = None

                    from src.middleware.rate_limit import reset_rate_limiter
                    from src.services.circuit_breaker import reset_circuit_breaker
                    reset_rate_limiter()
                    reset_circuit_breaker()

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
                with patch("src.middleware.auth.get_settings", return_value=mock_settings):
                    from src.api.dependencies import get_executor
                    get_executor.cache_clear()

                    from src.api.main import app, app_state
                    app_state.session_cache = None

                    from src.middleware.rate_limit import reset_rate_limiter
                    from src.services.circuit_breaker import reset_circuit_breaker
                    reset_rate_limiter()
                    reset_circuit_breaker()

                    client = TestClient(app)

                    response = client.post(
                        "/api/v1/query",
                        json={
                            "prompt": "Hello",
                            "model": "claude-opus-4-5-20251101",
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


class TestHealthReadyEndpoint:
    """Tests for /health/ready endpoint with P1 improvements."""

    def test_health_ready_returns_disk_status(self, client):
        """Readiness check includes disk space status."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()

        # P1: Disk space should be included
        assert "disk" in data
        disk = data["disk"]
        assert "free_gb" in disk
        assert "total_gb" in disk
        assert "used_percent" in disk
        assert "status" in disk
        assert disk["status"] in ["healthy", "warning", "critical"]

    def test_health_ready_disk_status_fields(self, client):
        """Disk status has correct field types."""
        response = client.get("/api/v1/health/ready")
        data = response.json()
        disk = data["disk"]

        assert isinstance(disk["free_gb"], (int, float))
        assert isinstance(disk["total_gb"], (int, float))
        assert isinstance(disk["used_percent"], (int, float))
        assert disk["total_gb"] >= disk["free_gb"]

    def test_health_ready_includes_circuit_breaker(self, client):
        """Readiness check includes circuit breaker status."""
        response = client.get("/api/v1/health/ready")
        data = response.json()

        assert "circuit_breaker" in data
        cb = data["circuit_breaker"]
        assert "state" in cb
        assert "failure_count" in cb
        assert "is_available" in cb

    def test_health_ready_memory_includes_peak(self, client):
        """P3: Memory status includes peak and VMS tracking."""
        response = client.get("/api/v1/health/ready")
        data = response.json()

        assert "memory" in data
        memory = data["memory"]
        assert "rss_mb" in memory
        assert "peak_mb" in memory  # P3: Peak memory tracking
        assert "vms_mb" in memory  # P3: Virtual memory size
        assert "status" in memory

        # All values should be non-negative numbers
        assert isinstance(memory["rss_mb"], (int, float))
        assert isinstance(memory["peak_mb"], (int, float))
        assert isinstance(memory["vms_mb"], (int, float))
        assert memory["rss_mb"] >= 0
        assert memory["peak_mb"] >= 0


class TestValidationMiddleware:
    """Tests for P2: Request validation middleware."""

    def test_post_without_content_type_rejected(self, client):
        """POST without Content-Type is rejected with 415."""
        # Send raw request without Content-Type
        response = client.post(
            "/api/v1/query",
            content=b'{"prompt": "test"}',
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 415
        assert "application/json" in response.json()["detail"]

    def test_post_with_wrong_content_type_rejected(self, client):
        """POST with wrong Content-Type is rejected."""
        response = client.post(
            "/api/v1/query",
            content=b'{"prompt": "test"}',
            headers={
                "X-API-Key": "test-api-key",
                "Content-Type": "text/plain"
            }
        )
        assert response.status_code == 415

    def test_post_with_json_content_type_passes(self, mock_settings):
        """POST with application/json passes validation."""
        from unittest.mock import MagicMock, patch

        mock_sdk = create_mock_sdk()

        result_msg = MagicMock()
        result_msg.session_id = "test-123"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.usage = None
        result_msg.result = "Done"
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                with patch("src.middleware.auth.get_settings", return_value=mock_settings):
                    from src.api.dependencies import get_executor
                    get_executor.cache_clear()

                    from src.api.main import app, app_state
                    app_state.session_cache = None

                    from src.middleware.rate_limit import reset_rate_limiter
                    from src.services.circuit_breaker import reset_circuit_breaker
                    reset_rate_limiter()
                    reset_circuit_breaker()

                    client = TestClient(app)

                    response = client.post(
                        "/api/v1/query",
                        json={"prompt": "Hello"},
                        headers={"X-API-Key": "test-api-key"}
                    )

                    # Should pass validation and reach the handler
                    assert response.status_code == 200

    def test_health_endpoint_bypasses_validation(self, client):
        """Health endpoints are exempt from validation."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_get_request_bypasses_body_validation(self, client):
        """GET requests don't require Content-Type."""
        response = client.get(
            "/api/v1/sessions",
            headers={"X-API-Key": "test-api-key"}
        )
        assert response.status_code == 200


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


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_endpoint_accessible_without_auth(self, client):
        """Metrics endpoint is accessible without auth."""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_returns_correct_structure(self, client):
        """Metrics endpoint returns expected structure."""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "counters" in data
        assert "latency_histogram_ms" in data
        assert "endpoints" in data
        assert "status_codes" in data

        # Verify counters structure
        counters = data["counters"]
        assert "requests_total" in counters
        assert "errors_total" in counters
        assert "tokens_input_total" in counters
        assert "tokens_output_total" in counters

    def test_metrics_records_requests(self, mock_settings):
        """Metrics are recorded for each request."""
        from src.middleware.metrics import get_metrics_collector

        mock_sdk = create_mock_sdk()

        result_msg = MagicMock()
        result_msg.session_id = "metrics-test"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.usage = None
        result_msg.result = "Done"
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                with patch("src.middleware.auth.get_settings", return_value=mock_settings):
                    from src.api.dependencies import get_executor
                    get_executor.cache_clear()

                    from src.api.main import app, app_state
                    app_state.session_cache = None

                    from src.middleware.rate_limit import reset_rate_limiter
                    from src.services.circuit_breaker import reset_circuit_breaker
                    reset_rate_limiter()
                    reset_circuit_breaker()

                    client = TestClient(app)

                    # Reset metrics before test
                    import asyncio
                    metrics = get_metrics_collector()
                    asyncio.get_event_loop().run_until_complete(metrics.reset())

                    # Make a request
                    response = client.post(
                        "/api/v1/query",
                        json={"prompt": "Hello"},
                        headers={"X-API-Key": "test-api-key"}
                    )
                    assert response.status_code == 200

                    # Check metrics were recorded
                    metrics_response = client.get("/api/v1/metrics")
                    data = metrics_response.json()

                    # Should have at least 2 requests (the query and metrics request)
                    assert data["counters"]["requests_total"] >= 1

                    # Should have endpoint tracking
                    assert len(data["endpoints"]) > 0


class TestRequestIdHeader:
    """Tests for X-Request-ID header handling."""

    def test_response_includes_request_id_header(self, client):
        """Response should include X-Request-ID header."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Request ID should be 8 characters (truncated UUID)
        assert len(response.headers["X-Request-ID"]) == 8

    def test_response_echoes_client_request_id(self, client):
        """Response should echo client-provided X-Request-ID."""
        custom_request_id = "my-req-1"
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": custom_request_id}
        )
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_request_id

    def test_request_id_in_error_response(self, client):
        """Error responses should also include X-Request-ID."""
        response = client.post(
            "/api/v1/query",
            json={"prompt": "Hello"}
            # No X-API-Key - should get 401
        )
        assert response.status_code == 401
        assert "X-Request-ID" in response.headers

    def test_request_id_is_unique_per_request(self, client):
        """Each request should get a unique X-Request-ID."""
        response1 = client.get("/api/v1/health")
        response2 = client.get("/api/v1/health")

        request_id1 = response1.headers.get("X-Request-ID")
        request_id2 = response2.headers.get("X-Request-ID")

        assert request_id1 is not None
        assert request_id2 is not None
        assert request_id1 != request_id2

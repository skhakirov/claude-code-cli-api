"""
Tests for P3: Alerting service.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestAlertingService:
    """Tests for AlertingService."""

    def test_alerting_disabled_when_no_url(self):
        """Alerting is disabled when webhook URL is empty."""
        from src.services.alerting import AlertingService

        service = AlertingService(webhook_url=None)
        assert service.is_enabled is False

        service_empty = AlertingService(webhook_url="")
        assert service_empty.is_enabled is False

    def test_alerting_enabled_when_url_set(self):
        """Alerting is enabled when webhook URL is set."""
        from src.services.alerting import AlertingService

        service = AlertingService(webhook_url="https://example.com/webhook")
        assert service.is_enabled is True

    @pytest.mark.asyncio
    async def test_send_alert_returns_false_when_disabled(self):
        """Send alert returns False when disabled."""
        from src.services.alerting import AlertingService

        service = AlertingService(webhook_url=None)

        result = await service.send_alert(
            alert_type="test",
            title="Test Alert",
            message="This is a test"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_rate_limiting(self):
        """Rate limiting prevents duplicate alerts."""
        from src.services.alerting import AlertingService
        import httpx

        service = AlertingService(
            webhook_url="https://example.com/webhook",
            min_interval_seconds=60.0  # 1 minute rate limit
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # First alert should succeed
            result1 = await service.send_alert(
                alert_type="test_rate_limit",
                title="Test",
                message="First"
            )
            assert result1 is True
            assert mock_post.call_count == 1

            # Second alert of same type should be rate limited
            result2 = await service.send_alert(
                alert_type="test_rate_limit",
                title="Test",
                message="Second"
            )
            assert result2 is False
            assert mock_post.call_count == 1  # Not called again

            # Different alert type should succeed
            result3 = await service.send_alert(
                alert_type="different_type",
                title="Test",
                message="Third"
            )
            assert result3 is True
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_alert_force_bypasses_rate_limit(self):
        """Force flag bypasses rate limiting."""
        from src.services.alerting import AlertingService
        import httpx

        service = AlertingService(
            webhook_url="https://example.com/webhook",
            min_interval_seconds=60.0
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # First alert
            await service.send_alert(
                alert_type="test_force",
                title="Test",
                message="First"
            )

            # Second with force=True should bypass rate limit
            result = await service.send_alert(
                alert_type="test_force",
                title="Test",
                message="Second",
                force=True
            )
            assert result is True
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_alert_includes_exception(self):
        """Alert includes exception details when provided."""
        from src.services.alerting import AlertingService
        import httpx
        import json

        service = AlertingService(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 200
        captured_payload = None

        async def capture_post(url, json, **kwargs):
            nonlocal captured_payload
            captured_payload = json
            return mock_response

        with patch.object(httpx.AsyncClient, "post", side_effect=capture_post):
            try:
                raise ValueError("test error")
            except ValueError as e:
                await service.send_alert(
                    alert_type="error_test",
                    title="Error",
                    message="An error occurred",
                    error=e,
                    force=True
                )

        assert captured_payload is not None
        assert "exception" in captured_payload
        assert captured_payload["exception"]["type"] == "ValueError"
        assert captured_payload["exception"]["message"] == "test error"

    @pytest.mark.asyncio
    async def test_alert_critical_error_convenience_method(self):
        """alert_critical_error sends proper alert."""
        from src.services.alerting import AlertingService
        import httpx

        service = AlertingService(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            try:
                raise RuntimeError("critical failure")
            except RuntimeError as e:
                result = await service.alert_critical_error(
                    error=e,
                    context_description="Processing request",
                    request_id="req-123"
                )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_handles_timeout(self):
        """Alert handles HTTP timeout gracefully."""
        from src.services.alerting import AlertingService
        import httpx

        service = AlertingService(
            webhook_url="https://example.com/webhook",
            timeout=0.1
        )

        with patch.object(
            httpx.AsyncClient, "post",
            side_effect=httpx.TimeoutException("timeout")
        ):
            result = await service.send_alert(
                alert_type="timeout_test",
                title="Test",
                message="Test",
                force=True
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_handles_http_error(self):
        """Alert handles HTTP error response gracefully."""
        from src.services.alerting import AlertingService
        import httpx

        service = AlertingService(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await service.send_alert(
                alert_type="error_test",
                title="Test",
                message="Test",
                force=True
            )

        assert result is False


class TestGlobalAlertingService:
    """Tests for global alerting service functions."""

    def test_get_alerting_service_returns_singleton(self):
        """get_alerting_service returns the same instance."""
        from src.services.alerting import get_alerting_service, reset_alerting_service

        reset_alerting_service()

        with patch("src.services.alerting.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                alert_webhook_url="",
                alert_webhook_timeout=5.0
            )

            service1 = get_alerting_service()
            service2 = get_alerting_service()

            assert service1 is service2

        reset_alerting_service()

    def test_reset_alerting_service(self):
        """reset_alerting_service clears the singleton."""
        from src.services.alerting import get_alerting_service, reset_alerting_service

        with patch("src.services.alerting.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                alert_webhook_url="",
                alert_webhook_timeout=5.0
            )

            service1 = get_alerting_service()
            reset_alerting_service()
            service2 = get_alerting_service()

            assert service1 is not service2

        reset_alerting_service()

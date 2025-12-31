"""
Tests for P3: Alerting service.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
        import httpx

        from src.services.alerting import AlertingService

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
        import httpx

        from src.services.alerting import AlertingService

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

        import httpx

        from src.services.alerting import AlertingService

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
        import httpx

        from src.services.alerting import AlertingService

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
        import httpx

        from src.services.alerting import AlertingService

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
        import httpx

        from src.services.alerting import AlertingService

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


class TestAlertingServiceP2Improvements:
    """Tests for P2 improvements: thread-safety and cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_entries(self):
        """Cleanup removes entries older than threshold."""
        from datetime import datetime, timezone

        import httpx

        from src.services.alerting import (
            _CLEANUP_THRESHOLD_SECONDS,
            _MAX_LAST_ALERTS_SIZE,
            AlertingService,
        )

        service = AlertingService(
            webhook_url="https://example.com/webhook",
            min_interval_seconds=0.001  # Very short interval for testing
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        # Manually populate _last_alerts with old entries to trigger cleanup
        now = datetime.now(timezone.utc).timestamp()
        old_timestamp = now - _CLEANUP_THRESHOLD_SECONDS - 100  # Older than threshold

        # Add many old entries to exceed max size
        for i in range(_MAX_LAST_ALERTS_SIZE + 10):
            service._last_alerts[f"old_alert_{i}"] = old_timestamp

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # This should trigger cleanup
            await service.send_alert(
                alert_type="new_alert",
                title="Test",
                message="Test"
            )

        # Old entries should be cleaned up
        assert len(service._last_alerts) < _MAX_LAST_ALERTS_SIZE
        # New alert should be present
        assert "new_alert" in service._last_alerts

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_entries(self):
        """Cleanup keeps entries newer than threshold."""
        from datetime import datetime, timezone

        import httpx

        from src.services.alerting import (
            _CLEANUP_THRESHOLD_SECONDS,
            _MAX_LAST_ALERTS_SIZE,
            AlertingService,
        )

        service = AlertingService(
            webhook_url="https://example.com/webhook",
            min_interval_seconds=0.001
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        now = datetime.now(timezone.utc).timestamp()

        # Add recent entries (within threshold)
        for i in range(100):
            service._last_alerts[f"recent_alert_{i}"] = now - 60  # 1 minute old

        # Add old entries to exceed max size
        old_timestamp = now - _CLEANUP_THRESHOLD_SECONDS - 100
        for i in range(_MAX_LAST_ALERTS_SIZE + 10):
            service._last_alerts[f"old_alert_{i}"] = old_timestamp

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await service.send_alert(
                alert_type="trigger_cleanup",
                title="Test",
                message="Test"
            )

        # Recent entries should still be there
        recent_count = sum(1 for k in service._last_alerts if k.startswith("recent_alert_"))
        assert recent_count == 100

    def test_thread_safe_initialization(self):
        """get_alerting_service is thread-safe with concurrent access."""
        import concurrent.futures

        from src.services.alerting import get_alerting_service, reset_alerting_service

        reset_alerting_service()

        with patch("src.services.alerting.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                alert_webhook_url="https://example.com/webhook",
                alert_webhook_timeout=5.0
            )

            services = []

            def get_service():
                return get_alerting_service()

            # Call from multiple threads simultaneously
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(get_service) for _ in range(100)]
                for future in concurrent.futures.as_completed(futures):
                    services.append(future.result())

            # All should be the same instance
            assert len(services) == 100
            first_service = services[0]
            for service in services:
                assert service is first_service

        reset_alerting_service()

    def test_reset_is_thread_safe(self):
        """reset_alerting_service is thread-safe."""
        import concurrent.futures

        from src.services.alerting import get_alerting_service, reset_alerting_service

        with patch("src.services.alerting.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                alert_webhook_url="",
                alert_webhook_timeout=5.0
            )

            def reset_and_get():
                reset_alerting_service()
                return get_alerting_service()

            # This should not raise any errors
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(reset_and_get) for _ in range(20)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            assert len(results) == 20

        reset_alerting_service()

"""Alerting service for critical error notifications."""
import asyncio
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from ..core.config import get_settings
from ..core.logging import format_exception_chain, get_logger

logger = get_logger(__name__)

# Max entries in _last_alerts before cleanup is triggered
_MAX_LAST_ALERTS_SIZE = 1000
# Remove entries older than this many seconds during cleanup
_CLEANUP_THRESHOLD_SECONDS = 3600  # 1 hour


class AlertingService:
    """
    Service for sending critical alerts via webhook.

    Supports:
    - Async webhook delivery
    - Rate limiting to prevent alert storms
    - Configurable timeout
    - Graceful failure handling
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        timeout: float = 5.0,
        min_interval_seconds: float = 60.0  # Rate limit: max 1 alert per minute per type
    ):
        """
        Initialize alerting service.

        Args:
            webhook_url: URL to POST alerts to (None = disabled)
            timeout: HTTP request timeout in seconds
            min_interval_seconds: Minimum interval between alerts of same type
        """
        self._webhook_url = webhook_url
        self._timeout = timeout
        self._min_interval = min_interval_seconds
        self._last_alerts: Dict[str, float] = {}  # alert_type -> timestamp
        self._lock = asyncio.Lock()

    @property
    def is_enabled(self) -> bool:
        """Check if alerting is enabled."""
        return bool(self._webhook_url)

    async def _cleanup_old_alerts(self) -> None:
        """Remove old entries from _last_alerts to prevent memory leak.

        Called when _last_alerts exceeds MAX size. Removes entries older
        than _CLEANUP_THRESHOLD_SECONDS. Must be called with _lock held.
        """
        if len(self._last_alerts) < _MAX_LAST_ALERTS_SIZE:
            return

        now = datetime.now(timezone.utc).timestamp()
        old_keys = [
            key for key, timestamp in self._last_alerts.items()
            if now - timestamp > _CLEANUP_THRESHOLD_SECONDS
        ]

        for key in old_keys:
            del self._last_alerts[key]

        if old_keys:
            logger.debug(
                "alerting_cleanup_performed",
                removed_count=len(old_keys),
                remaining_count=len(self._last_alerts)
            )

    async def send_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        severity: str = "critical",
        error: Optional[BaseException] = None,
        context: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> bool:
        """
        Send an alert via webhook.

        Args:
            alert_type: Type of alert for rate limiting (e.g., "circuit_breaker_open")
            title: Short alert title
            message: Detailed alert message
            severity: Alert severity (critical, warning, info)
            error: Optional exception to include traceback
            context: Additional context fields
            force: Bypass rate limiting

        Returns:
            True if alert was sent, False if disabled, rate limited, or failed
        """
        if not self.is_enabled:
            return False

        # Rate limiting check
        if not force:
            async with self._lock:
                now = datetime.now(timezone.utc).timestamp()
                last_alert = self._last_alerts.get(alert_type, 0)

                if now - last_alert < self._min_interval:
                    logger.debug(
                        "alert_rate_limited",
                        alert_type=alert_type,
                        seconds_since_last=now - last_alert,
                        min_interval=self._min_interval
                    )
                    return False

                self._last_alerts[alert_type] = now

                # Periodic cleanup to prevent memory leak
                await self._cleanup_old_alerts()

        # Build payload
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_type": alert_type,
            "title": title,
            "message": message,
            "severity": severity,
            "service": "claude-code-api",
        }

        if error:
            payload["exception"] = {
                "type": type(error).__name__,
                "message": str(error),
                "chain": format_exception_chain(error),
            }

        if context:
            payload["context"] = context

        # Send webhook (webhook_url guaranteed by is_enabled check)
        webhook_url = self._webhook_url
        if not webhook_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code >= 400:
                    logger.warning(
                        "alert_webhook_error_response",
                        status_code=response.status_code,
                        alert_type=alert_type
                    )
                    return False

                logger.info(
                    "alert_sent",
                    alert_type=alert_type,
                    severity=severity,
                    status_code=response.status_code
                )
                return True

        except httpx.TimeoutException:
            logger.warning(
                "alert_webhook_timeout",
                alert_type=alert_type,
                timeout=self._timeout
            )
            return False

        except Exception as e:
            logger.warning(
                "alert_webhook_failed",
                alert_type=alert_type,
                error=str(e),
                error_type=type(e).__name__
            )
            return False

    async def alert_critical_error(
        self,
        error: BaseException,
        context_description: str,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Convenience method for critical error alerts.

        Args:
            error: The exception that occurred
            context_description: What was happening when error occurred
            request_id: Optional request correlation ID

        Returns:
            True if alert was sent
        """
        return await self.send_alert(
            alert_type=f"critical_error_{type(error).__name__}",
            title=f"Critical Error: {type(error).__name__}",
            message=f"{context_description}: {str(error)}",
            severity="critical",
            error=error,
            context={"request_id": request_id} if request_id else None
        )

    async def alert_circuit_breaker(
        self,
        state: str,
        failure_count: int,
        error_types: Optional[Dict[str, int]] = None
    ) -> bool:
        """
        Alert on circuit breaker state changes.

        Args:
            state: New circuit breaker state
            failure_count: Current failure count
            error_types: Breakdown of error types

        Returns:
            True if alert was sent
        """
        return await self.send_alert(
            alert_type="circuit_breaker_state_change",
            title=f"Circuit Breaker {state.upper()}",
            message=f"Circuit breaker transitioned to {state}. Failure count: {failure_count}",
            severity="critical" if state == "open" else "warning",
            context={
                "state": state,
                "failure_count": failure_count,
                "error_types": error_types or {}
            }
        )


# Global alerting service instance with thread-safe initialization
_alerting_service: Optional[AlertingService] = None
_alerting_service_lock = threading.Lock()


def get_alerting_service() -> AlertingService:
    """Get or create the global alerting service (thread-safe).

    Uses double-check locking pattern to ensure only one instance
    is created even with concurrent first calls.
    """
    global _alerting_service
    if _alerting_service is None:
        with _alerting_service_lock:
            # Double-check locking pattern
            if _alerting_service is None:
                settings = get_settings()
                _alerting_service = AlertingService(
                    webhook_url=settings.alert_webhook_url or None,
                    timeout=settings.alert_webhook_timeout
                )
                logger.info(
                    "alerting_service_initialized",
                    enabled=bool(settings.alert_webhook_url),
                    timeout=settings.alert_webhook_timeout
                )
    return _alerting_service


def reset_alerting_service() -> None:
    """Reset the global alerting service (for testing)."""
    global _alerting_service
    with _alerting_service_lock:
        _alerting_service = None

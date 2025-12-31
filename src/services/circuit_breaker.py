"""Circuit breaker pattern for SDK calls."""
import asyncio
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable, Awaitable

from ..core.logging import get_logger
from ..core.config import get_settings

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


# Error type weights for weighted failure recording
# Timeouts are less critical, process errors are more critical
ERROR_WEIGHTS: Dict[str, float] = {
    "timeout": 0.5,      # Timeouts may be transient
    "connection": 1.0,   # Connection errors are standard
    "process": 1.5,      # Process errors indicate real problems
    "unknown": 1.0,      # Default weight
}


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Weighted failures to open circuit
    success_threshold: int = 2      # Successes to close circuit
    timeout_seconds: float = 30.0   # Time before half-open
    half_open_max_calls: int = 3    # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading SDK failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: After threshold failures, block all requests
    - HALF_OPEN: After timeout, allow limited requests to test recovery

    Thread-safe implementation using asyncio.Lock.
    """

    # Type alias for state change callback
    StateChangeCallback = Callable[
        [str, int, Dict[str, int]],  # state, failure_count, error_types
        Awaitable[None]
    ]

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._weighted_failure_count: float = 0.0  # Weighted failure tracking
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._error_types: Dict[str, int] = {}  # Track error types for analysis
        self._lock = asyncio.Lock()
        self._state_change_callback: Optional[CircuitBreaker.StateChangeCallback] = None

    def set_state_change_callback(
        self,
        callback: Optional["CircuitBreaker.StateChangeCallback"]
    ) -> None:
        """Set callback for state changes (used for alerting).

        Args:
            callback: Async function called with (state, failure_count, error_types)
                     when circuit breaker changes state.
        """
        self._state_change_callback = callback

    async def _notify_state_change(self, new_state: str) -> None:
        """Notify callback of state change (fire and forget, errors logged)."""
        if self._state_change_callback is None:
            return

        try:
            await self._state_change_callback(
                new_state,
                self._failure_count,
                dict(self._error_types)
            )
        except Exception as e:
            logger.warning(
                "circuit_breaker_callback_error",
                state=new_state,
                error=str(e),
                error_type=type(e).__name__
            )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    def is_available(self) -> bool:
        """Check if circuit allows requests (non-blocking, for monitoring only).

        Note: This is a racy check for monitoring/health endpoints.
        Use acquire() for actual request gating.
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.timeout_seconds:
                    return True  # Will transition to half-open
            return False

        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls

        return False

    async def is_available_async(self) -> bool:
        """Check if circuit allows requests (async-safe, locked).

        Use this for accurate state checks that need consistency.
        For request gating, use acquire() instead.
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.timeout_seconds:
                        return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.config.half_open_max_calls

            return False

    async def acquire(self) -> bool:
        """
        Try to acquire permission for a request.

        Returns:
            True if request is allowed, False if circuit is open
        """
        state_changed_to: Optional[str] = None
        result = False

        async with self._lock:
            if self._state == CircuitState.CLOSED:
                result = True
            elif self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        self._success_count = 0
                        state_changed_to = CircuitState.HALF_OPEN.value
                        logger.info(
                            "circuit_breaker_half_open",
                            elapsed_seconds=elapsed
                        )
                        self._half_open_calls += 1
                        result = True
            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    result = True

        # Notify callback outside of lock
        if state_changed_to:
            await self._notify_state_change(state_changed_to)

        return result

    async def record_success(self) -> None:
        """Record a successful call."""
        state_changed_to: Optional[str] = None

        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._weighted_failure_count = 0.0
                    self._success_count = 0
                    self._half_open_calls = 0
                    self._error_types = {}
                    state_changed_to = CircuitState.CLOSED.value
                    logger.info("circuit_breaker_closed", reason="success_threshold")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
                self._weighted_failure_count = 0.0
                self._error_types = {}

        # Notify callback outside of lock
        if state_changed_to:
            await self._notify_state_change(state_changed_to)

    async def record_failure(self, error_type: str = "unknown") -> None:
        """Record a failed call with error type weighting.

        Args:
            error_type: Type of error for weighted counting.
                       Values: "timeout", "connection", "process", "unknown"
        """
        state_changed_to: Optional[str] = None

        async with self._lock:
            # Get weight for error type
            weight = ERROR_WEIGHTS.get(error_type, ERROR_WEIGHTS["unknown"])

            self._failure_count += 1
            self._weighted_failure_count += weight
            self._last_failure_time = time.time()

            # Track error types for analysis
            self._error_types[error_type] = self._error_types.get(error_type, 0) + 1

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._state = CircuitState.OPEN
                self._success_count = 0
                state_changed_to = CircuitState.OPEN.value
                logger.warning(
                    "circuit_breaker_reopened",
                    failure_count=self._failure_count,
                    weighted_count=self._weighted_failure_count,
                    error_type=error_type
                )
            elif self._state == CircuitState.CLOSED:
                # Use weighted count for threshold comparison
                if self._weighted_failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    state_changed_to = CircuitState.OPEN.value
                    logger.warning(
                        "circuit_breaker_opened",
                        failure_count=self._failure_count,
                        weighted_count=self._weighted_failure_count,
                        threshold=self.config.failure_threshold,
                        error_types=self._error_types
                    )

        # Notify callback outside of lock to avoid blocking
        if state_changed_to:
            await self._notify_state_change(state_changed_to)

    async def reset(self) -> None:
        """Reset circuit breaker to closed state (for testing)."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._weighted_failure_count = 0.0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            self._error_types = {}

    def get_status(self) -> dict:
        """Get circuit breaker status for health checks."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "weighted_failure_count": self._weighted_failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "error_types": dict(self._error_types),  # Copy for safety
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            }
        }


# Global circuit breaker for SDK calls with thread-safe initialization
_circuit_breaker: Optional[CircuitBreaker] = None
_circuit_breaker_lock = threading.Lock()


async def _alerting_callback(
    state: str,
    failure_count: int,
    error_types: Dict[str, int]
) -> None:
    """Callback for circuit breaker state changes to send alerts."""
    from .alerting import get_alerting_service

    alerting = get_alerting_service()
    if not alerting.is_enabled:
        return

    # Only alert on OPEN state (critical) or recovery to CLOSED (info)
    if state == CircuitState.OPEN.value:
        await alerting.alert_circuit_breaker(
            state=state,
            failure_count=failure_count,
            error_types=error_types
        )
    elif state == CircuitState.CLOSED.value:
        await alerting.send_alert(
            alert_type="circuit_breaker_recovered",
            title="Circuit Breaker Recovered",
            message="Circuit breaker has closed after successful recovery",
            severity="info"
        )


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create the global circuit breaker (thread-safe).

    Uses configuration from settings for threshold and timeout values.
    Configures alerting callback for state changes.
    """
    global _circuit_breaker
    if _circuit_breaker is None:
        with _circuit_breaker_lock:
            # Double-check locking pattern
            if _circuit_breaker is None:
                settings = get_settings()
                config = CircuitBreakerConfig(
                    failure_threshold=settings.circuit_breaker_failure_threshold,
                    success_threshold=settings.circuit_breaker_success_threshold,
                    timeout_seconds=settings.circuit_breaker_timeout,
                )
                _circuit_breaker = CircuitBreaker(config=config)
                _circuit_breaker.set_state_change_callback(_alerting_callback)
                logger.info(
                    "circuit_breaker_initialized",
                    failure_threshold=config.failure_threshold,
                    success_threshold=config.success_threshold,
                    timeout_seconds=config.timeout_seconds,
                    alerting_enabled=bool(settings.alert_webhook_url),
                )
    return _circuit_breaker


def reset_circuit_breaker() -> None:
    """Reset the global circuit breaker (for testing)."""
    global _circuit_breaker
    with _circuit_breaker_lock:
        _circuit_breaker = None

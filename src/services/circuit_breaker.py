"""Circuit breaker pattern for SDK calls."""
import asyncio
import threading
import time
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from ..core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Failures to open circuit
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

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    def is_available(self) -> bool:
        """Check if circuit allows requests (non-blocking check)."""
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

    async def acquire(self) -> bool:
        """
        Try to acquire permission for a request.

        Returns:
            True if request is allowed, False if circuit is open
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        self._success_count = 0
                        logger.info(
                            "circuit_breaker_half_open",
                            elapsed_seconds=elapsed
                        )
                        self._half_open_calls += 1
                        return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
                    logger.info("circuit_breaker_closed", reason="success_threshold")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(
                    "circuit_breaker_reopened",
                    failure_count=self._failure_count
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "circuit_breaker_opened",
                        failure_count=self._failure_count,
                        threshold=self.config.failure_threshold
                    )

    async def reset(self) -> None:
        """Reset circuit breaker to closed state (for testing)."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None

    def get_status(self) -> dict:
        """Get circuit breaker status for health checks."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            }
        }


# Global circuit breaker for SDK calls with thread-safe initialization
_circuit_breaker: Optional[CircuitBreaker] = None
_circuit_breaker_lock = threading.Lock()


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create the global circuit breaker (thread-safe)."""
    global _circuit_breaker
    if _circuit_breaker is None:
        with _circuit_breaker_lock:
            # Double-check locking pattern
            if _circuit_breaker is None:
                _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


def reset_circuit_breaker() -> None:
    """Reset the global circuit breaker (for testing)."""
    global _circuit_breaker
    with _circuit_breaker_lock:
        _circuit_breaker = None

"""Simple rate limiting middleware using token bucket algorithm."""
import time
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float  # Maximum tokens
    rate: float  # Tokens per second
    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = self.capacity

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Returns True if tokens were consumed, False if rate limited.
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Add tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Calculate time until tokens become available."""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.rate


class RateLimiter:
    """
    Per-key rate limiter using token bucket algorithm.

    Thread-safe for use in async context.
    """

    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20
    ):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = 300  # Clean up old buckets every 5 minutes
        self._last_cleanup = time.time()

    async def is_allowed(self, key: str) -> tuple[bool, float]:
        """
        Check if request is allowed for the given key.

        Returns:
            Tuple of (allowed: bool, retry_after: float)
        """
        async with self._lock:
            # Periodic cleanup of old buckets
            now = time.time()
            if now - self._last_cleanup > self._cleanup_interval:
                await self._cleanup_old_buckets()
                self._last_cleanup = now

            # Get or create bucket for this key
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    capacity=float(self.burst_size),
                    rate=self.requests_per_second
                )

            bucket = self._buckets[key]
            allowed = bucket.consume()
            retry_after = 0.0 if allowed else bucket.time_until_available()

            return allowed, retry_after

    async def _cleanup_old_buckets(self) -> None:
        """Remove buckets that haven't been used recently."""
        now = time.time()
        stale_threshold = 600  # 10 minutes

        keys_to_remove = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_update > stale_threshold
        ]

        for key in keys_to_remove:
            del self._buckets[key]

        if keys_to_remove:
            logger.debug(
                "rate_limiter_cleanup",
                removed_keys=len(keys_to_remove)
            )

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "active_keys": len(self._buckets),
            "requests_per_second": self.requests_per_second,
            "burst_size": self.burst_size,
        }


# Global rate limiter instance with thread-safe initialization
_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter (thread-safe)."""
    global _rate_limiter
    if _rate_limiter is None:
        with _rate_limiter_lock:
            # Double-check locking pattern
            if _rate_limiter is None:
                settings = get_settings()
                # Handle mocked settings in tests - use defaults if values are not numbers
                try:
                    rps = float(settings.rate_limit_requests_per_second)
                except (TypeError, ValueError):
                    rps = 10.0
                try:
                    burst = int(settings.rate_limit_burst_size)
                except (TypeError, ValueError):
                    burst = 20

                _rate_limiter = RateLimiter(
                    requests_per_second=rps,
                    burst_size=burst
                )
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    with _rate_limiter_lock:
        _rate_limiter = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for per-API-key rate limiting.

    Extracts API key from X-API-Key header and applies token bucket rate limiting.
    """

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/api/v1/health", "/api/v1/health/ready", "/api/v1/metrics"}

    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply rate limiting to the request."""
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key", "anonymous")

        # Check rate limit
        limiter = get_rate_limiter()
        allowed, retry_after = await limiter.is_allowed(api_key)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                api_key=api_key[:8] + "..." if len(api_key) > 8 else api_key,
                path=request.url.path,
                retry_after=round(retry_after, 2)
            )

            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": round(retry_after, 2)
                },
                headers={"Retry-After": str(int(retry_after) + 1)}
            )

        return await call_next(request)

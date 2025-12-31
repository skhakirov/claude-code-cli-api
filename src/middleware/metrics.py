"""Simple metrics collection middleware without external dependencies."""
import asyncio
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class MetricsCollector:
    """Async-safe metrics collector with simple aggregations.

    Uses asyncio.Lock for non-blocking async operations.
    """

    # Counters
    request_count: int = 0
    error_count: int = 0
    tokens_input: int = 0
    tokens_output: int = 0

    # Latency buckets (ms): <100, <500, <1000, <5000, <10000, >10000
    latency_buckets: Dict[str, int] = field(default_factory=lambda: {
        "lt_100": 0,
        "lt_500": 0,
        "lt_1000": 0,
        "lt_5000": 0,
        "lt_10000": 0,
        "gt_10000": 0
    })

    # Per-endpoint counters
    endpoint_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    endpoint_errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Status code distribution
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))

    # Async lock (lazy initialized)
    _lock: Optional[asyncio.Lock] = field(default=None, repr=False)
    # Thread lock for safe asyncio.Lock initialization
    _init_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _get_lock(self) -> asyncio.Lock:
        """Get or create asyncio.Lock with thread-safe initialization."""
        if self._lock is None:
            with self._init_lock:
                # Double-check locking pattern
                if self._lock is None:
                    self._lock = asyncio.Lock()
        return self._lock

    async def record_request(
        self,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        is_error: bool = False,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """Record a request with all its metrics (async-safe)."""
        async with self._get_lock():
            self.request_count += 1
            self.endpoint_counts[endpoint] += 1
            self.status_codes[status_code] += 1

            if is_error or status_code >= 400:
                self.error_count += 1
                self.endpoint_errors[endpoint] += 1

            # Record latency bucket
            if duration_ms < 100:
                self.latency_buckets["lt_100"] += 1
            elif duration_ms < 500:
                self.latency_buckets["lt_500"] += 1
            elif duration_ms < 1000:
                self.latency_buckets["lt_1000"] += 1
            elif duration_ms < 5000:
                self.latency_buckets["lt_5000"] += 1
            elif duration_ms < 10000:
                self.latency_buckets["lt_10000"] += 1
            else:
                self.latency_buckets["gt_10000"] += 1

            # Token usage
            self.tokens_input += input_tokens
            self.tokens_output += output_tokens

    async def get_metrics(self) -> dict:
        """Get current metrics as a dict (async-safe)."""
        async with self._get_lock():
            return {
                "counters": {
                    "requests_total": self.request_count,
                    "errors_total": self.error_count,
                    "tokens_input_total": self.tokens_input,
                    "tokens_output_total": self.tokens_output,
                },
                "latency_histogram_ms": dict(self.latency_buckets),
                "endpoints": {
                    endpoint: {
                        "requests": count,
                        "errors": self.endpoint_errors.get(endpoint, 0)
                    }
                    for endpoint, count in self.endpoint_counts.items()
                },
                "status_codes": dict(self.status_codes),
            }

    async def reset(self) -> None:
        """Reset all metrics (async-safe, useful for testing)."""
        async with self._get_lock():
            self.request_count = 0
            self.error_count = 0
            self.tokens_input = 0
            self.tokens_output = 0
            self.latency_buckets = {
                "lt_100": 0,
                "lt_500": 0,
                "lt_1000": 0,
                "lt_5000": 0,
                "lt_10000": 0,
                "gt_10000": 0
            }
            self.endpoint_counts = defaultdict(int)
            self.endpoint_errors = defaultdict(int)
            self.status_codes = defaultdict(int)


# Global singleton metrics collector
metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return metrics

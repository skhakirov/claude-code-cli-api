"""Health check endpoints."""
import shutil
import sys
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from ...core.config import get_settings
from ...middleware.metrics import get_metrics_collector
from ...services.circuit_breaker import get_circuit_breaker
from ..state import app_state

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Basic health check response."""
    status: str
    version: str


class CacheStatus(BaseModel):
    """Cache status info."""
    status: str
    sessions_count: int
    max_size: int


class SDKStatus(BaseModel):
    """SDK availability status."""
    status: str
    available: bool
    version: Optional[str] = None


class MemoryStatus(BaseModel):
    """Memory usage info."""
    rss_mb: float
    status: str


class DiskStatus(BaseModel):
    """Disk space status info."""
    free_gb: float
    total_gb: float
    used_percent: float
    status: str


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status info."""
    state: str
    failure_count: int
    is_available: bool


class ReadyResponse(BaseModel):
    """Detailed readiness check response."""
    status: str
    version: str
    cache: CacheStatus
    sdk: SDKStatus
    memory: MemoryStatus
    disk: DiskStatus
    circuit_breaker: CircuitBreakerStatus
    active_tasks: int


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint - no auth required.

    Returns minimal health status for simple liveness probes.
    """
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.api_version
    )


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness_check() -> ReadyResponse:
    """Detailed readiness check - no auth required.

    Returns comprehensive health status including:
    - Cache status and session count
    - SDK availability
    - Memory usage
    - Active tasks count

    Use this for Kubernetes/Docker readiness probes.
    """
    settings = get_settings()

    # Check cache status
    cache_status = "healthy"
    sessions_count = 0
    if app_state.session_cache:
        sessions_count = len(app_state.session_cache)
        if sessions_count >= settings.session_cache_maxsize:
            cache_status = "full"

    # Check SDK availability
    sdk_available = False
    sdk_version = None
    try:
        from claude_agent_sdk import __version__ as sdk_ver
        sdk_available = True
        sdk_version = sdk_ver
    except ImportError:
        pass

    sdk_status = "healthy" if sdk_available else "unavailable"

    # Check memory usage
    try:
        import resource
        rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # On Linux, ru_maxrss is in kilobytes
        if sys.platform == "linux":
            rss_mb = rss_bytes / 1024
        else:
            # On macOS, it's in bytes
            rss_mb = rss_bytes / (1024 * 1024)
    except Exception:
        rss_mb = 0.0

    memory_status = "healthy"
    if rss_mb > 1024:  # > 1GB
        memory_status = "high"
    elif rss_mb > 2048:  # > 2GB
        memory_status = "critical"

    # Check disk space
    try:
        disk_usage = shutil.disk_usage("/")
        disk_free_gb = disk_usage.free / (1024 ** 3)
        disk_total_gb = disk_usage.total / (1024 ** 3)
        disk_used_percent = ((disk_usage.total - disk_usage.free) / disk_usage.total) * 100
    except Exception:
        disk_free_gb = 0.0
        disk_total_gb = 0.0
        disk_used_percent = 0.0

    disk_status = "healthy"
    if disk_used_percent > 90:  # > 90% used
        disk_status = "critical"
    elif disk_used_percent > 80:  # > 80% used
        disk_status = "warning"

    # Count active tasks
    active_tasks = len(app_state.active_tasks)

    # Check circuit breaker
    circuit_breaker = get_circuit_breaker()
    cb_state = circuit_breaker.state.value
    cb_available = circuit_breaker.is_available()

    # Overall status
    overall_status = "healthy"
    if sdk_status != "healthy":
        overall_status = "degraded"
    if memory_status == "critical":
        overall_status = "unhealthy"
    if disk_status == "critical":
        overall_status = "unhealthy"
    if cb_state == "open":
        overall_status = "degraded"

    return ReadyResponse(
        status=overall_status,
        version=settings.api_version,
        cache=CacheStatus(
            status=cache_status,
            sessions_count=sessions_count,
            max_size=settings.session_cache_maxsize
        ),
        sdk=SDKStatus(
            status=sdk_status,
            available=sdk_available,
            version=sdk_version
        ),
        memory=MemoryStatus(
            rss_mb=round(rss_mb, 2),
            status=memory_status
        ),
        disk=DiskStatus(
            free_gb=round(disk_free_gb, 2),
            total_gb=round(disk_total_gb, 2),
            used_percent=round(disk_used_percent, 1),
            status=disk_status
        ),
        circuit_breaker=CircuitBreakerStatus(
            state=cb_state,
            failure_count=circuit_breaker.failure_count,
            is_available=cb_available
        ),
        active_tasks=active_tasks
    )


@router.get("/metrics")
async def get_metrics_endpoint() -> dict:
    """Get application metrics - no auth required.

    Returns aggregated metrics including:
    - Request counts (total, errors)
    - Token usage (input, output)
    - Latency histogram
    - Per-endpoint statistics
    - Status code distribution

    Use for monitoring dashboards and alerting.
    """
    collector = get_metrics_collector()
    return await collector.get_metrics()

"""Request/Response logging middleware."""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.logging import get_logger, log_request, log_response, log_error
from .metrics import get_metrics_collector

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests and responses."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request with logging."""
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

        # Store request ID in state for other handlers
        request.state.request_id = request_id

        # Log incoming request
        log_request(
            logger,
            method=request.method,
            path=request.url.path,
            request_id=request_id,
            query_params=str(request.query_params) if request.query_params else None,
            client_host=request.client.host if request.client else None,
        )

        # Track timing
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log response
            log_response(
                logger,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=request_id,
            )

            # Record metrics (async)
            metrics = get_metrics_collector()
            await metrics.record_request(
                endpoint=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                is_error=response.status_code >= 400,
            )

            return response

        except Exception as e:
            # Calculate duration even on error
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log error
            log_error(
                logger,
                error=e,
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )

            # Record error metrics (async)
            metrics = get_metrics_collector()
            await metrics.record_request(
                endpoint=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                is_error=True,
            )

            # Re-raise to let FastAPI handle the error
            raise

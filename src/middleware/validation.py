"""Request validation middleware for early rejection of invalid requests."""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for early request validation.

    Performs lightweight checks before request processing:
    - Content-Type validation for POST/PUT/PATCH requests
    - Request body size limits
    - Rejects obviously invalid requests early

    This saves resources by not parsing invalid requests.
    """

    # Paths that don't require validation (health, metrics)
    EXEMPT_PATHS = {"/api/v1/health", "/api/v1/health/ready", "/api/v1/metrics"}

    # Methods that should have JSON body
    JSON_BODY_METHODS = {"POST", "PUT", "PATCH"}

    # Valid content types for JSON body
    VALID_CONTENT_TYPES = {
        "application/json",
        "application/json; charset=utf-8",
        "application/json;charset=utf-8",
        "application/json; charset=UTF-8",
        "application/json;charset=UTF-8",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate request before processing."""
        # Skip validation for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip validation for non-body methods
        if request.method not in self.JSON_BODY_METHODS:
            return await call_next(request)

        # Validate Content-Type for body methods
        content_type = request.headers.get("content-type", "").lower().strip()

        # Normalize content-type (remove extra whitespace)
        content_type_base = content_type.split(";")[0].strip()

        if content_type_base != "application/json":
            logger.warning(
                "invalid_content_type",
                content_type=content_type,
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=415,
                content={
                    "detail": "Unsupported Media Type. Expected application/json",
                    "received": content_type or "none",
                }
            )

        # Validate Content-Length if provided
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                settings = get_settings()

                # Use configured max or default (150KB should cover 100K chars + JSON overhead)
                max_body_size = getattr(settings, 'max_request_body_size', 150_000)

                if length > max_body_size:
                    logger.warning(
                        "request_body_too_large",
                        content_length=length,
                        max_size=max_body_size,
                        path=request.url.path,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Request body too large",
                            "max_size": max_body_size,
                            "received_size": length,
                        }
                    )
            except ValueError:
                # Invalid Content-Length header
                logger.warning(
                    "invalid_content_length",
                    content_length=content_length,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"}
                )

        return await call_next(request)

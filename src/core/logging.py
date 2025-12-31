"""Structured logging configuration using structlog."""
import logging
import sys
from typing import Optional

import structlog
from structlog.types import Processor

from .config import get_settings


def configure_logging(log_level: Optional[str] = None) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Override log level (default: from settings)
    """
    settings = get_settings()
    level = log_level or settings.log_level

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    # Configure structlog processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Use JSON in production, pretty console in development
    if level.upper() == "DEBUG":
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Convenience functions for common log operations
def log_request(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    request_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log an incoming request."""
    logger.info(
        "request_received",
        method=method,
        path=path,
        request_id=request_id,
        **kwargs
    )


def log_response(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log an outgoing response."""
    logger.info(
        "request_completed",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        request_id=request_id,
        **kwargs
    )


def log_error(
    logger: structlog.stdlib.BoundLogger,
    error: Exception,
    request_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log an error with stack trace."""
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        request_id=request_id,
        exc_info=True,
        **kwargs
    )


def log_sdk_call(
    logger: structlog.stdlib.BoundLogger,
    action: str,
    session_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    cost_usd: Optional[float] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    is_error: bool = False,
    **kwargs
) -> None:
    """Log an SDK call with metrics."""
    log_method = logger.error if is_error else logger.info
    log_method(
        "sdk_call",
        action=action,
        session_id=session_id,
        duration_ms=round(duration_ms, 2) if duration_ms else None,
        cost_usd=round(cost_usd, 6) if cost_usd else None,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        is_error=is_error,
        **kwargs
    )

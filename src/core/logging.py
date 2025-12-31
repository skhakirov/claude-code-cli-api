"""Structured logging configuration using structlog."""
import logging
import sys
import traceback
from typing import List, Optional

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


def format_exception_chain(exc: BaseException, max_depth: int = 10) -> List[dict]:
    """
    Format exception chain with full traceback for each exception.

    Captures the complete exception chain (__cause__, __context__)
    with cleaned stack traces.

    Args:
        exc: The exception to format
        max_depth: Maximum chain depth to prevent infinite loops

    Returns:
        List of exception info dicts with type, message, and traceback
    """
    chain: list[dict[str, str]] = []
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    depth = 0

    while current is not None and depth < max_depth:
        exc_id = id(current)
        if exc_id in seen:
            break
        seen.add(exc_id)

        # Format traceback
        tb_lines = traceback.format_exception(
            type(current), current, current.__traceback__
        )
        tb_str = "".join(tb_lines)

        chain.append({
            "type": type(current).__name__,
            "message": str(current),
            "traceback": tb_str,
            "module": type(current).__module__,
        })

        # Follow the chain
        current = current.__cause__ or current.__context__
        depth += 1

    return chain


def log_critical_error(
    logger: structlog.stdlib.BoundLogger,
    error: BaseException,
    context: str,
    request_id: Optional[str] = None,
    **kwargs
) -> None:
    """
    Log a critical error with full exception chain and context.

    Use for errors that require immediate attention (alerting).

    Args:
        logger: The logger instance
        error: The exception to log
        context: Description of what was happening when error occurred
        request_id: Optional request correlation ID
        **kwargs: Additional context fields
    """
    exception_chain = format_exception_chain(error)

    logger.critical(
        "critical_error",
        context=context,
        error_type=type(error).__name__,
        error_message=str(error),
        exception_chain=exception_chain,
        request_id=request_id,
        exc_info=True,
        **kwargs
    )


def get_simplified_traceback(exc: BaseException, max_frames: int = 10) -> List[str]:
    """
    Get simplified traceback showing only application frames.

    Filters out framework/library frames to focus on application code.

    Args:
        exc: The exception
        max_frames: Maximum frames to include

    Returns:
        List of formatted frame strings
    """
    frames: list[str] = []
    tb = exc.__traceback__

    while tb is not None and len(frames) < max_frames:
        frame = tb.tb_frame
        filename = frame.f_code.co_filename

        # Include only application frames (src/ directory)
        if "/src/" in filename or "\\src\\" in filename:
            frames.append(
                f"{filename}:{tb.tb_lineno} in {frame.f_code.co_name}"
            )

        tb = tb.tb_next

    return frames

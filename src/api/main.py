"""
FastAPI application for Claude Code CLI API.

Source: https://platform.claude.com/docs/en/agent-sdk/python
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..core.config import get_settings
from ..core.logging import configure_logging, get_logger
from ..middleware.logging import RequestLoggingMiddleware
from ..middleware.rate_limit import RateLimitMiddleware
from ..middleware.validation import RequestValidationMiddleware
from ..services.session_cache import SessionCache

# Import routes after state to avoid circular imports
from .routes import health, query, sessions

# Import app_state from state module to avoid circular imports
from .state import AppState, app_state, get_app_state

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

# Re-export for backwards compatibility
__all__ = ["app", "app_state", "get_app_state", "AppState"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with graceful shutdown."""
    # Startup
    settings = get_settings()
    logger.info(
        "application_starting",
        title=settings.api_title,
        version=settings.api_version
    )

    # Initialize session cache in app state
    # Use file-based persistence if configured
    if settings.session_persistence_path:
        app_state.session_cache = SessionCache.load_from_file(
            persistence_path=settings.session_persistence_path,
            maxsize=settings.session_cache_maxsize,
            ttl=settings.session_cache_ttl
        )
        logger.info(
            "session_cache_persistence_enabled",
            path=settings.session_persistence_path
        )
    else:
        app_state.session_cache = SessionCache(
            maxsize=settings.session_cache_maxsize,
            ttl=settings.session_cache_ttl
        )

    yield

    # Shutdown
    logger.info(
        "application_shutting_down",
        shutdown_timeout=settings.shutdown_timeout
    )

    # Signal shutdown to all components
    app_state.shutdown_event.set()

    # Wait for active tasks with configurable timeout
    cancelled = await app_state.wait_for_tasks(timeout=settings.shutdown_timeout)
    if cancelled > 0:
        logger.warning(
            "tasks_cancelled",
            cancelled_count=cancelled,
            reason="shutdown_timeout",
            timeout=settings.shutdown_timeout
        )

    # Persist session cache before clearing (if persistence enabled)
    if app_state.session_cache:
        if settings.session_persistence_path:
            persisted = await app_state.session_cache.persist_to_file()
            if not persisted:
                logger.warning("session_cache_persist_on_shutdown_failed")

        cleared = await app_state.session_cache.clear()
        logger.info("cache_cleared", sessions_cleared=cleared)

    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )

    # Add middleware (order matters - first added = outermost)
    # Order: Request -> Logging -> Validation -> RateLimit -> Handler -> ...
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestValidationMiddleware)  # P2: Early request validation
    app.add_middleware(RequestLoggingMiddleware)

    # Include routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")

    return app


app = create_app()

"""
FastAPI application for Claude Code CLI API.

Source: https://platform.claude.com/docs/en/agent-sdk/python
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Set
from fastapi import FastAPI

from ..core.config import get_settings
from ..services.session_cache import SessionCache
from .routes import health, query, sessions


# Global state for tracking active tasks and shutdown
class AppState:
    """Application state for graceful shutdown support."""

    def __init__(self):
        self.active_tasks: Set[asyncio.Task] = set()
        self._shutdown_event: asyncio.Event | None = None
        self.session_cache: SessionCache | None = None

    @property
    def shutdown_event(self) -> asyncio.Event:
        """Lazy initialization of asyncio.Event (must be created in event loop)."""
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        return self._shutdown_event

    def track_task(self, task: asyncio.Task) -> None:
        """Track an active task for graceful shutdown."""
        self.active_tasks.add(task)
        task.add_done_callback(self.active_tasks.discard)

    async def wait_for_tasks(self, timeout: float = 30.0) -> int:
        """Wait for active tasks to complete with timeout.

        Returns:
            Number of tasks that were cancelled due to timeout
        """
        if not self.active_tasks:
            return 0

        # Wait for tasks with timeout
        done, pending = await asyncio.wait(
            self.active_tasks,
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED
        )

        # Cancel remaining tasks
        cancelled = 0
        for task in pending:
            task.cancel()
            cancelled += 1

        return cancelled


# Singleton app state (created once at module load)
app_state = AppState()


def get_app_state() -> AppState:
    """Get the global app state."""
    return app_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with graceful shutdown."""
    # Startup
    settings = get_settings()
    print(f"Starting {settings.api_title} v{settings.api_version}")

    # Initialize session cache in app state
    app_state.session_cache = SessionCache(
        maxsize=settings.session_cache_maxsize,
        ttl=settings.session_cache_ttl
    )

    yield

    # Shutdown
    print("Shutting down...")

    # Signal shutdown to all components
    app_state.shutdown_event.set()

    # Wait for active tasks with timeout
    cancelled = await app_state.wait_for_tasks(timeout=30.0)
    if cancelled > 0:
        print(f"Cancelled {cancelled} active tasks due to shutdown timeout")

    # Clear session cache
    if app_state.session_cache:
        cleared = await app_state.session_cache.clear()
        print(f"Cleared {cleared} sessions from cache")

    print("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")

    return app


app = create_app()

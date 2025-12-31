"""
FastAPI application for Claude Code CLI API.

Source: https://platform.claude.com/docs/en/agent-sdk/python
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from ..core.config import get_settings
from .routes import health, query, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"Starting {settings.api_title} v{settings.api_version}")
    yield
    # Shutdown
    print("Shutting down...")


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

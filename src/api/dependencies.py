"""Dependency injection for FastAPI."""
from functools import lru_cache

from ..core.config import get_settings
from ..services.claude_executor import ClaudeExecutor
from ..services.session_cache import SessionCache


@lru_cache
def get_executor() -> ClaudeExecutor:
    """Get cached ClaudeExecutor instance."""
    return ClaudeExecutor()


def get_session_cache() -> SessionCache:
    """Get SessionCache instance from app state.

    Uses the session cache initialized during app lifespan.
    Falls back to creating a new instance if app_state cache is not available
    (e.g., during testing).
    """
    from .main import app_state

    if app_state.session_cache is not None:
        return app_state.session_cache

    # Fallback for testing or when lifespan hasn't run
    settings = get_settings()
    return SessionCache(
        maxsize=settings.session_cache_maxsize,
        ttl=settings.session_cache_ttl
    )

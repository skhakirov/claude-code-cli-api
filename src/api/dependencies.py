"""Dependency injection for FastAPI."""
from functools import lru_cache

from ..core.config import get_settings, Settings
from ..services.claude_executor import ClaudeExecutor
from ..services.session_cache import SessionCache


@lru_cache
def get_executor() -> ClaudeExecutor:
    """Get cached ClaudeExecutor instance."""
    return ClaudeExecutor()


@lru_cache
def get_session_cache() -> SessionCache:
    """Get cached SessionCache instance."""
    settings = get_settings()
    return SessionCache(
        maxsize=settings.session_cache_maxsize,
        ttl=settings.session_cache_ttl
    )

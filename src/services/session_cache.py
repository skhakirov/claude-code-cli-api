"""In-memory session cache with TTL and async-safe access."""
import asyncio
import threading
from typing import Optional, List
from datetime import datetime, timezone
from cachetools import TTLCache
from pydantic import BaseModel


class SessionMetadata(BaseModel):
    """Metadata for a session."""
    session_id: str
    created_at: datetime
    last_activity: datetime
    working_directory: str
    model: Optional[str] = None
    prompt_count: int = 0
    total_cost_usd: float = 0.0


class SessionCache:
    """Async-safe in-memory session cache with TTL.

    Uses asyncio.Lock instead of threading.Lock to avoid blocking
    the event loop in async FastAPI application.
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        Initialize session cache.

        Args:
            maxsize: Maximum number of sessions to cache
            ttl: Time-to-live in seconds
        """
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock: asyncio.Lock | None = None
        self._init_lock = threading.Lock()  # For thread-safe asyncio.Lock init

    def _get_lock(self) -> asyncio.Lock:
        """Lazy initialization of asyncio.Lock with thread-safe double-check locking."""
        if self._lock is None:
            with self._init_lock:
                # Double-check locking pattern
                if self._lock is None:
                    self._lock = asyncio.Lock()
        return self._lock

    async def save(self, session_id: str, metadata: SessionMetadata) -> None:
        """Save session metadata to cache."""
        async with self._get_lock():
            self._cache[session_id] = metadata

    async def get(self, session_id: str) -> Optional[SessionMetadata]:
        """Get session metadata from cache."""
        async with self._get_lock():
            return self._cache.get(session_id)

    async def update_activity(self, session_id: str, cost: float = 0.0) -> bool:
        """
        Update session activity timestamp and increment counters.

        Args:
            session_id: Session ID to update
            cost: Cost to add to total

        Returns:
            True if session was found and updated, False otherwise
        """
        async with self._get_lock():
            if session_id in self._cache:
                metadata = self._cache[session_id]
                metadata.last_activity = datetime.now(timezone.utc)
                metadata.prompt_count += 1
                metadata.total_cost_usd += cost
                self._cache[session_id] = metadata
                return True
            return False

    async def list_all(self) -> List[SessionMetadata]:
        """List all cached sessions."""
        async with self._get_lock():
            return list(self._cache.values())

    async def delete(self, session_id: str) -> bool:
        """
        Delete session from cache.

        Returns:
            True if session was found and deleted, False otherwise
        """
        async with self._get_lock():
            if session_id in self._cache:
                del self._cache[session_id]
                return True
            return False

    async def clear(self) -> int:
        """
        Clear all sessions from cache.

        Returns:
            Number of sessions cleared
        """
        async with self._get_lock():
            count = len(self._cache)
            self._cache.clear()
            return count

    def __len__(self) -> int:
        """Return number of cached sessions (sync, for monitoring)."""
        return len(self._cache)

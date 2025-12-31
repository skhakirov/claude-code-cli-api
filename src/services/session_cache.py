"""In-memory session cache with TTL."""
from typing import Optional, List
from datetime import datetime, timezone
from threading import Lock
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
    """Thread-safe in-memory session cache with TTL."""

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        Initialize session cache.

        Args:
            maxsize: Maximum number of sessions to cache
            ttl: Time-to-live in seconds
        """
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = Lock()

    def save(self, session_id: str, metadata: SessionMetadata) -> None:
        """Save session metadata to cache."""
        with self._lock:
            self._cache[session_id] = metadata

    def get(self, session_id: str) -> Optional[SessionMetadata]:
        """Get session metadata from cache."""
        return self._cache.get(session_id)

    def update_activity(self, session_id: str, cost: float = 0.0) -> bool:
        """
        Update session activity timestamp and increment counters.

        Args:
            session_id: Session ID to update
            cost: Cost to add to total

        Returns:
            True if session was found and updated, False otherwise
        """
        with self._lock:
            if session_id in self._cache:
                metadata = self._cache[session_id]
                metadata.last_activity = datetime.now(timezone.utc)
                metadata.prompt_count += 1
                metadata.total_cost_usd += cost
                self._cache[session_id] = metadata
                return True
            return False

    def list_all(self) -> List[SessionMetadata]:
        """List all cached sessions."""
        return list(self._cache.values())

    def delete(self, session_id: str) -> bool:
        """
        Delete session from cache.

        Returns:
            True if session was found and deleted, False otherwise
        """
        with self._lock:
            if session_id in self._cache:
                del self._cache[session_id]
                return True
            return False

    def __len__(self) -> int:
        """Return number of cached sessions."""
        return len(self._cache)

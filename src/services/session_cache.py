"""In-memory session cache with TTL and async-safe access."""
import asyncio
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from cachetools import TTLCache
from pydantic import BaseModel

from ..core.logging import get_logger

logger = get_logger(__name__)


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

    Supports optional file-based persistence for recovery after restart.
    """

    def __init__(
        self,
        maxsize: int = 1000,
        ttl: int = 3600,
        persistence_path: Optional[str] = None
    ):
        """
        Initialize session cache.

        Args:
            maxsize: Maximum number of sessions to cache
            ttl: Time-to-live in seconds
            persistence_path: Optional path for file-based persistence
        """
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock: asyncio.Lock | None = None
        self._init_lock = threading.Lock()  # For thread-safe asyncio.Lock init
        self._persistence_path = persistence_path
        self._maxsize = maxsize
        self._ttl = ttl

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

    async def persist_to_file(self) -> bool:
        """
        Persist cache contents to file for recovery after restart.

        Uses atomic write (temp file + rename) to prevent corruption.

        Returns:
            True if persistence succeeded, False otherwise
        """
        if not self._persistence_path:
            return False

        try:
            async with self._get_lock():
                # Collect all session data
                sessions_data = [
                    metadata.model_dump(mode="json")
                    for metadata in self._cache.values()
                ]

            # Write to temp file then rename (atomic operation)
            persistence_path = Path(self._persistence_path)
            persistence_path.parent.mkdir(parents=True, exist_ok=True)

            # Use same directory for temp file to ensure atomic rename works
            fd, temp_path = tempfile.mkstemp(
                dir=persistence_path.parent,
                prefix=".session_cache_",
                suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump({
                        "version": 1,
                        "sessions": sessions_data,
                        "saved_at": datetime.now(timezone.utc).isoformat(),
                    }, f, indent=2)

                # Atomic rename
                os.replace(temp_path, persistence_path)

                logger.info(
                    "session_cache_persisted",
                    path=str(persistence_path),
                    session_count=len(sessions_data)
                )
                return True

            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise e

        except Exception as e:
            logger.error(
                "session_cache_persist_failed",
                path=self._persistence_path,
                error=str(e),
                error_type=type(e).__name__
            )
            return False

    @classmethod
    def load_from_file(
        cls,
        persistence_path: str,
        maxsize: int = 1000,
        ttl: int = 3600
    ) -> "SessionCache":
        """
        Create a SessionCache and load sessions from persistence file.

        Args:
            persistence_path: Path to persistence file
            maxsize: Maximum number of sessions to cache
            ttl: Time-to-live in seconds

        Returns:
            SessionCache instance (empty if file doesn't exist or load fails)
        """
        cache = cls(maxsize=maxsize, ttl=ttl, persistence_path=persistence_path)

        if not persistence_path:
            return cache

        path = Path(persistence_path)
        if not path.exists():
            logger.debug("session_cache_file_not_found", path=persistence_path)
            return cache

        try:
            with open(path, "r") as f:
                data = json.load(f)

            version = data.get("version", 0)
            if version != 1:
                logger.warning(
                    "session_cache_version_mismatch",
                    expected=1,
                    found=version
                )
                return cache

            sessions = data.get("sessions", [])
            loaded_count = 0
            now = datetime.now(timezone.utc)

            for session_data in sessions:
                try:
                    metadata = SessionMetadata(**session_data)

                    # Skip expired sessions
                    age_seconds = (now - metadata.last_activity).total_seconds()
                    if age_seconds > ttl:
                        continue

                    cache._cache[metadata.session_id] = metadata
                    loaded_count += 1

                except Exception as e:
                    logger.warning(
                        "session_cache_load_item_failed",
                        error=str(e),
                        session_data=str(session_data)[:100]
                    )

            logger.info(
                "session_cache_loaded",
                path=persistence_path,
                loaded_count=loaded_count,
                total_in_file=len(sessions)
            )

        except json.JSONDecodeError as e:
            logger.error(
                "session_cache_load_json_error",
                path=persistence_path,
                error=str(e)
            )
        except Exception as e:
            logger.error(
                "session_cache_load_failed",
                path=persistence_path,
                error=str(e),
                error_type=type(e).__name__
            )

        return cache

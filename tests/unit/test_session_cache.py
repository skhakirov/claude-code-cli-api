"""
TDD: Session cache tests.
Status: GREEN (async methods)
"""
import pytest
from datetime import datetime, timezone


class TestSessionCache:
    """Tests for SessionCache."""

    @pytest.mark.asyncio
    async def test_cache_save_and_get(self):
        """Save and retrieve session."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache(maxsize=100, ttl=3600)
        now = datetime.now(timezone.utc)

        metadata = SessionMetadata(
            session_id="test-123",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        )

        await cache.save("test-123", metadata)
        result = await cache.get("test-123")

        assert result is not None
        assert result.session_id == "test-123"

    @pytest.mark.asyncio
    async def test_cache_get_nonexistent(self):
        """Get non-existent session returns None."""
        from src.services.session_cache import SessionCache

        cache = SessionCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_update_activity(self):
        """Update session activity."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache()
        now = datetime.now(timezone.utc)

        metadata = SessionMetadata(
            session_id="test-123",
            created_at=now,
            last_activity=now,
            working_directory="/workspace",
            prompt_count=0,
            total_cost_usd=0.0
        )

        await cache.save("test-123", metadata)
        await cache.update_activity("test-123", cost=0.005)

        result = await cache.get("test-123")
        assert result.prompt_count == 1
        assert result.total_cost_usd == 0.005

    @pytest.mark.asyncio
    async def test_cache_update_activity_nonexistent(self):
        """Update non-existent session returns False."""
        from src.services.session_cache import SessionCache

        cache = SessionCache()
        result = await cache.update_activity("nonexistent", cost=0.001)
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Delete session."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache()
        now = datetime.now(timezone.utc)

        await cache.save("test-123", SessionMetadata(
            session_id="test-123",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        ))

        assert await cache.delete("test-123") is True
        assert await cache.get("test-123") is None
        assert await cache.delete("test-123") is False

    @pytest.mark.asyncio
    async def test_cache_list_all(self):
        """List all sessions."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache()
        now = datetime.now(timezone.utc)

        for i in range(3):
            await cache.save(f"session-{i}", SessionMetadata(
                session_id=f"session-{i}",
                created_at=now,
                last_activity=now,
                working_directory="/workspace"
            ))

        all_sessions = await cache.list_all()
        assert len(all_sessions) == 3

    @pytest.mark.asyncio
    async def test_cache_maxsize(self):
        """Cache respects maxsize limit."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache(maxsize=2, ttl=3600)
        now = datetime.now(timezone.utc)

        for i in range(5):
            await cache.save(f"session-{i}", SessionMetadata(
                session_id=f"session-{i}",
                created_at=now,
                last_activity=now,
                working_directory="/workspace"
            ))

        assert len(cache) <= 2

    @pytest.mark.asyncio
    async def test_cache_len(self):
        """Cache length."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache()
        now = datetime.now(timezone.utc)

        assert len(cache) == 0

        await cache.save("test-1", SessionMetadata(
            session_id="test-1",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        ))

        assert len(cache) == 1

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Clear all sessions."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache()
        now = datetime.now(timezone.utc)

        for i in range(3):
            await cache.save(f"session-{i}", SessionMetadata(
                session_id=f"session-{i}",
                created_at=now,
                last_activity=now,
                working_directory="/workspace"
            ))

        assert len(cache) == 3
        cleared = await cache.clear()
        assert cleared == 3
        assert len(cache) == 0


class TestSessionMetadata:
    """Tests for SessionMetadata model."""

    def test_session_metadata_minimal(self):
        """SessionMetadata with minimal fields."""
        from src.services.session_cache import SessionMetadata

        now = datetime.now(timezone.utc)
        metadata = SessionMetadata(
            session_id="test-123",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        )
        assert metadata.session_id == "test-123"
        assert metadata.prompt_count == 0
        assert metadata.total_cost_usd == 0.0

    def test_session_metadata_full(self):
        """SessionMetadata with all fields."""
        from src.services.session_cache import SessionMetadata

        now = datetime.now(timezone.utc)
        metadata = SessionMetadata(
            session_id="test-123",
            created_at=now,
            last_activity=now,
            working_directory="/workspace",
            model="claude-sonnet-4-20250514",
            prompt_count=5,
            total_cost_usd=0.025
        )
        assert metadata.model == "claude-sonnet-4-20250514"
        assert metadata.prompt_count == 5
        assert metadata.total_cost_usd == 0.025

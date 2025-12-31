"""
TDD: Session cache tests.
Status: GREEN (async methods)
"""
from datetime import datetime, timezone

import pytest


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


class TestStreamingState:
    """Tests for P1: SSE StreamingState with event IDs."""

    @pytest.mark.asyncio
    async def test_streaming_state_event_counter_increments(self):
        """Event counter should increment on each call."""
        from src.api.routes.query import StreamingState

        state = StreamingState()

        id1 = await state.get_next_event_id()
        id2 = await state.get_next_event_id()
        id3 = await state.get_next_event_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    @pytest.mark.asyncio
    async def test_streaming_state_event_counter_starts_at_zero(self):
        """Event counter should start at zero."""
        from src.api.routes.query import StreamingState

        state = StreamingState()
        assert state.event_counter == 0

    @pytest.mark.asyncio
    async def test_streaming_state_concurrent_event_ids(self):
        """Event IDs should be unique under concurrent access."""
        import asyncio

        from src.api.routes.query import StreamingState

        state = StreamingState()
        results = []

        async def get_id():
            event_id = await state.get_next_event_id()
            results.append(event_id)

        # Run 100 concurrent event ID requests
        await asyncio.gather(*[get_id() for _ in range(100)])

        # All IDs should be unique
        assert len(results) == 100
        assert len(set(results)) == 100  # All unique
        assert sorted(results) == list(range(1, 101))

    @pytest.mark.asyncio
    async def test_streaming_state_update_from_result(self):
        """State should update from result event data."""
        from src.api.routes.query import StreamingState

        state = StreamingState()

        await state.update_from_result({
            "session_id": "test-session",
            "total_cost_usd": 0.005
        })

        session_id, total_cost, _, _ = await state.get_snapshot()
        assert session_id == "test-session"
        assert total_cost == 0.005

    @pytest.mark.asyncio
    async def test_streaming_state_mark_disconnected(self):
        """State should track client disconnect."""
        from src.api.routes.query import StreamingState

        state = StreamingState()
        assert state.client_disconnected is False

        await state.mark_disconnected()

        _, _, _, disconnected = await state.get_snapshot()
        assert disconnected is True


class TestSessionPersistence:
    """Tests for P2: File-based session persistence."""

    @pytest.mark.asyncio
    async def test_persist_to_file_creates_file(self, tmp_path):
        """Persistence creates file with correct structure."""
        import json

        from src.services.session_cache import SessionCache, SessionMetadata

        persistence_file = tmp_path / "sessions.json"
        cache = SessionCache(
            maxsize=100,
            ttl=3600,
            persistence_path=str(persistence_file)
        )

        now = datetime.now(timezone.utc)
        await cache.save("test-1", SessionMetadata(
            session_id="test-1",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        ))

        result = await cache.persist_to_file()
        assert result is True
        assert persistence_file.exists()

        # Verify file structure
        with open(persistence_file) as f:
            data = json.load(f)

        assert data["version"] == 1
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "test-1"

    @pytest.mark.asyncio
    async def test_persist_without_path_returns_false(self):
        """Persistence without path returns False."""
        from src.services.session_cache import SessionCache, SessionMetadata

        cache = SessionCache(maxsize=100, ttl=3600)  # No persistence_path

        now = datetime.now(timezone.utc)
        await cache.save("test-1", SessionMetadata(
            session_id="test-1",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        ))

        result = await cache.persist_to_file()
        assert result is False

    def test_load_from_file_restores_sessions(self, tmp_path):
        """Load from file restores saved sessions."""
        import json

        from src.services.session_cache import SessionCache

        persistence_file = tmp_path / "sessions.json"
        now = datetime.now(timezone.utc)

        # Create persistence file
        sessions_data = [{
            "session_id": "restored-1",
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "working_directory": "/workspace",
            "model": "claude-sonnet-4",
            "prompt_count": 5,
            "total_cost_usd": 0.025
        }]

        with open(persistence_file, "w") as f:
            json.dump({
                "version": 1,
                "sessions": sessions_data,
                "saved_at": now.isoformat()
            }, f)

        # Load cache from file
        cache = SessionCache.load_from_file(
            persistence_path=str(persistence_file),
            maxsize=100,
            ttl=3600
        )

        assert len(cache) == 1

    @pytest.mark.asyncio
    async def test_load_skips_expired_sessions(self, tmp_path):
        """Expired sessions are not loaded."""
        import json
        from datetime import timedelta

        from src.services.session_cache import SessionCache

        persistence_file = tmp_path / "sessions.json"
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=2)  # 2 hours ago

        sessions_data = [{
            "session_id": "expired-1",
            "created_at": old_time.isoformat(),
            "last_activity": old_time.isoformat(),
            "working_directory": "/workspace",
            "prompt_count": 0,
            "total_cost_usd": 0
        }]

        with open(persistence_file, "w") as f:
            json.dump({
                "version": 1,
                "sessions": sessions_data,
                "saved_at": old_time.isoformat()
            }, f)

        # Load with 1 hour TTL - session should be skipped
        cache = SessionCache.load_from_file(
            persistence_path=str(persistence_file),
            maxsize=100,
            ttl=3600  # 1 hour TTL
        )

        assert len(cache) == 0  # Expired session not loaded

    def test_load_from_nonexistent_file_returns_empty(self, tmp_path):
        """Loading from nonexistent file returns empty cache."""
        from src.services.session_cache import SessionCache

        persistence_file = tmp_path / "nonexistent.json"

        cache = SessionCache.load_from_file(
            persistence_path=str(persistence_file),
            maxsize=100,
            ttl=3600
        )

        assert len(cache) == 0

    def test_load_from_invalid_json_returns_empty(self, tmp_path):
        """Loading from invalid JSON returns empty cache."""
        from src.services.session_cache import SessionCache

        persistence_file = tmp_path / "invalid.json"
        with open(persistence_file, "w") as f:
            f.write("not valid json{")

        cache = SessionCache.load_from_file(
            persistence_path=str(persistence_file),
            maxsize=100,
            ttl=3600
        )

        assert len(cache) == 0

    @pytest.mark.asyncio
    async def test_persist_atomic_no_temp_files_left(self, tmp_path):
        """Atomic persistence doesn't leave temp files."""
        from src.services.session_cache import SessionCache, SessionMetadata

        persistence_file = tmp_path / "sessions.json"
        cache = SessionCache(
            maxsize=100,
            ttl=3600,
            persistence_path=str(persistence_file)
        )

        now = datetime.now(timezone.utc)
        await cache.save("test-atomic", SessionMetadata(
            session_id="test-atomic",
            created_at=now,
            last_activity=now,
            working_directory="/workspace"
        ))

        result = await cache.persist_to_file()

        assert result is True
        assert persistence_file.exists()

        # No temp files should remain
        temp_files = list(tmp_path.glob(".session_cache_*.tmp"))
        assert len(temp_files) == 0

"""Tests for application state management."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.api.state import AppState, app_state, get_app_state


class TestAppState:
    """Tests for AppState class."""

    def test_init(self):
        """Test AppState initialization."""
        state = AppState()
        assert state.active_tasks == set()
        assert state._shutdown_event is None
        assert state.session_cache is None

    def test_shutdown_event_lazy_init(self):
        """Test that shutdown_event is lazily initialized."""
        state = AppState()
        assert state._shutdown_event is None

        event = state.shutdown_event
        assert event is not None
        assert isinstance(event, asyncio.Event)

        # Same instance on second access
        assert state.shutdown_event is event

    def test_track_task(self):
        """Test task tracking."""
        state = AppState()

        # Create a mock task
        task = MagicMock(spec=asyncio.Task)
        task.add_done_callback = MagicMock()

        state.track_task(task)

        assert task in state.active_tasks
        task.add_done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_tasks_empty(self):
        """Test wait_for_tasks with no active tasks."""
        state = AppState()

        cancelled = await state.wait_for_tasks(timeout=1.0)

        assert cancelled == 0

    @pytest.mark.asyncio
    async def test_wait_for_tasks_completed(self):
        """Test wait_for_tasks when all tasks complete within timeout."""
        state = AppState()

        async def quick_task():
            await asyncio.sleep(0.01)
            return "done"

        task = asyncio.create_task(quick_task())
        state.active_tasks.add(task)

        cancelled = await state.wait_for_tasks(timeout=1.0)

        assert cancelled == 0
        assert task.done()

    @pytest.mark.asyncio
    async def test_wait_for_tasks_timeout_and_cancel(self):
        """Test wait_for_tasks cancels tasks that exceed timeout."""
        state = AppState()

        async def slow_task():
            try:
                await asyncio.sleep(10.0)  # Long sleep
            except asyncio.CancelledError:
                # Task properly received cancellation
                raise

        task = asyncio.create_task(slow_task())
        state.active_tasks.add(task)

        # Use very short timeout
        cancelled = await state.wait_for_tasks(timeout=0.05)

        assert cancelled == 1
        assert task.done()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_wait_for_tasks_awaits_cancelled_tasks(self):
        """Test that wait_for_tasks awaits cancelled tasks to finish cleanup."""
        state = AppState()
        cleanup_completed = False

        async def task_with_cleanup():
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                # Simulate cleanup that takes time
                nonlocal cleanup_completed
                await asyncio.sleep(0.01)
                cleanup_completed = True
                raise

        task = asyncio.create_task(task_with_cleanup())
        state.active_tasks.add(task)

        cancelled = await state.wait_for_tasks(timeout=0.05)

        assert cancelled == 1
        # The key assertion: cleanup must be completed
        assert cleanup_completed, "Task cleanup was not awaited"

    @pytest.mark.asyncio
    async def test_wait_for_tasks_multiple_tasks(self):
        """Test wait_for_tasks with multiple tasks, some complete, some timeout."""
        state = AppState()

        async def quick_task():
            await asyncio.sleep(0.01)

        async def slow_task():
            await asyncio.sleep(10.0)

        quick = asyncio.create_task(quick_task())
        slow = asyncio.create_task(slow_task())
        state.active_tasks.add(quick)
        state.active_tasks.add(slow)

        cancelled = await state.wait_for_tasks(timeout=0.1)

        # Only slow task should be cancelled
        assert cancelled == 1
        assert quick.done()
        assert slow.cancelled()


class TestGlobalAppState:
    """Tests for global app state singleton."""

    def test_app_state_singleton(self):
        """Test that app_state is a singleton."""
        assert app_state is not None
        assert isinstance(app_state, AppState)

    def test_get_app_state(self):
        """Test get_app_state returns the singleton."""
        assert get_app_state() is app_state

"""Application state for graceful shutdown support."""
import asyncio
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from ..services.session_cache import SessionCache


class AppState:
    """Application state for graceful shutdown support."""

    def __init__(self):
        self.active_tasks: Set[asyncio.Task] = set()
        self._shutdown_event: asyncio.Event | None = None
        self.session_cache: "SessionCache | None" = None

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

        # Wait for cancelled tasks to actually finish (they will raise CancelledError)
        # This ensures resources are properly cleaned up before shutdown completes
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        return cancelled


# Singleton app state (created once at module load)
app_state = AppState()


def get_app_state() -> AppState:
    """Get the global app state."""
    return app_state

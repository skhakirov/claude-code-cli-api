"""
Query endpoints.

Source: https://platform.claude.com/docs/en/agent-sdk/python#query
"""
import asyncio
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from ...models.request import QueryRequest
from ...models.response import QueryResponse
from ...services.claude_executor import ClaudeExecutor
from ...services.session_cache import SessionCache, SessionMetadata
from ..dependencies import get_executor, get_session_cache
from ...middleware.auth import verify_api_key
from ...core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Query"])


@dataclass
class StreamingState:
    """Thread-safe state container for SSE streaming.

    Uses asyncio.Lock for safe concurrent access to streaming state.
    """
    session_id: Optional[str] = None
    total_cost: float = 0.0
    model_used: Optional[str] = None
    client_disconnected: bool = False
    _lock: Optional[asyncio.Lock] = field(default=None, repr=False)
    _init_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _get_lock(self) -> asyncio.Lock:
        """Get or create asyncio.Lock with thread-safe initialization."""
        if self._lock is None:
            with self._init_lock:
                if self._lock is None:
                    self._lock = asyncio.Lock()
        return self._lock

    async def update_from_result(self, data: dict) -> None:
        """Update state from result event data."""
        async with self._get_lock():
            self.session_id = data.get("session_id")
            self.total_cost = data.get("total_cost_usd") or 0.0

    async def update_model(self, model: Optional[str]) -> None:
        """Update model if provided."""
        if model:
            async with self._get_lock():
                self.model_used = model

    async def mark_disconnected(self) -> None:
        """Mark client as disconnected."""
        async with self._get_lock():
            self.client_disconnected = True

    async def get_snapshot(self) -> tuple[Optional[str], float, Optional[str], bool]:
        """Get atomic snapshot of current state."""
        async with self._get_lock():
            return (
                self.session_id,
                self.total_cost,
                self.model_used,
                self.client_disconnected
            )


def safe_json_dumps(data: Any) -> str:
    """Safely serialize data to JSON with fallback for non-serializable types."""
    try:
        return json.dumps(data)
    except (TypeError, ValueError) as e:
        logger.warning(
            "json_serialization_failed",
            error=str(e),
            data_type=type(data).__name__
        )
        return json.dumps({"error": "Serialization failed", "type": str(type(data))})


@router.post("", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    api_key: str = Depends(verify_api_key),
    executor: ClaudeExecutor = Depends(get_executor),
    cache: SessionCache = Depends(get_session_cache)
) -> QueryResponse:
    """Execute a query and return complete response."""
    response = await executor.execute_query(request)

    # Save session metadata
    now = datetime.now(timezone.utc)
    existing = await cache.get(response.session_id)

    if existing:
        await cache.update_activity(response.session_id, response.total_cost_usd or 0)
    else:
        await cache.save(response.session_id, SessionMetadata(
            session_id=response.session_id,
            created_at=now,
            last_activity=now,
            working_directory=request.working_directory or "/workspace",
            model=response.model,
            prompt_count=1,
            total_cost_usd=response.total_cost_usd or 0
        ))

    return response


@router.post("/stream")
async def execute_streaming_query(
    request: QueryRequest,
    api_key: str = Depends(verify_api_key),
    executor: ClaudeExecutor = Depends(get_executor),
    cache: SessionCache = Depends(get_session_cache)
):
    """Execute query with SSE streaming.

    Handles client disconnects gracefully and saves session metadata
    after stream completion. Uses StreamingState for thread-safe state access.
    """
    state = StreamingState()

    async def generate():
        try:
            async for event in executor.execute_streaming(request):
                # Extract session info from result event
                if event.event == "result" and isinstance(event.data, dict):
                    await state.update_from_result(event.data)

                # Extract model from text event
                if event.event == "text" and isinstance(event.data, dict):
                    await state.update_model(event.data.get("model"))

                yield {"event": event.event, "data": safe_json_dumps(event.data)}

        except asyncio.CancelledError:
            # Client disconnected - mark for cleanup
            await state.mark_disconnected()
            # Re-raise to properly close the connection
            raise

        except Exception as e:
            # Send error event before re-raising
            yield {"event": "error", "data": safe_json_dumps({"error": str(e)})}
            raise

        finally:
            # Get atomic snapshot of state
            session_id, total_cost, model_used, disconnected = await state.get_snapshot()

            # Save session metadata after stream completion
            if session_id and not disconnected:
                now = datetime.now(timezone.utc)
                try:
                    existing = await cache.get(session_id)
                    if existing:
                        await cache.update_activity(session_id, total_cost)
                    else:
                        await cache.save(session_id, SessionMetadata(
                            session_id=session_id,
                            created_at=now,
                            last_activity=now,
                            working_directory=request.working_directory or "/workspace",
                            model=model_used,
                            prompt_count=1,
                            total_cost_usd=total_cost
                        ))
                except Exception as cache_err:
                    # Log cache error but don't fail the response
                    logger.warning(
                        "session_cache_save_failed",
                        session_id=session_id,
                        error=str(cache_err),
                        error_type=type(cache_err).__name__
                    )

    return EventSourceResponse(generate())

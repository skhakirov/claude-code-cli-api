"""
Query endpoints.

Source: https://platform.claude.com/docs/en/agent-sdk/python#query
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from ...models.request import QueryRequest
from ...models.response import QueryResponse
from ...services.claude_executor import ClaudeExecutor
from ...services.session_cache import SessionCache, SessionMetadata
from ..dependencies import get_executor, get_session_cache
from ...middleware.auth import verify_api_key

router = APIRouter(prefix="/query", tags=["Query"])


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
    after stream completion.
    """
    # Session tracking variables
    session_id: Optional[str] = None
    total_cost: float = 0.0
    model_used: Optional[str] = None
    client_disconnected = False

    async def generate():
        nonlocal session_id, total_cost, model_used, client_disconnected

        try:
            async for event in executor.execute_streaming(request):
                # Extract session info from result event
                if event.event == "result" and isinstance(event.data, dict):
                    session_id = event.data.get("session_id")
                    total_cost = event.data.get("total_cost_usd") or 0.0

                # Extract model from text event
                if event.event == "text" and isinstance(event.data, dict):
                    model_used = event.data.get("model") or model_used

                yield {"event": event.event, "data": json.dumps(event.data)}

        except asyncio.CancelledError:
            # Client disconnected - mark for cleanup
            client_disconnected = True
            # Re-raise to properly close the connection
            raise

        except Exception as e:
            # Send error event before re-raising
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            raise

        finally:
            # Save session metadata after stream completion
            if session_id and not client_disconnected:
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
                except Exception:
                    # Don't fail the response if cache save fails
                    pass

    return EventSourceResponse(generate())

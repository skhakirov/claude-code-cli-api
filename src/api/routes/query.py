"""
Query endpoints.

Source: https://platform.claude.com/docs/en/agent-sdk/python#query
"""
import json
from datetime import datetime, timezone
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
    existing = cache.get(response.session_id)

    if existing:
        cache.update_activity(response.session_id, response.total_cost_usd or 0)
    else:
        cache.save(response.session_id, SessionMetadata(
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
    executor: ClaudeExecutor = Depends(get_executor)
):
    """Execute query with SSE streaming."""
    async def generate():
        async for event in executor.execute_streaming(request):
            yield {"event": event.event, "data": json.dumps(event.data)}

    return EventSourceResponse(generate())

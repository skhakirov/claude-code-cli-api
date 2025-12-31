"""Session management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from ...services.session_cache import SessionCache, SessionMetadata
from ..dependencies import get_session_cache
from ...middleware.auth import verify_api_key

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=List[SessionMetadata])
async def list_sessions(
    api_key: str = Depends(verify_api_key),
    cache: SessionCache = Depends(get_session_cache)
) -> List[SessionMetadata]:
    """List all cached sessions."""
    return cache.list_all()


@router.get("/{session_id}", response_model=SessionMetadata)
async def get_session(
    session_id: str,
    api_key: str = Depends(verify_api_key),
    cache: SessionCache = Depends(get_session_cache)
) -> SessionMetadata:
    """Get session by ID."""
    session = cache.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    api_key: str = Depends(verify_api_key),
    cache: SessionCache = Depends(get_session_cache)
):
    """Delete session by ID."""
    if not cache.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}

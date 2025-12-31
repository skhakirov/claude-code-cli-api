"""Health check endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

from ...core.config import get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint - no auth required."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.api_version
    )

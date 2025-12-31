"""Authentication middleware."""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from ..core.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key from header."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key"
        )

    settings = get_settings()
    if api_key not in settings.api_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return api_key

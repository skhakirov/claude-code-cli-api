"""
Exception handling for SDK errors.

Source: https://platform.claude.com/docs/en/agent-sdk/python#error-types

SDK Exception Classes:
- ClaudeSDKError: Base error for Claude SDK
- CLINotFoundError: Claude Code CLI is not installed
- CLIConnectionError: Connection to Claude Code fails
- ProcessError: Claude Code process fails (has exit_code, stderr)
- CLIJSONDecodeError: JSON parsing fails (has line, original_error)
"""
from fastapi import HTTPException
from typing import Type, Optional

from .logging import get_logger

logger = get_logger(__name__)


class ClaudeAPIError(Exception):
    """Base exception for our API errors."""
    pass


class PathTraversalError(ClaudeAPIError):
    """Directory traversal attempt detected."""
    pass


class UnauthorizedDirectoryError(ClaudeAPIError):
    """Access to unauthorized directory."""
    pass


class SessionNotFoundError(ClaudeAPIError):
    """Session not found in cache."""
    pass


# SDK error mapping to HTTP status codes
# Source: https://platform.claude.com/docs/en/agent-sdk/python#error-types
# Note: SDK exceptions are imported dynamically to avoid import errors when SDK not installed
SDK_ERROR_MAPPING: dict[Type[Exception], tuple[int, str]] = {
    PathTraversalError: (400, "Invalid path"),
    UnauthorizedDirectoryError: (403, "Directory access denied"),
    SessionNotFoundError: (404, "Session not found"),
}


def _get_sdk_error_mapping() -> dict[Type[Exception], tuple[int, str]]:
    """Get SDK error mapping, importing SDK exceptions if available."""
    mapping = SDK_ERROR_MAPPING.copy()

    try:
        from claude_agent_sdk import (
            ClaudeSDKError,
            CLINotFoundError,
            CLIConnectionError,
            ProcessError,
            CLIJSONDecodeError,
        )
        mapping.update({
            CLINotFoundError: (503, "Claude CLI not available"),
            CLIConnectionError: (502, "Claude service connection failed"),
            ProcessError: (500, "Claude execution failed"),
            CLIJSONDecodeError: (500, "Invalid response from Claude"),
            ClaudeSDKError: (500, "Claude SDK error"),
        })
    except ImportError:
        pass

    return mapping


def handle_sdk_error(error: Exception, request_id: Optional[str] = None) -> HTTPException:
    """Convert SDK/API exception to HTTPException with logging."""
    mapping = _get_sdk_error_mapping()

    # Extract additional details from ProcessError
    exit_code: Optional[int] = None
    stderr: Optional[str] = None
    if hasattr(error, 'exit_code'):
        exit_code = error.exit_code
    if hasattr(error, 'stderr'):
        stderr = error.stderr

    for error_type, (status, detail) in mapping.items():
        if isinstance(error, error_type):
            # Log the error with full details
            logger.error(
                "sdk_error",
                error_type=type(error).__name__,
                error_message=str(error),
                status_code=status,
                exit_code=exit_code,
                stderr=stderr[:500] if stderr else None,  # Truncate stderr
                request_id=request_id,
                exc_info=True,
            )
            return HTTPException(status_code=status, detail=f"{detail}: {str(error)}")

    # Unknown error
    logger.error(
        "unexpected_error",
        error_type=type(error).__name__,
        error_message=str(error),
        request_id=request_id,
        exc_info=True,
    )
    return HTTPException(status_code=500, detail=f"Unexpected error: {str(error)}")

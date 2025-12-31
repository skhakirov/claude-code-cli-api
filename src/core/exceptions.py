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
from typing import Type


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


def handle_sdk_error(error: Exception) -> HTTPException:
    """Convert SDK/API exception to HTTPException."""
    mapping = _get_sdk_error_mapping()

    for error_type, (status, detail) in mapping.items():
        if isinstance(error, error_type):
            return HTTPException(status_code=status, detail=f"{detail}: {str(error)}")

    return HTTPException(status_code=500, detail=f"Unexpected error: {str(error)}")

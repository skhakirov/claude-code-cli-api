"""
Security utilities for path and prompt sanitization.
"""
from pathlib import Path
from typing import List

from .exceptions import PathTraversalError, UnauthorizedDirectoryError


def sanitize_path(path: str, allowed_directories: List[str]) -> str:
    """
    Sanitize and validate a path against allowed directories.

    Args:
        path: The path to sanitize
        allowed_directories: List of allowed base directories

    Returns:
        Normalized absolute path

    Raises:
        PathTraversalError: If path traversal attack detected
        UnauthorizedDirectoryError: If path is not in allowed directories
    """
    # Normalize the path
    normalized = Path(path).resolve()
    normalized_str = str(normalized)

    # Check for path traversal - if resolved path differs significantly
    # from original after normalization, it might be a traversal attempt
    original_parts = Path(path).parts
    if ".." in original_parts:
        # Check if the resolved path is still within allowed directories
        is_within_allowed = False
        for allowed_dir in allowed_directories:
            allowed_path = Path(allowed_dir).resolve()
            try:
                normalized.relative_to(allowed_path)
                is_within_allowed = True
                break
            except ValueError:
                continue

        if not is_within_allowed:
            raise PathTraversalError(f"Path traversal detected: {path}")

    # Check if path is within any allowed directory
    for allowed_dir in allowed_directories:
        allowed_path = Path(allowed_dir).resolve()
        try:
            normalized.relative_to(allowed_path)
            return normalized_str
        except ValueError:
            continue

    raise UnauthorizedDirectoryError(
        f"Path '{path}' is not within allowed directories: {allowed_directories}"
    )


def sanitize_prompt(prompt: str, max_length: int = 100000) -> str:
    """
    Sanitize a prompt string.

    Args:
        prompt: The prompt to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized prompt string
    """
    # Strip leading/trailing whitespace
    sanitized = prompt.strip()

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized

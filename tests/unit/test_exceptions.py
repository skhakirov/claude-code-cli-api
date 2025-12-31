"""
TDD: Exception handling tests.
Status: RED (must fail before implementation)
"""
from fastapi import HTTPException


class TestExceptions:
    """Tests for custom exceptions."""

    def test_claude_api_error(self):
        """ClaudeAPIError base exception."""
        from src.core.exceptions import ClaudeAPIError

        error = ClaudeAPIError("Test error")
        assert str(error) == "Test error"

    def test_path_traversal_error(self):
        """PathTraversalError exception."""
        from src.core.exceptions import PathTraversalError

        error = PathTraversalError("Invalid path")
        assert isinstance(error, Exception)

    def test_unauthorized_directory_error(self):
        """UnauthorizedDirectoryError exception."""
        from src.core.exceptions import UnauthorizedDirectoryError

        error = UnauthorizedDirectoryError("Access denied")
        assert isinstance(error, Exception)

    def test_session_not_found_error(self):
        """SessionNotFoundError exception."""
        from src.core.exceptions import SessionNotFoundError

        error = SessionNotFoundError("Session not found")
        assert isinstance(error, Exception)


class TestSDKErrorMapping:
    """Tests for SDK error to HTTP mapping."""

    def test_handle_path_traversal_error(self):
        """PathTraversalError maps to 400."""
        from src.core.exceptions import PathTraversalError, handle_sdk_error

        error = PathTraversalError("path traversal attempt")
        http_error = handle_sdk_error(error)

        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 400

    def test_handle_unauthorized_directory_error(self):
        """UnauthorizedDirectoryError maps to 403."""
        from src.core.exceptions import UnauthorizedDirectoryError, handle_sdk_error

        error = UnauthorizedDirectoryError("/etc/passwd")
        http_error = handle_sdk_error(error)

        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 403

    def test_handle_session_not_found_error(self):
        """SessionNotFoundError maps to 404."""
        from src.core.exceptions import SessionNotFoundError, handle_sdk_error

        error = SessionNotFoundError("session-123")
        http_error = handle_sdk_error(error)

        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 404

    def test_handle_unknown_error(self):
        """Unknown errors map to 500."""
        from src.core.exceptions import handle_sdk_error

        error = ValueError("unexpected")
        http_error = handle_sdk_error(error)

        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 500

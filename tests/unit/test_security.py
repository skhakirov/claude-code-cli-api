"""
TDD: Security tests.
Status: RED (must fail before implementation)
"""
import pytest


class TestPathSanitization:
    """Tests for path sanitization."""

    def test_valid_path_allowed(self):
        """Valid path in allowed directory passes."""
        from src.core.security import sanitize_path

        result = sanitize_path("/workspace/project", ["/workspace"])
        assert result == "/workspace/project"

    def test_path_traversal_blocked(self):
        """Path traversal attacks are blocked."""
        from src.core.security import sanitize_path
        from src.core.exceptions import PathTraversalError

        with pytest.raises(PathTraversalError):
            sanitize_path("/workspace/../etc/passwd", ["/workspace"])

    def test_unauthorized_directory_blocked(self):
        """Access to unauthorized directories is blocked."""
        from src.core.security import sanitize_path
        from src.core.exceptions import UnauthorizedDirectoryError

        with pytest.raises(UnauthorizedDirectoryError):
            sanitize_path("/etc/passwd", ["/workspace"])

    def test_relative_path_normalized(self):
        """Relative paths are normalized."""
        from src.core.security import sanitize_path

        result = sanitize_path("/workspace/./project/../other", ["/workspace"])
        assert result == "/workspace/other"

    def test_multiple_allowed_directories(self):
        """Multiple allowed directories work."""
        from src.core.security import sanitize_path

        result = sanitize_path("/tmp/file.txt", ["/workspace", "/tmp"])
        assert result == "/tmp/file.txt"

    def test_nested_path_allowed(self):
        """Deeply nested paths in allowed directory pass."""
        from src.core.security import sanitize_path

        result = sanitize_path("/workspace/a/b/c/d/file.txt", ["/workspace"])
        assert result == "/workspace/a/b/c/d/file.txt"

    def test_double_dot_in_middle_blocked(self):
        """Double dots in path middle are blocked."""
        from src.core.security import sanitize_path
        from src.core.exceptions import PathTraversalError

        with pytest.raises(PathTraversalError):
            sanitize_path("/workspace/project/../../etc", ["/workspace"])


class TestPromptSanitization:
    """Tests for prompt sanitization."""

    def test_prompt_trimmed(self):
        """Prompt is trimmed of extra whitespace."""
        from src.core.security import sanitize_prompt

        result = sanitize_prompt("  Hello World  ")
        assert result == "Hello World"

    def test_prompt_max_length(self):
        """Prompt is truncated to max length."""
        from src.core.security import sanitize_prompt

        long_prompt = "x" * 200000
        result = sanitize_prompt(long_prompt, max_length=100000)
        assert len(result) == 100000

    def test_prompt_preserves_content(self):
        """Normal prompt content is preserved."""
        from src.core.security import sanitize_prompt

        prompt = "Hello, Claude! Can you help me?"
        result = sanitize_prompt(prompt)
        assert result == prompt

    def test_prompt_default_max_length(self):
        """Default max length is applied."""
        from src.core.security import sanitize_prompt

        # Should not truncate normal prompts
        prompt = "Hello"
        result = sanitize_prompt(prompt)
        assert result == "Hello"

    def test_prompt_newlines_preserved(self):
        """Newlines in prompt are preserved."""
        from src.core.security import sanitize_prompt

        prompt = "Line 1\nLine 2\nLine 3"
        result = sanitize_prompt(prompt)
        assert "\n" in result

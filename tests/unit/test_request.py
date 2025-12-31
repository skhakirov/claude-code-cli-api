"""
TDD: Request models tests.
Status: RED (must fail before implementation)
"""
import pytest
from pydantic import ValidationError


class TestQueryRequest:
    """Tests for QueryRequest model."""

    def test_query_request_minimal(self):
        """QueryRequest with minimal parameters."""
        from src.models.request import QueryRequest

        req = QueryRequest(prompt="Hello")
        assert req.prompt == "Hello"
        assert req.permission_mode == "acceptEdits"
        assert req.max_turns == 20

    def test_query_request_full(self):
        """QueryRequest with all parameters."""
        from src.models.request import QueryRequest

        req = QueryRequest(
            prompt="Test prompt",
            resume="session-123",
            continue_conversation=True,
            fork_session=False,
            allowed_tools=["Read", "Write"],
            disallowed_tools=["Bash"],
            system_prompt="You are helpful",
            max_turns=50,
            model="claude-opus-4-20250514",
            permission_mode="bypassPermissions",
            working_directory="/workspace/project",
            mcp_servers={"server1": {"command": "npx"}},
            include_partial_messages=True,
            timeout=600
        )
        assert req.resume == "session-123"
        assert req.allowed_tools == ["Read", "Write"]
        assert req.model == "claude-opus-4-20250514"

    def test_query_request_prompt_required(self):
        """prompt is required."""
        from src.models.request import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest()

    def test_query_request_prompt_min_length(self):
        """prompt must be at least 1 character."""
        from src.models.request import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(prompt="")

    def test_query_request_max_turns_range(self):
        """max_turns must be between 1 and 100."""
        from src.models.request import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(prompt="test", max_turns=0)

        with pytest.raises(ValidationError):
            QueryRequest(prompt="test", max_turns=101)

    def test_query_request_permission_mode_values(self):
        """permission_mode only accepts valid values."""
        from src.models.request import QueryRequest

        for mode in ["default", "acceptEdits", "plan", "bypassPermissions"]:
            req = QueryRequest(prompt="test", permission_mode=mode)
            assert req.permission_mode == mode

    def test_query_request_timeout_range(self):
        """timeout must be between 1 and 600."""
        from src.models.request import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(prompt="test", timeout=0)

        with pytest.raises(ValidationError):
            QueryRequest(prompt="test", timeout=601)

    def test_query_request_prompt_max_length(self):
        """prompt must not exceed 100000 characters."""
        from src.models.request import QueryRequest

        long_prompt = "x" * 100001
        with pytest.raises(ValidationError):
            QueryRequest(prompt=long_prompt)

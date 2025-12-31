"""
TDD: Response models tests.
Status: RED (must fail before implementation)
"""
import pytest


class TestQueryResponse:
    """Tests for QueryResponse model."""

    def test_query_response_minimal(self):
        """QueryResponse with minimal fields."""
        from src.models.response import QueryResponse, QueryStatus

        response = QueryResponse(
            result="Hello!",
            session_id="test-123",
            status=QueryStatus.SUCCESS,
            duration_ms=1000,
            duration_api_ms=800
        )
        assert response.result == "Hello!"
        assert response.session_id == "test-123"
        assert response.status == QueryStatus.SUCCESS

    def test_query_response_full(self):
        """QueryResponse with all fields."""
        from src.models.response import (
            QueryResponse, QueryStatus, UsageInfo, ToolCallInfo, ThinkingInfo
        )

        response = QueryResponse(
            result="Hello!",
            session_id="test-123",
            status=QueryStatus.SUCCESS,
            duration_ms=1500,
            duration_api_ms=1200,
            is_error=False,
            num_turns=2,
            total_cost_usd=0.005,
            model="claude-sonnet-4-20250514",
            usage=UsageInfo(input_tokens=100, output_tokens=50),
            tool_calls=[
                ToolCallInfo(id="tool-1", name="Read", input={"path": "/file.txt"})
            ],
            thinking=[
                ThinkingInfo(thinking="Let me think...", signature="sig123")
            ]
        )
        assert response.num_turns == 2
        assert response.usage.input_tokens == 100
        assert len(response.tool_calls) == 1
        assert len(response.thinking) == 1

    def test_query_status_values(self):
        """QueryStatus enum values."""
        from src.models.response import QueryStatus

        assert QueryStatus.SUCCESS.value == "success"
        assert QueryStatus.ERROR.value == "error"
        assert QueryStatus.TIMEOUT.value == "timeout"

    def test_usage_info(self):
        """UsageInfo model."""
        from src.models.response import UsageInfo

        usage = UsageInfo(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_tool_call_info(self):
        """ToolCallInfo model."""
        from src.models.response import ToolCallInfo

        tool = ToolCallInfo(
            id="tool-1",
            name="Read",
            input={"path": "/file.txt"},
            output="file contents"
        )
        assert tool.id == "tool-1"
        assert tool.name == "Read"
        assert tool.output == "file contents"

    def test_thinking_info(self):
        """ThinkingInfo model."""
        from src.models.response import ThinkingInfo

        thinking = ThinkingInfo(
            thinking="Let me analyze this...",
            signature="abc123"
        )
        assert thinking.thinking == "Let me analyze this..."
        assert thinking.signature == "abc123"


class TestStreamEvent:
    """Tests for StreamEvent model."""

    def test_stream_event(self):
        """StreamEvent model."""
        from src.models.response import StreamEvent

        event = StreamEvent(
            event="text",
            data={"text": "Hello", "model": "claude-sonnet-4-20250514"}
        )
        assert event.event == "text"
        assert event.data["text"] == "Hello"

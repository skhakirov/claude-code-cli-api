"""
TDD: Integration tests for ClaudeExecutor.
Status: GREEN (with mocked SDK)
"""
import pytest
from unittest.mock import patch, MagicMock


class TestClaudeExecutor:
    """Tests for ClaudeExecutor with mocked SDK."""

    @pytest.fixture
    def mock_sdk(self):
        """Create mock SDK components."""
        # Create mock message types as classes
        class MockAssistantMessage:
            pass

        class MockResultMessage:
            pass

        class MockSystemMessage:
            pass

        class MockUserMessage:
            pass

        class MockTextBlock:
            pass

        class MockThinkingBlock:
            pass

        class MockToolUseBlock:
            pass

        class MockToolResultBlock:
            pass

        return {
            'query': MagicMock(),  # Will be set per test
            'ClaudeAgentOptions': MagicMock(),
            'AssistantMessage': MockAssistantMessage,
            'ResultMessage': MockResultMessage,
            'SystemMessage': MockSystemMessage,
            'UserMessage': MockUserMessage,
            'TextBlock': MockTextBlock,
            'ThinkingBlock': MockThinkingBlock,
            'ToolUseBlock': MockToolUseBlock,
            'ToolResultBlock': MockToolResultBlock,
        }

    @pytest.mark.asyncio
    async def test_execute_query_success(self, mock_settings, mock_sdk):
        """Successful query execution."""
        # Create mock result message
        result_msg = MagicMock()
        result_msg.session_id = "test-session-123"
        result_msg.duration_ms = 1500
        result_msg.duration_api_ms = 1200
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.003
        result_msg.usage = {"input_tokens": 100, "output_tokens": 50}
        result_msg.result = "Hello! I can help you with that."

        # Make it instance of our mock class
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(prompt="Hello")
                response = await executor.execute_query(request)

                assert response.status.value == "success"
                assert response.session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_execute_query_timeout(self, mock_settings, mock_sdk):
        """Execution timeout handling - should raise HTTPException with 504."""
        import asyncio
        from fastapi import HTTPException

        async def slow_gen(*args, **kwargs):
            await asyncio.sleep(10)
            yield MagicMock()

        mock_sdk['query'] = slow_gen

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(prompt="Hello", timeout=1)

                # TimeoutError now raises HTTPException with 504 status
                with pytest.raises(HTTPException) as exc_info:
                    await executor.execute_query(request)

                assert exc_info.value.status_code == 504
                assert "timeout" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_execute_query_with_model(self, mock_settings, mock_sdk):
        """Query with specific model."""
        result_msg = MagicMock()
        result_msg.session_id = "test-session-456"
        result_msg.duration_ms = 1000
        result_msg.duration_api_ms = 800
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.01
        result_msg.usage = None
        result_msg.result = "Done"
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(
                    prompt="Hello",
                    model="claude-opus-4-20250514"
                )
                response = await executor.execute_query(request)

                assert response.status.value == "success"

    @pytest.mark.asyncio
    async def test_execute_query_with_session_resume(self, mock_settings, mock_sdk):
        """Query with session resume."""
        result_msg = MagicMock()
        result_msg.session_id = "resumed-session"
        result_msg.duration_ms = 500
        result_msg.duration_api_ms = 400
        result_msg.is_error = False
        result_msg.num_turns = 2
        result_msg.total_cost_usd = 0.002
        result_msg.usage = None
        result_msg.result = "Continued"
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(
                    prompt="Continue from before",
                    resume="previous-session-id"
                )
                response = await executor.execute_query(request)

                assert response.status.value == "success"
                assert response.session_id == "resumed-session"

    @pytest.mark.asyncio
    async def test_execute_streaming_success(self, mock_settings, mock_sdk):
        """Streaming query execution."""
        result_msg = MagicMock()
        result_msg.session_id = "stream-session"
        result_msg.duration_ms = 1000
        result_msg.duration_api_ms = 800
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def async_gen(*args, **kwargs):
            yield result_msg

        mock_sdk['query'] = async_gen

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(prompt="Hello", include_partial_messages=True)

                events = []
                async for event in executor.execute_streaming(request):
                    events.append(event)

                assert len(events) > 0

    @pytest.mark.asyncio
    async def test_build_options_with_working_directory(self, mock_settings, mock_sdk):
        """Options builder with working directory."""
        mock_options = MagicMock()
        mock_sdk['ClaudeAgentOptions'].return_value = mock_options

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(
                    prompt="Hello",
                    working_directory="/workspace/project"
                )

                options = executor._build_options(request)
                assert options is not None

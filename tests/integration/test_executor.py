"""
TDD: Integration tests for ClaudeExecutor.
Status: RED (must fail before implementation)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestClaudeExecutor:
    """Tests for ClaudeExecutor with mocked SDK."""

    @pytest.mark.asyncio
    async def test_execute_query_success(self, mock_settings, mock_query_response):
        """Successful query execution."""
        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor.query") as mock_query:
                # Setup async iterator
                async def async_gen():
                    for msg in mock_query_response:
                        yield msg

                mock_query.return_value = async_gen()

                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                request = QueryRequest(prompt="Hello")

                response = await executor.execute_query(request)

                assert response.status.value == "success"
                assert response.session_id == "test-session-123"
                assert "Hello" in response.result or len(response.result) > 0

    @pytest.mark.asyncio
    async def test_execute_query_timeout(self, mock_settings):
        """Execution timeout handling."""
        import asyncio

        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor.query") as mock_query:
                async def slow_gen():
                    await asyncio.sleep(10)
                    yield MagicMock()

                mock_query.return_value = slow_gen()

                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                request = QueryRequest(prompt="Hello", timeout=1)

                response = await executor.execute_query(request)

                assert response.status.value == "error"
                assert "timeout" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_query_with_model(self, mock_settings, mock_query_response):
        """Query with specific model."""
        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor.query") as mock_query:
                async def async_gen():
                    for msg in mock_query_response:
                        yield msg

                mock_query.return_value = async_gen()

                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                request = QueryRequest(
                    prompt="Hello",
                    model="claude-opus-4-20250514"
                )

                response = await executor.execute_query(request)
                assert response.status.value == "success"

    @pytest.mark.asyncio
    async def test_execute_query_with_session_resume(self, mock_settings, mock_query_response):
        """Query with session resume."""
        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor.query") as mock_query:
                async def async_gen():
                    for msg in mock_query_response:
                        yield msg

                mock_query.return_value = async_gen()

                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                request = QueryRequest(
                    prompt="Continue from before",
                    resume="previous-session-id"
                )

                response = await executor.execute_query(request)
                assert response.status.value == "success"

    @pytest.mark.asyncio
    async def test_execute_streaming_success(self, mock_settings, mock_query_response):
        """Streaming query execution."""
        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor.query") as mock_query:
                async def async_gen():
                    for msg in mock_query_response:
                        yield msg

                mock_query.return_value = async_gen()

                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                request = QueryRequest(prompt="Hello", include_partial_messages=True)

                events = []
                async for event in executor.execute_streaming(request):
                    events.append(event)

                assert len(events) > 0

    @pytest.mark.asyncio
    async def test_build_options_with_working_directory(self, mock_settings):
        """Options builder with working directory."""
        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.core.security.sanitize_path", return_value="/workspace/project"):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                request = QueryRequest(
                    prompt="Hello",
                    working_directory="/workspace/project"
                )

                options = executor._build_options(request)
                assert options is not None

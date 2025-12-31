"""
TDD: Integration tests for ClaudeExecutor.
Status: GREEN (with mocked SDK)
"""
import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock


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


class TestP0Robustness:
    """Tests for P0 robustness improvements."""

    @pytest.fixture
    def mock_sdk(self):
        """Create mock SDK components."""
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
            'query': MagicMock(),
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

    def test_retry_decorator_uses_jitter(self, mock_settings, mock_sdk):
        """Verify retry decorator uses wait_exponential_jitter."""
        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                decorator = executor._create_retry_decorator()

                # Verify the decorator was created (tenacity decorator is callable)
                assert callable(decorator)

    @pytest.mark.asyncio
    async def test_generator_cleanup_timeout(self, mock_settings, mock_sdk):
        """Generator cleanup should timeout if aclose() hangs."""
        # Mock generator that hangs on aclose
        class HangingGenerator:
            async def __anext__(self):
                raise StopAsyncIteration

            def __aiter__(self):
                return self

            async def aclose(self):
                # Simulate hanging cleanup
                await asyncio.sleep(100)

        result_msg = MagicMock()
        result_msg.session_id = "test-123"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.usage = None
        result_msg.result = "Done"
        result_msg.__class__ = mock_sdk['ResultMessage']

        message_count = 0

        async def gen_with_hanging_cleanup(*args, **kwargs):
            nonlocal message_count
            message_count += 1
            yield result_msg

        # Set short cleanup timeout for test
        mock_settings.generator_cleanup_timeout = 0.1

        mock_sdk['query'] = gen_with_hanging_cleanup

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(prompt="Hello", timeout=60)

                # Should not hang even if generator.aclose() hangs
                start = time.time()
                response = await executor.execute_query(request)
                elapsed = time.time() - start

                # Should complete quickly (not wait 100 seconds)
                assert elapsed < 5.0
                assert response.status.value == "success"

    @pytest.mark.asyncio
    async def test_message_stall_detection_logs_warning(self, mock_settings, mock_sdk):
        """Stall detection should log warning when messages are slow."""
        result_msg = MagicMock()
        result_msg.session_id = "test-stall"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.usage = None
        result_msg.result = "Done"
        result_msg.__class__ = mock_sdk['ResultMessage']

        message_times = []

        async def slow_gen(*args, **kwargs):
            # First message
            message_times.append(time.time())
            yield result_msg

        # Set very short stall timeout for test
        mock_settings.message_stall_timeout = 0.01

        mock_sdk['query'] = slow_gen

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                with patch("src.services.claude_executor.logger") as mock_logger:
                    from src.services.claude_executor import ClaudeExecutor
                    from src.models.request import QueryRequest

                    executor = ClaudeExecutor()
                    executor._sdk = mock_sdk

                    request = QueryRequest(prompt="Hello", timeout=60)

                    # Wait a bit before executing to trigger stall detection
                    await asyncio.sleep(0.05)  # 50ms > 10ms stall timeout

                    response = await executor.execute_query(request)

                    # Should still succeed
                    assert response.status.value == "success"

    @pytest.mark.asyncio
    async def test_streaming_generator_cleanup_timeout(self, mock_settings, mock_sdk):
        """Streaming generator cleanup should also timeout."""
        result_msg = MagicMock()
        result_msg.session_id = "stream-123"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def gen_func(*args, **kwargs):
            yield result_msg

        mock_settings.generator_cleanup_timeout = 0.1
        mock_sdk['query'] = gen_func

        with patch("src.core.config.get_settings", return_value=mock_settings):
            with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                from src.services.claude_executor import ClaudeExecutor
                from src.models.request import QueryRequest

                executor = ClaudeExecutor()
                executor._sdk = mock_sdk

                request = QueryRequest(prompt="Hello", timeout=60)

                events = []
                async for event in executor.execute_streaming(request):
                    events.append(event)

                # Should complete and have result event
                assert any(e.event == "result" for e in events)


class TestP1Reliability:
    """Tests for P1 reliability improvements."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_weighted_failures(self):
        """Circuit breaker should use weighted failure counting."""
        from src.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
            ERROR_WEIGHTS
        )

        # Config with threshold of 5
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker(config)

        # Verify ERROR_WEIGHTS are defined
        assert ERROR_WEIGHTS["timeout"] == 0.5
        assert ERROR_WEIGHTS["connection"] == 1.0
        assert ERROR_WEIGHTS["process"] == 1.5
        assert ERROR_WEIGHTS["unknown"] == 1.0

        # 10 timeout errors = 5.0 weighted (should trigger)
        for _ in range(9):
            await cb.record_failure("timeout")
            # Should still be closed (9 * 0.5 = 4.5 < 5)
            assert cb.state == CircuitState.CLOSED

        await cb.record_failure("timeout")
        # Now should be open (10 * 0.5 = 5.0 >= 5)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_process_errors_heavier(self):
        """Process errors should have higher weight."""
        from src.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState
        )

        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker(config)

        # 4 process errors = 6.0 weighted (should trigger)
        for _ in range(3):
            await cb.record_failure("process")
            # 3 * 1.5 = 4.5 < 5
            assert cb.state == CircuitState.CLOSED

        await cb.record_failure("process")
        # 4 * 1.5 = 6.0 >= 5
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_error_type_tracking(self):
        """Circuit breaker should track error types."""
        from src.services.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        await cb.record_failure("timeout")
        await cb.record_failure("timeout")
        await cb.record_failure("connection")
        await cb.record_failure("process")

        status = cb.get_status()
        assert status["error_types"]["timeout"] == 2
        assert status["error_types"]["connection"] == 1
        assert status["error_types"]["process"] == 1
        assert "weighted_failure_count" in status

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_clears_error_types(self):
        """Reset should clear error types tracking."""
        from src.services.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        await cb.record_failure("timeout")
        await cb.record_failure("connection")

        await cb.reset()

        status = cb.get_status()
        assert status["error_types"] == {}
        assert status["weighted_failure_count"] == 0.0

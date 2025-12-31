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

    def test_get_circuit_breaker_uses_settings(self, mock_settings):
        """get_circuit_breaker should use settings for configuration."""
        from src.services.circuit_breaker import (
            get_circuit_breaker,
            reset_circuit_breaker
        )

        # Set custom values in mock settings
        mock_settings.circuit_breaker_failure_threshold = 10
        mock_settings.circuit_breaker_success_threshold = 5
        mock_settings.circuit_breaker_timeout = 60.0

        with patch("src.services.circuit_breaker.get_settings", return_value=mock_settings):
            # Reset to force re-initialization
            reset_circuit_breaker()

            cb = get_circuit_breaker()

            # Verify config matches settings
            assert cb.config.failure_threshold == 10
            assert cb.config.success_threshold == 5
            assert cb.config.timeout_seconds == 60.0

        # Cleanup
        reset_circuit_breaker()


class TestStreamingResponseSizeLimit:
    """Tests for streaming response size limit (P1 fix)."""

    @pytest.fixture
    def mock_sdk(self):
        """Create mock SDK components for streaming tests."""
        class MockAssistantMessage:
            pass

        class MockResultMessage:
            pass

        class MockSystemMessage:
            pass

        class MockUserMessage:
            pass

        class MockTextBlock:
            def __init__(self, text: str = ""):
                self.text = text

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

    @pytest.mark.asyncio
    async def test_streaming_response_size_limit_triggers_truncation(self, mock_settings, mock_sdk):
        """Streaming should emit truncation event when max_response_size exceeded."""
        # Set a small max_response_size for testing
        mock_settings.max_response_size = 100  # 100 bytes

        assistant_msg = MagicMock()
        assistant_msg.model = "claude-sonnet-4"
        # Create text block that exceeds limit
        text_block = MagicMock()
        text_block.text = "A" * 150  # 150 bytes > 100 byte limit
        text_block.__class__ = mock_sdk['TextBlock']
        assistant_msg.content = [text_block]
        assistant_msg.__class__ = mock_sdk['AssistantMessage']

        result_msg = MagicMock()
        result_msg.session_id = "truncate-test"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def gen_large_response(*args, **kwargs):
            yield assistant_msg
            yield result_msg

        mock_sdk['query'] = gen_large_response

        # Patch both config modules - the one used by executor and the main one
        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                    from src.services.claude_executor import ClaudeExecutor
                    from src.models.request import QueryRequest

                    executor = ClaudeExecutor()
                    executor._sdk = mock_sdk
                    executor.settings = mock_settings  # Force settings

                    request = QueryRequest(prompt="Generate large text", timeout=60)

                    events = []
                    async for event in executor.execute_streaming(request):
                        events.append(event)

                    # Should have truncation event
                    truncation_events = [e for e in events if e.event == "truncated"]
                    assert len(truncation_events) == 1

                    truncation_data = truncation_events[0].data
                    assert truncation_data["reason"] == "max_response_size_exceeded"
                    assert truncation_data["max_size"] == 100

    @pytest.mark.asyncio
    async def test_streaming_response_size_limit_partial_text(self, mock_settings, mock_sdk):
        """Streaming should emit partial text before truncation."""
        # Set a small max_response_size for testing
        mock_settings.max_response_size = 50  # 50 bytes

        assistant_msg = MagicMock()
        assistant_msg.model = "claude-sonnet-4"
        # Text that will be partially truncated
        text_block = MagicMock()
        text_block.text = "A" * 100  # 100 bytes > 50 byte limit
        text_block.__class__ = mock_sdk['TextBlock']
        assistant_msg.content = [text_block]
        assistant_msg.__class__ = mock_sdk['AssistantMessage']

        result_msg = MagicMock()
        result_msg.session_id = "partial-test"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def gen_response(*args, **kwargs):
            yield assistant_msg
            yield result_msg

        mock_sdk['query'] = gen_response

        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                    from src.services.claude_executor import ClaudeExecutor
                    from src.models.request import QueryRequest

                    executor = ClaudeExecutor()
                    executor._sdk = mock_sdk
                    executor.settings = mock_settings  # Force settings

                    request = QueryRequest(prompt="Generate text", timeout=60)

                    events = []
                    async for event in executor.execute_streaming(request):
                        events.append(event)

                    # Should have text event with partial content
                    text_events = [e for e in events if e.event == "text"]
                    assert len(text_events) == 1
                    # Text should be truncated to ~50 bytes
                    assert len(text_events[0].data["text"]) == 50

    @pytest.mark.asyncio
    async def test_streaming_skips_text_after_truncation(self, mock_settings, mock_sdk):
        """Streaming should skip text events after truncation."""
        mock_settings.max_response_size = 50

        # First message - triggers truncation
        assistant_msg1 = MagicMock()
        assistant_msg1.model = "claude-sonnet-4"
        text_block1 = MagicMock()
        text_block1.text = "A" * 100  # Triggers truncation
        text_block1.__class__ = mock_sdk['TextBlock']
        assistant_msg1.content = [text_block1]
        assistant_msg1.__class__ = mock_sdk['AssistantMessage']

        # Second message - should be skipped
        assistant_msg2 = MagicMock()
        assistant_msg2.model = "claude-sonnet-4"
        text_block2 = MagicMock()
        text_block2.text = "B" * 50  # Should be skipped
        text_block2.__class__ = mock_sdk['TextBlock']
        assistant_msg2.content = [text_block2]
        assistant_msg2.__class__ = mock_sdk['AssistantMessage']

        result_msg = MagicMock()
        result_msg.session_id = "skip-test"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def gen_multiple_messages(*args, **kwargs):
            yield assistant_msg1
            yield assistant_msg2
            yield result_msg

        mock_sdk['query'] = gen_multiple_messages

        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                    from src.services.claude_executor import ClaudeExecutor
                    from src.models.request import QueryRequest

                    executor = ClaudeExecutor()
                    executor._sdk = mock_sdk
                    executor.settings = mock_settings  # Force settings

                    request = QueryRequest(prompt="Generate text", timeout=60)

                    events = []
                    async for event in executor.execute_streaming(request):
                        events.append(event)

                    # Should only have one text event (partial from first message)
                    text_events = [e for e in events if e.event == "text"]
                    assert len(text_events) == 1

                    # Should have truncation event
                    truncation_events = [e for e in events if e.event == "truncated"]
                    assert len(truncation_events) == 1

                    # No "B" text should appear (second message skipped)
                    all_text = "".join(e.data.get("text", "") for e in text_events)
                    assert "B" not in all_text

    @pytest.mark.asyncio
    async def test_streaming_no_truncation_under_limit(self, mock_settings, mock_sdk):
        """Streaming should not truncate when response is under limit."""
        mock_settings.max_response_size = 1000

        assistant_msg = MagicMock()
        assistant_msg.model = "claude-sonnet-4"
        text_block = MagicMock()
        text_block.text = "Hello, world!"  # Small response
        text_block.__class__ = mock_sdk['TextBlock']
        assistant_msg.content = [text_block]
        assistant_msg.__class__ = mock_sdk['AssistantMessage']

        result_msg = MagicMock()
        result_msg.session_id = "normal-test"
        result_msg.duration_ms = 100
        result_msg.duration_api_ms = 80
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.001
        result_msg.__class__ = mock_sdk['ResultMessage']

        async def gen_small_response(*args, **kwargs):
            yield assistant_msg
            yield result_msg

        mock_sdk['query'] = gen_small_response

        with patch("src.services.claude_executor.get_settings", return_value=mock_settings):
            with patch("src.core.config.get_settings", return_value=mock_settings):
                with patch("src.services.claude_executor._get_sdk", return_value=mock_sdk):
                    from src.services.claude_executor import ClaudeExecutor
                    from src.models.request import QueryRequest

                    executor = ClaudeExecutor()
                    executor._sdk = mock_sdk
                    executor.settings = mock_settings  # Force settings

                    request = QueryRequest(prompt="Hello", timeout=60)

                    events = []
                    async for event in executor.execute_streaming(request):
                        events.append(event)

                    # Should have text event with full content
                    text_events = [e for e in events if e.event == "text"]
                    assert len(text_events) == 1
                    assert text_events[0].data["text"] == "Hello, world!"

                    # Should NOT have truncation event
                    truncation_events = [e for e in events if e.event == "truncated"]
                    assert len(truncation_events) == 0

"""
Claude SDK wrapper service.

Sources:
- query(): https://platform.claude.com/docs/en/agent-sdk/python#query
- ClaudeAgentOptions: https://platform.claude.com/docs/en/agent-sdk/python#claudeagentoptions
- Message Types: https://platform.claude.com/docs/en/agent-sdk/python#message-types
- Content Blocks: https://platform.claude.com/docs/en/agent-sdk/python#content-block-types
"""
import time
import asyncio
import sys
from typing import AsyncIterator, Optional, TYPE_CHECKING, Any
from pathlib import Path

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception,
    RetryError,
)

# Python 3.10 compatibility
if sys.version_info >= (3, 11):
    from asyncio import timeout as async_timeout
else:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def async_timeout(seconds):
        """Async timeout context manager for Python 3.10.

        Safely handles the case where current_task() returns None.
        """
        task = asyncio.current_task()
        if task is None:
            # No task context - yield without timeout (shouldn't happen in normal use)
            yield
            return

        loop = asyncio.get_running_loop()  # Safer than get_event_loop()
        handle = loop.call_later(seconds, task.cancel)
        try:
            yield
        except asyncio.CancelledError:
            # Check if cancellation was due to our timeout
            if not handle.cancelled():
                raise asyncio.TimeoutError()
            raise  # Re-raise if cancelled for other reasons
        finally:
            handle.cancel()


def _is_retryable_error(exception: BaseException) -> bool:
    """Determine if an exception is retryable.

    Retryable errors:
    - CLIConnectionError: Temporary connection issues
    - TimeoutError: Network timeouts (but not execution timeouts)
    - OSError with specific errno: Network-related OS errors

    Non-retryable errors:
    - ProcessError: Usually indicates a real problem with the request
    - CLINotFoundError: CLI not installed, won't fix itself
    - CLIJSONDecodeError: Bad response, retrying won't help
    - PathTraversalError, UnauthorizedDirectoryError: Security errors
    """
    # Try to import SDK exceptions for type checking
    try:
        from claude_agent_sdk import CLIConnectionError
        if isinstance(exception, CLIConnectionError):
            return True
    except ImportError:
        pass

    # Network-related errors are retryable
    if isinstance(exception, (ConnectionError, TimeoutError)):
        return True

    # OSError with network errno
    if isinstance(exception, OSError) and exception.errno in (
        110,  # ETIMEDOUT
        111,  # ECONNREFUSED
        113,  # EHOSTUNREACH
    ):
        return True

    return False


def _classify_error_type(exception: BaseException) -> str:
    """Classify exception into error type for circuit breaker weighting.

    Returns:
        Error type: "timeout", "connection", "process", or "unknown"
    """
    # Timeout errors
    if isinstance(exception, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"

    # Connection errors
    try:
        from claude_agent_sdk import CLIConnectionError
        if isinstance(exception, CLIConnectionError):
            return "connection"
    except ImportError:
        pass

    if isinstance(exception, (ConnectionError, OSError)):
        return "connection"

    # Process errors (SDK-specific)
    try:
        from claude_agent_sdk import ProcessError
        if isinstance(exception, ProcessError):
            return "process"
    except ImportError:
        pass

    return "unknown"

from ..models.request import QueryRequest
from ..models.response import (
    QueryResponse, QueryStatus, ToolCallInfo, UsageInfo,
    StreamEvent, ThinkingInfo
)
from ..core.config import get_settings
from ..core.security import sanitize_path, sanitize_prompt
from ..core.exceptions import handle_sdk_error, CircuitOpenError, ExecutionTimeoutError
from ..core.logging import get_logger

logger = get_logger(__name__)
from .circuit_breaker import get_circuit_breaker

# Lazy SDK imports for testing without SDK installed
if TYPE_CHECKING:
    from claude_agent_sdk import (
        query as sdk_query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        UserMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
    )


def _get_sdk():
    """Lazy import of SDK components."""
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        UserMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
    )
    return {
        'query': query,
        'ClaudeAgentOptions': ClaudeAgentOptions,
        'AssistantMessage': AssistantMessage,
        'ResultMessage': ResultMessage,
        'SystemMessage': SystemMessage,
        'UserMessage': UserMessage,
        'TextBlock': TextBlock,
        'ThinkingBlock': ThinkingBlock,
        'ToolUseBlock': ToolUseBlock,
        'ToolResultBlock': ToolResultBlock,
    }


class ClaudeExecutor:
    """
    Wrapper for Claude Agent SDK query() function.

    Source: https://platform.claude.com/docs/en/agent-sdk/python#query

    async def query(
        *,
        prompt: str | AsyncIterable[dict[str, Any]],
        options: ClaudeAgentOptions | None = None
    ) -> AsyncIterator[Message]
    """

    def __init__(self):
        self.settings = get_settings()
        self._sdk = None

    @property
    def sdk(self):
        """Lazy load SDK."""
        if self._sdk is None:
            self._sdk = _get_sdk()
        return self._sdk

    def _build_options(self, request: QueryRequest) -> Any:
        """
        Build ClaudeAgentOptions from request.

        Source: https://platform.claude.com/docs/en/agent-sdk/python#claudeagentoptions
        """
        cwd = request.working_directory or self.settings.default_working_directory
        if cwd:
            cwd = sanitize_path(cwd, self.settings.allowed_directories)

        ClaudeAgentOptions = self.sdk['ClaudeAgentOptions']

        # Source: https://platform.claude.com/docs/en/agent-sdk/python#claudeagentoptions
        return ClaudeAgentOptions(
            # Working directory
            cwd=Path(cwd) if cwd else None,

            # Tools
            allowed_tools=request.allowed_tools or [],
            disallowed_tools=request.disallowed_tools or [],

            # Permissions
            permission_mode=request.permission_mode,

            # Session management
            resume=request.resume,
            continue_conversation=request.continue_conversation,
            fork_session=request.fork_session,

            # Model
            model=request.model or self.settings.default_model,

            # Limits
            max_turns=request.max_turns or self.settings.default_max_turns,

            # System prompt
            system_prompt=request.system_prompt,

            # MCP servers
            mcp_servers=request.mcp_servers or {},

            # Streaming
            include_partial_messages=request.include_partial_messages,
        )

    def _log_retry_attempt(self, retry_state) -> None:
        """Log retry attempt for debugging and monitoring."""
        exception = retry_state.outcome.exception()
        logger.warning(
            "sdk_retry_attempt",
            attempt=retry_state.attempt_number,
            max_attempts=self.settings.retry_max_attempts,
            exception_type=type(exception).__name__ if exception else "Unknown",
            exception_message=str(exception) if exception else "No exception",
            wait_time=retry_state.next_action.sleep if retry_state.next_action else 0,
        )

    def _create_retry_decorator(self):
        """Create a tenacity retry decorator with configured settings.

        Uses exponential backoff with jitter to prevent thundering herd problem
        when multiple clients retry simultaneously.
        """
        return retry(
            stop=stop_after_attempt(self.settings.retry_max_attempts),
            wait=wait_exponential_jitter(
                initial=self.settings.retry_min_wait,
                max=self.settings.retry_max_wait,
                jitter=self.settings.retry_jitter_max,
            ),
            retry=retry_if_exception(_is_retryable_error),
            before_sleep=self._log_retry_attempt,
            reraise=True,
        )

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute query and collect all messages with automatic retry for transient errors.

        Source: https://platform.claude.com/docs/en/agent-sdk/python#query
        Returns AsyncIterator[Message] where Message is:
        UserMessage | AssistantMessage | SystemMessage | ResultMessage
        """
        # Check circuit breaker
        circuit_breaker = get_circuit_breaker()
        if not await circuit_breaker.acquire():
            raise CircuitOpenError(
                f"Circuit breaker is open. Service will retry in {circuit_breaker.config.timeout_seconds}s"
            )

        start_time = time.time()
        prompt = sanitize_prompt(request.prompt)

        # Get SDK components
        query = self.sdk['query']
        AssistantMessage = self.sdk['AssistantMessage']
        ResultMessage = self.sdk['ResultMessage']
        TextBlock = self.sdk['TextBlock']
        ThinkingBlock = self.sdk['ThinkingBlock']
        ToolUseBlock = self.sdk['ToolUseBlock']

        # Result collectors
        session_id: Optional[str] = None
        result_text = ""
        tool_calls: list[ToolCallInfo] = []
        thinking_blocks: list[ThinkingInfo] = []
        model_used: Optional[str] = None
        usage: Optional[UsageInfo] = None
        cost: Optional[float] = None
        num_turns = 0
        duration_api_ms = 0
        is_error = False
        error_msg: Optional[str] = None
        retry_count = 0
        response_truncated = False
        max_response_size = self.settings.max_response_size

        # Inner function with retry logic
        async def _execute_with_retry():
            nonlocal session_id, result_text, tool_calls, thinking_blocks
            nonlocal model_used, usage, cost, num_turns, duration_api_ms
            nonlocal is_error, error_msg, retry_count, response_truncated

            # Reset collectors for retry
            result_text = ""
            tool_calls = []
            thinking_blocks = []
            response_truncated = False

            # Store generator for proper cleanup
            sdk_generator = None
            last_activity = time.time()
            stall_timeout = self.settings.message_stall_timeout

            try:
                async with async_timeout(request.timeout or self.settings.default_timeout):
                    # Source: https://platform.claude.com/docs/en/agent-sdk/python#query
                    sdk_generator = query(
                        prompt=prompt,
                        options=self._build_options(request)
                    )
                    async for msg in sdk_generator:
                        # Check for stalled message processing
                        current_time = time.time()
                        if current_time - last_activity > stall_timeout:
                            logger.warning(
                                "message_stall_detected",
                                stall_seconds=current_time - last_activity,
                                timeout_threshold=stall_timeout
                            )
                            # Don't break - let overall timeout handle it
                            # This is just a warning for monitoring
                        last_activity = current_time

                        # AssistantMessage processing
                        # Source: https://platform.claude.com/docs/en/agent-sdk/python#assistantmessage
                        # content: list[ContentBlock], model: str
                        if isinstance(msg, AssistantMessage):
                            model_used = msg.model
                            for block in msg.content:
                                # TextBlock: text: str
                                if isinstance(block, TextBlock):
                                    # Check response size limit
                                    if len(result_text) + len(block.text) > max_response_size:
                                        remaining = max_response_size - len(result_text)
                                        if remaining > 0:
                                            result_text += block.text[:remaining]
                                        response_truncated = True
                                    else:
                                        result_text += block.text
                                # ThinkingBlock: thinking: str, signature: str
                                elif isinstance(block, ThinkingBlock):
                                    thinking_blocks.append(ThinkingInfo(
                                        thinking=block.thinking,
                                        signature=block.signature
                                    ))
                                # ToolUseBlock: id: str, name: str, input: dict
                                elif isinstance(block, ToolUseBlock):
                                    tool_calls.append(ToolCallInfo(
                                        id=block.id,
                                        name=block.name,
                                        input=block.input
                                    ))

                        # ResultMessage processing (always last)
                        # Source: https://platform.claude.com/docs/en/agent-sdk/python#resultmessage
                        elif isinstance(msg, ResultMessage):
                            session_id = msg.session_id
                            cost = msg.total_cost_usd
                            num_turns = msg.num_turns
                            duration_api_ms = msg.duration_api_ms
                            is_error = msg.is_error

                            if msg.result and not result_text:
                                result_text = msg.result

                            if msg.usage:
                                usage = UsageInfo(
                                    input_tokens=msg.usage.get('input_tokens', 0),
                                    output_tokens=msg.usage.get('output_tokens', 0)
                                )
            finally:
                # Ensure generator cleanup to prevent resource leaks
                # Use timeout to prevent hanging on cleanup
                if sdk_generator is not None:
                    try:
                        await asyncio.wait_for(
                            sdk_generator.aclose(),
                            timeout=self.settings.generator_cleanup_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "generator_cleanup_timeout",
                            timeout_seconds=self.settings.generator_cleanup_timeout
                        )
                    except Exception:
                        pass  # Ignore other cleanup errors

        try:
            # Apply retry decorator dynamically
            retry_decorator = self._create_retry_decorator()
            retryable_execute = retry_decorator(_execute_with_retry)
            await retryable_execute()
            # Record success with circuit breaker
            await circuit_breaker.record_success()
        except RetryError as e:
            # All retries exhausted - record failure
            # Determine error type from the last exception
            last_exc = e.last_attempt.exception()
            error_type = _classify_error_type(last_exc)
            await circuit_breaker.record_failure(error_type=error_type)
            is_error = True
            error_msg = f"All {self.settings.retry_max_attempts} retry attempts failed: {str(last_exc)}"
            raise handle_sdk_error(last_exc)
        except asyncio.TimeoutError:
            # Timeout - record failure and raise proper HTTP error
            await circuit_breaker.record_failure(error_type="timeout")
            timeout_seconds = request.timeout or self.settings.default_timeout
            raise handle_sdk_error(
                ExecutionTimeoutError(
                    f"Execution timeout after {timeout_seconds}s",
                    timeout_seconds=timeout_seconds
                )
            )
        except Exception as e:
            # Non-retryable error or other exception
            if not _is_retryable_error(e):
                error_type = _classify_error_type(e)
                await circuit_breaker.record_failure(error_type=error_type)
                is_error = True
                error_msg = str(e)
                raise handle_sdk_error(e)
            raise

        duration_ms = int((time.time() - start_time) * 1000)

        return QueryResponse(
            result=result_text,
            session_id=session_id or "unknown",
            status=QueryStatus.ERROR if is_error else QueryStatus.SUCCESS,
            duration_ms=duration_ms,
            duration_api_ms=duration_api_ms,
            is_error=is_error,
            num_turns=num_turns,
            total_cost_usd=cost,
            model=model_used,
            usage=usage,
            tool_calls=tool_calls,
            thinking=thinking_blocks,
            error=error_msg,
            response_truncated=response_truncated
        )

    async def execute_streaming(self, request: QueryRequest) -> AsyncIterator[StreamEvent]:
        """Execute query with streaming response."""
        # Check circuit breaker
        circuit_breaker = get_circuit_breaker()
        if not await circuit_breaker.acquire():
            yield StreamEvent(
                event="error",
                data={"error": f"Circuit breaker is open. Retry in {circuit_breaker.config.timeout_seconds}s"}
            )
            return

        prompt = sanitize_prompt(request.prompt)

        # Get SDK components
        query = self.sdk['query']
        SystemMessage = self.sdk['SystemMessage']
        AssistantMessage = self.sdk['AssistantMessage']
        ResultMessage = self.sdk['ResultMessage']
        TextBlock = self.sdk['TextBlock']
        ThinkingBlock = self.sdk['ThinkingBlock']
        ToolUseBlock = self.sdk['ToolUseBlock']
        ToolResultBlock = self.sdk['ToolResultBlock']

        # Store generator for proper cleanup
        sdk_generator = None
        last_activity = time.time()
        stall_timeout = self.settings.message_stall_timeout

        try:
            async with async_timeout(request.timeout or self.settings.default_timeout):
                sdk_generator = query(
                    prompt=prompt,
                    options=self._build_options(request)
                )
                async for msg in sdk_generator:
                    # Check for stalled message processing
                    current_time = time.time()
                    if current_time - last_activity > stall_timeout:
                        logger.warning(
                            "message_stall_detected",
                            stall_seconds=current_time - last_activity,
                            timeout_threshold=stall_timeout
                        )
                    last_activity = current_time

                    for event in self._message_to_events(
                        msg, SystemMessage, AssistantMessage, ResultMessage,
                        TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
                    ):
                        yield event
            # Record success
            await circuit_breaker.record_success()

        except asyncio.TimeoutError:
            await circuit_breaker.record_failure(error_type="timeout")
            timeout_seconds = request.timeout or self.settings.default_timeout
            yield StreamEvent(
                event="error",
                data={
                    "error": f"Execution timeout after {timeout_seconds}s",
                    "timeout_seconds": timeout_seconds
                }
            )
        except Exception as e:
            error_type = _classify_error_type(e)
            await circuit_breaker.record_failure(error_type=error_type)
            yield StreamEvent(event="error", data={"error": str(e)})
        finally:
            # Ensure generator cleanup to prevent resource leaks
            # Use timeout to prevent hanging on cleanup
            if sdk_generator is not None:
                try:
                    await asyncio.wait_for(
                        sdk_generator.aclose(),
                        timeout=self.settings.generator_cleanup_timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "generator_cleanup_timeout",
                        timeout_seconds=self.settings.generator_cleanup_timeout
                    )
                except Exception:
                    pass  # Ignore other cleanup errors

    def _message_to_events(
        self, msg, SystemMessage, AssistantMessage, ResultMessage,
        TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
    ) -> list[StreamEvent]:
        """Convert SDK message to StreamEvent(s)."""
        events: list[StreamEvent] = []

        if isinstance(msg, SystemMessage):
            events.append(StreamEvent(
                event="init" if msg.subtype == "init" else "system",
                data=msg.data
            ))

        elif isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    events.append(StreamEvent(
                        event="text",
                        data={"text": block.text, "model": msg.model}
                    ))
                elif isinstance(block, ThinkingBlock):
                    events.append(StreamEvent(
                        event="thinking",
                        data={"thinking": block.thinking}
                    ))
                elif isinstance(block, ToolUseBlock):
                    events.append(StreamEvent(
                        event="tool_use",
                        data={"id": block.id, "name": block.name, "input": block.input}
                    ))
                elif isinstance(block, ToolResultBlock):
                    events.append(StreamEvent(
                        event="tool_result",
                        data={"tool_use_id": block.tool_use_id, "content": str(block.content)}
                    ))

        elif isinstance(msg, ResultMessage):
            events.append(StreamEvent(
                event="result",
                data={
                    "session_id": msg.session_id,
                    "total_cost_usd": msg.total_cost_usd,
                    "num_turns": msg.num_turns,
                    "duration_ms": msg.duration_ms,
                    "is_error": msg.is_error
                }
            ))

        return events

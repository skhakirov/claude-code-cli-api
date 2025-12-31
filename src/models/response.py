"""
Response models matching SDK message types.

Sources:
- Message Types: https://platform.claude.com/docs/en/agent-sdk/python#message-types
- Content Blocks: https://platform.claude.com/docs/en/agent-sdk/python#content-block-types
- ResultMessage: https://platform.claude.com/docs/en/agent-sdk/python#resultmessage
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class QueryStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ToolCallInfo(BaseModel):
    """
    Tool usage from ToolUseBlock.

    Source: https://platform.claude.com/docs/en/agent-sdk/python#tooluseblock
    - id: str
    - name: str
    - input: dict[str, Any]
    """
    id: str
    name: str
    input: Dict[str, Any]
    output: Optional[str] = None


class ThinkingInfo(BaseModel):
    """
    Thinking block from reasoning models.

    Source: https://platform.claude.com/docs/en/agent-sdk/python#thinkingblock
    - thinking: str
    - signature: str
    """
    thinking: str
    signature: str


class UsageInfo(BaseModel):
    """
    Token usage from ResultMessage.usage.

    Source: https://platform.claude.com/docs/en/agent-sdk/python#resultmessage
    - usage: dict[str, Any] | None
    """
    input_tokens: int
    output_tokens: int


class QueryResponse(BaseModel):
    """
    Response model matching ResultMessage from SDK.

    Source: https://platform.claude.com/docs/en/agent-sdk/python#resultmessage

    @dataclass
    class ResultMessage:
        subtype: str
        duration_ms: int
        duration_api_ms: int
        is_error: bool
        num_turns: int
        session_id: str
        total_cost_usd: float | None = None
        usage: dict[str, Any] | None = None
        result: str | None = None
    """
    # Aggregated result
    result: str
    session_id: str
    status: QueryStatus

    # From ResultMessage
    duration_ms: int
    duration_api_ms: int
    is_error: bool = False
    num_turns: int = 0
    total_cost_usd: Optional[float] = None
    usage: Optional[UsageInfo] = None

    # From AssistantMessage.model
    # Source: https://platform.claude.com/docs/en/agent-sdk/python#assistantmessage
    model: Optional[str] = None

    # Collected from messages
    tool_calls: List[ToolCallInfo] = []
    thinking: List[ThinkingInfo] = []
    error: Optional[str] = None


class StreamEvent(BaseModel):
    """SSE event for streaming responses."""
    event: str
    data: Dict[str, Any]

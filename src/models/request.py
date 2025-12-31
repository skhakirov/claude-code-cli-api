"""
Request models matching ClaudeAgentOptions from SDK.

Source: https://platform.claude.com/docs/en/agent-sdk/python#claudeagentoptions
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Source: https://platform.claude.com/docs/en/agent-sdk/python#permissionmode
PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]


class QueryRequest(BaseModel):
    """
    Request model for /query endpoint.

    All parameters correspond to ClaudeAgentOptions from SDK.
    Source: https://platform.claude.com/docs/en/agent-sdk/python#claudeagentoptions
    """
    prompt: str = Field(..., min_length=1, max_length=100000)

    # Session management
    # Source: https://platform.claude.com/docs/en/agent-sdk/python#claudeagentoptions
    # resume: str | None - "Session ID to resume"
    # continue_conversation: bool - "Continue the most recent conversation"
    # fork_session: bool - "When resuming, fork to a new session ID"
    resume: Optional[str] = None
    continue_conversation: bool = False
    fork_session: bool = False

    # Tools
    # Source: ClaudeAgentOptions.allowed_tools, .disallowed_tools
    allowed_tools: Optional[List[str]] = None
    disallowed_tools: Optional[List[str]] = None

    # System prompt
    # Source: ClaudeAgentOptions.system_prompt
    system_prompt: Optional[str] = None

    # Limits
    # Source: ClaudeAgentOptions.max_turns
    max_turns: Optional[int] = Field(default=20, ge=1, le=100)

    # Model
    # Source: ClaudeAgentOptions.model
    model: Optional[str] = None

    # Permission mode
    # Source: https://platform.claude.com/docs/en/agent-sdk/python#permissionmode
    permission_mode: PermissionMode = "acceptEdits"

    # Working directory
    # Source: ClaudeAgentOptions.cwd
    working_directory: Optional[str] = None

    # MCP servers
    # Source: ClaudeAgentOptions.mcp_servers
    mcp_servers: Optional[Dict[str, Any]] = None

    # Streaming
    # Source: ClaudeAgentOptions.include_partial_messages
    include_partial_messages: bool = False

    # Timeout (our parameter for asyncio.timeout)
    timeout: Optional[int] = Field(default=300, ge=1, le=600)

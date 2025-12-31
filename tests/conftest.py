"""
Pytest fixtures for TDD.
These fixtures are used before writing production code.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator


@pytest.fixture
def mock_settings():
    """Mock Settings for tests without .env file."""
    return MagicMock(
        api_keys=["test-api-key"],
        anthropic_api_key="sk-ant-test",
        default_model="claude-sonnet-4-20250514",
        default_max_turns=20,
        default_timeout=300,
        default_permission_mode="acceptEdits",
        allowed_directories=["/workspace", "/tmp"],
        default_working_directory="/workspace",
        session_cache_maxsize=100,
        session_cache_ttl=3600,
        log_level="DEBUG"
    )


@pytest.fixture
def mock_query_response():
    """Mock result from SDK query()."""
    # Mock TextBlock
    text_block = MagicMock()
    text_block.text = "Hello! I can help you with that."
    # Add type checking support
    type(text_block).__name__ = "TextBlock"

    # Mock AssistantMessage
    assistant_msg = MagicMock()
    assistant_msg.content = [text_block]
    assistant_msg.model = "claude-sonnet-4-20250514"
    type(assistant_msg).__name__ = "AssistantMessage"

    # Mock ResultMessage
    result_msg = MagicMock()
    result_msg.session_id = "test-session-123"
    result_msg.duration_ms = 1500
    result_msg.duration_api_ms = 1200
    result_msg.is_error = False
    result_msg.num_turns = 1
    result_msg.total_cost_usd = 0.003
    result_msg.usage = {"input_tokens": 100, "output_tokens": 50}
    result_msg.result = "Hello! I can help you with that."
    type(result_msg).__name__ = "ResultMessage"

    return [assistant_msg, result_msg]


@pytest.fixture
def sample_query_request():
    """Sample request for tests."""
    return {
        "prompt": "Hello, Claude!",
        "working_directory": "/workspace",
        "permission_mode": "acceptEdits",
        "max_turns": 10
    }


@pytest.fixture
def mock_session_metadata():
    """Sample session metadata."""
    from datetime import datetime, timezone
    return {
        "session_id": "test-session-123",
        "created_at": datetime.now(timezone.utc),
        "last_activity": datetime.now(timezone.utc),
        "working_directory": "/workspace",
        "model": "claude-sonnet-4-20250514",
        "prompt_count": 1,
        "total_cost_usd": 0.003
    }

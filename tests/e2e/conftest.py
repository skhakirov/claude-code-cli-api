"""
E2E test configuration.

Sets up environment variables before app import.
"""
import os

import pytest

# Set environment before any imports
os.environ["CLAUDE_API_API_KEYS"] = '["test-key", "valid-key"]'
os.environ["CLAUDE_API_ALLOWED_DIRECTORIES"] = '["/tmp", "/workspace"]'
os.environ["CLAUDE_API_DEFAULT_WORKING_DIRECTORY"] = "/tmp"


@pytest.fixture(scope="session", autouse=True)
def setup_e2e_environment():
    """Ensure environment is set for all E2E tests."""
    # Environment already set at module level
    yield

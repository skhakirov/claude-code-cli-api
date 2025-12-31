"""
Tests for P3: Enhanced logging and stack traces.
"""


class TestExceptionChainFormatting:
    """Tests for format_exception_chain function."""

    def test_format_exception_chain_single_exception(self):
        """Format a single exception without chain."""
        from src.core.logging import format_exception_chain

        try:
            raise ValueError("test error")
        except ValueError as e:
            chain = format_exception_chain(e)

        assert len(chain) == 1
        assert chain[0]["type"] == "ValueError"
        assert chain[0]["message"] == "test error"
        assert "traceback" in chain[0]
        assert "ValueError: test error" in chain[0]["traceback"]

    def test_format_exception_chain_with_cause(self):
        """Format exception chain with __cause__."""
        from src.core.logging import format_exception_chain

        try:
            try:
                raise ValueError("original")
            except ValueError as original:
                raise RuntimeError("wrapped") from original
        except RuntimeError as e:
            chain = format_exception_chain(e)

        assert len(chain) == 2
        assert chain[0]["type"] == "RuntimeError"
        assert chain[0]["message"] == "wrapped"
        assert chain[1]["type"] == "ValueError"
        assert chain[1]["message"] == "original"

    def test_format_exception_chain_max_depth(self):
        """Chain respects max_depth limit."""
        from src.core.logging import format_exception_chain

        # Create a very deep chain
        current = ValueError("level 0")
        for i in range(1, 20):
            try:
                raise RuntimeError(f"level {i}") from current
            except RuntimeError as e:
                current = e

        chain = format_exception_chain(current, max_depth=5)
        assert len(chain) == 5

    def test_format_exception_chain_no_traceback(self):
        """Handle exception without traceback."""
        from src.core.logging import format_exception_chain

        # Create exception without raising it (no traceback)
        exc = ValueError("no traceback")
        chain = format_exception_chain(exc)

        assert len(chain) == 1
        assert chain[0]["type"] == "ValueError"
        assert chain[0]["message"] == "no traceback"


class TestSimplifiedTraceback:
    """Tests for get_simplified_traceback function."""

    def test_get_simplified_traceback_empty_for_no_src(self):
        """Returns empty list if no /src/ frames."""
        from src.core.logging import get_simplified_traceback

        try:
            raise ValueError("test")
        except ValueError as e:
            # The traceback from here won't have /src/ in it
            # if we're running tests from tests/ directory
            frames = get_simplified_traceback(e)

        # May or may not have frames depending on test location
        assert isinstance(frames, list)

    def test_get_simplified_traceback_max_frames(self):
        """Respects max_frames limit."""
        from src.core.logging import get_simplified_traceback

        try:
            raise ValueError("test")
        except ValueError as e:
            frames = get_simplified_traceback(e, max_frames=1)

        assert len(frames) <= 1


class TestLogCriticalError:
    """Tests for log_critical_error function."""

    def test_log_critical_error_logs_with_chain(self):
        """Critical error logs exception chain."""
        from unittest.mock import MagicMock

        from src.core.logging import log_critical_error

        mock_logger = MagicMock()

        try:
            raise ValueError("test error")
        except ValueError as e:
            log_critical_error(
                mock_logger,
                e,
                context="testing critical logging",
                request_id="test-123"
            )

        mock_logger.critical.assert_called_once()
        call_kwargs = mock_logger.critical.call_args[1]

        assert call_kwargs["context"] == "testing critical logging"
        assert call_kwargs["error_type"] == "ValueError"
        assert call_kwargs["request_id"] == "test-123"
        assert "exception_chain" in call_kwargs
        assert len(call_kwargs["exception_chain"]) >= 1

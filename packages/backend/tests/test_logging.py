"""Tests for structlog setup — TTY-aware renderer selection."""

from __future__ import annotations

import structlog

from meeting_playbook.logging import setup_logging


def test_setup_logging_uses_console_renderer_when_tty(monkeypatch):
    """When stderr is a TTY, structlog should be configured with ConsoleRenderer."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)

    setup_logging()

    config = structlog.get_config()
    last_processor = config["processors"][-1]
    assert isinstance(last_processor, structlog.dev.ConsoleRenderer)


def test_setup_logging_uses_json_renderer_when_not_tty(monkeypatch):
    """When stderr is not a TTY (e.g., piped), structlog should use JSONRenderer."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)

    setup_logging()

    config = structlog.get_config()
    last_processor = config["processors"][-1]
    assert isinstance(last_processor, structlog.processors.JSONRenderer)


def test_setup_logging_respects_level(monkeypatch):
    """LOG_LEVEL controls the filtering wrapper; DEBUG enables debug logs."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)

    setup_logging(level="DEBUG")
    logger = structlog.get_logger()

    assert logger.is_enabled_for(10)  # logging.DEBUG == 10


def test_setup_logging_default_level_is_info(monkeypatch):
    """Default level is INFO — DEBUG should be filtered out."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)

    setup_logging()
    logger = structlog.get_logger()

    assert logger.is_enabled_for(20)  # INFO
    assert not logger.is_enabled_for(10)  # DEBUG suppressed

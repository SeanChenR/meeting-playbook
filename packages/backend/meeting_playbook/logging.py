"""Structured logging setup for the backend.

TTY-aware renderer: ConsoleRenderer when stderr is a TTY (dev),
JSONRenderer otherwise (production / log shipping).
"""

from __future__ import annotations

import logging as stdlib_logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with a TTY-aware renderer.

    Idempotent — safe to call multiple times (re-configures from scratch each call).

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
    """
    is_tty = sys.stderr.isatty()

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    renderer: object = (
        structlog.dev.ConsoleRenderer() if is_tty else structlog.processors.JSONRenderer()
    )

    numeric_level = getattr(stdlib_logging, level.upper(), stdlib_logging.INFO)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )

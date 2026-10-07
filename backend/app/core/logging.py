"""
core/logging.py
===============
Structured logging setup using structlog.

Configures structlog to output JSON in production and coloured console
output in development. All loggers should be obtained through this module.

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("document.uploaded", document_id="abc123", size_bytes=1024)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_app_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject application-level context into every log record."""
    from app.core.config import settings

    event_dict["app"] = settings.APP_NAME
    event_dict["version"] = settings.APP_VERSION
    event_dict["env"] = settings.APP_ENV
    return event_dict


def configure_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """
    Configure structlog and the standard library logging.

    Parameters
    ----------
    log_level:
        Minimum log level to emit (DEBUG | INFO | WARNING | ERROR | CRITICAL).
    json_logs:
        If True, emit JSON Lines suitable for log aggregation pipelines.
        If False, emit coloured human-readable output for development.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        # add_logger_name requires a stdlib Logger.name attribute which
        # PrintLogger does not have. We bind the name manually via get_logger().
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_app_context,
    ]

    if json_logs:
        # Production: structured JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: readable coloured console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure standard-library logging so third-party libraries
    # (SQLAlchemy, uvicorn, httpx, etc.) feed into structlog.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level),
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Return a bound structlog logger with optional name context.

    Parameters
    ----------
    name:
        Module name, typically __name__.

    Returns
    -------
    A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)

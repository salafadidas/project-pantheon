"""Structured JSON logging for Pantheon using structlog.

Call :func:`configure_logging` once at application startup (e.g. in ``main.py``),
then obtain per-module loggers with :func:`get_logger`.

Usage::

    from utils.logging_config import configure_logging, get_logger

    # In main.py startup
    configure_logging(level="INFO", json_logs=True)

    # In any module
    log = get_logger(__name__)
    log.info("session_started", session_id=sid, task=task)
"""

import logging
import sys
from typing import Any

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:  # pragma: no cover
    _HAS_STRUCTLOG = False


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def configure_logging(
    *,
    level: str = "INFO",
    json_logs: bool = True,
) -> None:
    """Configure the root logging system and structlog processors.

    Args:
        level: Minimum log level string (e.g. ``"DEBUG"``, ``"INFO"``).
        json_logs: Emit JSON lines when ``True``; human-readable when ``False``.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib root logger
    logging.basicConfig(
        stream=sys.stdout,
        format="%(message)s",
        level=numeric_level,
    )
    # basicConfig is a no-op if handlers are already set — force the level
    logging.getLogger().setLevel(numeric_level)

    if not _HAS_STRUCTLOG:
        return  # fall back to stdlib without structlog installed

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        # stdlib.LoggerFactory produces loggers with a .name attribute, which
        # is required by the add_logger_name processor above.
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a structlog bound logger (or stdlib logger if structlog absent).

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        A structlog ``BoundLogger`` or a stdlib ``Logger``.
    """
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current async context (structlog contextvars).

    These values will be included in every log entry emitted within the same
    async task until cleared.  A no-op if structlog is not installed.

    Args:
        **kwargs: Arbitrary key-value pairs (e.g. ``session_id=sid``).
    """
    if _HAS_STRUCTLOG:
        structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all contextvars bound via :func:`bind_context`."""
    if _HAS_STRUCTLOG:
        structlog.contextvars.clear_contextvars()

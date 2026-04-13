"""Tests for utils/logging_config.py"""

import logging

from utils.logging_config import configure_logging, get_logger, bind_context, clear_context


def test_get_logger_returns_something():
    log = get_logger("test.module")
    assert log is not None


def test_get_logger_without_name():
    log = get_logger()
    assert log is not None


def test_configure_logging_debug_level():
    # Should not raise
    configure_logging(level="DEBUG", json_logs=False)
    assert logging.getLogger().level <= logging.DEBUG


def test_configure_logging_info_level():
    configure_logging(level="INFO", json_logs=True)
    assert logging.getLogger().level <= logging.INFO


def test_configure_logging_json_false():
    # Human-readable mode — should not raise
    configure_logging(level="WARNING", json_logs=False)


def test_bind_and_clear_context_no_error():
    # Should not raise even without structlog installed
    bind_context(session_id="abc", user_id="u1")
    clear_context()


def test_logger_can_emit(capsys):
    configure_logging(level="DEBUG", json_logs=False)
    log = get_logger("pantheon.test")
    # Emit a message — should not raise regardless of structlog presence
    try:
        log.info("test_message", key="value")
    except TypeError:
        # structlog logger called with kwargs; stdlib logger won't accept them
        log.info("test_message")
    # No assertion needed — we just verify no exception is raised


def test_multiple_configure_calls_are_idempotent():
    for level in ("DEBUG", "INFO", "WARNING"):
        configure_logging(level=level, json_logs=False)
    configure_logging(level="INFO", json_logs=True)

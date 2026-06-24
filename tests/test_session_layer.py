"""
Tests for core/session.py — session layer as sole producer of thread_id.

These tests use no live Redis; the T1 implementation is stateless.
"""
import pytest
from unittest.mock import AsyncMock

from core.session import SessionManager, make_thread_id


# --------------------------------------------------------------------------- #
# make_thread_id                                                               #
# --------------------------------------------------------------------------- #

def test_make_thread_id_t1_equals_user_id():
    """T1: thread_id must equal user_id regardless of session_id."""
    assert make_thread_id("user_123", "user_123") == "user_123"
    assert make_thread_id("user_abc", "some-uuid") == "user_abc"


def test_make_thread_id_deterministic():
    """Same inputs always produce the same thread_id."""
    assert make_thread_id("u1", "s1") == make_thread_id("u1", "s1")


# --------------------------------------------------------------------------- #
# SessionManager.get_or_create_session                                         #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_or_create_returns_tuple():
    redis_mock = AsyncMock()
    mgr = SessionManager(redis_mock)
    result = await mgr.get_or_create_session("5178700920")
    assert isinstance(result, tuple) and len(result) == 2


@pytest.mark.asyncio
async def test_get_or_create_t1_session_id_equals_user_id():
    """T1: session_id and thread_id both equal user_id."""
    redis_mock = AsyncMock()
    mgr = SessionManager(redis_mock)
    session_id, thread_id = await mgr.get_or_create_session("5178700920")
    assert session_id == "5178700920"
    assert thread_id == "5178700920"


@pytest.mark.asyncio
async def test_get_or_create_uses_make_thread_id():
    """thread_id must always be the result of make_thread_id(user_id, session_id)."""
    redis_mock = AsyncMock()
    mgr = SessionManager(redis_mock)
    user_id = "u_42"
    session_id, thread_id = await mgr.get_or_create_session(user_id)
    assert thread_id == make_thread_id(user_id, session_id)


@pytest.mark.asyncio
async def test_end_session_is_noop_under_t1():
    """T1: end_session must not raise and must not call Redis."""
    redis_mock = AsyncMock()
    mgr = SessionManager(redis_mock)
    await mgr.end_session("user_1", "user_1")
    redis_mock.delete.assert_not_called()


# --------------------------------------------------------------------------- #
# Canonical rule: adapters must not construct thread_id themselves             #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_thread_id_source_is_session_manager():
    """
    Regression: thread_id must come from SessionManager, not hardcoded in callers.

    This test documents the contract; the actual enforcement is in the
    telegram_bot.py call site (thread_id is obtained via get_or_create_session).
    """
    redis_mock = AsyncMock()
    mgr = SessionManager(redis_mock)
    user_id = "telegram_user_999"
    _, thread_id = await mgr.get_or_create_session(user_id)
    # Under T1 this is user_id; under T2 it will be f"{user_id}:{session_id}".
    # Callers should treat thread_id as opaque — never construct it themselves.
    assert thread_id is not None
    assert isinstance(thread_id, str)
    assert len(thread_id) > 0

"""
Tests for core/session.py — session layer as sole producer of thread_id.

S1-TID-1: T2 mode — thread_id = f"{user_id}:{session_id}" (UUID-based sessions).
"""
import pytest
from unittest.mock import AsyncMock

from core.session import SessionManager, make_thread_id, _SESSION_KEY_PREFIX


# --------------------------------------------------------------------------- #
# make_thread_id — T2                                                          #
# --------------------------------------------------------------------------- #

def test_make_thread_id_t2_format():
    """T2: thread_id must be 'user_id:session_id'."""
    assert make_thread_id("user_123", "uuid-abc") == "user_123:uuid-abc"


def test_make_thread_id_does_not_equal_user_id():
    """T2: thread_id must NOT be bare user_id (T1 regression guard)."""
    assert make_thread_id("user_123", "some-uuid") != "user_123"


def test_make_thread_id_deterministic():
    assert make_thread_id("u1", "s1") == make_thread_id("u1", "s1")


# --------------------------------------------------------------------------- #
# SessionManager.get_or_create_session                                         #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_or_create_creates_new_session_when_none_exists():
    """First call should generate a UUID session_id and persist it in Redis."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    mgr = SessionManager(redis_mock)
    session_id, thread_id = await mgr.get_or_create_session("user_42")

    redis_mock.set.assert_called_once()
    call_args = redis_mock.set.call_args
    assert call_args[0][0] == f"{_SESSION_KEY_PREFIX}:user_42"
    assert call_args[0][1] == session_id
    assert thread_id == f"user_42:{session_id}"


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_session():
    """Subsequent calls return the same session_id from Redis."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"existing-uuid-1234"

    mgr = SessionManager(redis_mock)
    session_id, thread_id = await mgr.get_or_create_session("user_42")

    assert session_id == "existing-uuid-1234"
    assert thread_id == "user_42:existing-uuid-1234"
    redis_mock.set.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_handles_str_from_redis():
    """Redis may return str (decode_responses=True) — must handle both."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = "str-session-id"

    mgr = SessionManager(redis_mock)
    session_id, _ = await mgr.get_or_create_session("u1")
    assert session_id == "str-session-id"


@pytest.mark.asyncio
async def test_get_or_create_uses_make_thread_id():
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"fixed-uuid"

    mgr = SessionManager(redis_mock)
    session_id, thread_id = await mgr.get_or_create_session("u99")
    assert thread_id == make_thread_id("u99", session_id)


# --------------------------------------------------------------------------- #
# SessionManager.end_session                                                   #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_end_session_deletes_redis_key():
    redis_mock = AsyncMock()
    redis_mock.delete.return_value = 1

    mgr = SessionManager(redis_mock)
    await mgr.end_session("user_42", "some-uuid")

    redis_mock.delete.assert_called_once_with(f"{_SESSION_KEY_PREFIX}:user_42")


@pytest.mark.asyncio
async def test_end_session_noop_when_no_key():
    redis_mock = AsyncMock()
    redis_mock.delete.return_value = 0

    mgr = SessionManager(redis_mock)
    await mgr.end_session("user_42", "ghost-session")  # must not raise


@pytest.mark.asyncio
async def test_reset_flow_yields_new_session_id():
    """After end_session, get_or_create_session returns a different session_id."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    mgr = SessionManager(redis_mock)
    session_id_1, _ = await mgr.get_or_create_session("user_42")

    redis_mock.delete.return_value = 1
    await mgr.end_session("user_42", session_id_1)

    redis_mock.get.return_value = None
    session_id_2, _ = await mgr.get_or_create_session("user_42")

    assert session_id_1 != session_id_2


# --------------------------------------------------------------------------- #
# Canonical rule: adapters must not construct thread_id themselves             #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_thread_id_is_opaque_to_callers():
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"opaque-uuid"

    mgr = SessionManager(redis_mock)
    _, thread_id = await mgr.get_or_create_session("telegram_user_999")

    assert isinstance(thread_id, str) and len(thread_id) > 0
    assert thread_id.startswith("telegram_user_999:")

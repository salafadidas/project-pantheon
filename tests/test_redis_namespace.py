"""Tests for S1-AUTH-3: per-tenant Redis namespace.

Verifies that every key produced by core/redis_utils.py and
api/v1/sessions.py carries the "pantheon:" prefix, so Pantheon
keys never collide with other applications sharing the same Redis
instance.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.redis_utils import (
    _NS as UTILS_NS,
    _ns,
    add_message_to_buffer,
    clear_message_buffer,
    clear_processing_schedule,
    check_llm_rate_limit,
    get_buffered_messages,
    get_buffered_messages_without_clearing,
    get_last_processed_time,
    is_buffer_active,
    is_processing_scheduled,
    schedule_processing,
    set_buffer_processing,
    set_last_processed_time,
)
from api.v1.sessions import _session_key, _events_channel, _NS as SESSIONS_NS


# ---------------------------------------------------------------------------
# Namespace constant checks
# ---------------------------------------------------------------------------

def test_namespace_constant_is_pantheon():
    assert UTILS_NS == "pantheon"
    assert SESSIONS_NS == "pantheon"


def test_ns_helper_prepends_prefix():
    assert _ns("user:42:buffer") == "pantheon:user:42:buffer"
    assert _ns("rate:llm:99") == "pantheon:rate:llm:99"


# ---------------------------------------------------------------------------
# api/v1/sessions.py key helpers
# ---------------------------------------------------------------------------

def test_session_key_has_namespace():
    key = _session_key("abc-123")
    assert key.startswith("pantheon:"), f"Missing prefix: {key}"
    assert "abc-123" in key


def test_events_channel_has_namespace():
    channel = _events_channel("abc-123")
    assert channel.startswith("pantheon:"), f"Missing prefix: {channel}"
    assert "abc-123" in channel


def test_session_key_and_events_channel_are_distinct():
    assert _session_key("x") != _events_channel("x")


# ---------------------------------------------------------------------------
# core/redis_utils.py — key shapes via mock Redis
# ---------------------------------------------------------------------------

def _make_redis():
    redis = AsyncMock()
    pipe = AsyncMock()
    # pipeline() is a sync call that returns an async context manager
    pipeline_cm = MagicMock()
    pipeline_cm.__aenter__ = AsyncMock(return_value=pipe)
    pipeline_cm.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=pipeline_cm)
    return redis, pipe


@pytest.mark.asyncio
async def test_add_message_to_buffer_uses_namespaced_key():
    redis, pipe = _make_redis()
    await add_message_to_buffer(redis, "u1", "hello")
    pipe.rpush.assert_awaited_once()
    key_used = pipe.rpush.call_args[0][0]
    assert key_used == "pantheon:user:u1:buffer", key_used


@pytest.mark.asyncio
async def test_clear_message_buffer_uses_namespaced_key():
    redis = AsyncMock()
    await clear_message_buffer(redis, "u1")
    redis.delete.assert_awaited_once_with("pantheon:user:u1:buffer")


@pytest.mark.asyncio
async def test_is_buffer_active_uses_namespaced_key():
    redis = AsyncMock()
    redis.exists.return_value = 0
    await is_buffer_active(redis, "u1")
    redis.exists.assert_awaited_once_with("pantheon:user:u1:processing")


@pytest.mark.asyncio
async def test_set_buffer_processing_uses_namespaced_key():
    redis = AsyncMock()
    await set_buffer_processing(redis, "u1", timeout=10)
    redis.setex.assert_awaited_once_with("pantheon:user:u1:processing", 10, "1")


@pytest.mark.asyncio
async def test_schedule_processing_uses_namespaced_key():
    redis = AsyncMock()
    redis.setnx.return_value = True
    await schedule_processing(redis, "u1", 5.0)
    redis.setnx.assert_awaited_once()
    key_used = redis.setnx.call_args[0][0]
    assert key_used == "pantheon:user:u1:scheduled", key_used


@pytest.mark.asyncio
async def test_is_processing_scheduled_uses_namespaced_key():
    redis = AsyncMock()
    redis.exists.return_value = 0
    await is_processing_scheduled(redis, "u1")
    redis.exists.assert_awaited_once_with("pantheon:user:u1:scheduled")


@pytest.mark.asyncio
async def test_clear_processing_schedule_uses_namespaced_key():
    redis = AsyncMock()
    await clear_processing_schedule(redis, "u1")
    redis.delete.assert_awaited_once_with("pantheon:user:u1:scheduled")


@pytest.mark.asyncio
async def test_get_last_processed_time_uses_namespaced_key():
    redis = AsyncMock()
    redis.get.return_value = None
    await get_last_processed_time(redis, "u1")
    redis.get.assert_awaited_once_with("pantheon:user:u1:last_processed")


@pytest.mark.asyncio
async def test_set_last_processed_time_uses_namespaced_key():
    redis = AsyncMock()
    await set_last_processed_time(redis, "u1", 1234567890.0)
    redis.set.assert_awaited_once_with("pantheon:user:u1:last_processed", "1234567890.0")


@pytest.mark.asyncio
async def test_check_llm_rate_limit_uses_namespaced_key():
    redis = AsyncMock()
    redis.incr.return_value = 1
    await check_llm_rate_limit(redis, "u1")
    redis.incr.assert_awaited_once_with("pantheon:rate:llm:u1")

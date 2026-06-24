"""Tests for api/middleware/auth.py — S1-AUTH-2 API-key middleware.

All tests use mocked pool and request objects — no live DB required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.middleware.auth import APIKeyMiddleware, _hash_key, _lookup_key, _EXEMPT_PREFIXES


# --------------------------------------------------------------------------- #
# _hash_key                                                                    #
# --------------------------------------------------------------------------- #

def test_hash_key_returns_sha256_hex():
    result = _hash_key("my-secret-key")
    import hashlib
    expected = hashlib.sha256(b"my-secret-key").hexdigest()
    assert result == expected


def test_hash_key_is_deterministic():
    assert _hash_key("abc") == _hash_key("abc")


def test_hash_key_differs_for_different_inputs():
    assert _hash_key("key1") != _hash_key("key2")


def test_hash_key_64_chars():
    """SHA-256 hex digest is always 64 characters."""
    assert len(_hash_key("anything")) == 64


# --------------------------------------------------------------------------- #
# _lookup_key                                                                  #
# --------------------------------------------------------------------------- #

async def test_lookup_key_returns_true_when_found():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "some-uuid"})
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.connection = MagicMock(return_value=cm)

    result = await _lookup_key(pool, "abc123hash")
    assert result is True


async def test_lookup_key_returns_false_when_not_found():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.connection = MagicMock(return_value=cm)

    result = await _lookup_key(pool, "nonexistent")
    assert result is False


async def test_lookup_key_returns_false_on_exception():
    pool = MagicMock()
    pool.connection = MagicMock(side_effect=Exception("DB down"))

    result = await _lookup_key(pool, "anyhash")
    assert result is False


# --------------------------------------------------------------------------- #
# Middleware dispatch — exempt routes                                          #
# --------------------------------------------------------------------------- #

def _make_request(path: str, headers: dict = None, pool=None):
    """Build a minimal mock Request."""
    request = MagicMock()
    request.url.path = path
    request.headers = headers or {}
    request.app.state.pg_pool = pool
    return request


async def test_health_route_is_exempt():
    """Requests to /api/v1/health must bypass auth unconditionally."""
    mw = APIKeyMiddleware(app=MagicMock())
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    request = _make_request("/api/v1/health")
    request.headers.get = MagicMock(return_value="")

    await mw.dispatch(request, call_next)
    call_next.assert_called_once()


async def test_docs_route_is_exempt():
    mw = APIKeyMiddleware(app=MagicMock())
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    request = _make_request("/docs")
    await mw.dispatch(request, call_next)
    call_next.assert_called_once()


async def test_non_api_path_is_exempt():
    mw = APIKeyMiddleware(app=MagicMock())
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    request = _make_request("/static/logo.png")
    await mw.dispatch(request, call_next)
    call_next.assert_called_once()


# --------------------------------------------------------------------------- #
# Middleware dispatch — auth enforcement                                       #
# --------------------------------------------------------------------------- #

async def test_missing_header_returns_401():
    mw = APIKeyMiddleware(app=MagicMock())
    call_next = AsyncMock()
    request = _make_request("/api/v1/sessions")
    request.headers = {"X-API-Key": ""}

    response = await mw.dispatch(request, call_next)
    assert response.status_code == 401
    call_next.assert_not_called()


async def test_invalid_key_returns_401():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.connection = MagicMock(return_value=cm)

    mw = APIKeyMiddleware(app=MagicMock())
    call_next = AsyncMock()
    request = _make_request("/api/v1/sessions", pool=pool)
    request.headers = {"X-API-Key": "bad-key"}

    response = await mw.dispatch(request, call_next)
    assert response.status_code == 401
    call_next.assert_not_called()


async def test_valid_key_calls_next():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "tenant-uuid"})
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.connection = MagicMock(return_value=cm)

    mw = APIKeyMiddleware(app=MagicMock())
    next_response = MagicMock(status_code=202)
    call_next = AsyncMock(return_value=next_response)
    request = _make_request("/api/v1/sessions", pool=pool)
    request.headers = {"X-API-Key": "valid-raw-key"}

    response = await mw.dispatch(request, call_next)
    assert response.status_code == 202
    call_next.assert_called_once()


async def test_pool_unavailable_returns_503():
    """Before lifespan startup, pg_pool is None — must return 503, not crash."""
    mw = APIKeyMiddleware(app=MagicMock())
    call_next = AsyncMock()
    request = _make_request("/api/v1/sessions", pool=None)
    request.headers = {"X-API-Key": "some-key"}

    response = await mw.dispatch(request, call_next)
    assert response.status_code == 503
    call_next.assert_not_called()


# --------------------------------------------------------------------------- #
# Exempt prefix coverage                                                       #
# --------------------------------------------------------------------------- #

def test_exempt_prefixes_includes_health():
    assert "/api/v1/health" in _EXEMPT_PREFIXES


def test_exempt_prefixes_includes_docs():
    assert "/docs" in _EXEMPT_PREFIXES

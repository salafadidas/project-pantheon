"""Regression tests for clear_user_data (issue #25).

Three bugs fixed:
  Bug 1 — store DELETE silently rolled back when store_vectors table missing
  Bug 2 — checkpoint_writes never deleted
  Bug 3 — no cross-section atomicity (accepted-risk: independent sections,
           each idempotent; saga compensation deferred)

All tests use AsyncMock / MagicMock — no live DB or Redis required.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, call

import pytest

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

USER_ID = "5178700920"


def _make_cursor(rowcount: int = 1) -> AsyncMock:
    cur = AsyncMock()
    cur.rowcount = rowcount
    return cur


def _make_conn_cm(conn: AsyncMock) -> AsyncMock:
    """Wrap a conn mock in an async context manager."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_checkpoint_conn(
    cw_rowcount: int = 13,
    ck_rowcount: int = 6,
    raises: Exception | None = None,
) -> AsyncMock:
    conn = AsyncMock()
    if raises:
        conn.execute = AsyncMock(side_effect=raises)
    else:
        conn.execute = AsyncMock(side_effect=[
            _make_cursor(cw_rowcount),   # checkpoint_writes DELETE
            _make_cursor(ck_rowcount),   # checkpoints DELETE
        ])
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=None)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)
    return conn


def _make_store_conn(rowcount: int = 3, raises: Exception | None = None) -> AsyncMock:
    conn = AsyncMock()
    if raises:
        conn.execute = AsyncMock(side_effect=raises)
    else:
        conn.execute = AsyncMock(return_value=_make_cursor(rowcount))
    return conn


def _make_vectors_conn(rowcount: int = 2, raises: Exception | None = None) -> AsyncMock:
    conn = AsyncMock()
    if raises:
        conn.execute = AsyncMock(side_effect=raises)
    else:
        conn.execute = AsyncMock(return_value=_make_cursor(rowcount))
    return conn


def _make_pool(*conns) -> tuple[MagicMock, list]:
    """Return (pool, [conn, ...]).  pool.connection() yields conns in order."""
    pool = MagicMock()
    cms = [_make_conn_cm(c) for c in conns]
    pool.connection = MagicMock(side_effect=list(cms))
    return pool, list(conns)


def _make_redis(key_count: int = 2, raises: Exception | None = None) -> AsyncMock:
    redis = AsyncMock()
    if raises:
        redis.keys = AsyncMock(side_effect=raises)
    else:
        redis.keys = AsyncMock(return_value=[f"user:{USER_ID}:k{i}" for i in range(key_count)])
    redis.delete = AsyncMock(return_value=key_count)
    return redis


def _make_store_obj() -> AsyncMock:
    s = AsyncMock()
    s.adelete = AsyncMock(return_value=None)
    return s


# --------------------------------------------------------------------------- #
# Bug 2 regression — checkpoint_writes must be deleted                        #
# --------------------------------------------------------------------------- #

async def test_checkpoint_writes_deleted(monkeypatch):
    """Bug 2: checkpoint_writes DELETE must be issued before checkpoints DELETE."""
    monkeypatch.setenv("EMBED_MODEL", "none")

    ck_conn = _make_checkpoint_conn()
    store_conn = _make_store_conn()
    pool, conns = _make_pool(ck_conn, store_conn)

    from db.user_data import clear_user_data
    await clear_user_data(USER_ID, _make_redis(), pool, _make_store_obj())

    execute_calls = ck_conn.execute.call_args_list
    assert len(execute_calls) == 2, (
        f"Expected 2 execute calls on checkpoint conn, got {len(execute_calls)}"
    )

    first_sql = execute_calls[0].args[0]
    second_sql = execute_calls[1].args[0]

    assert "checkpoint_writes" in first_sql.lower(), (
        f"First DELETE must target checkpoint_writes, got: {first_sql!r}"
    )
    assert "checkpoints" in second_sql.lower(), (
        f"Second DELETE must target checkpoints, got: {second_sql!r}"
    )
    assert execute_calls[0].args[1] == (USER_ID,)
    assert execute_calls[1].args[1] == (USER_ID,)


# --------------------------------------------------------------------------- #
# Bug 1 regression — store DELETE not rolled back when store_vectors missing  #
# --------------------------------------------------------------------------- #

async def test_store_delete_succeeds_when_store_vectors_missing(monkeypatch):
    """Bug 1: store DELETE must complete even when store_vectors table is absent."""
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")

    ck_conn = _make_checkpoint_conn()
    store_conn = _make_store_conn(rowcount=3)
    vecs_conn = _make_vectors_conn(
        raises=Exception('relation "store_vectors" does not exist')
    )
    pool, conns = _make_pool(ck_conn, store_conn, vecs_conn)

    from db.user_data import clear_user_data
    # Must not raise
    await clear_user_data(USER_ID, _make_redis(), pool, _make_store_obj())

    store_calls = store_conn.execute.call_args_list
    assert len(store_calls) == 1
    assert "delete from store" in store_calls[0].args[0].lower()
    assert store_calls[0].args[1] == (str(USER_ID),)


async def test_store_delete_skips_vectors_when_embed_model_none(monkeypatch):
    """Bug 1: when EMBED_MODEL=none, store_vectors DELETE must not be attempted."""
    monkeypatch.setenv("EMBED_MODEL", "none")

    ck_conn = _make_checkpoint_conn()
    store_conn = _make_store_conn()
    pool, conns = _make_pool(ck_conn, store_conn)  # only 2 CMs — 3rd would explode

    from db.user_data import clear_user_data
    await clear_user_data(USER_ID, _make_redis(), pool, _make_store_obj())

    # Exactly 2 pool.connection() calls: checkpoint + store
    assert pool.connection.call_count == 2, (
        f"Expected 2 pool.connection() calls, got {pool.connection.call_count}"
    )


# --------------------------------------------------------------------------- #
# Bug 3 — cross-section independence (accepted-risk verification)             #
# --------------------------------------------------------------------------- #

async def test_redis_failure_does_not_abort_checkpoints_section(monkeypatch):
    """Bug 3: Redis failure must not prevent checkpoint delete."""
    monkeypatch.setenv("EMBED_MODEL", "none")

    ck_conn = _make_checkpoint_conn()
    store_conn = _make_store_conn()
    pool, conns = _make_pool(ck_conn, store_conn)

    from db.user_data import clear_user_data
    await clear_user_data(
        USER_ID,
        _make_redis(raises=ConnectionError("Redis down")),
        pool,
        _make_store_obj(),
    )

    assert ck_conn.execute.call_count == 2, (
        "checkpoints + checkpoint_writes DELETE must run even after Redis failure"
    )


async def test_checkpoints_failure_does_not_abort_store_section(monkeypatch):
    """Bug 3: checkpoints failure must not prevent store delete."""
    monkeypatch.setenv("EMBED_MODEL", "none")

    ck_conn = _make_checkpoint_conn(raises=Exception("DB connection error"))
    store_conn = _make_store_conn(rowcount=3)
    pool, conns = _make_pool(ck_conn, store_conn)

    from db.user_data import clear_user_data
    await clear_user_data(USER_ID, _make_redis(), pool, _make_store_obj())

    assert store_conn.execute.call_count == 1, (
        "store DELETE must run even after checkpoints section failure"
    )


# --------------------------------------------------------------------------- #
# Happy path — full delete EMBED_MODEL=none                                   #
# --------------------------------------------------------------------------- #

async def test_full_delete_embed_model_none(monkeypatch):
    """Row 7 happy path with EMBED_MODEL=none."""
    monkeypatch.setenv("EMBED_MODEL", "none")

    ck_conn = _make_checkpoint_conn(cw_rowcount=13, ck_rowcount=6)
    store_conn = _make_store_conn(rowcount=3)
    pool, conns = _make_pool(ck_conn, store_conn)
    redis = _make_redis(key_count=2)
    store_obj = _make_store_obj()

    from db.user_data import clear_user_data
    await clear_user_data(USER_ID, redis, pool, store_obj)

    redis.keys.assert_called_once_with(f"user:{USER_ID}:*")
    redis.delete.assert_called_once()
    assert ck_conn.execute.call_count == 2
    assert store_conn.execute.call_count == 1
    store_obj.adelete.assert_called_once_with(("memories",), USER_ID)


# --------------------------------------------------------------------------- #
# Happy path — full delete with embedding enabled                             #
# --------------------------------------------------------------------------- #

async def test_full_delete_with_vectors(monkeypatch):
    """Row 7 full path: store_vectors also deleted when EMBED_MODEL is set."""
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")

    ck_conn = _make_checkpoint_conn(cw_rowcount=13, ck_rowcount=6)
    store_conn = _make_store_conn(rowcount=3)
    vecs_conn = _make_vectors_conn(rowcount=3)
    pool, conns = _make_pool(ck_conn, store_conn, vecs_conn)
    redis = _make_redis(key_count=2)
    store_obj = _make_store_obj()

    from db.user_data import clear_user_data
    await clear_user_data(USER_ID, redis, pool, store_obj)

    assert pool.connection.call_count == 3
    vecs_calls = vecs_conn.execute.call_args_list
    assert len(vecs_calls) == 1
    assert "store_vectors" in vecs_calls[0].args[0].lower()

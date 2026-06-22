"""Tests for S1-NS-1 namespace migration + SPRINT1-CKPT-MIG checkpoint migration.

All tests use AsyncMock — no live DB required.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SQL_DIR = Path(__file__).parent.parent / "db" / "migrations"


# --------------------------------------------------------------------------- #
# SQL file checks                                                              #
# --------------------------------------------------------------------------- #

def test_checkpoint_migration_sql_exists():
    assert (SQL_DIR / "002_checkpoint_migration.sql").exists()


def test_namespace_migration_sql_exists():
    assert (SQL_DIR / "003_namespace_migration.sql").exists()


def test_checkpoint_migration_idempotent_guard():
    """Both UPDATE statements must include NOT LIKE '%:%' guard."""
    sql = (SQL_DIR / "002_checkpoint_migration.sql").read_text().lower()
    assert "not like '%:%'" in sql, "idempotency guard missing from checkpoint migration SQL"


def test_checkpoint_migration_covers_checkpoint_writes():
    """checkpoint_writes must be updated alongside checkpoints."""
    sql = (SQL_DIR / "002_checkpoint_migration.sql").read_text().lower()
    assert "update checkpoint_writes" in sql


def test_namespace_migration_insert_not_exists():
    """003 must use INSERT ... WHERE NOT EXISTS for idempotency."""
    sql = (SQL_DIR / "003_namespace_migration.sql").read_text().lower()
    assert "not exists" in sql


def test_namespace_migration_preserves_old_rows():
    """003 must NOT delete old rows (old rows needed for dual-read fallback)."""
    raw = (SQL_DIR / "003_namespace_migration.sql").read_text()
    sql = " ".join(l for l in raw.splitlines() if not l.strip().startswith("--")).lower()
    assert "delete" not in sql, "003 must not delete old store rows"


# --------------------------------------------------------------------------- #
# namespace helper unit tests                                                  #
# --------------------------------------------------------------------------- #

def test_new_namespace():
    from agent.agent_factory import new_namespace
    assert new_namespace("tenant-abc", "user-123") == ("tenant-abc", "user-123")


def test_legacy_namespace():
    from agent.agent_factory import legacy_namespace
    assert legacy_namespace("user-123") == ("user-123",)


def test_new_namespace_uses_str():
    from agent.agent_factory import new_namespace
    ns = new_namespace(123, 456)
    assert ns == ("123", "456")


# --------------------------------------------------------------------------- #
# dual-read: new namespace hit                                                 #
# --------------------------------------------------------------------------- #

async def test_dual_read_returns_new_namespace_results():
    """When new namespace has results, legacy namespace must not be queried."""
    from agent.agent_factory import _search_with_dual_read

    mock_item = MagicMock()
    mock_item.value = {"content": "new memory"}

    store = AsyncMock()
    store.asearch = AsyncMock(return_value=[mock_item])

    results = await _search_with_dual_read(store, "t1", "u1", "query")

    assert len(results) == 1
    assert store.asearch.call_count == 1
    called_ns = store.asearch.call_args.args[0]
    assert called_ns == ("t1", "u1"), f"expected new namespace, got {called_ns}"


# --------------------------------------------------------------------------- #
# dual-read: new namespace miss → fallback to legacy                          #
# --------------------------------------------------------------------------- #

async def test_dual_read_falls_back_to_legacy_when_new_empty():
    """When new namespace is empty, legacy (user_id,) must be tried."""
    from agent.agent_factory import _search_with_dual_read

    legacy_item = MagicMock()
    legacy_item.value = {"content": "old memory"}

    store = AsyncMock()
    # first call (new ns) returns empty; second call (legacy) returns item
    store.asearch = AsyncMock(side_effect=[[], [legacy_item]])

    results = await _search_with_dual_read(store, "t1", "u1", "query")

    assert len(results) == 1
    assert store.asearch.call_count == 2
    legacy_call_ns = store.asearch.call_args_list[1].args[0]
    assert legacy_call_ns == ("u1",), f"expected legacy namespace, got {legacy_call_ns}"


# --------------------------------------------------------------------------- #
# dual-read: both empty                                                        #
# --------------------------------------------------------------------------- #

async def test_dual_read_returns_empty_when_both_miss():
    from agent.agent_factory import _search_with_dual_read

    store = AsyncMock()
    store.asearch = AsyncMock(return_value=[])

    results = await _search_with_dual_read(store, "t1", "u1", "query")

    assert results == []
    assert store.asearch.call_count == 2


# --------------------------------------------------------------------------- #
# write goes to new namespace only                                             #
# --------------------------------------------------------------------------- #

async def test_create_agent_uses_new_namespace_for_write_tool(monkeypatch):
    """manage_memory_tool must be created with new (tenant_id, user_id) namespace."""
    captured = {}

    def fake_create_manage_memory_tool(namespace):
        captured["namespace"] = namespace
        return MagicMock()

    def fake_create_react_agent(*args, **kwargs):
        return MagicMock()

    monkeypatch.setattr("agent.agent_factory.create_manage_memory_tool",
                        fake_create_manage_memory_tool)
    monkeypatch.setattr("agent.agent_factory.create_react_agent",
                        fake_create_react_agent)

    pool = MagicMock()
    pool.connection = MagicMock()

    store_mock = AsyncMock()
    store_mock.asearch = AsyncMock(return_value=[])

    monkeypatch.setattr("agent.agent_factory.create_memory_store",
                        AsyncMock(return_value=store_mock))

    provider_mock = MagicMock()
    provider_mock.get_chat_model = MagicMock(return_value=MagicMock())
    provider_mock.get_litellm_model_string = MagicMock(return_value="claude-haiku")
    monkeypatch.setattr("agent.agent_factory.get_llm_provider",
                        MagicMock(return_value=provider_mock))

    checkpointer_mock = MagicMock()
    monkeypatch.setattr("agent.agent_factory.AsyncPostgresSaver",
                        MagicMock(return_value=checkpointer_mock))

    from agent.agent_factory import AgentFactory
    await AgentFactory.create_agent(
        pg_connection="postgresql://localhost/test",
        pool=pool,
        llm_model="claude-haiku",
        vector_dims=1536,
        embed_model="none",
        user_id="u123",
        tenant_id="t456",
    )

    assert captured.get("namespace") == ("t456", "u123"), (
        f"write tool namespace must be (tenant_id, user_id), got {captured.get('namespace')}"
    )


async def test_create_agent_synthesizes_tenant_when_none(monkeypatch):
    """When tenant_id=None, effective_tenant_id must be synthesized as user_id."""
    captured = {}

    def fake_create_manage_memory_tool(namespace):
        captured["namespace"] = namespace
        return MagicMock()

    def fake_create_react_agent(*args, **kwargs):
        return MagicMock()

    monkeypatch.setattr("agent.agent_factory.create_manage_memory_tool",
                        fake_create_manage_memory_tool)
    monkeypatch.setattr("agent.agent_factory.create_react_agent",
                        fake_create_react_agent)

    pool = MagicMock()
    store_mock = AsyncMock()
    store_mock.asearch = AsyncMock(return_value=[])

    monkeypatch.setattr("agent.agent_factory.create_memory_store",
                        AsyncMock(return_value=store_mock))

    provider_mock = MagicMock()
    provider_mock.get_chat_model = MagicMock(return_value=MagicMock())
    provider_mock.get_litellm_model_string = MagicMock(return_value="claude-haiku")
    monkeypatch.setattr("agent.agent_factory.get_llm_provider",
                        MagicMock(return_value=provider_mock))
    monkeypatch.setattr("agent.agent_factory.AsyncPostgresSaver",
                        MagicMock(return_value=MagicMock()))

    from agent.agent_factory import AgentFactory
    await AgentFactory.create_agent(
        pg_connection="postgresql://localhost/test",
        pool=pool,
        llm_model="claude-haiku",
        vector_dims=1536,
        embed_model="none",
        user_id="u999",
        tenant_id=None,   # synthesize
    )

    # synthesized tenant = user_id
    assert captured.get("namespace") == ("u999", "u999"), (
        f"synthesized namespace must be (user_id, user_id), got {captured.get('namespace')}"
    )

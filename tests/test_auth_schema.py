"""Tests for S1-AUTH-1 auth schema setup.

Verifies that:
  1. setup_auth_schema() executes the DDL via the pool (smoke test)
  2. The SQL file contains all required CREATE TABLE statements
  3. All required unique constraints are present
  4. No forbidden columns exist in the minimal schema (deferred columns check)

No live DB required — pool is mocked.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SQL_FILE = Path(__file__).parent.parent / "db" / "migrations" / "001_auth_schema.sql"


# --------------------------------------------------------------------------- #
# SQL file content checks (no DB needed)                                      #
# --------------------------------------------------------------------------- #

def test_sql_file_exists():
    assert SQL_FILE.exists(), f"Migration file not found: {SQL_FILE}"


def test_tenants_table_defined():
    sql = SQL_FILE.read_text().lower()
    assert "create table if not exists tenants" in sql


def test_users_table_defined():
    sql = SQL_FILE.read_text().lower()
    assert "create table if not exists users" in sql


def test_api_keys_table_defined():
    sql = SQL_FILE.read_text().lower()
    assert "create table if not exists api_keys" in sql


def test_users_tenant_id_not_null():
    """tenant_id on users must be NOT NULL — every user must belong to a tenant."""
    sql = SQL_FILE.read_text().lower()
    # find users table block and confirm not null on tenant_id
    users_block_start = sql.find("create table if not exists users")
    users_block_end = sql.find(";", users_block_start)
    users_block = sql[users_block_start:users_block_end]
    assert "tenant_id" in users_block
    assert "not null" in users_block


def test_users_tenant_id_foreign_key():
    sql = SQL_FILE.read_text().lower()
    assert "references tenants" in sql


def test_api_keys_tenant_id_foreign_key():
    sql = SQL_FILE.read_text().lower()
    # api_keys table block
    ak_start = sql.find("create table if not exists api_keys")
    ak_end = sql.find(";", ak_start)
    ak_block = sql[ak_start:ak_end]
    assert "references tenants" in ak_block


def test_users_telegram_user_id_unique_index():
    sql = SQL_FILE.read_text().lower()
    assert "unique index if not exists users_telegram_user_id_uidx" in sql
    assert "on users (telegram_user_id)" in sql


def test_api_keys_key_hash_unique_index():
    sql = SQL_FILE.read_text().lower()
    assert "unique index if not exists api_keys_key_hash_uidx" in sql
    assert "on api_keys (key_hash)" in sql


def test_no_deferred_columns_in_schema():
    """Deferred columns must NOT be in the minimal schema."""
    raw = SQL_FILE.read_text()
    lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
    sql = " ".join(lines).lower()
    forbidden = ["created_at", "updated_at", "is_active", "scopes", "last_used_at"]
    present = [col for col in forbidden if col in sql]
    assert not present, "Deferred columns in schema: " + str(present)


def test_schema_is_idempotent():
    """Every CREATE TABLE and CREATE INDEX must use IF NOT EXISTS."""
    sql = SQL_FILE.read_text()
    create_stmts = re.findall(r"CREATE\s+(UNIQUE\s+)?(?:TABLE|INDEX)\s+(\w+)", sql, re.IGNORECASE)
    non_idempotent = []
    for match in re.finditer(r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)(?!\s+IF\s+NOT\s+EXISTS)", sql, re.IGNORECASE):
        non_idempotent.append(match.group(0))
    assert not non_idempotent, (
        f"Non-idempotent CREATE statements (missing IF NOT EXISTS): {non_idempotent}"
    )


# --------------------------------------------------------------------------- #
# setup_auth_schema() execution smoke test (mocked pool)                      #
# --------------------------------------------------------------------------- #

async def test_setup_auth_schema_executes_sql():
    """setup_auth_schema() must call conn.execute() with the DDL content."""
    conn = AsyncMock()
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=None)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.connection = MagicMock(return_value=cm)

    from db.schema import setup_auth_schema
    await setup_auth_schema(pool)

    pool.connection.assert_called_once()
    conn.execute.assert_called_once()
    sql_arg = conn.execute.call_args.args[0]
    assert "CREATE TABLE IF NOT EXISTS tenants" in sql_arg
    assert "CREATE TABLE IF NOT EXISTS users" in sql_arg
    assert "CREATE TABLE IF NOT EXISTS api_keys" in sql_arg


async def test_setup_auth_schema_uses_transaction():
    """setup_auth_schema() must wrap DDL in a transaction."""
    conn = AsyncMock()
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=None)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.connection = MagicMock(return_value=cm)

    from db.schema import setup_auth_schema
    await setup_auth_schema(pool)

    conn.transaction.assert_called_once()

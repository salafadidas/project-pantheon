"""
Auth schema setup — S1-AUTH-1.

Provides setup_auth_schema(), called once at startup after setup_database().
All DDL is idempotent (IF NOT EXISTS); safe to run on every boot.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

# Path to the SQL migration file, relative to this module.
_MIGRATION_FILE = Path(__file__).parent / "migrations" / "001_auth_schema.sql"


async def setup_auth_schema(pool) -> None:
    """Create tenants / users / api_keys tables if they do not exist.

    Reads ``db/migrations/001_auth_schema.sql`` and executes it via the
    supplied connection pool.  All statements are idempotent — safe to call
    on every startup.

    Args:
        pool: AsyncConnectionPool connected to the Pantheon Postgres DB.
    """
    sql = _MIGRATION_FILE.read_text()

    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(sql)

    logger.info("S1-AUTH-1: auth schema verified / created (tenants, users, api_keys)")


# --------------------------------------------------------------------------- #
# Sprint 1 migration functions                                                 #
# --------------------------------------------------------------------------- #

_CKPT_MIGRATION = Path(__file__).parent / "migrations" / "002_checkpoint_migration.sql"
_NS_MIGRATION   = Path(__file__).parent / "migrations" / "003_namespace_migration.sql"


async def run_checkpoint_migration(pool) -> None:
    """Rename existing checkpoints thread_id=user_id → thread_id=user_id:legacy.

    SPRINT1-CKPT-MIG — idempotent, safe to run on every startup during
    the migration compatibility window (Sprint 1-3).
    Logs pre/post row counts for verification.
    """
    sql = _CKPT_MIGRATION.read_text()

    async with pool.connection() as conn:
        # Pre-counts
        r = await conn.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id NOT LIKE '%:%'"
        )
        row = await r.fetchone()
        pre_ck = row[0] if row else 0

        r = await conn.execute(
            "SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id NOT LIKE '%:%'"
        )
        row = await r.fetchone()
        pre_cw = row[0] if row else 0

        if pre_ck == 0 and pre_cw == 0:
            logger.info(
                "SPRINT1-CKPT-MIG: no legacy thread_ids found — already migrated or empty"
            )
            return

        async with conn.transaction():
            await conn.execute(sql)

        # Post-counts
        r = await conn.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id LIKE '%:legacy'"
        )
        row = await r.fetchone()
        post_ck = row[0] if row else 0

        r = await conn.execute(
            "SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id LIKE '%:legacy'"
        )
        row = await r.fetchone()
        post_cw = row[0] if row else 0

    logger.info(
        "SPRINT1-CKPT-MIG: checkpoints %d→%d :legacy, checkpoint_writes %d→%d :legacy",
        pre_ck, post_ck, pre_cw, post_cw,
    )


async def run_namespace_migration(pool) -> None:
    """Copy store rows from (user_id,) prefix to (tenant_id/user_id) prefix.

    S1-NS-1 backfill — idempotent (INSERT WHERE NOT EXISTS).
    Old rows are preserved for dual-read fallback window.
    """
    sql = _NS_MIGRATION.read_text()

    async with pool.connection() as conn:
        r = await conn.execute(
            "SELECT COUNT(*) FROM store WHERE prefix NOT LIKE '%/%'"
        )
        row = await r.fetchone()
        pre = row[0] if row else 0

        if pre == 0:
            logger.info("S1-NS-1 backfill: no legacy-shape store rows found")
            return

        async with conn.transaction():
            await conn.execute(sql)

        r = await conn.execute(
            "SELECT COUNT(*) FROM store WHERE prefix LIKE '%/%'"
        )
        row = await r.fetchone()
        post = row[0] if row else 0

    logger.info(
        "S1-NS-1 backfill: store rows legacy=%d, new-shape=%d (delta +%d)",
        pre, post, post - (post - pre),
    )

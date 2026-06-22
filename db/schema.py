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

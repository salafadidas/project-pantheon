"""
User data management utilities.
"""

import os
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from psycopg_pool import AsyncConnectionPool
    from langgraph.store.postgres import AsyncPostgresStore

logger = logging.getLogger(__name__)


async def clear_user_data(
    user_id: str,
    redis,   # Redis
    pool,    # AsyncConnectionPool
    store,   # AsyncPostgresStore
) -> None:
    """Clear all data for a user to start fresh.

    Deletes, in order:
      1. Redis keys matching ``user:<user_id>:*``
      2. ``checkpoint_writes`` rows for the user's thread_id
      3. ``checkpoints`` rows for the user's thread_id
      4. ``store`` rows for the user's namespace prefix
      5. ``store_vectors`` rows (only when the table exists)
      6. Legacy ``store.adelete`` call for backward-compat rows

    Bug-fix notes (issue #25):
      - Bug 1: store and store_vectors DELETE used to share one connection
        context. When EMBED_MODEL=none the store_vectors table does not exist,
        causing psycopg3 to roll back the entire transaction and silently
        leaving store rows intact.
        Fix: each DELETE now runs in its own connection context.
      - Bug 2: checkpoint_writes was never deleted. Orphaned rows cause
        INVALID_CHAT_HISTORY on the next session.
        Fix: checkpoint_writes is deleted in the same transaction as
        checkpoints.
      - Bug 3: no cross-section atomicity (accepted-risk approach):
        each section is independent and idempotent; a failure in one section
        is logged with enough context for manual reconciliation but does not
        abort subsequent sections.
    """

    embed_model = os.environ.get("EMBED_MODEL", "").strip().lower()
    vectors_enabled = embed_model != "none" and embed_model != ""

    # ------------------------------------------------------------------ #
    # Section 1 — Redis                                                    #
    # ------------------------------------------------------------------ #
    try:
        user_keys = await redis.keys(f"user:{user_id}:*")
        if user_keys:
            await redis.delete(*user_keys)
            logger.info("Cleared %d Redis keys for user %s", len(user_keys), user_id)
        else:
            logger.debug("No Redis keys found for user %s", user_id)
    except Exception as exc:
        logger.error(
            "Section 1 FAILED — Redis clear for user %s: %s",
            user_id, exc, exc_info=True,
        )

    # ------------------------------------------------------------------ #
    # Section 2 — Checkpoints (checkpoint_writes + checkpoints)           #
    # Bug 2 fix: checkpoint_writes deleted alongside checkpoints           #
    # ------------------------------------------------------------------ #
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                # checkpoint_writes before checkpoints (FK order)
                cw = await conn.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                    (user_id,),
                )
                ck = await conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id = %s",
                    (user_id,),
                )
        logger.info(
            "Cleared checkpoints (%d rows) + checkpoint_writes (%d rows) for user %s",
            ck.rowcount, cw.rowcount, user_id,
        )
    except Exception as exc:
        logger.error(
            "Section 2 FAILED — checkpoints clear for user %s: %s",
            user_id, exc, exc_info=True,
        )

    # ------------------------------------------------------------------ #
    # Section 3a — store (always)                                          #
    # Bug 1 fix: own connection context, independent of store_vectors      #
    # ------------------------------------------------------------------ #
    try:
        async with pool.connection() as conn:
            result = await conn.execute(
                "DELETE FROM store WHERE prefix = %s",
                (str(user_id),),
            )
        logger.info(
            "Deleted %d rows from store for user %s",
            result.rowcount, user_id,
        )
    except Exception as exc:
        logger.error(
            "Section 3a FAILED — store DELETE for user %s: %s",
            user_id, exc, exc_info=True,
        )

    # ------------------------------------------------------------------ #
    # Section 3b — store_vectors (only when embedding enabled)             #
    # Bug 1 fix: separate connection context                               #
    # ------------------------------------------------------------------ #
    if vectors_enabled:
        try:
            async with pool.connection() as conn:
                result = await conn.execute(
                    "DELETE FROM store_vectors WHERE prefix = %s",
                    (str(user_id),),
                )
            logger.info(
                "Deleted %d rows from store_vectors for user %s",
                result.rowcount, user_id,
            )
        except Exception as exc:
            logger.error(
                "Section 3b FAILED — store_vectors DELETE for user %s: %s",
                user_id, exc, exc_info=True,
            )
    else:
        logger.debug(
            "EMBED_MODEL=none — skipping store_vectors DELETE for user %s", user_id
        )

    # ------------------------------------------------------------------ #
    # Section 3c — legacy store.adelete (backward compat)                  #
    # ------------------------------------------------------------------ #
    try:
        old_namespace = ("memories",)
        await store.adelete(old_namespace, user_id)
        logger.info("Deleted legacy memory (namespace=memories, key=%s)", user_id)
    except Exception as exc:
        logger.debug(
            "No legacy memory found (namespace=memories, key=%s): %s", user_id, exc
        )

    logger.info("Completed data clearing for user %s", user_id)

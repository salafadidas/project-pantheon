"""
Session lifecycle management.

This module is the **sole producer** of ``thread_id``.
Adapters (Telegram, Web UI, future REST/SSE clients) MUST NOT construct
``thread_id`` themselves — they call :func:`get_or_create_session` and use
the returned value.

Current mode: T1 — ``thread_id == user_id`` (single conversation per user).
S1-TID-1 will switch to T2 by changing :func:`make_thread_id` only.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def make_thread_id(user_id: str, session_id: str) -> str:
    """Return the canonical ``thread_id`` for a user + session pair.

    T1 (current): returns ``user_id`` — one persistent thread per user.
    T2 (S1-TID-1): returns ``f"{user_id}:{session_id}"`` — per-session threads.

    This is the single line that changes when Step 1.5 switches from T1 to T2.
    """
    return user_id  # T1 — change to f"{user_id}:{session_id}" in S1-TID-1


class SessionManager:
    """Manages Pantheon session lifecycle.

    The sole authority for ``thread_id`` production.  Adapters pass only
    ``user_id`` (and optionally adapter-specific metadata); they receive back
    a ``(session_id, thread_id)`` pair and must not derive either themselves.
    """

    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def get_or_create_session(self, user_id: str) -> tuple[str, str]:
        """Return ``(session_id, thread_id)`` for the user's current session.

        Under T1 both values equal ``user_id``; no Redis state is written.
        Under T2 (after S1-TID-1) a UUID session_id is persisted in Redis and
        a new one is created when the previous session has ended.
        """
        # T1: session collapses to the user identity; no persistence needed.
        session_id = user_id
        thread_id = make_thread_id(user_id, session_id)
        logger.debug("session resolved: user_id=%s session_id=%s thread_id=%s",
                     user_id, session_id, thread_id)
        return session_id, thread_id

    async def end_session(self, user_id: str, session_id: str) -> None:
        """Mark a session as ended.

        No-op under T1.  Under T2 this will delete the Redis session key so
        the next call to :meth:`get_or_create_session` starts a fresh session.
        """
        # T1: nothing to clean up.
        pass

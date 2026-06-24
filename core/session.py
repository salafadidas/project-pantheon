"""
Session lifecycle management.

This module is the **sole producer** of ``thread_id``.
Adapters (Telegram, Web UI, future REST/SSE clients) MUST NOT construct
``thread_id`` themselves — they call :func:`get_or_create_session` and use
the returned value.

Current mode: T2 — ``thread_id = f"{user_id}:{session_id}"``.
One UUID session per user; a new session starts after :meth:`end_session` is called.
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_SESSION_KEY_PREFIX = "pantheon:user_session"
_SESSION_TTL = 86400 * 30  # 30 days


def make_thread_id(user_id: str, session_id: str) -> str:
    """Return the canonical ``thread_id`` for a user + session pair.

    T2: ``f"{user_id}:{session_id}"`` — per-session threads, multiple
    conversations per user.
    """
    return f"{user_id}:{session_id}"


class SessionManager:
    """Manages Pantheon session lifecycle.

    The sole authority for ``thread_id`` production.  Adapters pass only
    ``user_id``; they receive back ``(session_id, thread_id)`` and must not
    derive either themselves.

    Redis key: ``pantheon:user_session:{user_id}`` → current ``session_id`` (UUID string).
    A new session UUID is generated when none exists (first use or after reset).
    """

    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    def _key(self, user_id: str) -> str:
        return f"{_SESSION_KEY_PREFIX}:{user_id}"

    async def get_or_create_session(self, user_id: str) -> tuple[str, str]:
        """Return ``(session_id, thread_id)`` for the user's current session.

        Reads the current ``session_id`` from Redis.  If none exists, generates
        a new UUID, persists it, and returns the new pair.
        """
        existing = await self._redis.get(self._key(user_id))
        if existing:
            session_id = existing if isinstance(existing, str) else existing.decode()
        else:
            session_id = str(uuid.uuid4())
            await self._redis.set(self._key(user_id), session_id, ex=_SESSION_TTL)
            logger.info("new session created: user_id=%s session_id=%s", user_id, session_id)

        thread_id = make_thread_id(user_id, session_id)
        logger.debug("session resolved: user_id=%s session_id=%s thread_id=%s",
                     user_id, session_id, thread_id)
        return session_id, thread_id

    async def end_session(self, user_id: str, session_id: str) -> None:
        """End the current session so the next interaction starts a fresh one.

        Deletes the Redis key; the next call to :meth:`get_or_create_session`
        will generate a new UUID session.

        Called by ``/reset`` after ``clear_user_data`` wipes checkpoint and
        memory state, ensuring the new conversation starts on a clean thread.
        """
        deleted = await self._redis.delete(self._key(user_id))
        if deleted:
            logger.info("session ended: user_id=%s session_id=%s", user_id, session_id)
        else:
            logger.debug("end_session: no active session key for user_id=%s", user_id)

"""
Per-session asyncio Queue progress bus.

Nodes call `publish()` as each individual model finishes; the sessions runner
drains the queue concurrently and forwards events to Redis pub/sub in real time.

Usage from a node:
    from graph.progress import publish_progress
    await publish_progress(session_id, {"event": "model_response", ...})

Usage from the sessions runner:
    from graph.progress import register, unregister
    queue = register(session_id)
    ...
    unregister(session_id)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# session_id → Queue (populated by graph nodes, drained by the sessions runner)
_queues: dict[str, asyncio.Queue] = {}

_SENTINEL = object()  # signals the drainer that the graph has finished


def register(session_id: str) -> asyncio.Queue:
    """Create and register a queue for the given session.  Must be called
    before the graph starts so nodes can publish immediately."""
    q: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = q
    logger.debug("progress_bus: registered session %s", session_id)
    return q


def get(session_id: str) -> Optional[asyncio.Queue]:
    """Return the queue for *session_id*, or None if not registered."""
    return _queues.get(session_id)


def unregister(session_id: str) -> None:
    """Remove the queue.  Call this after the drainer has finished."""
    _queues.pop(session_id, None)
    logger.debug("progress_bus: unregistered session %s", session_id)


async def publish_progress(session_id: str, event: dict) -> None:
    """Push *event* onto the session's queue.

    Silently no-ops if the session is not registered (e.g. called from a test
    context or after the session has ended) so nodes never raise.
    """
    q = _queues.get(session_id)
    if q is not None:
        await q.put(event)


async def close_queue(session_id: str) -> None:
    """Signal the drainer that no more events will arrive."""
    q = _queues.get(session_id)
    if q is not None:
        await q.put(_SENTINEL)


def is_sentinel(item: object) -> bool:
    """Return True if *item* is the end-of-stream sentinel."""
    return item is _SENTINEL

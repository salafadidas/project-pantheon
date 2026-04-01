"""WebSocket endpoint for real-time Pantheon session streaming."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

_TERMINAL_EVENTS = {"session_complete", "session_cancelled", "session_error"}


@router.websocket("/api/v1/sessions/{session_id}/stream")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    """Stream real-time phase events for a session over WebSocket.

    Emits JSON objects:
      {"event": "phase_complete", "phase": "...", "data": {...}, "timestamp": "..."}
      {"event": "session_complete", "final_report": "...", "timestamp": "..."}
      {"event": "session_cancelled", "timestamp": "..."}
      {"event": "session_error", "error": "...", "timestamp": "..."}
    """
    redis: Redis | None = getattr(websocket.app.state, "redis", None)
    if redis is None:
        await websocket.close(code=1011)
        return

    session = await redis.hgetall(f"session:{session_id}")
    if not session:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    channel = f"session:{session_id}:events"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            raw = message["data"]
            text = raw if isinstance(raw, str) else raw.decode()
            await websocket.send_text(text)

            try:
                if json.loads(text).get("event") in _TERMINAL_EVENTS:
                    break
            except Exception:
                pass
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        try:
            await websocket.close()
        except Exception:
            pass

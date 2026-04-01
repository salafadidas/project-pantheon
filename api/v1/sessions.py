"""FastAPI router for Pantheon session management."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis

from graph.pantheon_graph import pantheon_graph

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

SESSION_TTL = 86400  # 24 hours

# Module-level task registry for cancellation
_session_tasks: Dict[str, asyncio.Task] = {}

_NODE_TO_PHASE = {
    "pm_router": "routing",
    "researcher": "research",
    "debater": "debate",
    "voter": "voting",
    "synthesizer": "synthesis",
}


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


def _events_channel(session_id: str) -> str:
    return f"session:{session_id}:events"


def _get_redis(request: Request) -> Redis:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis not available")
    return redis


# --------------------------------------------------------------------------- #
# Pydantic models                                                              #
# --------------------------------------------------------------------------- #

class CreateSessionResponse(BaseModel):
    session_id: str


class StartSessionRequest(BaseModel):
    task: str
    user_id: str = "api_user"


class SessionStatus(BaseModel):
    session_id: str
    status: str
    phase: Optional[str] = None
    task: Optional[str] = None
    created_at: Optional[str] = None


class SessionReport(BaseModel):
    session_id: str
    final_report: str
    cost_summary: Optional[dict] = None


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #

@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(request: Request) -> CreateSessionResponse:
    """Create a new session and return its ID."""
    redis = _get_redis(request)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await redis.hset(
        _session_key(session_id),
        mapping={
            "session_id": session_id,
            "status": "created",
            "phase": "",
            "task": "",
            "user_id": "",
            "final_report": "",
            "cost_summary": "{}",
            "created_at": now,
        },
    )
    await redis.expire(_session_key(session_id), SESSION_TTL)
    return CreateSessionResponse(session_id=session_id)


@router.post("/{session_id}/start", status_code=202)
async def start_session(
    session_id: str, body: StartSessionRequest, request: Request
) -> dict:
    """Start execution of a session with the given task."""
    redis = _get_redis(request)
    session = await redis.hgetall(_session_key(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") == "running":
        raise HTTPException(status_code=409, detail="Session already running")

    await redis.hset(
        _session_key(session_id),
        mapping={"task": body.task, "user_id": body.user_id, "status": "running", "phase": "routing"},
    )

    task = asyncio.create_task(_run_session(session_id, body.task, body.user_id, redis))
    _session_tasks[session_id] = task
    return {"session_id": session_id, "status": "started"}


@router.get("/{session_id}/status", response_model=SessionStatus)
async def get_session_status(session_id: str, request: Request) -> SessionStatus:
    """Get the current phase and status of a session."""
    redis = _get_redis(request)
    session = await redis.hgetall(_session_key(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionStatus(
        session_id=session_id,
        status=session.get("status", "unknown"),
        phase=session.get("phase") or None,
        task=session.get("task") or None,
        created_at=session.get("created_at") or None,
    )


@router.get("/{session_id}/report", response_model=SessionReport)
async def get_session_report(session_id: str, request: Request) -> SessionReport:
    """Get the final report for a completed session."""
    redis = _get_redis(request)
    session = await redis.hgetall(_session_key(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") != "complete":
        raise HTTPException(status_code=404, detail="Report not yet available")
    cost_summary: dict = {}
    try:
        cost_summary = json.loads(session.get("cost_summary", "{}"))
    except Exception:
        pass
    return SessionReport(
        session_id=session_id,
        final_report=session.get("final_report", ""),
        cost_summary=cost_summary,
    )


@router.delete("/{session_id}", status_code=204)
async def cancel_session(session_id: str, request: Request) -> None:
    """Cancel a running session."""
    redis = _get_redis(request)
    session = await redis.hgetall(_session_key(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    task = _session_tasks.pop(session_id, None)
    if task and not task.done():
        task.cancel()

    await redis.hset(_session_key(session_id), "status", "cancelled")
    await redis.publish(
        _events_channel(session_id),
        json.dumps({"event": "session_cancelled", "timestamp": datetime.now(timezone.utc).isoformat()}),
    )


# --------------------------------------------------------------------------- #
# Graph runner                                                                 #
# --------------------------------------------------------------------------- #

async def _run_session(session_id: str, task: str, user_id: str, redis: Redis) -> None:
    """Execute the Pantheon graph and stream events to Redis pub/sub."""
    channel = _events_channel(session_id)
    key = _session_key(session_id)

    initial_state = {
        "task": task,
        "session_id": session_id,
        "user_id": user_id,
        "phase": "routing",
        "pm_model": "claude-sonnet",
        "debate_round": 0,
        "research_results": {},
        "debate_history": [],
        "votes": {},
        "consensus": None,
        "final_report": None,
        "cost_summary": {},
        "messages": [],
    }

    try:
        final_state: dict = {}
        async for chunk in pantheon_graph.astream(initial_state):
            for node_name, state_update in chunk.items():
                phase = _NODE_TO_PHASE.get(node_name, node_name)
                now = datetime.now(timezone.utc).isoformat()

                await redis.hset(key, "phase", state_update.get("phase", phase))

                event_data: dict = {"event": "phase_complete", "phase": phase, "timestamp": now}
                if node_name == "researcher":
                    event_data["data"] = {"research_results": state_update.get("research_results", {})}
                elif node_name == "debater":
                    event_data["data"] = {"debate_round": state_update.get("debate_round", 0)}
                elif node_name == "voter":
                    event_data["data"] = {
                        "votes": state_update.get("votes", {}),
                        "consensus": state_update.get("consensus"),
                    }
                elif node_name == "synthesizer":
                    preview = (state_update.get("final_report") or "")[:200]
                    event_data["data"] = {"final_report_preview": preview}

                await redis.publish(channel, json.dumps(event_data))
                final_state = state_update

        final_report = final_state.get("final_report") or ""
        cost_summary = final_state.get("cost_summary") or {}
        await redis.hset(
            key,
            mapping={
                "status": "complete",
                "phase": "complete",
                "final_report": final_report,
                "cost_summary": json.dumps(cost_summary),
            },
        )
        await redis.publish(
            channel,
            json.dumps({
                "event": "session_complete",
                "final_report": final_report,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        )
    except asyncio.CancelledError:
        await redis.hset(key, "status", "cancelled")
        raise
    except Exception as exc:
        await redis.hset(key, mapping={"status": "failed", "error": str(exc)})
        await redis.publish(
            channel,
            json.dumps({
                "event": "session_error",
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        )
    finally:
        _session_tasks.pop(session_id, None)

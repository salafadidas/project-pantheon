"""Health-check endpoints for Project Pantheon.

GET /health         — lightweight liveness probe (no external dependencies).
GET /health/ready   — readiness probe: verifies Redis is reachable.
GET /health/models  — startup LLM health check results (cached from boot).

Designed for use with Docker Compose healthchecks and Kubernetes probes.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])

# Record the process start time for uptime reporting
_START_TIME: float = time.monotonic()

_VERSION = "0.1.0-poc"


# --------------------------------------------------------------------------- #
# Response schemas                                                             #
# --------------------------------------------------------------------------- #

class LivenessResponse(BaseModel):
    status: str          # "ok"
    version: str
    uptime_seconds: float
    timestamp: str


class ReadinessResponse(BaseModel):
    status: str          # "ok" | "degraded"
    version: str
    checks: dict[str, str]
    timestamp: str


class ModelHealthDetail(BaseModel):
    status: str                  # "ok" | "error" | "timeout" | "skipped"
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class ModelsHealthResponse(BaseModel):
    status: str                              # "ok" | "degraded" | "unknown"
    version: str
    checked_at: str
    summary: dict[str, int]                  # {"ok": N, "error": N, ...}
    models: dict[str, ModelHealthDetail]


# --------------------------------------------------------------------------- #
# Routes                                                                       #
# --------------------------------------------------------------------------- #

@router.get("/health", response_model=LivenessResponse, summary="Liveness probe")
async def health_live() -> LivenessResponse:
    """Return 200 as long as the process is alive.

    Does **not** check downstream dependencies — use ``/health/ready`` for that.
    """
    return LivenessResponse(
        status="ok",
        version=_VERSION,
        uptime_seconds=round(time.monotonic() - _START_TIME, 1),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def health_ready(request: Request) -> ReadinessResponse:
    """Check that all required backing services are reachable.

    Currently checks:
    - **redis**: ping via ``app.state.redis``

    Returns HTTP 200 with ``status="ok"`` when all checks pass,
    or HTTP 200 with ``status="degraded"`` if any check fails
    (so orchestrators can detect but not restart the pod for transient blips).
    """
    checks: dict[str, str] = {}
    now = datetime.now(timezone.utc).isoformat()

    # Redis check
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        checks["redis"] = "unavailable — not initialised"
    else:
        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"

    return ReadinessResponse(
        status=overall,
        version=_VERSION,
        checks=checks,
        timestamp=now,
    )


@router.get(
    "/health/models",
    response_model=ModelsHealthResponse,
    summary="LLM model health (startup + periodic probe results)",
)
async def health_models(request: Request) -> ModelsHealthResponse:
    """Return cached LLM model health.

    Cache is refreshed at startup and periodically (every 5 minutes) by a
    background task.  Use ``POST /health/models/refresh`` to force an
    immediate re-probe.  Models with status ``"skipped"`` have no API key
    configured.
    """
    model_health: dict = getattr(request.app.state, "model_health", {})
    checked_at = getattr(
        request.app.state, "model_health_checked_at", datetime.now(timezone.utc).isoformat()
    )

    if not model_health:
        return ModelsHealthResponse(
            status="unknown",
            version=_VERSION,
            checked_at=checked_at,
            summary={},
            models={},
        )

    summary: dict[str, int] = {}
    model_details: dict[str, ModelHealthDetail] = {}
    for model_key, health in model_health.items():
        status = health.get("status", "error")
        summary[status] = summary.get(status, 0) + 1
        model_details[model_key] = ModelHealthDetail(
            status=status,
            latency_ms=health.get("latency_ms"),
            error=health.get("error"),
        )

    # Overall status: degraded if any non-skipped model has error/timeout
    non_skipped = {k: v for k, v in model_health.items() if v.get("status") != "skipped"}
    overall = "ok" if all(v.get("status") == "ok" for v in non_skipped.values()) else "degraded"

    return ModelsHealthResponse(
        status=overall,
        version=_VERSION,
        checked_at=checked_at,
        summary=summary,
        models=model_details,
    )


@router.post(
    "/health/models/refresh",
    response_model=ModelsHealthResponse,
    summary="Re-probe all LLM models on demand",
)
async def health_models_refresh(request: Request) -> ModelsHealthResponse:
    """Re-run the LLM health check on demand and update cache.

    Useful when the user wants up-to-the-minute model status before submitting
    a task.  Same probe that runs at startup — takes ~20 s in the worst case
    (one model timing out).  If the refresh itself fails, the previous cache
    is preserved.
    """
    from llm.health_check import run_model_health_check
    from llm.provider import LLMProvider

    try:
        provider = LLMProvider()
        request.app.state.model_health = await run_model_health_check(provider)
        request.app.state.model_health_checked_at = datetime.now(timezone.utc).isoformat()
    except Exception:
        # Don't blank the existing cache if refresh fails
        pass

    return await health_models(request)

"""Health-check endpoint for Project Pantheon.

GET /health  — lightweight liveness probe (no external dependencies).
GET /health/ready — readiness probe: verifies Redis is reachable.

Designed for use with Docker Compose healthchecks and Kubernetes probes.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

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

"""FastAPI router that exposes the model catalog + live health to the frontend.

Combines the static catalog (pricing, strengths) with the dynamic health
cache so the UI can disable unhealthy models in a single round trip instead
of fetching catalog + health separately.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from llm.model_catalog import DEBATE_MODELS, DEFAULT_SELECTED

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
async def list_models(request: Request) -> dict:
    """Return all debate models with pricing, token estimates, and live health.

    Response shape::

        {
          "models": [
            {
              ...catalog fields...,
              "health": {"status": "ok"|"error"|"timeout"|"skipped"|"unknown",
                         "latency_ms": int|null, "error": str|null},
              "selectable": bool,   # false when health is bad → UI greys it out
            },
            ...
          ],
          "default_selected": [...healthy defaults only...],
          "health_checked_at": "ISO timestamp"
        }
    """
    health_cache: dict = getattr(request.app.state, "model_health", {})
    checked_at: str | None = getattr(
        request.app.state, "model_health_checked_at", None
    )

    models_out: list[dict] = []
    for m in DEBATE_MODELS:
        d = m.to_dict()

        h = health_cache.get(m.model_id, {"status": "unknown", "latency_ms": None, "error": None})
        d["health"] = {
            "status": h.get("status", "unknown"),
            "latency_ms": h.get("latency_ms"),
            "error": h.get("error"),
        }
        # selectable = API key configured AND last probe succeeded.
        # "unknown" (cache empty) is treated as selectable so the UI works even
        # when the periodic check hasn't run yet.
        d["selectable"] = (
            d["available"] and d["health"]["status"] in ("ok", "unknown")
        )
        models_out.append(d)

    # Filter defaults to only those that are currently selectable
    healthy_defaults = [
        mid for mid in DEFAULT_SELECTED
        if any(m["model_id"] == mid and m["selectable"] for m in models_out)
    ]

    return {
        "models": models_out,
        "default_selected": healthy_defaults,
        "health_checked_at": checked_at,
    }

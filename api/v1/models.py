"""FastAPI router that exposes the model catalog to the frontend."""
from __future__ import annotations

from fastapi import APIRouter

from llm.model_catalog import DEBATE_MODELS, DEFAULT_SELECTED

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
async def list_models() -> dict:
    """Return all debate models with pricing, token estimates, and availability."""
    return {
        "models": [m.to_dict() for m in DEBATE_MODELS],
        "default_selected": DEFAULT_SELECTED,
    }

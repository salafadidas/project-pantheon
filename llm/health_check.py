"""
Startup LLM health check — probes every configured model with a tiny request.

Results are stored in ``app.state.model_health`` at startup and exposed via
``GET /health/models``.  Broken models are flagged automatically so users
never have to report them manually.

Design decisions:
- Runs concurrently (all models in parallel) to keep total startup delay minimal.
- Only probes models whose API key env var is present (no point hitting auth errors).
- Uses a 20-second timeout per model — long enough to detect 504s, short enough
  that the full startup check completes in ~20s even with many models.
- Cost: ~10 output tokens per model, once per restart.  Acceptable for 15 models.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TypedDict

from langchain_core.messages import HumanMessage

from llm.model_catalog import MODEL_CATALOG
from llm.provider import DEFAULT_MODELS, LLMProvider

logger = logging.getLogger(__name__)

_PROBE_MSG = "Reply with exactly one word: OK"
_PROBE_TIMEOUT_SECONDS: int = 20   # per model — catches 504s without blocking forever
_PROBE_MAX_TOKENS: int = 10        # minimal cost


# ── Result type ──────────────────────────────────────────────────────────────

class ModelHealth(TypedDict):
    status: str             # "ok" | "error" | "timeout" | "skipped"
    latency_ms: int | None  # round-trip in ms; None on timeout/skip
    error: str | None       # truncated error message; None on success


# ── Per-model probe ──────────────────────────────────────────────────────────

async def _probe_model(provider: LLMProvider, model_key: str) -> ModelHealth:
    """Invoke a single model with a minimal prompt and return its health."""
    t0 = time.monotonic()
    try:
        llm = provider.get_chat_model(model_key, max_tokens=_PROBE_MAX_TOKENS)
        response = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content=_PROBE_MSG)]),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        # Validate there's actual content in the response
        content = response.content if hasattr(response, "content") else str(response)
        if not content:
            return ModelHealth(
                status="error",
                latency_ms=latency_ms,
                error="Empty response from model",
            )
        return ModelHealth(status="ok", latency_ms=latency_ms, error=None)

    except asyncio.TimeoutError:
        logger.warning(
            "health_check: %s timed out after %ds",
            model_key,
            _PROBE_TIMEOUT_SECONDS,
        )
        return ModelHealth(
            status="timeout",
            latency_ms=None,
            error=f"No response within {_PROBE_TIMEOUT_SECONDS}s — model may be unavailable",
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("health_check: %s failed (%dms): %.200s", model_key, latency_ms, exc)
        return ModelHealth(
            status="error",
            latency_ms=latency_ms,
            error=str(exc)[:300],
        )


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_model_health_check(
    provider: LLMProvider | None = None,
) -> dict[str, ModelHealth]:
    """Probe all models whose API key is configured, concurrently.

    Args:
        provider: Existing ``LLMProvider`` instance.  A fresh one is created
            when not provided.

    Returns:
        Mapping of ``model_key → ModelHealth`` for every model in
        ``DEFAULT_MODELS``.  Models without a configured API key are given
        status ``"skipped"``.
    """
    if provider is None:
        provider = LLMProvider()

    results: dict[str, ModelHealth] = {}
    probe_keys: list[str] = []

    # Separate models into "will probe" vs "skipped (no API key)"
    for model_key in DEFAULT_MODELS:
        catalog_entry = MODEL_CATALOG.get(model_key)
        if catalog_entry is None or not catalog_entry.is_available():
            results[model_key] = ModelHealth(
                status="skipped",
                latency_ms=None,
                error="API key not configured",
            )
        else:
            probe_keys.append(model_key)

    if not probe_keys:
        logger.warning("health_check: no models have API keys configured — skipping all")
        return results

    logger.info(
        "health_check: probing %d/%d models concurrently (timeout=%ds each, skipped=%d)",
        len(probe_keys),
        len(DEFAULT_MODELS),
        _PROBE_TIMEOUT_SECONDS,
        len(DEFAULT_MODELS) - len(probe_keys),
    )

    tasks = [_probe_model(provider, key) for key in probe_keys]
    probe_results = await asyncio.gather(*tasks, return_exceptions=False)

    ok_count = 0
    for key, result in zip(probe_keys, probe_results):
        results[key] = result
        if result["status"] == "ok":
            ok_count += 1
            logger.info("health_check: ✅ %s — ok (%dms)", key, result["latency_ms"] or 0)
        else:
            logger.warning(
                "health_check: ❌ %s — %s: %s",
                key,
                result["status"],
                result["error"],
            )

    logger.info(
        "health_check: complete — %d/%d probed models healthy",
        ok_count,
        len(probe_keys),
    )
    return results

"""
Quota-aware LLM call helper with automatic provider-level fallback.

When a model returns a 429 / RESOURCE_EXHAUSTED error the helper
transparently retries the call with the next model in the fallback chain
for that provider.  If all same-provider fallbacks are exhausted it can
optionally try a cross-provider "last resort" list (useful for nodes that
*must* produce output, e.g. the synthesizer).

A clean :class:`ProviderQuotaExhausted` exception is raised instead of
leaking raw 429 JSON when every candidate has failed.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ProviderQuotaExhausted(Exception):
    """Raised when every fallback model for a provider is quota-exhausted.

    The message is intentionally human-readable so callers can surface it
    directly in the UI without further formatting.
    """


# ---------------------------------------------------------------------------
# Fallback chains
# ---------------------------------------------------------------------------

# Google free-tier quota is tiny for 2.5 Pro; fall through to cheaper models.
GOOGLE_FALLBACK_CHAIN: list[str] = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# NVIDIA NIM free-tier (40 RPM): fall through to Kimi K2 if DeepSeek V3 hits limits.
NVIDIA_FALLBACK_CHAIN: list[str] = [
    "deepseek-v3",
    "kimi-k2",
]

# Cross-provider last-resort: used when ALL same-provider fallbacks are exhausted
# and the caller allows cross-provider fallback (synthesizer must always produce
# output, so it passes allow_cross_provider=True).
#
# NOTE: deepseek-v3 is intentionally NOT listed here.  It is already an official
# debater slot with kimi-k2 as its own NVIDIA fallback.  Including it here would
# consume NVIDIA NIM quota during another model's turn and then leave deepseek-v3
# with no capacity when it is called as an official debater, producing a confusing
# duplicate "deepseek-v3" entry in the same debate round.
CROSS_PROVIDER_LAST_RESORT: list[str] = [
    "claude-haiku",
    "gpt-4o-mini",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_quota_error(exc: BaseException) -> bool:
    """Return True when the exception is a provider-side rate-limit / quota error."""
    msg = str(exc).lower()
    quota_signals = (
        # HTTP 429 — explicit rate-limit status
        "429",
        # HTTP 503 — Gemini "high demand" / transient unavailability
        "503",
        "unavailable",
        "high demand",
        "serviceunavailable",
        # Provider-specific wording
        "resource_exhausted",
        "quota",
        "rate limit",
        "ratelimit",
        "too many requests",
        "overloaded",
    )
    return any(s in msg for s in quota_signals)


def _same_provider_fallbacks(model_key: str) -> list[str]:
    """Return the ordered same-provider fallback list starting *after* model_key.

    Google models fall through the Gemini chain; NVIDIA NIM models fall through
    to Kimi K2.  All other providers have no automatic chain.
    """
    if model_key in GOOGLE_FALLBACK_CHAIN:
        idx = GOOGLE_FALLBACK_CHAIN.index(model_key)
        return GOOGLE_FALLBACK_CHAIN[idx + 1:]
    if model_key in NVIDIA_FALLBACK_CHAIN:
        idx = NVIDIA_FALLBACK_CHAIN.index(model_key)
        return NVIDIA_FALLBACK_CHAIN[idx + 1:]
    return []


def _friendly_quota_message(model_key: str, chain: list[str]) -> str:
    """Build a clean, UI-safe quota-exhausted message."""
    if model_key in GOOGLE_FALLBACK_CHAIN:
        provider = "Gemini"
        reset_hint = "resets at midnight Pacific Time"
    elif model_key in NVIDIA_FALLBACK_CHAIN:
        provider = "NVIDIA NIM"
        reset_hint = "check your rate-limit (40 RPM free tier)"
    else:
        provider = model_key
        reset_hint = "check your API quota"
    models_tried = [model_key] + chain
    return (
        f"⚠️ {provider} quota exhausted "
        f"(tried: {', '.join(models_tried)}) — {reset_hint}. "
        "This model was skipped; other models continue."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def ainvoke_with_fallback(
    *,
    provider: Any,                    # LLMProvider — avoid circular import
    model_key: str,
    messages: Sequence[BaseMessage],
    allow_cross_provider: bool = False,
) -> tuple[str, str]:
    """Invoke a model, falling back on quota errors.

    Args:
        provider: :class:`LLMProvider` instance.
        model_key: Starting model key (e.g. ``"gemini-2.5-flash"``).
        messages: LangChain messages to send.
        allow_cross_provider: When *True* and all same-provider fallbacks are
            exhausted, continue trying :data:`CROSS_PROVIDER_LAST_RESORT`
            models before giving up.  Use this for nodes that **must** produce
            output (synthesizer).

    Returns:
        ``(actual_model_key, content)`` — *actual_model_key* may differ from
        *model_key* when a fallback was used.

    Raises:
        :class:`ProviderQuotaExhausted`: When every candidate is
            quota-exhausted.  The message is human-readable.
        Exception: Non-quota errors bubble up immediately from the first
            candidate that raises them.
    """
    same_provider = _same_provider_fallbacks(model_key)
    candidates = [model_key] + same_provider

    last_quota_exc: BaseException | None = None
    for idx, candidate in enumerate(candidates):
        try:
            llm = provider.get_chat_model(candidate)
            response = await llm.ainvoke(list(messages))
            content: str = (
                response.content if hasattr(response, "content") else str(response)
            )
            if candidate != model_key:
                logger.warning(
                    "quota_fallback: %s → %s (quota exceeded on primary)",
                    model_key,
                    candidate,
                )
            return candidate, content.strip()

        except Exception as exc:
            if _is_quota_error(exc):
                logger.warning(
                    "quota_fallback: %s quota exceeded — trying next. Error: %.120s",
                    candidate,
                    exc,
                )
                last_quota_exc = exc
                continue
            if idx > 0:
                # We're already in fallback mode.  Any error from a fallback
                # candidate (e.g. a LiteLLM parsing crash when the model returns
                # no-quota JSON instead of a proper 429) should skip to the next
                # candidate rather than surfacing as a confusing generic error.
                logger.warning(
                    "quota_fallback: fallback %s failed (%s: %.120s) — trying next",
                    candidate,
                    type(exc).__name__,
                    exc,
                )
                last_quota_exc = exc
                continue
            # Primary model, genuine non-quota error — bubble up immediately
            raise

    # All same-provider fallbacks exhausted — try cross-provider if allowed
    if allow_cross_provider:
        for candidate in CROSS_PROVIDER_LAST_RESORT:
            try:
                llm = provider.get_chat_model(candidate)
                response = await llm.ainvoke(list(messages))
                content = (
                    response.content if hasattr(response, "content") else str(response)
                )
                logger.warning(
                    "quota_fallback: all %s models exhausted — used cross-provider %s",
                    model_key,
                    candidate,
                )
                return candidate, content.strip()
            except Exception as exc:
                if _is_quota_error(exc):
                    logger.warning(
                        "quota_fallback: cross-provider %s also quota-exhausted: %.120s",
                        candidate,
                        exc,
                    )
                    last_quota_exc = exc
                    continue
                raise

    # Build a clean, friendly message for the UI
    friendly_msg = _friendly_quota_message(model_key, same_provider)
    raise ProviderQuotaExhausted(friendly_msg) from last_quota_exc

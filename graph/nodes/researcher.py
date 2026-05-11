"""
Researcher node for Phase 2 of the Pantheon workflow.

Each researcher model independently investigates the task and records its
findings.  All models run concurrently via asyncio.gather(); a per-model
timeout (PHASE_TIMEOUT_SECONDS) prevents slow providers from blocking the
pipeline.
"""

from __future__ import annotations

import asyncio
import os

from langchain_core.messages import HumanMessage, SystemMessage

from graph.progress import publish_progress
from graph.state import PantheonState
from llm.cost_tracker import merge_usage
from llm.provider import PHASE_MODEL_ROLES, LLMProvider
from llm.quota_fallback import ProviderQuotaExhausted, ainvoke_with_fallback
from utils.logging_config import get_logger
from utils.timeout import with_timeout, TimeoutError as PantheonTimeoutError

logger = get_logger(__name__)

PHASE_TIMEOUT_SECONDS: int = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

_SYSTEM_PROMPT = """\
你是一位獨立的 AI 研究員。
你的任務：針對給定的問題或課題進行深入研究，並產出一份簡潔、條理清晰的研究摘要（不超過 400 字）。

內容需涵蓋：
1. 與任務相關的關鍵事實、定義或技術細節
2. 重要的權衡取捨與注意事項
3. 你對後續小組辯論的建議立場

請在回應開頭標明你的模型名稱。\
"""


async def researcher_node(state: PantheonState) -> PantheonState:
    """Run independent research for every researcher model concurrently.

    Args:
        state: Current PantheonState (immutable — new values returned).

    Returns:
        Updated PantheonState with research_results populated and
        phase = "debate".
    """
    provider = LLMProvider()
    researcher_models = _resolve_researcher_models(provider, state)
    session_id: str = state.get("session_id", "")

    tasks = [
        _research_with_timeout(
            provider=provider,
            model_key=model_key,
            task=state["task"],
            timeout=PHASE_TIMEOUT_SECONDS,
            session_id=session_id,
        )
        for model_key in researcher_models
    ]

    results_list: list[tuple[str, str, dict]] = await asyncio.gather(*tasks)
    research_results: dict[str, str] = {model_key: text for model_key, text, _ in results_list}

    cost_summary: dict = dict(state.get("cost_summary") or {})
    for model_key, _text, usage in results_list:
        if usage.get("input_tokens") or usage.get("output_tokens"):
            cost_summary = merge_usage(
                cost_summary,
                model_key=model_key,
                litellm_model=usage["litellm_model"],
                phase="research",
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            )

    logger.info(
        "Research phase complete: %d models responded",
        sum(1 for _, v, _ in results_list if not v.startswith("[ERROR")),
    )

    return {
        **state,
        "research_results": research_results,
        "cost_summary": cost_summary,
        "phase": "debate",
    }


async def _research_with_timeout(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
    timeout: int,
    session_id: str = "",
) -> tuple[str, str, dict]:
    """Call a single researcher model, enforcing a timeout.

    Returns:
        (model_key, research_text, usage) — on failure, research_text is an
        error placeholder and usage is empty so downstream nodes always have an
        entry for every model.
    """
    from datetime import datetime, timezone  # local import to avoid circular at module level

    async def _publish(content: str, *, skipped: bool) -> None:
        await publish_progress(session_id, {
            "event": "model_response",
            "phase": "research",
            "model": model_key,
            "model_requested": None,
            "content": content,
            "skipped": skipped,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    _empty_usage: dict = {"input_tokens": 0, "output_tokens": 0, "litellm_model": ""}
    try:
        result, usage = await with_timeout(
            _get_research(provider=provider, model_key=model_key, task=task),
            seconds=float(timeout),
            label=f"researcher:{model_key}",
        )
        logger.info("researcher_done", model=model_key, chars=len(result))
        await _publish(result, skipped=False)
        return model_key, result, usage
    except PantheonTimeoutError:
        logger.warning("researcher_timeout", model=model_key, timeout_s=timeout)
        content = f"⚠️ {model_key} timed out after {timeout}s — skipped."
        await _publish(content, skipped=True)
        return model_key, content, _empty_usage
    except ProviderQuotaExhausted as exc:
        # Clean, user-friendly message — the str() of the exception is already
        # formatted for the UI by quota_fallback.py
        logger.warning("researcher_quota_exhausted", model=model_key, detail=str(exc))
        content = str(exc)
        await _publish(content, skipped=True)
        return model_key, content, _empty_usage
    except Exception as exc:
        logger.warning("researcher_error", model=model_key, error=str(exc))
        content = f"⚠️ {model_key} encountered an error and was skipped."
        await _publish(content, skipped=True)
        return model_key, content, _empty_usage


async def _get_research(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
) -> tuple[str, dict]:
    """Invoke the model and return (research_text, usage).

    Automatically falls back to cheaper models within the same provider when a
    quota / rate-limit error (429) is encountered.
    """
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Task to research:\n\n{task}\n\n"
                f"You are {model_key}. Provide your research summary now."
            )
        ),
    ]

    actual_model, content, usage = await ainvoke_with_fallback(
        provider=provider,
        model_key=model_key,
        messages=messages,
        allow_cross_provider=True,  # NVIDIA NIM (DeepSeek) backs up Gemini when quota hits
    )

    if actual_model != model_key:
        logger.info(
            "researcher_quota_fallback: used %s instead of %s",
            actual_model,
            model_key,
        )

    return content, usage


def _resolve_researcher_models(provider: LLMProvider, state: PantheonState) -> list[str]:
    """Return deduplicated list of model keys for the research phase.

    Priority:
    1. User-selected models (state["selected_models"]) when non-empty.
    2. Models mapped to researcher_* roles in PHASE_MODEL_ROLES.
    3. All provider-available models as a last resort.
    """
    user_selected: list[str] = state.get("selected_models") or []
    if user_selected:
        return list(dict.fromkeys(user_selected))  # deduplicate, preserve order

    researcher_keys = [
        model_key
        for role, model_key in PHASE_MODEL_ROLES.items()
        if role.startswith("researcher_")
    ]
    if researcher_keys:
        return list(dict.fromkeys(researcher_keys))

    return provider.available_models

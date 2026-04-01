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
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import PantheonState
from llm.provider import PHASE_MODEL_ROLES, LLMProvider
from utils.logging_config import get_logger
from utils.timeout import with_timeout, TimeoutError as PantheonTimeoutError

logger = get_logger(__name__)

PHASE_TIMEOUT_SECONDS: int = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

_SYSTEM_PROMPT = """\
You are an independent AI researcher.
Your task: thoroughly investigate the question or problem given to you and
produce a concise, well-structured research summary (≤ 400 words).

Cover:
1. Key facts, definitions, or technical details relevant to the task
2. Important trade-offs or considerations
3. Your recommended starting position for a group debate

Identify yourself by your model name at the top of your response.\
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
    researcher_models = _resolve_researcher_models(provider)

    tasks = [
        _research_with_timeout(
            provider=provider,
            model_key=model_key,
            task=state["task"],
            timeout=PHASE_TIMEOUT_SECONDS,
        )
        for model_key in researcher_models
    ]

    results_list: list[tuple[str, str]] = await asyncio.gather(*tasks)
    research_results: dict[str, str] = dict(results_list)

    logger.info(
        "Research phase complete: %d models responded",
        sum(1 for _, v in results_list if not v.startswith("[ERROR")),
    )

    return {
        **state,
        "research_results": research_results,
        "phase": "debate",
    }


async def _research_with_timeout(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
    timeout: int,
) -> tuple[str, str]:
    """Call a single researcher model, enforcing a timeout.

    Returns:
        (model_key, research_text) — on failure, research_text is an error
        placeholder so downstream nodes always have an entry for every model.
    """
    try:
        result = await with_timeout(
            _get_research(provider=provider, model_key=model_key, task=task),
            seconds=float(timeout),
            label=f"researcher:{model_key}",
        )
        logger.info("researcher_done", model=model_key, chars=len(result))
        return model_key, result
    except PantheonTimeoutError:
        logger.warning("researcher_timeout", model=model_key, timeout_s=timeout)
        return model_key, f"[ERROR: {model_key} timed out after {timeout}s]"
    except Exception as exc:
        logger.warning("researcher_error", model=model_key, error=str(exc))
        return model_key, f"[ERROR: {model_key} failed — {exc}]"


async def _get_research(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
) -> str:
    """Invoke the model and return its research text."""
    llm = provider.get_chat_model(model_key)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Task to research:\n\n{task}\n\n"
                f"You are {model_key}. Provide your research summary now."
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    content: str = response.content if hasattr(response, "content") else str(response)
    return content.strip()


def _resolve_researcher_models(provider: LLMProvider) -> list[str]:
    """Return deduplicated list of model keys for the research phase."""
    researcher_keys = [
        model_key
        for role, model_key in PHASE_MODEL_ROLES.items()
        if role.startswith("researcher_")
    ]
    if researcher_keys:
        seen: set[str] = set()
        unique: list[str] = []
        for k in researcher_keys:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        return unique

    return provider.available_models

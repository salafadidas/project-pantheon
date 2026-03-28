"""
PM Router node for Phase 1 of the Pantheon workflow.

Classifies the incoming task by type (technical / creative / analytical /
factual) and selects the most appropriate PM model for the session.  Sets
state.pm_model and advances the phase to "research".
"""

from __future__ import annotations

import json
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import PantheonState
from llm.provider import PHASE_MODEL_ROLES, LLMProvider

logger = logging.getLogger(__name__)

PHASE_TIMEOUT_SECONDS: int = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

# Map task types to the most suitable PM model key
_TASK_TYPE_MODEL_MAP: dict[str, str] = {
    "technical": "gpt-4o",
    "creative": "claude-sonnet",
    "analytical": "gemini-2.5-pro",
    "factual": "gpt-4o-mini",
}

_SYSTEM_PROMPT = """\
You are a project manager coordinating a multi-AI collaboration system.
Your job is to classify the incoming task and select the best lead AI model.

Respond with valid JSON only — no markdown fences, no extra text:
{
  "task_type": "<technical|creative|analytical|factual>",
  "pm_model": "<gpt-4o-mini|gpt-4o|claude-sonnet|gemini-2.5-pro|gemini-2.0-flash>",
  "reasoning": "<one sentence explaining the choice>"
}

Task types:
- technical: code, engineering, systems design, debugging
- creative: writing, ideation, storytelling, design
- analytical: data analysis, comparisons, evaluations, research synthesis
- factual: knowledge retrieval, definitions, factual Q&A\
"""


async def pm_router_node(state: PantheonState) -> PantheonState:
    """Classify the task and set the PM model for this session.

    Args:
        state: Current PantheonState (immutable — new values returned).

    Returns:
        Updated PantheonState with pm_model set and phase = "research".
    """
    provider = LLMProvider()
    router_model_key = PHASE_MODEL_ROLES.get("pm_router", "gpt-4o-mini")
    llm = provider.get_chat_model(router_model_key)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Classify and route this task:\n\n{state['task']}"),
    ]

    pm_model = router_model_key  # sensible fallback
    try:
        response = await llm.ainvoke(messages)
        raw: str = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(raw.strip())

        task_type = parsed.get("task_type", "factual")
        chosen = parsed.get("pm_model", "")
        reasoning = parsed.get("reasoning", "")

        # Accept the model if it is registered, otherwise derive from task type
        if chosen in provider.available_models:
            pm_model = chosen
        else:
            pm_model = _TASK_TYPE_MODEL_MAP.get(task_type, router_model_key)

        logger.info(
            "PM router: task_type=%s, pm_model=%s, reasoning=%s",
            task_type,
            pm_model,
            reasoning,
        )
    except Exception as exc:
        logger.warning(
            "PM router failed to parse response — using fallback model %s. Error: %s",
            pm_model,
            exc,
        )

    return {
        **state,
        "pm_model": pm_model,
        "phase": "research",
    }

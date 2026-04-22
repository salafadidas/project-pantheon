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
你是一個負責協調多 AI 協作系統的專案經理。
你的任務：分類傳入的問題，並選擇最適合的主導 AI 模型。

只回應有效的 JSON，不要加 Markdown 標記或其他文字：
{
  "task_type": "<technical|creative|analytical|factual>",
  "pm_model": "<gpt-4o-mini|gpt-4o|claude-sonnet|gemini-2.5-pro|gemini-2.0-flash>",
  "reasoning": "<一句話說明選擇原因>"
}

任務類型說明：
- technical（技術）：程式碼、工程、系統設計、除錯
- creative（創意）：寫作、發想、故事創作、設計
- analytical（分析）：資料分析、比較、評估、研究整合
- factual（事實）：知識查詢、定義、事實問答\
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

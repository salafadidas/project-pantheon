"""
Debate node for Phase 3 of the Pantheon workflow.

Each model in `debate_models` receives the full debate history so far and
adds one response per round.  The node runs for a single round per call;
the graph's conditional edge must loop back until `debate_round` reaches
MAX_DEBATE_ROUNDS.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from graph.progress import publish_progress
from graph.state import PantheonState
from llm.cost_tracker import merge_usage
from llm.provider import LLMProvider, PHASE_MODEL_ROLES
from llm.quota_fallback import ProviderQuotaExhausted, ainvoke_with_fallback
from utils.timeout import with_timeout, TimeoutError as PantheonTimeoutError

logger = logging.getLogger(__name__)

MAX_DEBATE_ROUNDS: int = int(os.getenv("MAX_DEBATE_ROUNDS", "3"))
DEBATE_TIMEOUT_SECONDS: int = int(os.getenv("DEBATE_TIMEOUT_SECONDS", "60"))

_SYSTEM_PROMPT = """\
你正在參與一場結構化的多模型辯論。
你的角色：分析任務與目前已提出的論點，然後提出一個有條理、有根據的回應，\
可以是延伸、挑戰或整合先前的立場。
回應請簡潔（不超過 300 字），並在開頭標明你的模型名稱。\
"""


def _format_history(debate_history: List[dict]) -> str:
    """Render debate history as a readable transcript."""
    if not debate_history:
        return "(No previous statements — you are opening the debate.)"
    lines: list[str] = []
    for entry in debate_history:
        ts = entry.get("timestamp", "")
        lines.append(
            f"[Round {entry['round']} | {entry['model']} | {ts}]\n{entry['content']}"
        )
    return "\n\n".join(lines)


async def debate_node(state: PantheonState) -> PantheonState:
    """Run one debate round: each model in debate_models adds one statement.

    Args:
        state: Current PantheonState (treated as immutable — new values are
               returned rather than mutating the input dict).

    Returns:
        Updated PantheonState with appended debate_history and incremented
        debate_round.  Phase stays "debate"; the graph's conditional edge
        decides whether to loop or advance.
    """
    provider = LLMProvider()
    current_round: int = state["debate_round"] + 1
    debate_models: list[str] = _resolve_debate_models(state, provider)

    history_snapshot = list(state.get("debate_history", []))
    new_entries: list[dict] = []
    cost_summary: dict = dict(state.get("cost_summary") or {})

    session_id: str = state.get("session_id", "")

    for model_key in debate_models:
        try:
            entry = await with_timeout(
                _get_model_statement(
                    provider=provider,
                    model_key=model_key,
                    task=state["task"],
                    history=history_snapshot + new_entries,
                    round_number=current_round,
                ),
                seconds=float(DEBATE_TIMEOUT_SECONDS),
                label=f"debater:{model_key}",
            )
            usage = entry.pop("usage", {})
            new_entries.append(entry)
            if usage.get("input_tokens") or usage.get("output_tokens"):
                cost_summary = merge_usage(
                    cost_summary,
                    model_key=entry["model"],
                    litellm_model=usage["litellm_model"],
                    phase="debate",
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                )
            logger.info("Debate round %d: %s responded (%d chars)",
                        current_round, model_key, len(entry["content"]))
            await publish_progress(session_id, {
                "event": "model_response",
                "phase": "debate",
                "model": entry["model"],
                "model_requested": entry.get("model_requested"),
                "round": current_round,
                "content": entry["content"],
                "skipped": False,
                "timestamp": entry["timestamp"],
            })
        except PantheonTimeoutError:
            logger.warning(
                "Debate round %d: %s timed out after %ds — skipped.",
                current_round, model_key, DEBATE_TIMEOUT_SECONDS,
            )
            ts = datetime.now(timezone.utc).isoformat()
            content = f"⚠️ {model_key} timed out after {DEBATE_TIMEOUT_SECONDS}s — skipped."
            new_entries.append({
                "round": current_round,
                "model": model_key,
                "model_requested": None,
                "content": content,
                "timestamp": ts,
                "skipped": True,
            })
            await publish_progress(session_id, {
                "event": "model_response",
                "phase": "debate",
                "model": model_key,
                "model_requested": None,
                "round": current_round,
                "content": content,
                "skipped": True,
                "timestamp": ts,
            })
        except ProviderQuotaExhausted as exc:
            # Log cleanly and add a skip-notice entry so the UI shows what happened
            logger.warning(
                "Debate round %d: %s quota exhausted — skipped.",
                current_round, model_key,
            )
            ts = datetime.now(timezone.utc).isoformat()
            content = str(exc)
            new_entries.append({
                "round": current_round,
                "model": model_key,
                "model_requested": None,
                "content": content,
                "timestamp": ts,
                "skipped": True,
            })
            await publish_progress(session_id, {
                "event": "model_response",
                "phase": "debate",
                "model": model_key,
                "model_requested": None,
                "round": current_round,
                "content": content,
                "skipped": True,
                "timestamp": ts,
            })
        except Exception as exc:
            logger.warning(
                "Debate round %d: model %s failed — skipping. Error: %s",
                current_round, model_key, exc,
            )
            ts = datetime.now(timezone.utc).isoformat()
            content = f"⚠️ {model_key} encountered an error and was skipped."
            new_entries.append({
                "round": current_round,
                "model": model_key,
                "model_requested": None,
                "content": content,
                "timestamp": ts,
                "skipped": True,
            })
            await publish_progress(session_id, {
                "event": "model_response",
                "phase": "debate",
                "model": model_key,
                "model_requested": None,
                "round": current_round,
                "content": content,
                "skipped": True,
                "timestamp": ts,
            })

    return {
        **state,
        "debate_history": history_snapshot + new_entries,
        "debate_round": current_round,
        "cost_summary": cost_summary,
        "phase": "debate",
    }


async def _get_model_statement(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
    history: list[dict],
    round_number: int,
) -> dict:
    """Call a single model and return a debate-history entry.

    Automatically falls back to cheaper models within the same provider when a
    quota / rate-limit error (429) is encountered.
    """
    history_text = _format_history(history)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Task under debate:\n{task}\n\n"
            f"Debate transcript so far:\n{history_text}\n\n"
            f"You are {model_key}. This is round {round_number}. "
            "Please add your statement now."
        )),
    ]

    actual_model, content, usage = await ainvoke_with_fallback(
        provider=provider,
        model_key=model_key,
        messages=messages,
        allow_cross_provider=True,  # NVIDIA NIM (DeepSeek) backs up Gemini when quota hits
    )

    return {
        "round": round_number,
        "model": actual_model,
        # Surface fallback visually when the original model was substituted
        "model_requested": model_key if actual_model != model_key else None,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usage": usage,
    }


def _resolve_debate_models(state: PantheonState, provider: LLMProvider) -> list[str]:
    """Return the list of model keys to use for debating.

    Priority:
    1. User-selected models (state["selected_models"]) when non-empty.
    2. Models mapped to debater_* roles in PHASE_MODEL_ROLES.
    3. All provider-available models as a last resort.
    """
    user_selected: list[str] = state.get("selected_models") or []
    if user_selected:
        return list(dict.fromkeys(user_selected))

    debater_keys = [
        model_key
        for role, model_key in PHASE_MODEL_ROLES.items()
        if role.startswith("debater_")
    ]
    if debater_keys:
        return list(dict.fromkeys(debater_keys))

    return provider.available_models

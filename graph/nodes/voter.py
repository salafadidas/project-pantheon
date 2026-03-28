"""
Voter node for Phase 4 of the Pantheon workflow.

Each debate model reads the full debate transcript and casts a vote for the
best approach or answer.  A simple majority-vote algorithm determines the
consensus winner.  All votes run concurrently with a per-model timeout.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import PantheonState
from llm.provider import PHASE_MODEL_ROLES, LLMProvider

logger = logging.getLogger(__name__)

PHASE_TIMEOUT_SECONDS: int = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

_SYSTEM_PROMPT = """\
You are an impartial AI judge reviewing a structured multi-model debate.
Read the full debate transcript below and cast your vote for the single best
approach or answer presented.

Respond with a short label (≤ 10 words) that identifies the winning position,
followed by one sentence of justification.  Format exactly:

VOTE: <label>
REASON: <one sentence>\
"""


def _format_debate(debate_history: List[dict]) -> str:
    """Render the full debate transcript for the voter prompt."""
    if not debate_history:
        return "(No debate history available.)"
    lines: list[str] = []
    for entry in debate_history:
        lines.append(
            f"[Round {entry['round']} | {entry['model']}]\n{entry['content']}"
        )
    return "\n\n---\n\n".join(lines)


async def voter_node(state: PantheonState) -> PantheonState:
    """Collect votes from all debate models and determine consensus.

    Args:
        state: Current PantheonState (immutable — new values returned).

    Returns:
        Updated PantheonState with votes, consensus, and phase = "synthesis".
    """
    provider = LLMProvider()
    voter_models = _resolve_voter_models(provider)
    debate_transcript = _format_debate(state.get("debate_history", []))

    tasks = [
        _vote_with_timeout(
            provider=provider,
            model_key=model_key,
            task=state["task"],
            debate_transcript=debate_transcript,
            timeout=PHASE_TIMEOUT_SECONDS,
        )
        for model_key in voter_models
    ]

    results: list[tuple[str, str]] = await asyncio.gather(*tasks)
    votes: dict[str, str] = {model: vote for model, vote in results}

    consensus = _calculate_consensus(votes)
    logger.info(
        "Voting complete: %d votes cast, consensus=%s",
        len(votes),
        consensus or "none",
    )

    return {
        **state,
        "votes": votes,
        "consensus": consensus,
        "phase": "synthesis",
    }


async def _vote_with_timeout(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
    debate_transcript: str,
    timeout: int,
) -> tuple[str, str]:
    """Cast one vote with a timeout guard.

    Returns:
        (model_key, vote_label) — placeholder on failure.
    """
    try:
        vote = await asyncio.wait_for(
            _cast_vote(
                provider=provider,
                model_key=model_key,
                task=task,
                debate_transcript=debate_transcript,
            ),
            timeout=float(timeout),
        )
        logger.info("Voter %s: %s", model_key, vote)
        return model_key, vote
    except asyncio.TimeoutError:
        logger.warning("Voter %s timed out after %ds", model_key, timeout)
        return model_key, "[TIMEOUT]"
    except Exception as exc:
        logger.warning("Voter %s failed: %s", model_key, exc)
        return model_key, "[ERROR]"


async def _cast_vote(
    *,
    provider: LLMProvider,
    model_key: str,
    task: str,
    debate_transcript: str,
) -> str:
    """Invoke a single model to cast its vote and return the extracted label."""
    llm = provider.get_chat_model(model_key)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Original task:\n{task}\n\n"
                f"Full debate transcript:\n{debate_transcript}\n\n"
                f"You are {model_key}. Cast your vote now."
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    raw: str = response.content if hasattr(response, "content") else str(response)

    # Extract the VOTE: label from the response
    for line in raw.splitlines():
        if line.strip().upper().startswith("VOTE:"):
            return line.split(":", 1)[1].strip()

    # Fallback: return first non-empty line
    for line in raw.splitlines():
        if line.strip():
            return line.strip()[:80]

    return raw.strip()[:80]


def _calculate_consensus(votes: dict[str, str]) -> str | None:
    """Determine the majority-vote winner.

    Returns the label that received the most votes.  Returns None only if
    there are no valid votes at all.
    """
    valid_votes = [v for v in votes.values() if v not in ("[TIMEOUT]", "[ERROR]")]
    if not valid_votes:
        return None

    # Normalise labels to lower-case for comparison
    counter: Counter[str] = Counter(v.lower() for v in valid_votes)
    winner_lower, _ = counter.most_common(1)[0]

    # Return the original-casing version of the winner
    for v in valid_votes:
        if v.lower() == winner_lower:
            return v

    return valid_votes[0]


def _resolve_voter_models(provider: LLMProvider) -> list[str]:
    """Return the list of models that should cast votes.

    Uses debater_* roles (same participants as the debate), falling back to
    all available models if none are configured.
    """
    debater_keys = [
        model_key
        for role, model_key in PHASE_MODEL_ROLES.items()
        if role.startswith("debater_")
    ]
    if debater_keys:
        seen: set[str] = set()
        unique: list[str] = []
        for k in debater_keys:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        return unique

    return provider.available_models

"""
Synthesizer node for Phase 5 of the Pantheon workflow.

The PM model combines the research findings, full debate transcript, and
voting results into a single structured markdown report.  This is the final
node — it sets phase = "complete".
"""

from __future__ import annotations

import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import PantheonState
from llm.provider import PHASE_MODEL_ROLES, LLMProvider

logger = logging.getLogger(__name__)

PHASE_TIMEOUT_SECONDS: int = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

_SYSTEM_PROMPT = """\
You are a senior project manager writing the final summary of a multi-AI
collaborative analysis session.

You will receive:
- The original task
- Each AI model's independent research summary
- The full multi-round debate transcript
- Each model's vote and the consensus decision

Produce a structured markdown report with these exact sections:

## Summary
One-paragraph executive summary of the task and the collaborative process.

## Key Insights
Bullet list of the most important findings surfaced during research and debate.

## Consensus Decision
The agreed-upon best approach or answer, with a brief rationale.

## Dissenting Views
Any significant minority positions or caveats raised in the debate.

## Cost Breakdown
A table or bullet list showing token usage / estimated cost by model and phase
(use the data provided; write "N/A" if unavailable).

Be precise, neutral, and concise.  Do not invent information not present in
the inputs.\
"""


def _format_research(research_results: dict[str, str]) -> str:
    if not research_results:
        return "(No research results available.)"
    sections: list[str] = []
    for model, text in research_results.items():
        sections.append(f"### {model}\n{text}")
    return "\n\n".join(sections)


def _format_debate(debate_history: list[dict]) -> str:
    if not debate_history:
        return "(No debate history available.)"
    lines: list[str] = []
    for entry in debate_history:
        lines.append(
            f"[Round {entry['round']} | {entry['model']}]\n{entry['content']}"
        )
    return "\n\n---\n\n".join(lines)


def _format_votes(votes: dict[str, str], consensus: str | None) -> str:
    if not votes:
        return "(No votes recorded.)"
    lines = [f"- **{model}**: {vote}" for model, vote in votes.items()]
    lines.append(f"\n**Consensus**: {consensus or 'No consensus reached'}")
    return "\n".join(lines)


def _format_cost(cost_summary: dict) -> str:
    if not cost_summary:
        return "N/A"
    lines: list[str] = []
    if "total_cost_usd" in cost_summary:
        lines.append(f"- **Total cost**: ${cost_summary['total_cost_usd']:.4f}")
    if "by_model" in cost_summary:
        for model, cost in cost_summary["by_model"].items():
            lines.append(f"  - {model}: ${cost:.4f}")
    if "by_phase" in cost_summary:
        for phase, cost in cost_summary["by_phase"].items():
            lines.append(f"  - Phase {phase}: ${cost:.4f}")
    return "\n".join(lines) if lines else "N/A"


async def synthesizer_node(state: PantheonState) -> PantheonState:
    """Synthesize all phase outputs into a final structured report.

    Args:
        state: Current PantheonState (immutable — new values returned).

    Returns:
        Updated PantheonState with final_report set and phase = "complete".
    """
    provider = LLMProvider()

    # Use the session PM model if available; fall back to role default
    pm_model_key = state.get("pm_model") or PHASE_MODEL_ROLES.get(
        "synthesizer", "claude-sonnet"
    )
    llm = provider.get_chat_model(pm_model_key)

    research_section = _format_research(state.get("research_results", {}))
    debate_section = _format_debate(state.get("debate_history", []))
    votes_section = _format_votes(
        state.get("votes", {}), state.get("consensus")
    )
    cost_section = _format_cost(state.get("cost_summary", {}))

    user_message = (
        f"## Original Task\n{state['task']}\n\n"
        f"## Research Summaries\n{research_section}\n\n"
        f"## Debate Transcript\n{debate_section}\n\n"
        f"## Votes & Consensus\n{votes_section}\n\n"
        f"## Cost Data\n{cost_section}\n\n"
        "Now write the final report."
    )

    final_report: str
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        )
        content: str = (
            response.content if hasattr(response, "content") else str(response)
        )
        final_report = content.strip()
        logger.info(
            "Synthesizer complete: %d chars in final report (model=%s)",
            len(final_report),
            pm_model_key,
        )
    except Exception as exc:
        logger.error("Synthesizer failed: %s", exc)
        final_report = (
            "# Synthesis Error\n\n"
            f"The synthesizer encountered an error: {exc}\n\n"
            f"## Partial Results\n\n"
            f"**Consensus**: {state.get('consensus') or 'N/A'}\n\n"
            f"**Votes**:\n{votes_section}"
        )

    return {
        **state,
        "final_report": final_report,
        "phase": "complete",
    }

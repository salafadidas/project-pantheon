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
from llm.quota_fallback import ainvoke_with_fallback

logger = logging.getLogger(__name__)

PHASE_TIMEOUT_SECONDS: int = int(os.getenv("PHASE_TIMEOUT_SECONDS", "60"))

_SYSTEM_PROMPT = """\
你是一位資深專案經理，負責撰寫多 AI 協作分析會議的最終總結報告。

你將收到以下資料：
- 原始任務
- 每個 AI 模型的獨立研究摘要
- 完整的多輪辯論記錄
- 每個模型的投票結果與共識決定

請用繁體中文撰寫一份結構化的 Markdown 報告，包含以下確切章節。
重要：每個章節必須詳盡且深入——每節最少 100 到 300 字。
不要只寫簡短的條列式重點，請對每個要點加以說明、提供背景脈絡與推理依據。

## 摘要
撰寫 2–3 段（至少 150 字），涵蓋：任務內容為何、為何重要、哪些 AI 模型參與、
進行了幾輪辯論，以及整體協作過程的概況。

## 關鍵洞見
列出至少 5 項關鍵洞見。每項洞見以粗體標題開頭，後跟 2–4 句說明（整節至少 200 字）。
涵蓋研究階段與辯論階段的發現。

## 共識決定
撰寫至少 150 字，說明：達成共識的答案或方案為何、背後的核心邏輯、
哪些模型支持此立場，以及這個決定對使用者的實際意義。

## 異見觀點
撰寫至少 100 字，涵蓋：少數派的立場、被提出但遭否決的替代方案、
重要的警告、風險，或共識未能完全處理的權衡取捨。
若所有模型均達成一致，請說明共識可能不成立的情境或條件。

## 建議行動
撰寫至少 150 字，提供具體可行的後續步驟，協助使用者根據共識決定採取行動。
請按優先順序排列，並說明每項建議的理由。

## 費用明細
以表格或條列方式呈現各模型與各階段的 Token 用量及估計費用
（使用所提供的數據；如無資料請填寫「無資料」）。

請保持精確、客觀、以證據為基礎。不要捏造輸入資料中沒有的資訊。
請擴展已提供的內容——深度與詳盡程度至關重要。\
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

    # Always use the designated synthesizer model — never the session pm_model.
    # pm_model can be set to any debater (including NVIDIA NIM models that time
    # out on long prompts), which caused the "Synthesis Error: 504" seen in prod.
    pm_model_key = PHASE_MODEL_ROLES.get("synthesizer", "claude-sonnet")

    research_section = _format_research(state.get("research_results", {}))
    debate_section = _format_debate(state.get("debate_history", []))
    votes_section = _format_votes(
        state.get("votes", {}), state.get("consensus")
    )
    cost_section = _format_cost(state.get("cost_summary", {}))

    user_message = (
        f"## 原始任務\n{state['task']}\n\n"
        f"## 研究摘要\n{research_section}\n\n"
        f"## 辯論記錄\n{debate_section}\n\n"
        f"## 投票與共識\n{votes_section}\n\n"
        f"## 費用資料\n{cost_section}\n\n"
        "請現在撰寫最終報告。"
    )

    final_report: str
    try:
        actual_model, content = await ainvoke_with_fallback(
            provider=provider,
            model_key=pm_model_key,
            messages=[
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ],
            # Synthesizer must always produce a report — fall through to
            # Claude Haiku / GPT-4o-mini if the primary provider is exhausted.
            allow_cross_provider=True,
        )
        final_report = content
        logger.info(
            "Synthesizer complete: %d chars in final report (model=%s)",
            len(final_report),
            actual_model,
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

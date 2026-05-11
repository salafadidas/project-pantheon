"""
Token usage and cost tracking for LLM API calls.

Uses LiteLLM's built-in cost calculation and stores per-session cost logs
for the 5-phase workflow. Thread-safe via asyncio.Lock.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import litellm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageRecord:
    """Immutable record of a single LLM API call's usage."""
    model: str
    phase: str
    role: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    timestamp: float
    session_id: Optional[str] = None


@dataclass
class SessionCostSummary:
    """Aggregated cost summary for a session."""
    session_id: str
    total_cost_usd: float
    total_tokens_in: int
    total_tokens_out: int
    records_count: int
    by_model: dict[str, float] = field(default_factory=dict)
    by_phase: dict[str, float] = field(default_factory=dict)


class CostTracker:
    """Tracks token usage and costs across LLM calls.

    Thread-safe. Stores records in memory; can be extended to persist to PostgreSQL.

    Usage:
        tracker = CostTracker()
        record = tracker.record_usage(response, model="gpt-4o-mini", phase="pm_router", role="classifier")
        summary = tracker.get_session_summary("session-123")
    """

    def __init__(self, budget_limit_usd: Optional[float] = None) -> None:
        self._records: list[UsageRecord] = []
        self._lock = asyncio.Lock()
        self._budget_limit = budget_limit_usd
        logger.info(
            "CostTracker initialized, budget_limit=%.2f USD"
            if budget_limit_usd
            else "CostTracker initialized, no budget limit",
            budget_limit_usd or 0,
        )

    def record_usage(
        self,
        response: object,
        *,
        model: str,
        phase: str,
        role: str,
        session_id: Optional[str] = None,
    ) -> UsageRecord:
        """Record usage from a LiteLLM/LangChain response synchronously.

        Args:
            response: LiteLLM ModelResponse or LangChain AIMessage with usage_metadata
            model: Model identifier (e.g. "gpt-4o-mini")
            phase: Current phase (e.g. "researcher", "debater")
            role: Agent role (e.g. "debater_claude")
            session_id: Optional session identifier

        Returns:
            Frozen UsageRecord
        """
        tokens_in, tokens_out = _extract_token_counts(response)
        cost = _calculate_cost(model, tokens_in, tokens_out)

        record = UsageRecord(
            model=model,
            phase=phase,
            role=role,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            timestamp=time.time(),
            session_id=session_id,
        )

        self._records.append(record)

        logger.info(
            "Cost recorded: model=%s phase=%s tokens=%d/%d cost=$%.4f",
            model,
            phase,
            tokens_in,
            tokens_out,
            cost,
        )

        if self._budget_limit and self._get_total_cost() > self._budget_limit:
            logger.warning(
                "Budget limit exceeded! Total: $%.4f / $%.4f",
                self._get_total_cost(),
                self._budget_limit,
            )

        return record

    async def arecord_usage(
        self,
        response: object,
        *,
        model: str,
        phase: str,
        role: str,
        session_id: Optional[str] = None,
    ) -> UsageRecord:
        """Async version of record_usage with lock for thread safety."""
        async with self._lock:
            return self.record_usage(
                response,
                model=model,
                phase=phase,
                role=role,
                session_id=session_id,
            )

    def get_session_summary(self, session_id: str) -> SessionCostSummary:
        """Get aggregated cost summary for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            SessionCostSummary with totals and breakdowns
        """
        session_records = [r for r in self._records if r.session_id == session_id]

        by_model: dict[str, float] = {}
        by_phase: dict[str, float] = {}

        for record in session_records:
            by_model[record.model] = by_model.get(record.model, 0) + record.cost_usd
            by_phase[record.phase] = by_phase.get(record.phase, 0) + record.cost_usd

        return SessionCostSummary(
            session_id=session_id,
            total_cost_usd=sum(r.cost_usd for r in session_records),
            total_tokens_in=sum(r.tokens_in for r in session_records),
            total_tokens_out=sum(r.tokens_out for r in session_records),
            records_count=len(session_records),
            by_model=by_model,
            by_phase=by_phase,
        )

    def get_all_records(self) -> list[UsageRecord]:
        """Return a copy of all usage records."""
        return list(self._records)

    def _get_total_cost(self) -> float:
        return sum(r.cost_usd for r in self._records)

    @property
    def total_cost_usd(self) -> float:
        """Total cost across all tracked calls."""
        return self._get_total_cost()

    @property
    def total_tokens(self) -> tuple[int, int]:
        """Total (tokens_in, tokens_out) across all calls."""
        return (
            sum(r.tokens_in for r in self._records),
            sum(r.tokens_out for r in self._records),
        )


def _extract_token_counts(response: object) -> tuple[int, int]:
    """Extract input/output token counts from various response types.

    Handles:
    - LiteLLM ModelResponse (response.usage)
    - LangChain AIMessage (response.usage_metadata)
    - Dict with usage info
    """
    # LiteLLM ModelResponse
    if hasattr(response, "usage") and response.usage:
        usage = response.usage
        return (
            getattr(usage, "prompt_tokens", 0),
            getattr(usage, "completion_tokens", 0),
        )

    # LangChain AIMessage with usage_metadata
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        return (
            meta.get("input_tokens", 0),
            meta.get("output_tokens", 0),
        )

    # Dict fallback
    if isinstance(response, dict):
        usage = response.get("usage", {})
        return (
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )

    logger.warning("Could not extract token counts from response type: %s", type(response))
    return (0, 0)


def _calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost using LiteLLM's built-in cost data.

    Falls back to zero if model pricing is not available.
    """
    try:
        cost = litellm.completion_cost(
            model=model,
            prompt_tokens=tokens_in,
            completion_tokens=tokens_out,
        )
        return cost
    except Exception:
        logger.debug("Cost calculation not available for model=%s, returning 0", model)
        return 0.0


def merge_usage(
    existing: dict,
    *,
    model_key: str,
    litellm_model: str,
    phase: str,
    input_tokens: int,
    output_tokens: int,
) -> dict:
    """Merge one LLM call's usage into the accumulated cost_summary dict.

    Pure function — returns a new dict, never mutates ``existing``.
    Designed for the LangGraph last-write-wins state pattern: each node calls
    this once per LLM call and returns the updated dict as part of its state.

    Structure of the returned dict::

        {
            "by_model": {
                "claude-sonnet": {"input_tokens": 1500, "output_tokens": 800, "cost_usd": 0.016},
                ...
            },
            "by_phase": {
                "research": {"input_tokens": 4500, "output_tokens": 2400, "cost_usd": 0.048},
                ...
            },
            "total_input_tokens": 6000,
            "total_output_tokens": 3200,
            "total_cost_usd": 0.064,
        }
    """
    cost = _calculate_cost(litellm_model, input_tokens, output_tokens)

    result = dict(existing) if existing else {}

    by_model: dict = {k: dict(v) for k, v in result.get("by_model", {}).items()}
    entry = dict(by_model.get(model_key, {}))
    entry["input_tokens"] = entry.get("input_tokens", 0) + input_tokens
    entry["output_tokens"] = entry.get("output_tokens", 0) + output_tokens
    entry["cost_usd"] = round(entry.get("cost_usd", 0.0) + cost, 6)
    by_model[model_key] = entry

    by_phase: dict = {k: dict(v) for k, v in result.get("by_phase", {}).items()}
    phase_entry = dict(by_phase.get(phase, {}))
    phase_entry["input_tokens"] = phase_entry.get("input_tokens", 0) + input_tokens
    phase_entry["output_tokens"] = phase_entry.get("output_tokens", 0) + output_tokens
    phase_entry["cost_usd"] = round(phase_entry.get("cost_usd", 0.0) + cost, 6)
    by_phase[phase] = phase_entry

    result["by_model"] = by_model
    result["by_phase"] = by_phase
    result["total_input_tokens"] = result.get("total_input_tokens", 0) + input_tokens
    result["total_output_tokens"] = result.get("total_output_tokens", 0) + output_tokens
    result["total_cost_usd"] = round(result.get("total_cost_usd", 0.0) + cost, 6)

    return result

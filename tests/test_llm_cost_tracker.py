"""Tests for llm/cost_tracker.py"""

import asyncio
import pytest
from unittest.mock import patch

from llm.cost_tracker import (
    CostTracker,
    UsageRecord,
    SessionCostSummary,
    _extract_token_counts,
    _calculate_cost,
)


# --------------------------------------------------------------------------- #
# _extract_token_counts                                                        #
# --------------------------------------------------------------------------- #

class _LiteLLMUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _LiteLLMResponse:
    def __init__(self, prompt_tokens, completion_tokens):
        self.usage = _LiteLLMUsage(prompt_tokens, completion_tokens)


class _LangChainMessage:
    def __init__(self, input_tokens, output_tokens):
        self.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}


def test_extract_from_litellm_response():
    resp = _LiteLLMResponse(100, 50)
    assert _extract_token_counts(resp) == (100, 50)


def test_extract_from_langchain_message():
    msg = _LangChainMessage(200, 80)
    assert _extract_token_counts(msg) == (200, 80)


def test_extract_from_dict():
    d = {"usage": {"prompt_tokens": 30, "completion_tokens": 15}}
    assert _extract_token_counts(d) == (30, 15)


def test_extract_from_unknown_returns_zeros():
    assert _extract_token_counts("unknown") == (0, 0)
    assert _extract_token_counts(None) == (0, 0)
    assert _extract_token_counts(42) == (0, 0)


def test_extract_from_dict_missing_usage():
    assert _extract_token_counts({}) == (0, 0)


# --------------------------------------------------------------------------- #
# _calculate_cost                                                              #
# --------------------------------------------------------------------------- #

def test_calculate_cost_returns_float():
    with patch("litellm.completion_cost", return_value=0.0012):
        cost = _calculate_cost("gpt-4o-mini", 100, 50)
    assert isinstance(cost, float)
    assert cost == pytest.approx(0.0012)


def test_calculate_cost_returns_zero_on_exception():
    with patch("litellm.completion_cost", side_effect=Exception("no pricing")):
        cost = _calculate_cost("unknown-model", 100, 50)
    assert cost == 0.0


# --------------------------------------------------------------------------- #
# CostTracker.record_usage                                                     #
# --------------------------------------------------------------------------- #

def test_record_usage_returns_usage_record():
    tracker = CostTracker()
    resp = _LangChainMessage(10, 20)
    with patch("litellm.completion_cost", return_value=0.001):
        record = tracker.record_usage(resp, model="gpt-4o-mini", phase="research", role="researcher_gpt")
    assert isinstance(record, UsageRecord)
    assert record.tokens_in == 10
    assert record.tokens_out == 20
    assert record.model == "gpt-4o-mini"
    assert record.phase == "research"
    assert record.cost_usd == pytest.approx(0.001)


def test_record_usage_accumulates():
    tracker = CostTracker()
    resp = _LangChainMessage(5, 5)
    with patch("litellm.completion_cost", return_value=0.0005):
        tracker.record_usage(resp, model="claude-sonnet", phase="debate", role="debater_claude")
        tracker.record_usage(resp, model="gpt-4o", phase="debate", role="debater_gpt")
    assert len(tracker.get_all_records()) == 2


def test_total_cost_sums_records():
    tracker = CostTracker()
    resp = _LangChainMessage(10, 10)
    with patch("litellm.completion_cost", return_value=0.001):
        tracker.record_usage(resp, model="gpt-4o-mini", phase="routing", role="pm_router")
        tracker.record_usage(resp, model="claude-sonnet", phase="synthesis", role="synthesizer")
    assert tracker.total_cost_usd == pytest.approx(0.002)


def test_total_tokens_property():
    tracker = CostTracker()
    with patch("litellm.completion_cost", return_value=0.0):
        tracker.record_usage(_LangChainMessage(10, 20), model="m", phase="p", role="r")
        tracker.record_usage(_LangChainMessage(30, 40), model="m", phase="p", role="r")
    assert tracker.total_tokens == (40, 60)


# --------------------------------------------------------------------------- #
# CostTracker.get_session_summary                                              #
# --------------------------------------------------------------------------- #

def test_session_summary_empty():
    tracker = CostTracker()
    summary = tracker.get_session_summary("nonexistent")
    assert summary.total_cost_usd == 0.0
    assert summary.records_count == 0
    assert summary.by_model == {}
    assert summary.by_phase == {}


def test_session_summary_correct_aggregation():
    tracker = CostTracker()
    with patch("litellm.completion_cost", return_value=0.01):
        tracker.record_usage(
            _LangChainMessage(10, 10), model="gpt-4o", phase="research",
            role="researcher_gpt", session_id="s1"
        )
        tracker.record_usage(
            _LangChainMessage(10, 10), model="claude-sonnet", phase="debate",
            role="debater_claude", session_id="s1"
        )
        # Different session — should not appear in s1's summary
        tracker.record_usage(
            _LangChainMessage(10, 10), model="gpt-4o", phase="research",
            role="researcher_gpt", session_id="s2"
        )

    summary = tracker.get_session_summary("s1")
    assert summary.records_count == 2
    assert summary.total_cost_usd == pytest.approx(0.02)
    assert "gpt-4o" in summary.by_model
    assert "claude-sonnet" in summary.by_model
    assert "research" in summary.by_phase
    assert "debate" in summary.by_phase


def test_session_summary_is_dataclass():
    tracker = CostTracker()
    summary = tracker.get_session_summary("x")
    assert isinstance(summary, SessionCostSummary)


# --------------------------------------------------------------------------- #
# CostTracker.arecord_usage (async)                                           #
# --------------------------------------------------------------------------- #

async def test_arecord_usage_is_async():
    tracker = CostTracker()
    resp = _LangChainMessage(5, 5)
    with patch("litellm.completion_cost", return_value=0.0):
        record = await tracker.arecord_usage(resp, model="m", phase="p", role="r")
    assert isinstance(record, UsageRecord)


# --------------------------------------------------------------------------- #
# Budget limit warning (doesn't raise, just logs)                             #
# --------------------------------------------------------------------------- #

def test_budget_limit_does_not_raise():
    tracker = CostTracker(budget_limit_usd=0.001)
    with patch("litellm.completion_cost", return_value=1.0):
        # Should log a warning but not raise
        tracker.record_usage(_LangChainMessage(100, 100), model="m", phase="p", role="r")
    assert tracker.total_cost_usd == pytest.approx(1.0)

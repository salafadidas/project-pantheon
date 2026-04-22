"""Tests for graph/nodes/voter.py — pure functions and mocked node."""

from unittest.mock import MagicMock, patch

from graph.nodes.voter import (
    _calculate_consensus,
    _format_debate,
    _resolve_voter_models,
)
from tests.conftest import make_state


# --------------------------------------------------------------------------- #
# _format_debate                                                               #
# --------------------------------------------------------------------------- #

def test_format_debate_empty_history():
    result = _format_debate([])
    assert "No debate history" in result


def test_format_debate_single_entry():
    history = [{"round": 1, "model": "claude-sonnet", "content": "My argument"}]
    result = _format_debate(history)
    assert "Round 1" in result
    assert "claude-sonnet" in result
    assert "My argument" in result


def test_format_debate_multiple_rounds():
    history = [
        {"round": 1, "model": "claude-sonnet", "content": "Point A"},
        {"round": 1, "model": "gpt-4o", "content": "Point B"},
        {"round": 2, "model": "claude-sonnet", "content": "Rebuttal"},
    ]
    result = _format_debate(history)
    assert "Round 1" in result
    assert "Round 2" in result
    assert "Point A" in result
    assert "Rebuttal" in result
    # Entries are separated
    assert "---" in result


# --------------------------------------------------------------------------- #
# _calculate_consensus                                                         #
# --------------------------------------------------------------------------- #

def test_consensus_single_vote():
    votes = {"claude-sonnet": "Approach A"}
    assert _calculate_consensus(votes) == "Approach A"


def test_consensus_majority():
    votes = {
        "claude-sonnet": "Approach A",
        "gpt-4o": "Approach A",
        "gemini-2.5-pro": "Approach B",
    }
    result = _calculate_consensus(votes)
    assert result == "Approach A"


def test_consensus_case_insensitive_matching():
    votes = {
        "claude-sonnet": "Approach A",
        "gpt-4o": "approach a",  # same, different case
        "gemini-2.5-pro": "Approach B",
    }
    result = _calculate_consensus(votes)
    # Winner is "approach a" / "Approach A" — either casing is acceptable
    assert result.lower() == "approach a"


def test_consensus_all_timeouts_returns_none():
    votes = {
        "claude-sonnet": "[TIMEOUT]",
        "gpt-4o": "[TIMEOUT]",
    }
    assert _calculate_consensus(votes) is None


def test_consensus_all_errors_returns_none():
    votes = {"claude-sonnet": "[ERROR]", "gpt-4o": "[ERROR]"}
    assert _calculate_consensus(votes) is None


def test_consensus_mixed_errors_and_valid():
    votes = {
        "claude-sonnet": "Approach X",
        "gpt-4o": "[ERROR]",
        "gemini-2.5-pro": "Approach X",
    }
    result = _calculate_consensus(votes)
    assert result == "Approach X"


def test_consensus_empty_votes():
    assert _calculate_consensus({}) is None


def test_consensus_tie_returns_a_winner():
    votes = {"m1": "A", "m2": "B"}
    result = _calculate_consensus(votes)
    assert result in ("A", "B")


# --------------------------------------------------------------------------- #
# _resolve_voter_models                                                        #
# --------------------------------------------------------------------------- #

def test_resolve_voter_models_returns_list():
    from llm.provider import LLMProvider
    provider = LLMProvider()
    state = make_state(selected_models=[])
    models = _resolve_voter_models(provider, state)
    assert isinstance(models, list)
    assert len(models) > 0


def test_resolve_voter_models_no_duplicates():
    from llm.provider import LLMProvider
    provider = LLMProvider()
    state = make_state(selected_models=[])
    models = _resolve_voter_models(provider, state)
    assert len(models) == len(set(models))


# --------------------------------------------------------------------------- #
# voter_node (mocked LLM)                                                     #
# --------------------------------------------------------------------------- #

async def test_voter_node_sets_phase_to_synthesis():
    from graph.nodes.voter import voter_node
    from tests.conftest import MockChatLLM

    state = make_state(
        phase="voting",
        debate_history=[
            {"round": 1, "model": "claude-sonnet", "content": "Arg A"},
            {"round": 1, "model": "gpt-4o", "content": "Arg B"},
        ],
    )

    mock_llm = MockChatLLM("VOTE: Approach A\nREASON: It is best.")

    with patch("graph.nodes.voter.LLMProvider") as mock_provider_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider_cls.return_value = mock_provider
        # Return at least one voter model
        mock_provider.available_models = ["claude-sonnet"]

        with patch("graph.nodes.voter.PHASE_MODEL_ROLES", {"debater_claude": "claude-sonnet"}):
            result = await voter_node(state)

    assert result["phase"] == "synthesis"


async def test_voter_node_populates_votes():
    from graph.nodes.voter import voter_node
    from tests.conftest import MockChatLLM

    state = make_state(phase="voting", debate_history=[])
    mock_llm = MockChatLLM("VOTE: REST is simpler\nREASON: Less overhead.")

    with patch("graph.nodes.voter.LLMProvider") as mock_provider_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider_cls.return_value = mock_provider
        mock_provider.available_models = ["gpt-4o-mini"]

        with patch("graph.nodes.voter.PHASE_MODEL_ROLES", {"debater_gpt": "gpt-4o-mini"}):
            result = await voter_node(state)

    assert isinstance(result["votes"], dict)
    assert len(result["votes"]) > 0

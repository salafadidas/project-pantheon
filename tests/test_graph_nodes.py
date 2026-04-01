"""Tests for graph node functions — pm_router and researcher (mocked LLM)."""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from tests.conftest import make_state, MockChatLLM


# --------------------------------------------------------------------------- #
# pm_router_node                                                               #
# --------------------------------------------------------------------------- #

async def test_pm_router_sets_phase_to_research():
    from graph.nodes.pm_router import pm_router_node

    state = make_state(task="How does DNS work?")
    response_json = json.dumps({
        "task_type": "factual",
        "pm_model": "gpt-4o-mini",
        "reasoning": "Simple factual query.",
    })
    mock_llm = MockChatLLM(response_json)

    with patch("graph.nodes.pm_router.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider.available_models = ["gpt-4o-mini", "gpt-4o", "claude-sonnet"]
        mock_cls.return_value = mock_provider

        result = await pm_router_node(state)

    assert result["phase"] == "research"


async def test_pm_router_sets_pm_model_from_response():
    from graph.nodes.pm_router import pm_router_node

    state = make_state(task="Write a poem about AI")
    response_json = json.dumps({
        "task_type": "creative",
        "pm_model": "claude-sonnet",
        "reasoning": "Creative task — Claude is best.",
    })
    mock_llm = MockChatLLM(response_json)

    with patch("graph.nodes.pm_router.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider.available_models = ["gpt-4o-mini", "gpt-4o", "claude-sonnet"]
        mock_cls.return_value = mock_provider

        result = await pm_router_node(state)

    assert result["pm_model"] == "claude-sonnet"


async def test_pm_router_fallback_on_bad_json():
    from graph.nodes.pm_router import pm_router_node

    state = make_state(task="Anything")
    mock_llm = MockChatLLM("not valid json at all !!!")

    with patch("graph.nodes.pm_router.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider.available_models = ["gpt-4o-mini"]

        with patch("graph.nodes.pm_router.PHASE_MODEL_ROLES", {"pm_router": "gpt-4o-mini"}):
            mock_cls.return_value = mock_provider
            result = await pm_router_node(state)

    # Phase still advances even on parse failure
    assert result["phase"] == "research"
    assert "pm_model" in result


async def test_pm_router_uses_task_type_map_for_unknown_model():
    from graph.nodes.pm_router import pm_router_node

    state = make_state(task="Debug this code")
    response_json = json.dumps({
        "task_type": "technical",
        "pm_model": "nonexistent-model",
        "reasoning": "Technical task.",
    })
    mock_llm = MockChatLLM(response_json)

    with patch("graph.nodes.pm_router.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider.available_models = ["gpt-4o-mini", "gpt-4o", "claude-sonnet"]
        mock_cls.return_value = mock_provider

        result = await pm_router_node(state)

    # Falls back to the task-type map: "technical" -> "gpt-4o"
    assert result["pm_model"] == "gpt-4o"


async def test_pm_router_preserves_task_in_state():
    from graph.nodes.pm_router import pm_router_node

    original_task = "What is quantum entanglement?"
    state = make_state(task=original_task)
    mock_llm = MockChatLLM(json.dumps({"task_type": "factual", "pm_model": "gpt-4o-mini", "reasoning": ""}))

    with patch("graph.nodes.pm_router.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_provider.available_models = ["gpt-4o-mini"]
        mock_cls.return_value = mock_provider

        result = await pm_router_node(state)

    assert result["task"] == original_task


# --------------------------------------------------------------------------- #
# researcher_node                                                              #
# --------------------------------------------------------------------------- #

async def test_researcher_node_sets_phase_to_debate():
    from graph.nodes.researcher import researcher_node

    state = make_state(phase="research")
    mock_llm = MockChatLLM("Here is my research summary.")

    with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_cls.return_value = mock_provider

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {
            "researcher_claude": "claude-sonnet",
        }):
            result = await researcher_node(state)

    assert result["phase"] == "debate"


async def test_researcher_node_populates_research_results():
    from graph.nodes.researcher import researcher_node

    state = make_state(phase="research")
    mock_llm = MockChatLLM("Detailed research findings.")

    with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_cls.return_value = mock_provider

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {
            "researcher_gpt": "gpt-4o",
        }):
            result = await researcher_node(state)

    assert "gpt-4o" in result["research_results"]
    assert result["research_results"]["gpt-4o"] == "Detailed research findings."


async def test_researcher_node_handles_timeout():
    from graph.nodes.researcher import researcher_node
    import asyncio

    state = make_state(phase="research")

    async def slow_invoke(_):
        await asyncio.sleep(100)

    mock_llm = MagicMock()
    mock_llm.ainvoke = slow_invoke

    with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_cls.return_value = mock_provider

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {"researcher_claude": "claude-sonnet"}):
            with patch("graph.nodes.researcher.PHASE_TIMEOUT_SECONDS", 0):
                result = await researcher_node(state)

    # Should not raise — returns error placeholder instead
    assert "claude-sonnet" in result["research_results"]
    assert "[ERROR" in result["research_results"]["claude-sonnet"]


async def test_researcher_node_handles_llm_exception():
    from graph.nodes.researcher import researcher_node

    state = make_state(phase="research")

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_cls.return_value = mock_provider

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {"researcher_gpt": "gpt-4o"}):
            result = await researcher_node(state)

    assert "gpt-4o" in result["research_results"]
    assert "[ERROR" in result["research_results"]["gpt-4o"]


async def test_researcher_node_concurrent_multiple_models():
    from graph.nodes.researcher import researcher_node

    state = make_state(phase="research")
    call_count = 0

    class CountingLLM:
        async def ainvoke(self, _):
            nonlocal call_count
            call_count += 1
            from tests.conftest import MockAIMessage
            return MockAIMessage(f"Research from model {call_count}")

    mock_llm = CountingLLM()

    with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.get_chat_model.return_value = mock_llm
        mock_cls.return_value = mock_provider

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {
            "researcher_claude": "claude-sonnet",
            "researcher_gpt": "gpt-4o",
            "researcher_gemini": "gemini-2.5-pro",
        }):
            result = await researcher_node(state)

    assert len(result["research_results"]) == 3
    assert call_count == 3

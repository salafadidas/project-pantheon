"""
Tests for the model-selection feature end-to-end:

  1. llm/model_catalog.py     — ModelInfo dataclass, pricing, availability
  2. api/v1/models.py          — GET /api/v1/models endpoint (FastAPI TestClient)
  3. api/v1/sessions.py        — selected_models in StartSessionRequest
  4. graph/nodes/researcher.py — _resolve_researcher_models honours selected_models
  5. graph/nodes/debater.py    — _resolve_debate_models honours selected_models
  6. graph/nodes/voter.py      — _resolve_voter_models honours selected_models
  7. Integration               — researcher/debater/voter nodes use only chosen models
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import MockChatLLM, MockAIMessage, make_state


# ===========================================================================
# 1. Model catalog
# ===========================================================================

class TestModelCatalog:
    def test_all_fields_present(self):
        from llm.model_catalog import DEBATE_MODELS
        for m in DEBATE_MODELS:
            assert m.model_id
            assert m.display_name
            assert m.provider in ("Anthropic", "OpenAI", "Google")
            assert m.price_input_per_1m >= 0
            assert m.price_output_per_1m >= 0
            assert m.context_window_k > 0
            assert isinstance(m.strengths, list) and len(m.strengths) >= 1
            assert m.env_key

    def test_estimated_cost_calculation(self):
        from llm.model_catalog import ModelInfo, ESTIMATED_INPUT_TOKENS, ESTIMATED_OUTPUT_TOKENS
        m = ModelInfo(
            model_id="test", display_name="Test", provider="Test",
            provider_color="blue", price_input_per_1m=10.0,
            price_output_per_1m=20.0, context_window_k=128,
            strengths=["fast"], env_key="TEST_KEY",
        )
        expected = (10.0 / 1_000_000 * ESTIMATED_INPUT_TOKENS
                    + 20.0 / 1_000_000 * ESTIMATED_OUTPUT_TOKENS)
        assert abs(m.estimated_cost_usd - expected) < 1e-9

    def test_is_available_false_when_key_missing(self, monkeypatch):
        from llm.model_catalog import ModelInfo
        monkeypatch.delenv("NO_SUCH_KEY_XYZ", raising=False)
        m = ModelInfo(
            model_id="x", display_name="X", provider="X", provider_color="blue",
            price_input_per_1m=1.0, price_output_per_1m=1.0, context_window_k=128,
            strengths=[], env_key="NO_SUCH_KEY_XYZ",
        )
        assert m.is_available() is False

    def test_is_available_true_when_key_set(self, monkeypatch):
        from llm.model_catalog import ModelInfo
        monkeypatch.setenv("MY_TEST_API_KEY", "abc123")
        m = ModelInfo(
            model_id="x", display_name="X", provider="X", provider_color="blue",
            price_input_per_1m=1.0, price_output_per_1m=1.0, context_window_k=128,
            strengths=[], env_key="MY_TEST_API_KEY",
        )
        assert m.is_available() is True

    def test_to_dict_includes_all_keys(self):
        from llm.model_catalog import DEBATE_MODELS
        d = DEBATE_MODELS[0].to_dict()
        for key in ("model_id", "display_name", "provider", "provider_color",
                    "price_input_per_1m", "price_output_per_1m", "context_window_k",
                    "strengths", "estimated_cost_usd", "estimated_tokens", "available"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_estimated_tokens_shape(self):
        from llm.model_catalog import DEBATE_MODELS, ESTIMATED_INPUT_TOKENS, ESTIMATED_OUTPUT_TOKENS
        d = DEBATE_MODELS[0].to_dict()
        assert d["estimated_tokens"]["input"] == ESTIMATED_INPUT_TOKENS
        assert d["estimated_tokens"]["output"] == ESTIMATED_OUTPUT_TOKENS

    def test_model_catalog_dict_keyed_by_model_id(self):
        from llm.model_catalog import MODEL_CATALOG, DEBATE_MODELS
        assert len(MODEL_CATALOG) == len(DEBATE_MODELS)
        for m in DEBATE_MODELS:
            assert MODEL_CATALOG[m.model_id] is m

    def test_default_selected_subset_of_catalog(self):
        from llm.model_catalog import DEFAULT_SELECTED, MODEL_CATALOG
        for mid in DEFAULT_SELECTED:
            assert mid in MODEL_CATALOG

    def test_claude_sonnet_pricing(self):
        from llm.model_catalog import MODEL_CATALOG
        m = MODEL_CATALOG["claude-sonnet"]
        assert m.price_input_per_1m == pytest.approx(3.00)
        assert m.price_output_per_1m == pytest.approx(15.00)

    def test_gpt4o_mini_cheapest_openai(self):
        from llm.model_catalog import DEBATE_MODELS
        openai_models = [m for m in DEBATE_MODELS if m.provider == "OpenAI"]
        mini = min(openai_models, key=lambda m: m.price_input_per_1m)
        assert mini.model_id == "gpt-4o-mini"

    def test_gemini_flash_cheapest_google(self):
        from llm.model_catalog import DEBATE_MODELS
        google_models = [m for m in DEBATE_MODELS if m.provider == "Google"]
        flash = min(google_models, key=lambda m: m.price_input_per_1m)
        assert flash.model_id == "gemini-2.0-flash"


# ===========================================================================
# 2. GET /api/v1/models endpoint
# ===========================================================================

class TestModelsEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.v1.models import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_returns_200(self, client):
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200

    def test_response_has_models_list(self, client):
        data = client.get("/api/v1/models").json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0

    def test_response_has_default_selected(self, client):
        data = client.get("/api/v1/models").json()
        assert "default_selected" in data
        assert isinstance(data["default_selected"], list)

    def test_each_model_has_required_fields(self, client):
        data = client.get("/api/v1/models").json()
        for model in data["models"]:
            for field in ("model_id", "display_name", "provider", "estimated_cost_usd",
                          "estimated_tokens", "available"):
                assert field in model, f"Field '{field}' missing from {model.get('model_id')}"

    def test_estimated_tokens_shape(self, client):
        data = client.get("/api/v1/models").json()
        for model in data["models"]:
            tokens = model["estimated_tokens"]
            assert "input" in tokens and "output" in tokens

    def test_default_selected_are_valid_model_ids(self, client):
        data = client.get("/api/v1/models").json()
        all_ids = {m["model_id"] for m in data["models"]}
        for mid in data["default_selected"]:
            assert mid in all_ids


# ===========================================================================
# 3. StartSessionRequest accepts selected_models
# ===========================================================================

class TestStartSessionRequest:
    def test_selected_models_defaults_to_none(self):
        from api.v1.sessions import StartSessionRequest
        req = StartSessionRequest(task="Test", user_id="u1")
        assert req.selected_models is None

    def test_selected_models_accepted(self):
        from api.v1.sessions import StartSessionRequest
        req = StartSessionRequest(
            task="Test", user_id="u1",
            selected_models=["claude-sonnet", "gpt-4o"],
        )
        assert req.selected_models == ["claude-sonnet", "gpt-4o"]

    def test_empty_list_accepted(self):
        from api.v1.sessions import StartSessionRequest
        req = StartSessionRequest(task="T", user_id="u", selected_models=[])
        assert req.selected_models == []


# ===========================================================================
# 4. _resolve_researcher_models
# ===========================================================================

class TestResolveResearcherModels:
    def _make_provider(self, available=None):
        provider = MagicMock()
        provider.available_models = available or ["claude-sonnet", "gpt-4o"]
        return provider

    def test_user_selection_takes_priority_over_roles(self):
        from graph.nodes.researcher import _resolve_researcher_models
        state = make_state(selected_models=["claude-sonnet", "gemini-2.5-pro"])
        provider = self._make_provider()

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {
            "researcher_gpt": "gpt-4o",   # should be ignored
        }):
            result = _resolve_researcher_models(provider, state)

        assert result == ["claude-sonnet", "gemini-2.5-pro"]

    def test_empty_selection_falls_back_to_roles(self):
        from graph.nodes.researcher import _resolve_researcher_models
        state = make_state(selected_models=[])
        provider = self._make_provider()

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {
            "researcher_gpt": "gpt-4o",
            "researcher_claude": "claude-sonnet",
        }):
            result = _resolve_researcher_models(provider, state)

        assert set(result) == {"gpt-4o", "claude-sonnet"}

    def test_none_selection_falls_back_to_roles(self):
        from graph.nodes.researcher import _resolve_researcher_models
        state = make_state()
        state["selected_models"] = None   # type: ignore[assignment]
        provider = self._make_provider()

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {
            "researcher_gpt": "gpt-4o",
        }):
            result = _resolve_researcher_models(provider, state)

        assert "gpt-4o" in result

    def test_no_roles_falls_back_to_provider_available(self):
        from graph.nodes.researcher import _resolve_researcher_models
        state = make_state(selected_models=[])
        provider = self._make_provider(["gemini-2.0-flash"])

        with patch("graph.nodes.researcher.PHASE_MODEL_ROLES", {}):
            result = _resolve_researcher_models(provider, state)

        assert result == ["gemini-2.0-flash"]

    def test_user_selection_deduplicated(self):
        from graph.nodes.researcher import _resolve_researcher_models
        state = make_state(selected_models=["gpt-4o", "gpt-4o", "claude-sonnet"])
        provider = self._make_provider()
        result = _resolve_researcher_models(provider, state)
        assert result.count("gpt-4o") == 1


# ===========================================================================
# 5. _resolve_debate_models
# ===========================================================================

class TestResolveDebateModels:
    def _make_provider(self, available=None):
        provider = MagicMock()
        provider.available_models = available or ["claude-sonnet", "gpt-4o"]
        return provider

    def test_user_selection_takes_priority(self):
        from graph.nodes.debater import _resolve_debate_models
        state = make_state(selected_models=["gpt-4o-mini"])
        provider = self._make_provider()

        with patch("graph.nodes.debater.PHASE_MODEL_ROLES",
                   {"debater_claude": "claude-sonnet"}):  # should be ignored
            result = _resolve_debate_models(state, provider)

        assert result == ["gpt-4o-mini"]

    def test_empty_selection_uses_roles(self):
        from graph.nodes.debater import _resolve_debate_models
        state = make_state(selected_models=[])
        provider = self._make_provider()

        with patch("graph.nodes.debater.PHASE_MODEL_ROLES", {
            "debater_a": "claude-sonnet",
            "debater_b": "gpt-4o",
        }):
            result = _resolve_debate_models(state, provider)

        assert set(result) == {"claude-sonnet", "gpt-4o"}

    def test_no_roles_uses_provider_available(self):
        from graph.nodes.debater import _resolve_debate_models
        state = make_state(selected_models=[])
        provider = self._make_provider(["gemini-2.5-pro"])

        with patch("graph.nodes.debater.PHASE_MODEL_ROLES", {}):
            result = _resolve_debate_models(state, provider)

        assert result == ["gemini-2.5-pro"]

    def test_order_preserved(self):
        from graph.nodes.debater import _resolve_debate_models
        chosen = ["gemini-2.0-flash", "claude-sonnet", "gpt-4o"]
        state = make_state(selected_models=chosen)
        provider = self._make_provider()
        result = _resolve_debate_models(state, provider)
        assert result == chosen


# ===========================================================================
# 6. _resolve_voter_models
# ===========================================================================

class TestResolveVoterModels:
    def _make_provider(self, available=None):
        provider = MagicMock()
        provider.available_models = available or ["claude-sonnet", "gpt-4o"]
        return provider

    def test_user_selection_takes_priority(self):
        from graph.nodes.voter import _resolve_voter_models
        state = make_state(selected_models=["gemini-2.5-pro", "gpt-4o"])
        provider = self._make_provider()

        with patch("graph.nodes.voter.PHASE_MODEL_ROLES",
                   {"debater_x": "claude-sonnet"}):
            result = _resolve_voter_models(provider, state)

        assert result == ["gemini-2.5-pro", "gpt-4o"]

    def test_empty_selection_uses_debater_roles(self):
        from graph.nodes.voter import _resolve_voter_models
        state = make_state(selected_models=[])
        provider = self._make_provider()

        with patch("graph.nodes.voter.PHASE_MODEL_ROLES", {
            "debater_a": "claude-sonnet",
            "debater_b": "gemini-2.5-pro",
            "researcher_x": "gpt-4o",  # should NOT be included
        }):
            result = _resolve_voter_models(provider, state)

        assert "claude-sonnet" in result
        assert "gemini-2.5-pro" in result
        assert "gpt-4o" not in result

    def test_no_roles_uses_provider_available(self):
        from graph.nodes.voter import _resolve_voter_models
        state = make_state(selected_models=[])
        provider = self._make_provider(["gpt-4o-mini"])

        with patch("graph.nodes.voter.PHASE_MODEL_ROLES", {}):
            result = _resolve_voter_models(provider, state)

        assert result == ["gpt-4o-mini"]

    def test_deduplicated(self):
        from graph.nodes.voter import _resolve_voter_models
        state = make_state(selected_models=["gpt-4o", "gpt-4o", "gpt-4o"])
        provider = self._make_provider()
        result = _resolve_voter_models(provider, state)
        assert result.count("gpt-4o") == 1


# ===========================================================================
# 7. Integration — nodes use ONLY user-selected models
# ===========================================================================

class TestSelectedModelsIntegration:
    """Verify that researcher/debater/voter nodes invoke only the user's chosen models."""

    async def test_researcher_calls_only_selected_models(self):
        from graph.nodes.researcher import researcher_node

        state = make_state(
            phase="research",
            selected_models=["claude-sonnet", "gpt-4o"],
        )

        invoked: list[str] = []

        class TrackingLLM:
            def __init__(self, key: str):
                self._key = key
            async def ainvoke(self, _messages):
                invoked.append(self._key)
                return MockAIMessage(f"Research from {self._key}")

        def get_chat_model(key: str):
            return TrackingLLM(key)

        with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
            mock_provider = MagicMock()
            mock_provider.get_chat_model.side_effect = get_chat_model
            mock_cls.return_value = mock_provider

            result = await researcher_node(state)

        assert set(invoked) == {"claude-sonnet", "gpt-4o"}
        assert set(result["research_results"].keys()) == {"claude-sonnet", "gpt-4o"}

    async def test_debater_calls_only_selected_models(self):
        from graph.nodes.debater import debate_node

        state = make_state(
            phase="debate",
            selected_models=["gemini-2.5-pro"],
            debate_round=0,
            debate_history=[],
        )

        invoked: list[str] = []

        class TrackingLLM:
            def __init__(self, key: str):
                self._key = key
            async def ainvoke(self, _messages):
                invoked.append(self._key)
                return MockAIMessage(f"Debate from {self._key}")

        def get_chat_model(key: str):
            return TrackingLLM(key)

        with patch("graph.nodes.debater.LLMProvider") as mock_cls:
            mock_provider = MagicMock()
            mock_provider.get_chat_model.side_effect = get_chat_model
            mock_cls.return_value = mock_provider

            result = await debate_node(state)

        assert invoked == ["gemini-2.5-pro"]
        assert any(e["model"] == "gemini-2.5-pro" for e in result["debate_history"])

    async def test_voter_calls_only_selected_models(self):
        from graph.nodes.voter import voter_node

        state = make_state(
            phase="voting",
            selected_models=["claude-sonnet", "gpt-4o-mini"],
            debate_history=[],
        )

        invoked: list[str] = []

        class TrackingLLM:
            def __init__(self, key: str):
                self._key = key
            async def ainvoke(self, _messages):
                invoked.append(self._key)
                return MockAIMessage("VOTE: Approach A\nREASON: Best.")

        def get_chat_model(key: str):
            return TrackingLLM(key)

        with patch("graph.nodes.voter.LLMProvider") as mock_cls:
            mock_provider = MagicMock()
            mock_provider.get_chat_model.side_effect = get_chat_model
            mock_cls.return_value = mock_provider

            result = await voter_node(state)

        assert set(invoked) == {"claude-sonnet", "gpt-4o-mini"}
        assert set(result["votes"].keys()) == {"claude-sonnet", "gpt-4o-mini"}

    async def test_single_model_selection_still_works(self):
        """Edge case: user picks only one model — must not crash."""
        from graph.nodes.researcher import researcher_node

        state = make_state(
            phase="research",
            selected_models=["gpt-4o-mini"],
        )

        with patch("graph.nodes.researcher.LLMProvider") as mock_cls:
            mock_provider = MagicMock()
            mock_provider.get_chat_model.return_value = MockChatLLM("Solo research")
            mock_cls.return_value = mock_provider

            result = await researcher_node(state)

        assert "gpt-4o-mini" in result["research_results"]
        assert result["phase"] == "debate"

    async def test_all_three_nodes_use_same_selection(self):
        """Guarantee researcher, debater, and voter all honour the same list."""
        selected = ["claude-sonnet", "gemini-2.0-flash"]

        researcher_invoked: list[str] = []
        debater_invoked: list[str] = []
        voter_invoked: list[str] = []

        def make_tracking_llm(store: list):
            class T:
                def __init__(self, k: str):
                    self._k = k
                async def ainvoke(self, _):
                    store.append(self._k)
                    return MockAIMessage(f"VOTE: X\nREASON: y. from {self._k}")
            return T

        ResearcherLLM = make_tracking_llm(researcher_invoked)
        DebaterLLM = make_tracking_llm(debater_invoked)
        VoterLLM = make_tracking_llm(voter_invoked)

        # --- researcher ---
        from graph.nodes.researcher import researcher_node
        r_state = make_state(phase="research", selected_models=selected)
        with patch("graph.nodes.researcher.LLMProvider") as mc:
            mp = MagicMock()
            mp.get_chat_model.side_effect = lambda k: ResearcherLLM(k)
            mc.return_value = mp
            r_result = await researcher_node(r_state)

        # --- debater ---
        from graph.nodes.debater import debate_node
        d_state = make_state(phase="debate", selected_models=selected,
                             debate_round=0, debate_history=[])
        with patch("graph.nodes.debater.LLMProvider") as mc:
            mp = MagicMock()
            mp.get_chat_model.side_effect = lambda k: DebaterLLM(k)
            mc.return_value = mp
            d_result = await debate_node(d_state)

        # --- voter ---
        from graph.nodes.voter import voter_node
        v_state = make_state(phase="voting", selected_models=selected, debate_history=[])
        with patch("graph.nodes.voter.LLMProvider") as mc:
            mp = MagicMock()
            mp.get_chat_model.side_effect = lambda k: VoterLLM(k)
            mc.return_value = mp
            v_result = await voter_node(v_state)

        assert set(researcher_invoked) == set(selected)
        assert set(debater_invoked) == set(selected)
        assert set(voter_invoked) == set(selected)

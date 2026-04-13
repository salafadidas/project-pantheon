"""Tests for llm/provider.py"""

import pytest
from unittest.mock import MagicMock, patch

from llm.provider import (
    LLMProvider,
    ModelConfig,
    ModelProvider,
    DEFAULT_MODELS,
    PHASE_MODEL_ROLES,
)


# --------------------------------------------------------------------------- #
# ModelConfig                                                                  #
# --------------------------------------------------------------------------- #

def test_model_config_is_frozen():
    cfg = ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-test",
        display_name="Claude Test",
        litellm_model="anthropic/claude-test",
    )
    with pytest.raises((AttributeError, TypeError)):
        cfg.model_id = "modified"  # type: ignore[misc]


def test_default_models_populated():
    assert len(DEFAULT_MODELS) > 0
    assert "claude-sonnet" in DEFAULT_MODELS
    assert "gpt-4o" in DEFAULT_MODELS
    assert "gemini-2.5-pro" in DEFAULT_MODELS


def test_phase_model_roles_cover_all_phases():
    roles = set(PHASE_MODEL_ROLES.keys())
    assert "pm_router" in roles
    assert any(r.startswith("researcher_") for r in roles)
    assert any(r.startswith("debater_") for r in roles)
    assert "voter" in roles
    assert "synthesizer" in roles


# --------------------------------------------------------------------------- #
# LLMProvider construction                                                     #
# --------------------------------------------------------------------------- #

def test_provider_available_models():
    provider = LLMProvider()
    models = provider.available_models
    assert isinstance(models, list)
    assert len(models) == len(DEFAULT_MODELS)


def test_provider_custom_models_merged():
    extra = ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="custom-model",
        display_name="Custom",
        litellm_model="openai/custom-model",
    )
    provider = LLMProvider(custom_models={"custom": extra})
    assert "custom" in provider.available_models


def test_provider_default_model_override():
    provider = LLMProvider(default_model="claude-sonnet")
    # get_chat_model with no args should use the default
    with patch("llm.provider.ChatLiteLLM") as mock_cls:
        mock_cls.return_value = MagicMock()
        provider.get_chat_model()
    assert mock_cls.called
    call_kwargs = mock_cls.call_args.kwargs
    assert "claude" in call_kwargs["model"]


# --------------------------------------------------------------------------- #
# LLMProvider.get_model_config                                                 #
# --------------------------------------------------------------------------- #

def test_get_model_config_known_key():
    provider = LLMProvider()
    cfg = provider.get_model_config("gpt-4o-mini")
    assert cfg.litellm_model == "gpt-4o-mini"
    assert cfg.provider == ModelProvider.OPENAI


def test_get_model_config_unknown_key_raises():
    provider = LLMProvider()
    with pytest.raises(ValueError, match="Unknown model"):
        provider.get_model_config("does-not-exist")


# --------------------------------------------------------------------------- #
# LLMProvider.get_chat_model — caching                                        #
# --------------------------------------------------------------------------- #

def test_get_chat_model_caches_instance():
    provider = LLMProvider()
    with patch("llm.provider.ChatLiteLLM") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        llm1 = provider.get_chat_model("gpt-4o-mini")
        llm2 = provider.get_chat_model("gpt-4o-mini")

    # Should only be instantiated once
    assert mock_cls.call_count == 1
    assert llm1 is llm2


def test_get_chat_model_different_temps_not_cached_together():
    provider = LLMProvider()
    with patch("llm.provider.ChatLiteLLM") as mock_cls:
        mock_cls.side_effect = lambda **kw: MagicMock()
        llm1 = provider.get_chat_model("gpt-4o-mini", temperature=0.0)
        llm2 = provider.get_chat_model("gpt-4o-mini", temperature=1.0)

    assert mock_cls.call_count == 2
    assert llm1 is not llm2


def test_get_chat_model_respects_temperature_override():
    provider = LLMProvider()
    with patch("llm.provider.ChatLiteLLM") as mock_cls:
        mock_cls.return_value = MagicMock()
        provider.get_chat_model("gpt-4o-mini", temperature=0.2)

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["temperature"] == pytest.approx(0.2)


# --------------------------------------------------------------------------- #
# LLMProvider.get_model_for_role                                               #
# --------------------------------------------------------------------------- #

def test_get_model_for_role_known_role():
    provider = LLMProvider()
    with patch("llm.provider.ChatLiteLLM") as mock_cls:
        mock_cls.return_value = MagicMock()
        llm = provider.get_model_for_role("synthesizer")
    assert llm is not None


def test_get_model_for_role_unknown_falls_back_to_default():
    provider = LLMProvider(default_model="gpt-4o-mini")
    with patch("llm.provider.ChatLiteLLM") as mock_cls:
        mock_cls.return_value = MagicMock()
        provider.get_model_for_role("nonexistent_role")
    call_kwargs = mock_cls.call_args.kwargs
    # Should use the default model's litellm string
    assert "gpt-4o-mini" in call_kwargs["model"]


# --------------------------------------------------------------------------- #
# LLMProvider.get_litellm_model_string                                        #
# --------------------------------------------------------------------------- #

def test_get_litellm_model_string_claude():
    provider = LLMProvider()
    model_str = provider.get_litellm_model_string("claude-sonnet")
    assert "anthropic" in model_str or "claude" in model_str


def test_get_litellm_model_string_default():
    provider = LLMProvider(default_model="gpt-4o-mini")
    model_str = provider.get_litellm_model_string()
    assert "gpt-4o-mini" in model_str

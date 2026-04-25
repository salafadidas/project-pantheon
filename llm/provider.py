"""
Unified LLM provider using LiteLLM for multi-model support.

Supports Claude, GPT, and Gemini through a single interface,
compatible with LangChain's ChatLiteLLM wrapper for LangGraph integration.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from langchain_community.chat_models import ChatLiteLLM

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    NVIDIA = "nvidia"


@dataclass(frozen=True)
class ModelConfig:
    """Immutable configuration for a single LLM model."""
    provider: ModelProvider
    model_id: str
    display_name: str
    litellm_model: str  # LiteLLM format: "provider/model" or just "model"
    max_tokens: int = 4096
    temperature: Optional[float] = 0.7  # None = omit param (required for o-series)


# Default model configurations for the PoC (3 models)
DEFAULT_MODELS: dict[str, ModelConfig] = {
    # ── OpenAI ──────────────────────────────────────────────────────────────
    "o3": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="o3",
        display_name="o3",
        litellm_model="o3",
        max_tokens=4096,
        temperature=None,  # o-series rejects the temperature parameter
    ),
    "o4-mini": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="o4-mini",
        display_name="o4-mini",
        litellm_model="o4-mini",
        max_tokens=4096,
        temperature=None,  # o-series rejects the temperature parameter
    ),
    "gpt-4.1": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-4.1",
        display_name="GPT-4.1",
        litellm_model="gpt-4.1",
        max_tokens=4096,
    ),
    "gpt-4.1-mini": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        litellm_model="gpt-4.1-mini",
        max_tokens=4096,
    ),
    "gpt-4o": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-4o",
        display_name="GPT-4o",
        litellm_model="gpt-4o",
        max_tokens=4096,
    ),
    "gpt-4o-mini": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        litellm_model="gpt-4o-mini",
        max_tokens=4096,
    ),
    "claude-opus": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-opus-4-20250514",
        display_name="Claude Opus 4",
        litellm_model="anthropic/claude-opus-4-20250514",
        max_tokens=4096,
    ),
    "claude-sonnet": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4.5",
        litellm_model="anthropic/claude-sonnet-4-20250514",
        max_tokens=4096,
    ),
    "claude-haiku": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-haiku-4-5-20251001",
        display_name="Claude Haiku 4.5",
        litellm_model="anthropic/claude-haiku-4-5-20251001",
        max_tokens=4096,
    ),
    "gemini-2.5-pro": ModelConfig(
        provider=ModelProvider.GOOGLE,
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        litellm_model="gemini/gemini-2.5-pro",
        max_tokens=4096,
    ),
    "gemini-2.5-flash": ModelConfig(
        provider=ModelProvider.GOOGLE,
        model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        litellm_model="gemini/gemini-2.5-flash",
        max_tokens=4096,
    ),
    "gemini-2.0-flash": ModelConfig(
        provider=ModelProvider.GOOGLE,
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        litellm_model="gemini/gemini-2.0-flash",
        max_tokens=4096,
    ),
    "gemini-2.0-flash-lite": ModelConfig(
        provider=ModelProvider.GOOGLE,
        model_id="gemini-2.0-flash-lite",
        display_name="Gemini 2.0 Flash Lite",
        litellm_model="gemini/gemini-2.0-flash-lite",
        max_tokens=4096,
    ),
    # ── NVIDIA NIM (free-tier, 40 RPM, 12-month key) ────────────────────────
    "deepseek-v3": ModelConfig(
        provider=ModelProvider.NVIDIA,
        model_id="deepseek-v3",
        display_name="DeepSeek V4 Flash",
        # deepseek-v3.2 is permanently unavailable on NIM (504 gateway timeout);
        # v4-flash is the confirmed working replacement (tested 2026-04-25).
        litellm_model="nvidia_nim/deepseek-ai/deepseek-v4-flash",
        max_tokens=4096,
        temperature=0.7,
    ),
    "kimi-k2": ModelConfig(
        provider=ModelProvider.NVIDIA,
        model_id="kimi-k2",
        display_name="Kimi K2.5",
        litellm_model="nvidia_nim/moonshotai/kimi-k2-instruct",
        max_tokens=4096,
        temperature=0.7,
    ),
}

# Role assignments for the 5-phase workflow
PHASE_MODEL_ROLES: dict[str, str] = {
    "pm_router": "gpt-4o-mini",       # Phase 1: fast classification
    "researcher_claude": "claude-sonnet",   # Phase 2: deep research
    "researcher_gpt": "gpt-4o",            # Phase 2: alternative perspective
    "researcher_gemini": "gemini-2.5-flash",  # Phase 2: third perspective
    "debater_claude": "claude-sonnet",       # Phase 3: debate
    "debater_gpt": "gpt-4o",                # Phase 3: debate
    "debater_gemini": "gemini-2.5-flash",   # Phase 3: debate (2.5-pro has tiny free quota)
    "debater_deepseek": "deepseek-v3",      # Phase 3: 4th voice via NVIDIA NIM (free)
    "voter": "gpt-4o-mini",                 # Phase 4: fast voting
    "synthesizer": "claude-sonnet",         # Phase 5: final synthesis
}


class LLMProvider:
    """Unified LLM provider that creates LangChain-compatible chat models via LiteLLM.

    Usage:
        provider = LLMProvider()
        llm = provider.get_chat_model("claude-sonnet")
        # Use with LangGraph's create_react_agent or any LangChain chain
    """

    def __init__(
        self,
        custom_models: Optional[dict[str, ModelConfig]] = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self._models = {**DEFAULT_MODELS, **(custom_models or {})}
        self._default_model = default_model
        self._cache: dict[str, ChatLiteLLM] = {}
        logger.info(
            "LLMProvider initialized with %d models, default=%s",
            len(self._models),
            default_model,
        )

    @property
    def available_models(self) -> list[str]:
        """List all registered model keys."""
        return list(self._models.keys())

    def get_model_config(self, model_key: str) -> ModelConfig:
        """Get configuration for a model by key.

        Args:
            model_key: Key from DEFAULT_MODELS (e.g. "claude-sonnet")

        Returns:
            Frozen ModelConfig dataclass

        Raises:
            ValueError: If model_key is not registered
        """
        if model_key not in self._models:
            raise ValueError(
                f"Unknown model '{model_key}'. "
                f"Available: {', '.join(self._models.keys())}"
            )
        return self._models[model_key]

    def get_chat_model(
        self,
        model_key: Optional[str] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatLiteLLM:
        """Create or retrieve a cached LangChain ChatLiteLLM instance.

        Args:
            model_key: Key from DEFAULT_MODELS. Uses default if None.
            temperature: Override model's default temperature.
            max_tokens: Override model's default max_tokens.

        Returns:
            ChatLiteLLM instance compatible with LangGraph
        """
        key = model_key or self._default_model
        config = self.get_model_config(key)

        temp = temperature if temperature is not None else config.temperature
        tokens = max_tokens if max_tokens is not None else config.max_tokens

        cache_key = f"{key}:{temp}:{tokens}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build kwargs carefully: o-series models (o3, o4-mini) reject the
        # temperature parameter entirely — omit it when config.temperature is None.
        llm_kwargs: dict = {"model": config.litellm_model, "max_tokens": tokens}
        if temp is not None:
            llm_kwargs["temperature"] = temp

        llm = ChatLiteLLM(**llm_kwargs)

        self._cache[cache_key] = llm
        logger.info(
            "Created ChatLiteLLM: model=%s, temp=%s, max_tokens=%d",
            config.litellm_model,
            temp,
            tokens,
        )
        return llm

    def get_model_for_role(self, role: str) -> ChatLiteLLM:
        """Get the appropriate chat model for a workflow role.

        Args:
            role: Role from PHASE_MODEL_ROLES (e.g. "debater_claude")

        Returns:
            ChatLiteLLM instance for that role
        """
        model_key = PHASE_MODEL_ROLES.get(role, self._default_model)
        return self.get_chat_model(model_key)

    def get_litellm_model_string(self, model_key: Optional[str] = None) -> str:
        """Get the raw LiteLLM model string for direct LangGraph usage.

        This is needed for `create_react_agent(model=...)` which accepts
        a model string rather than a ChatModel instance.

        Args:
            model_key: Key from DEFAULT_MODELS. Uses default if None.

        Returns:
            LiteLLM model string (e.g. "anthropic/claude-sonnet-4-20250514")
        """
        key = model_key or self._default_model
        config = self.get_model_config(key)
        return config.litellm_model

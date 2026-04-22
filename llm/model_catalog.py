"""
Central model catalog: pricing, metadata, and session cost estimates.

All prices are per 1M tokens (USD) as of 2025.
Session cost estimates assume ~15k input + ~3k output tokens per model,
covering all 5 phases (research + 3 debate rounds + vote + synthesis).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ── Per-session token estimates (rough average across all phases) ────────────
ESTIMATED_INPUT_TOKENS: int = 15_000
ESTIMATED_OUTPUT_TOKENS: int = 3_000


@dataclass(frozen=True)
class ModelInfo:
    """Immutable descriptor for a single LLM available in Pantheon debates."""

    model_id: str               # matches key in llm/provider.py DEFAULT_MODELS
    display_name: str
    provider: str               # "Anthropic" | "OpenAI" | "Google"
    provider_color: str         # Tailwind bg class for UI badge
    price_input_per_1m: float   # USD per 1M input tokens
    price_output_per_1m: float  # USD per 1M output tokens
    context_window_k: int       # context window in K tokens
    strengths: list[str]        # 2–3 bullet points shown in the UI
    env_key: str                # env var that must be set for this model to work

    @property
    def estimated_cost_usd(self) -> float:
        """Estimated USD cost for one full Pantheon session using this model."""
        return (
            self.price_input_per_1m / 1_000_000 * ESTIMATED_INPUT_TOKENS
            + self.price_output_per_1m / 1_000_000 * ESTIMATED_OUTPUT_TOKENS
        )

    def is_available(self) -> bool:
        """True when the required API key environment variable is present."""
        return bool(os.getenv(self.env_key))

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "provider_color": self.provider_color,
            "price_input_per_1m": self.price_input_per_1m,
            "price_output_per_1m": self.price_output_per_1m,
            "context_window_k": self.context_window_k,
            "strengths": self.strengths,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "estimated_tokens": {
                "input": ESTIMATED_INPUT_TOKENS,
                "output": ESTIMATED_OUTPUT_TOKENS,
            },
            "available": self.is_available(),
        }


# ── Master catalog ───────────────────────────────────────────────────────────

DEBATE_MODELS: list[ModelInfo] = [
    ModelInfo(
        model_id="claude-sonnet",
        display_name="Claude Sonnet 4.5",
        provider="Anthropic",
        provider_color="amber",
        price_input_per_1m=3.00,
        price_output_per_1m=15.00,
        context_window_k=200,
        strengths=["Deep reasoning", "Code & analysis", "Nuanced writing"],
        env_key="ANTHROPIC_API_KEY",
    ),
    ModelInfo(
        model_id="gpt-4o",
        display_name="GPT-4o",
        provider="OpenAI",
        provider_color="emerald",
        price_input_per_1m=2.50,
        price_output_per_1m=10.00,
        context_window_k=128,
        strengths=["Broad knowledge", "Structured output", "Reliable"],
        env_key="OPENAI_API_KEY",
    ),
    ModelInfo(
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider="OpenAI",
        provider_color="emerald",
        price_input_per_1m=0.15,
        price_output_per_1m=0.60,
        context_window_k=128,
        strengths=["Ultra-fast", "Lowest cost", "High throughput"],
        env_key="OPENAI_API_KEY",
    ),
    ModelInfo(
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider="Google",
        provider_color="blue",
        price_input_per_1m=1.25,
        price_output_per_1m=10.00,
        context_window_k=1_000,
        strengths=["Largest context (1M)", "Multimodal", "Strong coding"],
        env_key="GOOGLE_API_KEY",
    ),
    ModelInfo(
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider="Google",
        provider_color="blue",
        price_input_per_1m=0.10,
        price_output_per_1m=0.40,
        context_window_k=1_000,
        strengths=["Fastest response", "Cheapest Google model", "Large context"],
        env_key="GOOGLE_API_KEY",
    ),
]

# Quick lookup by model_id
MODEL_CATALOG: dict[str, ModelInfo] = {m.model_id: m for m in DEBATE_MODELS}

# Default selection shown in the UI (the original 3-model PoC set)
DEFAULT_SELECTED: list[str] = ["claude-sonnet", "gpt-4o", "gemini-2.5-pro"]

"""Shared fixtures for the Pantheon test suite."""

from __future__ import annotations



# --------------------------------------------------------------------------- #
# State factory                                                                #
# --------------------------------------------------------------------------- #

def make_state(**overrides) -> dict:
    """Return a minimal PantheonState dict for use in node tests."""
    base = {
        "task": "Compare REST and GraphQL APIs",
        "phase": "routing",
        "session_id": "test-session-001",
        "user_id": "test-user",
        "pm_model": "gpt-4o-mini",
        "selected_models": [],
        "research_results": {},
        "debate_history": [],
        "debate_round": 0,
        "votes": {},
        "consensus": None,
        "final_report": None,
        "cost_summary": {},
        "messages": [],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Mock LLM response helpers                                                    #
# --------------------------------------------------------------------------- #

class MockAIMessage:
    """Minimal mock for a LangChain AIMessage."""

    def __init__(self, content: str, usage_metadata: dict | None = None) -> None:
        self.content = content
        self.usage_metadata = usage_metadata or {"input_tokens": 10, "output_tokens": 20}


class MockChatLLM:
    """Minimal async mock for ChatLiteLLM."""

    def __init__(self, content: str = "mock response") -> None:
        self._content = content

    async def ainvoke(self, messages):  # noqa: ARG002
        return MockAIMessage(self._content)

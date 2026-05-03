"""Utilities for sanitizing LangChain messages before Anthropic API calls."""
from __future__ import annotations

from langchain_core.messages import BaseMessage


def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Remove empty text content blocks that cause Anthropic API 400 errors.

    When create_react_agent generates tool-call messages, LangChain may produce
    content blocks like {"type": "text", "text": ""} alongside tool_use blocks.
    Anthropic rejects these with:
      - "text content blocks must be non-empty"
      - "cache_control cannot be set for empty text blocks"
    """
    sanitized: list[BaseMessage] = []
    for msg in messages:
        if not isinstance(msg.content, list):
            if isinstance(msg.content, str) and msg.content == "":
                continue
            sanitized.append(msg)
            continue

        filtered = [
            block for block in msg.content
            if not (
                isinstance(block, dict)
                and block.get("type") == "text"
                and not block.get("text", "").strip()
            )
        ]
        if not filtered:
            continue
        sanitized.append(msg.model_copy(update={"content": filtered}))

    return sanitized

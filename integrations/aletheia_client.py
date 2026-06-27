"""No-op Aletheia client skeleton for Phase 1 planning.

This module intentionally does not change Pantheon's production execution path.
It defines the future integration surface while keeping all operations safe when
Aletheia is disabled or unavailable.

Boundary rule:
    Aletheia owns memory.
    Pantheon reasons over memory.
    GitHub validates memory.
    Agents act on memory.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AletheiaClientConfig:
    """Configuration for optional Aletheia integration."""

    enabled: bool = False
    base_url: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "AletheiaClientConfig":
        """Build config from environment variables without requiring them."""
        enabled = os.getenv("ALETHEIA_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        timeout_raw = os.getenv("ALETHEIA_TIMEOUT_SECONDS", "10")
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 10.0

        return cls(
            enabled=enabled,
            base_url=os.getenv("ALETHEIA_BASE_URL"),
            timeout_seconds=timeout_seconds,
        )


class AletheiaClient:
    """Future Pantheon ↔ Aletheia integration adapter.

    Phase 1 behavior is deliberately no-op:
    - no HTTP dependency is introduced;
    - no production path imports this client;
    - all methods return explicit disabled/queued/fallback shaped responses;
    - callers can later integrate this safely behind feature flags.
    """

    def __init__(self, config: AletheiaClientConfig | None = None) -> None:
        self.config = config or AletheiaClientConfig.from_env()
        if self.config.enabled:
            logger.info("Aletheia integration configured but Phase 1 client is no-op")
        else:
            logger.info("Aletheia integration disabled; using Pantheon fallback behavior")

    async def get_context_pack(
        self,
        task: str,
        project: str,
        repo: str | None = None,
        requested_output: str = "council_resolution",
    ) -> dict[str, Any]:
        """Return a minimal context pack shape without calling Aletheia yet."""
        return {
            "available": False,
            "fallback": True,
            "reason": "Phase 1 no-op client; live Aletheia service not called",
            "context_pack": {
                "context_pack_id": None,
                "target_agent": "pantheon",
                "task": task,
                "project": project,
                "repo": repo,
                "complexity": "medium",
                "risk": "medium",
                "relevant_memories": [],
                "active_decisions": [],
                "related_files": [],
                "related_symbols": [],
                "conflicting_evidence": [],
                "requested_output": requested_output,
            },
        }

    async def submit_council_resolution(
        self,
        session_id: str,
        resolution: dict[str, Any],
    ) -> dict[str, Any]:
        """Accept the future call shape but do not persist anything in Phase 1."""
        return {
            "accepted": False,
            "fallback": True,
            "session_id": session_id,
            "status": "not_submitted_phase1_noop",
            "warnings": ["AletheiaClient is a Phase 1 no-op skeleton."],
        }

    async def submit_memory_update_candidates(
        self,
        session_id: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Accept candidate memory shape without promoting or storing memory."""
        return {
            "accepted_count": 0,
            "rejected_count": len(candidates),
            "session_id": session_id,
            "candidate_ids": [],
            "warnings": ["Candidate memories are not submitted by the Phase 1 no-op client."],
        }

    async def submit_adr_candidate(
        self,
        session_id: str,
        adr: dict[str, Any],
    ) -> dict[str, Any]:
        """Accept ADR candidate shape without creating GitHub/Notion/Obsidian records."""
        return {
            "accepted": False,
            "session_id": session_id,
            "candidate_id": None,
            "github_pr_url": None,
            "review_url": None,
            "warnings": ["ADR candidates are not submitted by the Phase 1 no-op client."],
        }

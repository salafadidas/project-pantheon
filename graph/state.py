"""
PantheonState: shared state schema for the multi-agent LangGraph workflow.

All nodes receive and return this TypedDict.  LangGraph's built-in
reducer for `messages` (append-only) is used; all other fields are
replaced on each update (last-write-wins).
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class PantheonState(TypedDict):
    # ------------------------------------------------------------------ core
    task: str
    """The user's original task / question, unchanged throughout the run."""

    phase: Literal["routing", "research", "debate", "voting", "synthesis", "complete"]
    """Current workflow phase.  Each phase-node sets this before returning."""

    session_id: str
    """Unique identifier for this workflow run."""

    user_id: str
    """Identifier of the user who submitted the task."""

    # ------------------------------------------------------------ model roles
    pm_model: str
    """Model key (from LLMProvider) acting as PM/router for this session."""

    selected_models: List[str]
    """Model keys chosen by the user for this session.  When non-empty, these
    override the default PHASE_MODEL_ROLES for research, debate, and voting."""

    # --------------------------------------------------------- phase outputs
    research_results: Dict[str, str]
    """Phase 2 output: mapping of model_name -> research text."""

    debate_history: List[Dict]
    """Phase 3 output: list of {round, model, content, timestamp} entries."""

    debate_round: int
    """Current debate round counter (0-indexed before the first round runs)."""

    votes: Dict[str, str]
    """Phase 4 output: mapping of model_name -> voted_best_approach."""

    consensus: Optional[str]
    """Winning approach after voting, or None if no consensus reached."""

    final_report: Optional[str]
    """Phase 5 output: synthesised final report text."""

    # ------------------------------------------------------------ bookkeeping
    cost_summary: Dict
    """Cumulative cost data collected by cost_tracker across all phases."""

    messages: Annotated[List[BaseMessage], add_messages]
    """LangGraph-managed message list (append-only via add_messages reducer)."""

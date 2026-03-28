"""
Pantheon LangGraph orchestrator — wires all 5 phase-nodes into a compiled graph.

Workflow:
    pm_router → researcher → debater ──(loop)──┐
                                    └──(vote)──→ voter → synthesizer → END

The conditional edge after `debater` checks whether the maximum number of
debate rounds has been reached.  If not, the graph loops back to `debater`
for another round; once the limit is hit, it advances to `voter`.
"""

from __future__ import annotations

import os

from langgraph.graph import END, StateGraph

from graph.nodes.debater import debate_node
from graph.nodes.pm_router import pm_router_node
from graph.nodes.researcher import researcher_node
from graph.nodes.synthesizer import synthesizer_node
from graph.nodes.voter import voter_node
from graph.state import PantheonState

MAX_DEBATE_ROUNDS: int = int(os.getenv("MAX_DEBATE_ROUNDS", "3"))


def should_continue_debate(state: PantheonState) -> str:
    """Routing function for the conditional edge after the debate node.

    Returns:
        "continue" — loop back to debater for another round.
        "vote"     — advance to voter once the round limit is reached.
    """
    if state["debate_round"] < MAX_DEBATE_ROUNDS:
        return "continue"
    return "vote"


def build_graph() -> StateGraph:
    """Construct and compile the Pantheon LangGraph.

    Returns:
        A compiled LangGraph ready to be invoked with a PantheonState.
    """
    graph = StateGraph(PantheonState)

    # Register all phase nodes
    graph.add_node("pm_router", pm_router_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("debater", debate_node)
    graph.add_node("voter", voter_node)
    graph.add_node("synthesizer", synthesizer_node)

    # Entry point
    graph.set_entry_point("pm_router")

    # Linear edges
    graph.add_edge("pm_router", "researcher")
    graph.add_edge("researcher", "debater")

    # Conditional edge: keep debating or move to voting
    graph.add_conditional_edges(
        "debater",
        should_continue_debate,
        {
            "continue": "debater",
            "vote": "voter",
        },
    )

    graph.add_edge("voter", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


# Module-level compiled graph — import this for use in the application
pantheon_graph = build_graph()

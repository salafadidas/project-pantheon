# Day 4: PM Router + Researcher + Voter + Synthesizer Nodes

## Context
Building on Day 3's state.py and debater.py.

## Task
Create remaining 4 phase nodes and wire the full LangGraph:

### 1. Create `graph/nodes/pm_router.py`
- Classifies the task type (technical/creative/analytical/factual)
- Selects the best PM model based on task type
- Sets state.pm_model and state.phase = "research"
- Prompt: "You are a project manager. Classify this task and select the best AI model..."

### 2. Create `graph/nodes/researcher.py`
- Each model in debate_models independently researches the task
- Runs concurrently using asyncio.gather()
- Stores results in state.research_results
- Sets state.phase = "debate"

### 3. Create `graph/nodes/voter.py`
- Each model reads full debate_history
- Votes on which approach/answer is best
- Stores in state.votes
- Calculates consensus (majority vote)
- Sets state.consensus and state.phase = "synthesis"

### 4. Create `graph/nodes/synthesizer.py`
- The PM model synthesizes all debate + votes into final_report
- Formats as structured markdown report
- Includes: summary, key insights, consensus decision, dissenting views, cost breakdown
- Sets state.final_report and state.phase = "complete"

### 5. Create `graph/pantheon_graph.py`
Wire all nodes into a StateGraph:
```python
graph = StateGraph(PantheonState)
graph.add_node("pm_router", pm_router_node)
graph.add_node("researcher", researcher_node)
graph.add_node("debater", debater_node)
graph.add_node("voter", voter_node)
graph.add_node("synthesizer", synthesizer_node)

graph.set_entry_point("pm_router")
graph.add_edge("pm_router", "researcher")
graph.add_edge("researcher", "debater")
# Conditional: keep debating or move to vote
graph.add_conditional_edges("debater", should_continue_debate,
    {"continue": "debater", "vote": "voter"})
graph.add_edge("voter", "synthesizer")
graph.add_edge("synthesizer", END)
```

### 6. Update `docs/PROJECT_PLAN.md` Day 4 status to "Done"

## Requirements
- All async
- Immutable state returns
- Error handling: if a model fails, use a placeholder response
- Timeout per model: 60 seconds (from PHASE_TIMEOUT_SECONDS env var)

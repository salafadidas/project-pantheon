# Day 3: LangGraph State Expansion + Debate Node

## Context
Project Pantheon is a multi-AI-agent system. The codebase is at:
- Current agent: `agent/agent_factory.py` (single-agent LangGraph)
- LLM provider: `llm/provider.py` (LiteLLM multi-model, already done)
- Config: `config/agent_config.py` (has debate_models, pm_model, synthesizer_model)

## Task
Create the multi-agent state graph foundation:

### 1. Create `graph/state.py`
Define the PantheonState TypedDict with fields:
- `task`: str (user's original task)
- `phase`: Literal["routing", "research", "debate", "voting", "synthesis", "complete"]
- `pm_model`: str (which model acts as PM for this session)
- `research_results`: Dict[str, str] (model_name -> research output)
- `debate_history`: List[Dict] (list of {round, model, content, timestamp})
- `debate_round`: int
- `votes`: Dict[str, str] (model_name -> voted_best_approach)
- `consensus`: Optional[str]
- `final_report`: Optional[str]
- `cost_summary`: Dict (from cost_tracker)
- `messages`: List[BaseMessage] (for LangGraph compatibility)
- `session_id`: str
- `user_id`: str

### 2. Create `graph/nodes/__init__.py` (empty)

### 3. Create `graph/nodes/debater.py`
Implement the debate node:
- Takes PantheonState as input
- Each model in debate_models gets to respond to others' previous statements
- Adds to debate_history with {round, model, content, timestamp}
- Increments debate_round
- Returns updated state
- Use LLMProvider from `llm/provider.py` to call each model
- Each model should receive previous debate history as context

### 4. Create `graph/__init__.py` (empty)

### 5. Update `docs/PROJECT_PLAN.md` Day 3 status to "Done"

## Requirements
- Follow immutable state patterns (return new state, don't mutate)
- Handle errors gracefully (if one model fails, continue with others)
- Use async/await throughout
- Max debate rounds from config: `os.getenv("MAX_DEBATE_ROUNDS", "3")`

# Project Pantheon - Architecture

## 5-Phase Workflow

```
User Input (Telegram / Web UI / REST API)
    |
    v
+-------------------+
| Phase 1: PM Router|  Classify task type, select lead AI model
+-------------------+
    |
    v
+--------------------+
| Phase 2: Researcher|  Each AI agent independently researches the topic
+--------------------+
    |
    v
+------------------+
| Phase 3: Debater |  Multi-round structured debate between agents
+------------------+
    |
    v
+----------------+
| Phase 4: Voter |  Consensus voting, score arguments
+----------------+
    |
    v
+---------------------+
| Phase 5: Synthesizer|  Combine perspectives into final report
+---------------------+
    |
    v
Final Report → User (Telegram / Web UI / REST API)
```

## System Architecture

```
+--------------------------------------------------+
|              Input Channels                       |
|  +----------+  +-----------+  +----------------+ |
|  | Telegram |  |  Web UI   |  | REST API       | |
|  |   Bot    |  | (React)   |  | (FastAPI)      | |
|  +----------+  +-----------+  +----------------+ |
+--------------------------------------------------+
                    |
                    v
+--------------------------------------------------+
|           Message Gateway (FastAPI)               |
|  Rate Limiting | Debouncing | Authentication      |
+--------------------------------------------------+
                    |
                    v
+--------------------------------------------------+
|     Multi-Agent Orchestrator (LangGraph)          |
|                                                   |
|  State Machine: PM → Research → Debate → Vote     |
|                  → Synthesize                     |
|                                                   |
|  Each phase = LangGraph node with conditional     |
|  edges for routing and error handling             |
+--------------------------------------------------+
                    |
                    v
+--------------------------------------------------+
|          LLM Integration Layer (LiteLLM)          |
|                                                   |
|  +--------+  +-------+  +--------+               |
|  | Claude |  |  GPT  |  | Gemini |               |
|  +--------+  +-------+  +--------+               |
|                                                   |
|  Unified API | Cost Tracking | Failover           |
+--------------------------------------------------+
                    |
                    v
+--------------------------------------------------+
|              Data Layer                           |
|  +------------+  +-------+  +-----------------+  |
|  | PostgreSQL |  | Redis |  | Vector Store    |  |
|  | (pgvector) |  |       |  | (pgvector)      |  |
|  +------------+  +-------+  +-----------------+  |
+--------------------------------------------------+
```

## File Structure (Target)

```
project-pantheon/
├── main.py                          # Entry point (existing)
├── agent/
│   ├── agent_factory.py             # Existing → extend for multi-agent
│   ├── agent_manager.py             # Existing → extend for phase agents
│   ├── prompts.py                   # Existing → add phase-specific prompts
│   ├── orchestrator.py              # NEW: 5-phase LangGraph state machine
│   ├── pm_router.py                 # NEW: Phase 1
│   ├── researcher.py                # NEW: Phase 2
│   ├── debater.py                   # NEW: Phase 3
│   ├── voter.py                     # NEW: Phase 4
│   └── synthesizer.py              # NEW: Phase 5
├── llm/
│   ├── provider.py                  # NEW: LiteLLM unified interface
│   └── cost_tracker.py              # NEW: Token/cost tracking
├── config/                          # Existing → extend
├── core/                            # Existing → extend
├── db/                              # Existing → extend
├── telegram_adapter/                # Existing → update commands
├── api/
│   ├── routes.py                    # NEW: FastAPI REST endpoints
│   └── websocket.py                 # NEW: WebSocket streaming
├── frontend/                        # Existing → add phase UI
│   ├── components/
│   │   ├── PhaseTimeline.tsx        # NEW: 5-phase progress bar
│   │   ├── DiscussionThread.tsx     # NEW: Agent debate display
│   │   └── CostMonitor.tsx          # NEW: Cost dashboard
├── docs/
├── tests/
└── docker-compose.yml               # Existing
```

## LLM Provider Matrix

| Provider | Model | Role in PoC | Cost |
|----------|-------|-------------|------|
| Anthropic | Claude Sonnet 4.6 | Primary debater | API |
| OpenAI | GPT-4o | Secondary debater | API |
| Google | Gemini 2.5 Pro | Third debater | Free tier |

## State Schema

```python
class PantheonState(TypedDict):
    task_input: str
    task_type: str
    pm_model: str
    research_results: dict[str, str]      # {model: findings}
    debate_history: list[dict]            # [{model, round, argument}]
    votes: dict[str, dict]                # {model: {choice, confidence, reasoning}}
    final_report: str
    phase: str                            # current phase
    cost_log: list[dict]                  # [{model, tokens_in, tokens_out, cost}]
```

---
title: Project Pantheon — Architecture
version: v2.0
date: 2026-04-01
---

# Project Pantheon — Architecture

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

## File Structure (Actual vs. Planned)

### Actual — Days 1–5 Complete (2026-04-01)

```
project-pantheon/
├── main.py                          # FastAPI app + Telegram bot concurrent startup
├── graph/
│   ├── state.py                     # PantheonState TypedDict (all fields)
│   ├── pantheon_graph.py            # Compiled LangGraph (all 5 phases + conditional edges)
│   └── nodes/
│       ├── pm_router.py             # Phase 1: task classification + model selection
│       ├── researcher.py            # Phase 2: concurrent multi-model research
│       ├── debater.py               # Phase 3: multi-round debate (loops via conditional edge)
│       ├── voter.py                 # Phase 4: consensus voting
│       └── synthesizer.py          # Phase 5: markdown report synthesis
├── llm/
│   ├── provider.py                  # LiteLLM unified interface, 5 models, role assignments
│   └── cost_tracker.py             # Token + cost tracking per session (asyncio-safe)
├── api/
│   └── v1/
│       ├── sessions.py              # REST: POST/GET/DELETE /api/v1/sessions
│       └── websocket.py            # WS: /api/v1/sessions/{id}/stream (Redis pub/sub)
├── telegram_adapter/
│   └── telegram_bot.py             # /submit /status /report /cancel + phase watch loop
├── agent/                           # Original single-agent layer (from fork)
│   ├── agent_factory.py
│   ├── agent_manager.py
│   └── prompts.py
├── config/
│   ├── base_config.py
│   ├── agent_config.py
│   └── bot_config.py
├── core/
│   ├── message_handler.py
│   ├── redis_utils.py
│   ├── exceptions.py
│   └── utils.py
├── db/
│   ├── postgres_utils.py
│   └── user_data.py
├── frontend/                        # Next.js skeleton (original fork components only)
│   └── components/
│       ├── MemoryList.tsx           # Original fork component
│       └── UserSelector.tsx         # Original fork component
├── docs/
│   ├── PROJECT_PLAN.md             # Master plan (this file's counterpart)
│   └── ARCHITECTURE.md             # ← This file
├── docker-compose.yml               # Production services
├── docker-compose.dev.yml           # Dev with hot-reload + pgAdmin
└── .env.example
```

### Planned Additions — Days 6–10

```
├── frontend/components/
│   ├── PhaseTimeline.tsx            # 5-phase progress visualization
│   ├── DiscussionThread.tsx         # Agent debate display with round markers
│   ├── CostMonitor.tsx              # Real-time cost dashboard
│   └── TaskSubmit.tsx               # Task submission + session tracking form
├── frontend/hooks/
│   └── useSession.ts                # WebSocket session management hook
├── utils/
│   ├── timeout.py                   # Async timeout wrapper with fallback
│   ├── logging_config.py           # structlog JSON structured logging
│   └── retry.py                     # Exponential backoff retry decorator
├── api/v1/
│   └── health.py                    # GET /health — service health checks
├── scripts/
│   └── demo.py                      # Standalone end-to-end demo runner
├── tests/
│   ├── conftest.py                  # pytest fixtures + mocked LLM provider
│   ├── unit/                        # Unit tests for all nodes + cost tracker
│   └── integration/                 # Full graph flow integration tests
├── .github/workflows/
│   └── ci.yml                       # CI: pytest + codecov on push/PR
└── docs/
    ├── DEMO_SCRIPT.md               # 3 demo scenarios with expected outputs
    └── HANDOVER.md                  # Production handover guide for Stage 2
```

## LLM Provider Matrix

| Provider | Model | Role in PoC | Cost |
|----------|-------|-------------|------|
| Anthropic | Claude Sonnet 4.6 | Primary debater + synthesizer | API |
| OpenAI | GPT-4o | Secondary debater | API |
| Google | Gemini 2.5 Pro | Third debater | Free tier |
| OpenAI | GPT-4o-mini | PM Router (fast classification) | API |

## State Schema (Actual — `graph/state.py`)

```python
class PantheonState(TypedDict):
    # Core
    task: str                        # User's original task (unchanged throughout)
    phase: Literal["routing", "research", "debate", "voting", "synthesis", "complete"]
    session_id: str
    user_id: str

    # Model roles
    pm_model: str                    # Model key selected by PM Router

    # Phase outputs
    research_results: Dict[str, str] # {model_name: research_text}
    debate_history: List[Dict]       # [{round, model, content, timestamp}]
    debate_round: int                # Current round counter
    votes: Dict[str, str]            # {model_name: voted_approach}
    consensus: Optional[str]         # Winning approach after voting
    final_report: Optional[str]      # Phase 5 synthesized markdown report

    # Bookkeeping
    cost_summary: Dict               # Cumulative cost data across all phases
    messages: Annotated[List[BaseMessage], add_messages]  # append-only
```

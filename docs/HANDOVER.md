# Project Pantheon — Handover Document

> **Release:** v0.1.0-poc  
> **Stage:** 1 of 3 — Proof of Concept  
> **Date:** 2026-04-01  
> **Repository:** `salafadidas/project-pantheon`

---

## 1. What Was Built

Project Pantheon is a multi-AI-agent collaboration system in which three LLM providers (Claude, GPT-4o, Gemini) work together through a structured 5-phase workflow to produce consensus-driven answers.

### 5-Phase Workflow

```
User Task
   │
   ▼
🧭 PM Router      — Classifies task; selects lead model
   │
   ▼
🔬 Researcher     — All 3 models research concurrently
   │
   ▼
💬 Debater        — Multi-round structured debate (default: 3 rounds)
   │  ↺ (loop until MAX_DEBATE_ROUNDS)
   ▼
🗳️  Voter          — Majority-vote consensus
   │
   ▼
📝 Synthesizer    — Claude writes the final report
   │
   ▼
Final Report
```

### Input Channels

| Channel | Entry point |
|---------|------------|
| Telegram bot | `/submit`, `/status`, `/report`, `/cancel` |
| REST API | `POST /api/v1/sessions` → `POST /{id}/start` |
| WebSocket | `WS /api/v1/sessions/{id}/stream` |
| Web UI | Next.js at `http://localhost:3000` |
| CLI demo | `python scripts/demo.py --task "..."` |

---

## 2. Repository Layout

```
project-pantheon/
├── main.py                     # FastAPI + Telegram bot (asyncio.gather)
├── graph/
│   ├── state.py                # PantheonState TypedDict
│   ├── pantheon_graph.py       # Compiled LangGraph (5 phases)
│   └── nodes/                  # pm_router, researcher, debater, voter, synthesizer
├── llm/
│   ├── provider.py             # LiteLLM unified interface + caching
│   └── cost_tracker.py        # Per-session token + cost tracking
├── api/v1/
│   ├── sessions.py             # REST session CRUD + graph runner
│   ├── websocket.py            # Redis pub/sub → WebSocket bridge
│   └── health.py               # GET /health, GET /health/ready
├── telegram_adapter/
│   └── telegram_bot.py        # Telegram command handlers
├── utils/
│   ├── timeout.py              # with_timeout() + @timeout decorator
│   ├── logging_config.py      # structlog JSON logging
│   └── retry.py               # @retry + retry_call()
├── frontend/                   # Next.js (Pages Router)
│   ├── pages/index.tsx         # Home: task submission
│   ├── pages/session/[id].tsx  # Session view: timeline + discussion + cost
│   ├── components/             # PhaseTimeline, DiscussionThread, CostMonitor, TaskSubmit
│   └── hooks/useSession.ts     # WebSocket state hook
├── tests/                      # pytest suite (60+ tests)
├── scripts/demo.py             # Standalone CLI demo
├── docs/
│   ├── PROJECT_PLAN.md         # Master plan (version-controlled)
│   ├── ARCHITECTURE.md         # System diagrams, state schema
│   ├── DEMO_SCRIPT.md          # 3 demo scenarios with expected output
│   └── HANDOVER.md             # This file
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 3. Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | GPT-4o / GPT-4o-mini |
| `ANTHROPIC_API_KEY` | Yes | Claude Sonnet 4 |
| `GOOGLE_API_KEY` | Yes | Gemini 2.5 Pro |
| `TELEGRAM_TOKEN` | Yes (bot only) | BotFather token |
| `PG_CONNECTION_STRING` | Yes | PostgreSQL DSN |
| `REDIS_URL` | Yes | Redis DSN |
| `PHASE_TIMEOUT_SECONDS` | No | Default: 60 |
| `MAX_DEBATE_ROUNDS` | No | Default: 3 |
| `LOG_LEVEL` | No | Default: INFO |
| `LOG_JSON` | No | Default: true |
| `BACKEND_URL` | No | For Next.js proxy, default: http://localhost:8000 |

---

## 4. Running Locally

```bash
# 1. Clone and configure
git clone https://github.com/salafadidas/project-pantheon
cd project-pantheon
cp .env.example .env   # fill in keys

# 2. Start backing services
docker compose up -d postgres redis

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Start the backend (FastAPI + Telegram bot)
python main.py

# 5. Start the frontend (separate terminal)
cd frontend
npm install
npm run dev            # http://localhost:3000

# 6. Run the demo
python scripts/demo.py --task "Compare REST and GraphQL for a mobile app"
```

### Health check

```bash
curl http://localhost:8000/health        # liveness
curl http://localhost:8000/health/ready  # readiness (Redis ping)
```

---

## 5. Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=graph --cov=llm --cov=utils --cov-report=term-missing

# Specific module
pytest tests/test_graph_voter.py -v
```

Coverage targets: `graph/`, `llm/`, `utils/` — 80%+.

---

## 6. Key Design Decisions

### Why LangGraph?
Provides a structured state machine with conditional edges (debate loop), built-in streaming via `astream()`, and clean node/edge separation. Alternatives considered: plain asyncio chains (less observable), CrewAI (less control over state).

### Why LiteLLM?
Single interface for Claude/GPT-4o/Gemini. Handles auth, retries, and token counting across providers. Allows swapping models via config without code changes.

### Why Redis for session state?
Sessions are short-lived (24h TTL), and pub/sub is needed for real-time WebSocket streaming. Redis handles both without a separate message broker.

### Why not use streaming LLM responses?
Phase-level streaming (per-node, not per-token) was chosen for PoC simplicity. Stage 2 should add token-level streaming via `StreamingCallback`.

---

## 7. Known Limitations (PoC scope)

| Limitation | Notes |
|------------|-------|
| No authentication | REST API is open; add API key middleware in Stage 2 |
| In-memory cost tracker | Resets on restart; persist to PostgreSQL in Stage 2 |
| Single-process deployment | Telegram + FastAPI share one event loop; use separate workers in Stage 2 |
| No rate limiting | Add per-user rate limiting in Stage 2 |
| Frontend has no auth | Add user accounts and session history in Stage 2 |
| Tests mock LLM calls | Integration tests against real APIs not included |

---

## 8. Stage 2 Priorities (Recommended)

1. **Authentication** — API key middleware for REST + WebSocket
2. **Persistent cost tracking** — write `UsageRecord` to PostgreSQL
3. **Token-level streaming** — LangChain streaming callbacks → WebSocket
4. **Worker separation** — separate uvicorn workers from Telegram bot process
5. **Rate limiting** — per-user / per-IP via Redis
6. **Monitoring** — Prometheus metrics endpoint + Grafana dashboard
7. **Frontend accounts** — session history, user profiles
8. **Production Docker Compose** — nginx reverse proxy, TLS, health probes

See `docs/PROJECT_PLAN.md` §3 (Stage 2) for the full scope.

---

## 9. CI / CD

GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push to `main` and `claude/**` branches:

| Job | What it checks |
|-----|---------------|
| `test` (Python 3.11 + 3.12) | pytest with coverage across `graph/`, `llm/`, `utils/`, `api/` |
| `lint` | ruff E/F/W rules |
| `frontend` | `npm run build` + TypeScript type-check |

---

## 10. Contacts & References

| Item | Location |
|------|----------|
| Master plan | `docs/PROJECT_PLAN.md` |
| Architecture diagrams | `docs/ARCHITECTURE.md` |
| Demo scenarios | `docs/DEMO_SCRIPT.md` |
| Issue tracker | `salafadidas/project-pantheon` on GitHub |
| Original fork | `francescofano/langgraph-telegram-bot` |

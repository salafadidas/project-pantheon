# Project Pantheon

Multi-engine multi-agent collaboration system: Claude, GPT-4o, and Gemini work together through a structured **5-phase workflow** to produce high-quality, consensus-driven answers.

> Stage 1 (PoC) — Days 1–5 of 10 complete. See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for full progress.

## How It Works

```
Task Input → PM Router → Researcher → Debater → Voter → Synthesizer → Final Report
                ↑           (concurrent)  (multi-round loop)    ↑
          selects model    all 3 LLMs      Claude/GPT/Gemini   markdown
```

1. **PM Router** — classifies the task and selects the lead model
2. **Researcher** — all three LLMs independently research in parallel
3. **Debater** — models debate across multiple rounds
4. **Voter** — models vote on the best approach; consensus calculated
5. **Synthesizer** — final structured markdown report combining all perspectives

## Status

| Stage | Description | Timeline | Status |
|-------|-------------|----------|--------|
| Stage 1 | PoC — core flow demo | 2 weeks | In progress (Day 5/10) |
| Stage 2 | Production deployment — scalable, monitored | 4–6 weeks | Not started |
| Stage 3 | Eigent integration (optional) | 1–2 weeks | Decision gate |

## Quick Start

```bash
cp .env.example .env
# Fill in: TELEGRAM_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY

docker-compose up --build
```

- API: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Usage

### Telegram Bot

```
/submit <task>          Start a new Pantheon session
/status <session_id>    Check current phase
/report <session_id>    Get the final report
/cancel <session_id>    Cancel a running session
```

### REST API

```bash
# Create session
curl -X POST http://localhost:8000/api/v1/sessions

# Start with task
curl -X POST http://localhost:8000/api/v1/sessions/{id}/start \
     -H "Content-Type: application/json" \
     -d '{"task": "Compare React vs Vue for a large-scale app"}'

# Check status
curl http://localhost:8000/api/v1/sessions/{id}/status

# Get report (when complete)
curl http://localhost:8000/api/v1/sessions/{id}/report
```

### WebSocket (real-time phase streaming)

```
WS ws://localhost:8000/api/v1/sessions/{id}/stream
```

Emits: `phase_complete`, `session_complete`, `session_error`

## Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11, FastAPI, asyncio |
| Orchestration | LangGraph (StateGraph) |
| LLM integration | LiteLLM |
| Models | Claude Sonnet 4.6 · GPT-4o · Gemini 2.5 Pro |
| Database | PostgreSQL + pgvector |
| Cache / pub-sub | Redis |
| Frontend | Next.js (React) |
| Infra | Docker Compose |

## Configuration

Copy `.env.example` and fill in your keys:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | From @BotFather |
| `ANTHROPIC_API_KEY` | Claude access |
| `OPENAI_API_KEY` | GPT-4o access |
| `GOOGLE_API_KEY` | Gemini access |
| `PG_CONNECTION_STRING` | PostgreSQL URL |
| `REDIS_URL` | Redis URL |
| `MAX_DEBATE_ROUNDS` | Debate iterations (default: 3) |
| `PHASE_TIMEOUT_SECONDS` | Per-model timeout (default: 60) |

## Documentation

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — Master plan: 3-stage roadmap + day-by-day progress
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — System diagrams, state schema, LLM matrix

## Development

```bash
docker-compose -f docker-compose.dev.yml up --build
# Hot-reload enabled; pgAdmin at http://localhost:5050
```

## License

MIT

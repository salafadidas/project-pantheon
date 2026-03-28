# Day 9: Docker Polish + End-to-End Validation

## Context
Building on Day 8's test suite. Final polishing for PoC demo-readiness.

## Task

### 1. Update `docker-compose.yml`
Ensure all services are production-ready for demo:
- `bot` service: add healthcheck using `curl -f http://localhost:8000/health || exit 1`
- Add `PHASE_TIMEOUT_SECONDS=60` env var to bot service
- Add `MAX_DEBATE_ROUNDS=3` env var to bot service
- Add `LLM_MAX_RETRIES=2` env var to bot service
- Verify all API keys are passed via env vars (not hardcoded)
- Add `depends_on` with `condition: service_healthy` for postgres and redis

### 2. Create `api/v1/health.py`
Health check endpoint:
```python
GET /health
# Returns: {"status": "ok", "version": "1.0.0", "services": {"postgres": "ok", "redis": "ok"}}
# Returns 503 if any dependency is unhealthy
```

### 3. Create `.env.example`
Template for all required environment variables:
```bash
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Multi-Model Config
DEBATE_MODELS=claude-sonnet,gpt-4o,gemini-2.5-pro
PM_MODEL=gpt-4o-mini
SYNTHESIZER_MODEL=claude-sonnet

# Timeouts & Limits
PHASE_TIMEOUT_SECONDS=60
MAX_DEBATE_ROUNDS=3
LLM_MAX_RETRIES=2
LLM_CALLS_PER_MINUTE=5

# Database
PG_CONNECTION_STRING=postgresql://langbotuser:yourpassword@postgres:5432/langbotdb
REDIS_URL=redis://redis:6379/0

# Logging
LOG_LEVEL=INFO
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
```

### 4. Create `scripts/demo.py`
Demo script that runs a complete 5-phase session programmatically:
```python
# Usage: python scripts/demo.py "What is the best Python web framework for a real-time chat app?"
# Prints phase-by-phase output to terminal
# At the end, prints the final_report
```
- Uses the full LangGraph directly (no HTTP, no Telegram)
- Loads env vars from `.env`
- Prints each phase result as it completes
- Shows total cost at the end

### 5. Update `README.md`
Add "Quick Start" section:
```markdown
## Quick Start

1. Copy `.env.example` to `.env` and fill in API keys
2. Run: `docker-compose up -d`
3. Open: http://localhost:3000 (Web UI)
4. Or use Telegram: send `/submit What is the best Python web framework?`
5. Demo script: `python scripts/demo.py "Your task here"`
```

### 6. Final smoke test
Run the demo script with a sample task. Verify:
- All 5 phases complete without error
- final_report is generated
- cost_summary shows reasonable token counts
- No Python exceptions or unhandled errors

### 7. Update `docs/PROJECT_PLAN.md` Day 9 status to "Done"

## Requirements
- Demo script must work with just `.env` + `python scripts/demo.py "task"`
- Health endpoint must check actual connectivity to postgres and redis
- docker-compose up must start cleanly on a fresh machine (no pre-existing state)

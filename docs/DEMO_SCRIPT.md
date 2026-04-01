# Project Pantheon — Demo Script

> **Version:** v0.1.0-poc  
> **Audience:** Stakeholders, reviewers, potential Stage 2 sponsors  
> **Duration:** ~15 minutes for all three scenarios

---

## Prerequisites

```bash
# Clone and set up
git clone https://github.com/salafadidas/project-pantheon
cd project-pantheon
cp .env.example .env          # fill in API keys

# Start services
docker compose up -d          # postgres + redis

# Install Python deps
pip install -r requirements.txt
```

Verify everything is healthy:

```bash
# Start the API server
python main.py &

curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0-poc","uptime_seconds":2.1,...}

curl http://localhost:8000/health/ready
# {"status":"ok","checks":{"redis":"ok"},...}
```

---

## Scenario 1 — CLI Demo (Fastest, ~3 min)

Shows the full 5-phase pipeline in the terminal.

```bash
python scripts/demo.py \
  --task "What are the key trade-offs between microservices and a monolith for a startup?"
```

**Expected output:**

```
──────────────────────────────────────────────────────────────────────
  Project Pantheon — Multi-Agent Demo
──────────────────────────────────────────────────────────────────────
  Task : What are the key trade-offs between microservices and a mono…
  Start: 2026-04-01 12:00:00
──────────────────────────────────────────────────────────────────────

  🧭  PM Router     ✓  1.2s  (analytical task → Gemini 2.5 Pro)
  🔬  Researcher    ✓  8.4s  (3 model(s) responded)
  💬  Debater       ✓  14.1s  (round 3)
  🗳️  Voter         ✓  16.2s  (consensus: Start monolith, migrate later)
  📝  Synthesizer   ✓  22.7s  (1842 chars)

──────────────────────────────────────────────────────────────────────
  FINAL REPORT
──────────────────────────────────────────────────────────────────────
  After three rounds of structured debate between Claude Sonnet,
  GPT-4o, and Gemini 2.5 Pro, all three models converged on the
  recommendation to start with a modular monolith…
──────────────────────────────────────────────────────────────────────

  💰  Total cost : $0.0234 USD
       claude-sonnet-4-20250514     $0.0091
       gpt-4o                       $0.0078
       gemini-2.5-pro               $0.0065

  ⏱  Total time : 22.7s
```

**Talking points:**
- Three different AI models each bring a distinct perspective
- Debate rounds surface disagreements; voting reaches consensus
- Cost transparency built-in from Day 1

---

## Scenario 2 — REST API + WebSocket (Live streaming, ~5 min)

Shows the HTTP API and real-time event streaming.

### Step 1 — Create a session

```bash
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" | jq -r .session_id)
echo "Session: $SESSION"
```

### Step 2 — Open a WebSocket stream (separate terminal)

```bash
websocat "ws://localhost:8000/api/v1/sessions/$SESSION/stream"
```

### Step 3 — Start the session

```bash
curl -s -X POST "http://localhost:8000/api/v1/sessions/$SESSION/start" \
  -H "Content-Type: application/json" \
  -d '{"task": "Compare React, Vue, and Svelte for a dashboard product", "user_id": "demo"}'
```

**WebSocket stream (live):**

```json
{"event":"phase_complete","phase":"routing","timestamp":"..."}
{"event":"phase_complete","phase":"research","data":{"research_results":{...}},...}
{"event":"phase_complete","phase":"debate","data":{"debate_round":1},...}
{"event":"phase_complete","phase":"debate","data":{"debate_round":2},...}
{"event":"phase_complete","phase":"debate","data":{"debate_round":3},...}
{"event":"phase_complete","phase":"voting","data":{"votes":{...},"consensus":"..."},...}
{"event":"session_complete","final_report":"...","timestamp":"..."}
```

### Step 4 — Fetch the report

```bash
curl -s "http://localhost:8000/api/v1/sessions/$SESSION/report" | jq .final_report
```

**Talking points:**
- REST API with 24-hour session persistence (Redis)
- Real-time streaming — clients never need to poll
- Full session lifecycle: create → start → stream → report

---

## Scenario 3 — Telegram Bot (~5 min)

Shows the conversational interface.

### Setup

Add `TELEGRAM_TOKEN` to `.env`, then restart:

```bash
python main.py
```

### Commands to demo

| Command | What it does |
|---------|-------------|
| `/submit Compare SQL and NoSQL databases for IoT sensor data` | Starts a session, returns session ID |
| `/status <session_id>` | Shows current phase |
| `/report <session_id>` | Fetches the final report when complete |
| `/cancel <session_id>` | Cancels a running session |

**Talking points:**
- Same backend, different interface — demonstrates the adapter pattern
- Real-time phase notifications pushed to the chat as phases complete
- Works in group chats (session ID keeps conversations separate)

---

## Key Demo Stats (reference)

| Metric | Typical value |
|--------|--------------|
| End-to-end latency | 20–45 s (depends on model response times) |
| Cost per session | $0.01–$0.05 USD |
| Debate rounds | 3 (configurable via `MAX_DEBATE_ROUNDS`) |
| Phase timeout | 60 s per model (configurable) |
| Session TTL | 24 hours (Redis) |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `redis not available` on `/health/ready` | Run `docker compose up -d redis` |
| Models return errors | Check API keys in `.env` |
| Timeout errors in research phase | Increase `PHASE_TIMEOUT_SECONDS` in `.env` |
| WebSocket disconnects immediately | Session may not exist — check session ID |

---
title: Project Pantheon — Master Implementation Plan
version: v3.3
date: 2026-04-14
status: Stage 1 (PoC) COMPLETE — tagged v0.1.0-poc; CI green
---

# Project Pantheon — Master Implementation Plan

> **Current file: `PROJECT_PLAN_v3.3.md`** — For NotebookLM: always upload the highest-numbered file. Check `version:` on line 3 and the filename to confirm currency.

---

## 1. Project Overview

Project Pantheon is a cross-engine multi-agent collaboration system where multiple LLM providers (Claude, GPT-4o, Gemini) work together through a structured 5-phase workflow to produce high-quality, consensus-driven answers.

**Origin:** Forked from `francescofano/langgraph-telegram-bot` (single-agent memory bot with Telegram + PostgreSQL + Redis).

**5-Phase Workflow:**
1. **PM Router** — Classify task type, select lead AI model
2. **Researcher** — Each AI independently researches the topic (concurrent)
3. **Debater** — Multi-round structured debate between models
4. **Voter** — Consensus voting on best approach
5. **Synthesizer** — Combine all perspectives into a structured final report

**Entry point:** `main.py` — FastAPI (port 8000) + Telegram bot running concurrently in one asyncio event loop.

**Input channels:** Telegram bot, REST API, WebSocket, Web UI (React)

---

## 2. Current Progress Snapshot

> Last updated: 2026-04-01 | **Stage 1 PoC — ALL 10 DAYS COMPLETE** ✅ Tagged `v0.1.0-poc`

| Component | Files | Status |
|-----------|-------|--------|
| LangGraph state + graph orchestrator | `graph/state.py`, `graph/pantheon_graph.py` | ✅ Complete |
| 5 phase nodes | `graph/nodes/{pm_router,researcher,debater,voter,synthesizer}.py` | ✅ Complete |
| LiteLLM multi-model provider | `llm/provider.py` | ✅ Complete |
| Cost tracker | `llm/cost_tracker.py` | ✅ Complete |
| FastAPI REST sessions API | `api/v1/sessions.py` | ✅ Complete |
| WebSocket streaming | `api/v1/websocket.py` | ✅ Complete |
| Telegram bot (Pantheon commands) | `telegram_adapter/telegram_bot.py` | ✅ Complete |
| React Phase UI components | `frontend/components/`, `frontend/pages/session/[id].tsx` | ✅ Complete |
| Utility layer (timeout, logging, retry) | `utils/timeout.py`, `utils/logging_config.py`, `utils/retry.py` | ✅ Complete |
| Test suite | `tests/` (8 modules, 60+ test cases) | ✅ Complete |
| Health endpoint + demo script | `api/v1/health.py`, `scripts/demo.py` | ✅ Complete |
| CI/CD pipeline | `.github/workflows/ci.yml` | ✅ Complete |
| Handover docs | `docs/DEMO_SCRIPT.md`, `docs/HANDOVER.md` | ✅ Complete |

---

## 3. Delivery Stages

### Stage 1: PoC — Proof of Concept (2 weeks)

**Goal:** Complete functional prototype that can demonstrate the core 5-phase flow end-to-end.

#### Days 1–5 — Complete

| Day | Task | Model | Status |
|-----|------|-------|--------|
| 1 | Fork repo, environment setup, docs | Haiku 4.5 | ✅ Done |
| 2 | LiteLLM multi-model provider + cost tracking | Sonnet 4.6 | ✅ Done |
| 3 | LangGraph state expansion + debate node | Sonnet 4.6 | ✅ Done |
| 4 | PM router, researcher, voter, synthesizer nodes | Sonnet 4.6 | ✅ Done |
| 5 | Telegram commands + FastAPI REST/WebSocket | Sonnet 4.6 | ✅ Done |

#### Days 6–10 — Complete

| Day | Task | Key Deliverables | Model | Status |
|-----|------|-----------------|-------|--------|
| 6 | React frontend Phase UI | `PhaseTimeline.tsx`, `DiscussionThread.tsx`, `CostMonitor.tsx`, `TaskSubmit.tsx`, `useSession` hook | Sonnet 4.6 | ✅ Done |
| 7 | Utility layer | `utils/timeout.py`, `utils/logging_config.py` (structlog), `utils/retry.py` | Haiku 4.5 | ✅ Done |
| 8 | Test suite | pytest, 80%+ coverage on `graph/` and `llm/` | Haiku 4.5 | ✅ Done |
| 9 | Health + demo prep | `api/v1/health.py`, `scripts/demo.py`, `.env.example` update | Haiku 4.5 | ✅ Done |
| 10 | CI/CD + release | `.github/workflows/ci.yml`, `docs/DEMO_SCRIPT.md`, `docs/HANDOVER.md`, git tag `v0.1.0-poc` | Haiku 4.5 | ✅ Done |

#### Stage 1 Exit Criteria

- [x] End-to-end demo runs in Docker Compose (single `docker-compose up`)
- [x] Telegram `/submit` → `/status` → `/report` flow functional
- [x] React UI streams live phase updates via WebSocket
- [x] pytest CI passes on main branch
- [x] Git tag `v0.1.0-poc` created

---

### Stage 2: 生產級部署 (Production-Grade Deployment) — 4–6 weeks

**Goal:** Production-ready, scalable, full monitoring + UI. Decision gate: after Stage 1 tag.

**Scope (to be detailed in Stage 2 sprint plan):**
- Cloud deployment (target: TBD — AWS / GCP / self-hosted)
- Authentication layer (API keys or OAuth)
- Full observability: structured metrics (Prometheus/Grafana), distributed tracing
- Multi-tenant session isolation and rate limiting
- Performance testing and SLA definition
- Production-grade frontend (user accounts, session history)
- Automated backups and disaster recovery

**Status: Not yet started** — detailed sprint plan to be written after `v0.1.0-poc` tag.

---

### Stage 3: Eigent 整合 — Path B (1–2 weeks, optional)

**Goal:** Add execution capability layer to Pantheon agents via API bridge.

**Scope:**
- Eigent API bridge module
- Allow agents to execute external actions (not just synthesize text)
- Integration hooks into existing 5-phase LangGraph (must be opt-in toggle)
- Must not break existing PoC/production flow

**Status: Optional** — decision gate after Stage 2 completion.

---

## 4. Technical Architecture Summary

> Full diagrams, state schema, and LLM matrix: see `docs/ARCHITECTURE.md`

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11, FastAPI, asyncio |
| Orchestration | LangGraph (StateGraph with conditional edges) |
| LLM integration | LiteLLM unified interface |
| Primary LLM | Claude Sonnet 4.6 (Anthropic) |
| Secondary LLM | GPT-4o (OpenAI) |
| Tertiary LLM | Gemini 2.5 Pro (Google) |
| Database | PostgreSQL + pgvector |
| Cache / pub-sub | Redis |
| Frontend | Next.js (React), WebSocket streaming |
| Infra | Docker Compose (dev + prod configs) |

---

## 5. Repository Map (Actual — v3.0)

```
project-pantheon/
├── main.py                          # FastAPI app + Telegram bot concurrent startup
├── graph/
│   ├── state.py                     # PantheonState TypedDict
│   ├── pantheon_graph.py            # Compiled LangGraph (all 5 phases wired)
│   └── nodes/
│       ├── pm_router.py             # Phase 1: task classification + model selection
│       ├── researcher.py            # Phase 2: concurrent multi-model research
│       ├── debater.py               # Phase 3: multi-round debate
│       ├── voter.py                 # Phase 4: consensus voting
│       └── synthesizer.py          # Phase 5: final report synthesis
├── llm/
│   ├── provider.py                  # LiteLLM unified multi-model interface
│   └── cost_tracker.py             # Token usage + cost tracking per session
├── api/v1/
│   ├── sessions.py                  # REST: POST/GET/DELETE /api/v1/sessions
│   ├── websocket.py                 # WS: /api/v1/sessions/{id}/stream
│   └── health.py                    # GET /health, GET /health/ready
├── telegram_adapter/
│   └── telegram_bot.py             # /submit /status /report /cancel
├── utils/
│   ├── timeout.py                   # Async timeout wrapper + @timeout decorator
│   ├── logging_config.py           # structlog JSON logging
│   └── retry.py                     # Exponential backoff @retry + retry_call()
├── frontend/                        # Next.js (Pages Router)
│   ├── pages/index.tsx              # Home: task submission
│   ├── pages/session/[id].tsx       # Session view
│   ├── components/                  # PhaseTimeline, DiscussionThread, CostMonitor, TaskSubmit
│   └── hooks/useSession.ts          # WebSocket state hook
├── tests/                           # pytest suite (8 modules, 60+ tests)
├── scripts/demo.py                  # Standalone CLI demo
├── .github/workflows/ci.yml         # CI: pytest + ruff + Next.js build
├── docs/
│   ├── PROJECT_PLAN_v3.0.md        # ← This file (master plan, current version)
│   ├── ARCHITECTURE.md             # System diagrams, state schema, LLM matrix
│   ├── DEMO_SCRIPT.md              # 3 demo scenarios with expected output
│   └── HANDOVER.md                 # Production handover guide
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
└── .env.example
```

---

## 6. Versioning Policy

### Filename versioning — rules

- **The filename IS the version**: `PROJECT_PLAN_vX.Y.md`
- **Only one versioned file exists at a time** — when bumping, rename the old file to the new version (git mv); do not accumulate stale copies
- The highest-numbered file in `docs/` is always the current plan
- Upload the current versioned file to NotebookLM (**account: salafadidas@gmail.com**); delete old sources before uploading

### When to bump

| Bump type | Example | Trigger |
|-----------|---------|---------|
| Patch | v3.0 → v3.1 | A day/task completes; status cells updated |
| Minor | v3.1 → v3.2 | Scope item added or removed within a stage |
| Major | v3.x → v4.0 | A stage completes and the next stage's sprint plan is written |

### Bump procedure (mandatory before any implementation code)

```
1. git mv docs/PROJECT_PLAN_vX.Y.md docs/PROJECT_PLAN_vX.(Y+1).md
2. Update version: and date: in YAML front-matter
3. Update the title line: "Current file: PROJECT_PLAN_vX.(Y+1).md"
4. Update the relevant status rows / day tables
5. Add an entry to the Version History section below
6. git add + git commit "chore: bump plan to vX.(Y+1) — <reason>"
7. Only then write implementation code
```

---

## 7. Open Questions / Decision Log

| Question | Status |
|----------|--------|
| Stage 2 cloud target (AWS / GCP / self-hosted) | TBD — decide at Stage 1 completion |
| Authentication strategy for Stage 2 API | TBD |
| Stage 3 Eigent integration — proceed or skip | Decision gate after Stage 2 |
| Frontend framework for Stage 2 (keep Next.js or migrate) | TBD |

---

## 8. Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v2.0 | 2026-03-26 | Sonnet 4.6 | Initial master plan rewrite — replaced fragmented v1.5.md files; added YAML front-matter; documented all 3 delivery stages |
| v2.1 | 2026-04-01 | Sonnet 4.6 | Day 6 started — React frontend in progress |
| v2.2 | 2026-04-01 | Sonnet 4.6 | Day 6 complete — PhaseTimeline, DiscussionThread, CostMonitor, TaskSubmit, useSession, session page, index page |
| v2.3 | 2026-04-01 | Sonnet 4.6 | Day 7 started — utility layer in progress |
| v2.4 | 2026-04-01 | Sonnet 4.6 | Day 7 complete — utils/timeout.py, utils/logging_config.py (structlog), utils/retry.py |
| v2.5 | 2026-04-01 | Sonnet 4.6 | Day 8 started — test suite in progress |
| v2.6 | 2026-04-01 | Sonnet 4.6 | Day 8 complete — pytest suite (8 modules, 60+ tests) |
| v2.7 | 2026-04-01 | Sonnet 4.6 | Day 9 started — health + demo in progress |
| v2.8 | 2026-04-01 | Sonnet 4.6 | Day 9 complete — api/v1/health.py, scripts/demo.py, .env.example |
| v2.9 | 2026-04-01 | Sonnet 4.6 | Day 10 started — CI/CD + release in progress |
| v3.0 | 2026-04-01 | Sonnet 4.6 | **Stage 1 PoC COMPLETE** — ci.yml, DEMO_SCRIPT.md, HANDOVER.md, git tag v0.1.0-poc; switched to filename-based versioning |
| v3.1 | 2026-04-13 | Sonnet 4.6 | CI fix — structlog PrintLoggerFactory → stdlib.LoggerFactory; explicit setLevel() for root logger; all 86 tests green |
| v3.2 | 2026-04-13 | Sonnet 4.6 | NotebookLM account migrated: susynoid09@gmail.com → salafadidas@gmail.com; account recorded in plan §6 and CLAUDE.md |
| v3.3 | 2026-04-14 | Sonnet 4.6 | CLAUDE.md: added Error Prevention standards (capability investigation protocol, forbidden anti-patterns) and CLAUDE.md Update Policy |

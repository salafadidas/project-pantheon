---
title: Project Pantheon — Master Implementation Plan
version: v2.6
date: 2026-04-01
status: Active — Stage 1 (PoC) Day 9 up next
---

# Project Pantheon — Master Implementation Plan

> **v2.6 | 2026-04-01** — Single source of truth. For NotebookLM: always upload this file; check `version:` on line 3 to confirm currency.

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

> Last updated: 2026-04-01 | Stage 1 PoC — Days 1–8 complete, Day 9 up next

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
| Health endpoint + demo script | `api/v1/health.py`, `scripts/demo.py` | ❌ Not started |
| CI/CD pipeline | `.github/workflows/ci.yml` | ❌ Not started |
| Handover docs | `docs/DEMO_SCRIPT.md`, `docs/HANDOVER.md` | ❌ Not started |

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

#### Days 6–10 — Pending

| Day | Task | Key Deliverables | Model | Status |
|-----|------|-----------------|-------|--------|
| 6 | React frontend Phase UI | `PhaseTimeline.tsx`, `DiscussionThread.tsx`, `CostMonitor.tsx`, `TaskSubmit.tsx`, `useSession` hook | Sonnet 4.6 | ✅ Done |
| 7 | Utility layer | `utils/timeout.py`, `utils/logging_config.py` (structlog), `utils/retry.py` | Haiku 4.5 | ✅ Done |
| 8 | Test suite | pytest, 80%+ coverage on `graph/` and `llm/` | Haiku 4.5 | ✅ Done |
| 9 | Health + demo prep | `api/v1/health.py`, `scripts/demo.py`, `.env.example` update | Haiku 4.5 | ⏳ Pending |
| 10 | CI/CD + release | `.github/workflows/ci.yml`, `docs/DEMO_SCRIPT.md`, `docs/HANDOVER.md`, git tag `v0.1.0-poc` | Haiku 4.5 | ⏳ Pending |

#### Stage 1 Exit Criteria

- [ ] End-to-end demo runs in Docker Compose (single `docker-compose up`)
- [ ] Telegram `/submit` → `/status` → `/report` flow functional
- [ ] React UI streams live phase updates via WebSocket
- [ ] pytest CI passes on main branch
- [ ] Git tag `v0.1.0-poc` created

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

## 5. Repository Map (Actual — 2026-04-01)

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
├── api/
│   └── v1/
│       ├── sessions.py              # REST: POST/GET/DELETE /api/v1/sessions
│       └── websocket.py            # WS: /api/v1/sessions/{id}/stream
├── telegram_adapter/
│   └── telegram_bot.py             # /submit /status /report /cancel + phase notifications
├── agent/                           # Original single-agent layer (from fork)
├── config/                          # BotConfig, AgentConfig, BaseConfig
├── core/                            # MessageProcessor, redis_utils, exceptions, utils
├── db/                              # PostgreSQL + pgvector utilities
├── frontend/                        # Next.js skeleton (original fork components only)
├── docs/
│   ├── PROJECT_PLAN.md             # ← This file (master plan)
│   └── ARCHITECTURE.md             # System diagrams, state schema, LLM matrix
├── docker-compose.yml               # Production: bot + postgres + redis + frontend
├── docker-compose.dev.yml           # Development: same + hot-reload + pgAdmin
├── Dockerfile
└── .env.example                     # All required environment variables
```

**Planned additions (Days 6–10):**
```
├── frontend/components/
│   ├── PhaseTimeline.tsx            # 5-phase progress visualization
│   ├── DiscussionThread.tsx         # Agent debate display
│   ├── CostMonitor.tsx              # Real-time cost tracking
│   └── TaskSubmit.tsx               # Task submission form
├── utils/
│   ├── timeout.py                   # Async timeout wrapper
│   ├── logging_config.py           # structlog JSON logging
│   └── retry.py                     # Exponential backoff retry
├── api/v1/health.py                 # GET /health endpoint
├── scripts/demo.py                  # Standalone end-to-end demo
├── tests/                           # pytest suite (80%+ coverage target)
├── .github/workflows/ci.yml         # CI pipeline
└── docs/
    ├── DEMO_SCRIPT.md               # 3 demo scenarios
    └── HANDOVER.md                  # Production handover guide
```

---

## 6. Versioning Policy

- Version lives in the YAML front-matter block at the top of this file — **never in the filename**
- `PROJECT_PLAN.md` is the permanent filename
- **Patch bump** (v2.0 → v2.1): a day completes, status cells updated
- **Minor bump** (v2.1 → v2.2): scope item added or removed within a stage
- **Major bump** (v2.x → v3.0): a stage completes and the next stage's sprint plan is written in full

---

## 7. Open Questions / Decision Log

| Question | Status |
|----------|--------|
| Stage 2 cloud target (AWS / GCP / self-hosted) | TBD — decide at Stage 1 completion |
| Authentication strategy for Stage 2 API | TBD |
| Stage 3 Eigent integration — proceed or skip | Decision gate after Stage 2 |
| Frontend framework for Stage 2 (keep Next.js or migrate) | TBD |

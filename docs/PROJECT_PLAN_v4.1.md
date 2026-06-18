---
title: Project Pantheon — Stage 2 Sprint Plan
version: v4.1
date: 2026-06-18
status: Active — Sprint 0 (Memory layer migration spike) added before Sprint 1
parent_plan: PROJECT_PLAN_v3.4.md
---

# Project Pantheon — Stage 2 Sprint Plan (Production-Grade Deployment)

> **Current file: `PROJECT_PLAN_v4.1.md`** — Sprint-level plan for Stage 2.
> Master plan continues to live in `PROJECT_PLAN_v3.4.md` (or its successor).

---

## 0. Change log for v4.1

**Added Sprint 0 — Memory layer migration spike (2026-06-18)**

`openmemory` has been inactive for 78+ days (last push 2026-04-01) and is flagged 🔴 in both Gstar v20260618 and eSystem v20260618 reports. The recommended replacement, `thedotmack/claude-mem` (83k★, MCP-native, active), is architecturally **NOT a drop-in** for Pantheon's deployment model. Before any code-level replacement, we run a 2-day spike to determine whether claude-mem can be adapted to Pantheon's server-side, Cloud-Run-bound architecture — or whether a different memory layer (langmem, agentmemory, custom Postgres+pgvector) is the better path.

**Decision gate at end of Sprint 0**: choose one of {claude-mem-adapted, claude-mem-rejected→alt, defer-replacement}. Only after this gate do Sprints 1–6 begin.

---

## 1. Goals & Non-Goals

### Goals
1. Run Pantheon as a **multi-tenant cloud service** with per-tenant rate limits and isolation.
2. Add **authentication** (API key for server-to-server, Google OAuth for browser users).
3. Add **observability** — Prometheus metrics, Grafana dashboards, OpenTelemetry traces.
4. **Performance test** — establish SLAs (p50 / p95 latency per phase, max concurrent sessions).
5. **Disaster recovery** — automated DB backups, runbook, restore drill.
6. **User-facing UI improvements** — accounts, session history, share-by-link.
7. **(NEW) Replace inactive openmemory memory layer** with a sustainable, MCP-compatible alternative.

### Non-Goals (deferred to Stage 3 or later)
- Eigent execution layer (Stage 3)
- Mobile-native app
- Offline mode
- Custom model fine-tuning
- Marketplace / plugin system

---

## 2. Decisions Locked (from v3.4 §7)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cloud target | **GCP Cloud Run + Memorystore + Cloud SQL** | LangGraph + Redis pub/sub friendly; Gemini in-network saves egress; pay-per-request matches bursty usage |
| Auth strategy | **API Key (server) + Google OAuth (browser)** | Reuses Google account already used for NotebookLM; no need to manage passwords |
| Frontend | **Keep Next.js 14**, add NextAuth | Avoid rewrite; mature WebSocket support |
| Stage 3 (Eigent) | **Deferred** to post-Stage 2 decision gate | Avoid scope creep |
| Memory layer | **Under review (Sprint 0 spike)** | openmemory inactive 78d; claude-mem not cloud-native |

---

## 3. Reference Architecture
(unchanged from v4.0 — see prior version)

---

## 4. Sprint Breakdown

### Sprint 0 — Memory Layer Migration Spike (2 days, 2026-06-19 → 2026-06-20) — **NEW**

**Objective**: Decide the production memory layer for Pantheon. Output is a written decision, not production code.

#### Context: why this is a spike, not a direct replacement

| Property | openmemory (current) | claude-mem (proposed) | Pantheon needs |
|----------|---------------------|----------------------|----------------|
| MCP transport | HTTP (`localhost:8080/mcp`) | **stdio** (per `src/servers/mcp-server.ts`) | HTTP (FastAPI container) |
| Storage | In-memory / configurable | **SQLite + Chroma on local FS** (`~/.claude-mem/`) | Postgres + pgvector (Cloud SQL) |
| Designed for | Generic MCP service | **Claude Code / Desktop / Cursor / Gemini CLI** | Server-side multi-tenant FastAPI |
| Cloud Run compat | Yes (HTTP service) | **No** (local worker + filesystem state) | Cloud Run required |
| Activity | ❌ Inactive 78 days | ✅ Active (83k★, daily commits) | Sustainable |
| License | — | AGPL-3.0 | Personal use OK; verify before any redistribution |

#### Spike tasks

| # | Task | Output | Time |
|---|------|--------|------|
| 0.1 | Map current openmemory usage surface in Pantheon code | grep results documented; confirm `.mcp.json` is the only touch point (initial scan: no `langmem`/`openmemory` strings in `agent/`, `core/`, `graph/`, `llm/`) | 1h |
| 0.2 | Run claude-mem Docker container (`docker/claude-mem/`) locally | Container boots; SQLite DB writes observations; web viewer reachable at `:37777` | 2h |
| 0.3 | Evaluate: can claude-mem's worker HTTP API (port 37777) be exposed as a tenant-scoped MCP-HTTP shim? | Written analysis: feasibility, security risk (single global DB), tenant isolation gap, AGPL license implications for hosting | 3h |
| 0.4 | Evaluate alternative A: `langmem` (already in `requirements.txt`, LangChain-native, Postgres backend) | PoC notebook: store/retrieve a memory across two LangGraph runs using existing pgvector | 3h |
| 0.5 | Evaluate alternative B: `rohitg00/agentmemory` (23k★, +521 this week, coding-focused) | Short note: API surface, storage backend, MCP availability | 1h |
| 0.6 | Evaluate alternative C: **build minimal in-house memory layer** on existing Postgres + pgvector (Pantheon already has both) | One-page design: schema, retrieval interface, ~LOC estimate | 2h |
| 0.7 | Decision document: pick one of {adapt-claude-mem, langmem, agentmemory, in-house}, with trade-off table | `docs/MEMORY_LAYER_DECISION_2026-06-20.md` committed | 1h |

#### Exit criteria

- [ ] `.mcp.json` openmemory entry **NOT yet removed** — spike is read-only on production config
- [ ] `MEMORY_LAYER_DECISION_2026-06-20.md` committed with explicit choice + rationale
- [ ] Risk register updated with new memory-layer risk row
- [ ] If decision = adapt-claude-mem: Sprint 0.5 added before Sprint 1 (adaptation work, est. 1 week)
- [ ] If decision = langmem / in-house: lighter, can run in parallel with Sprint 1
- [ ] If decision = defer: openmemory stays as-is; risk accepted in writing; revisit after Sprint 3

#### Risk-first notes

- **Don't replace `.mcp.json` until decision is made** — current openmemory pointer is broken-but-known. Replacing with a broken-and-unknown is worse.
- **AGPL-3.0** on claude-mem: personal use is fine; if Pantheon ever serves external users (which Sprint 6 explicitly plans), legal review is needed before bundling.
- **Single-DB risk**: claude-mem stores all observations in one SQLite per install — incompatible with Pantheon's per-tenant isolation goal (Sprint 1).

---

### Sprint 1 — Auth & Multi-tenant Isolation (Week 1)
(unchanged from v4.0)

### Sprint 2 — Observability (Week 2)
(unchanged from v4.0)

### Sprint 3 — GCP Deployment (Week 3)
(unchanged from v4.0)

### Sprint 4 — Rate Limiting & SLA (Week 4)
(unchanged from v4.0)

### Sprint 5 — Disaster Recovery (Week 5)
(unchanged from v4.0)

### Sprint 6 — UI Polish & Beta Launch (Week 6)
(unchanged from v4.0)

---

## 5. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| LLM cost overrun (single tenant runs 1000 sessions/day) | Medium | High | Spend cap (Sprint 4) + Stripe-style usage alerts |
| GCP region outage during a session | Low | Medium | Multi-zone Cloud Run; orphan recovery already handles partial failure |
| Memorystore eviction during long debate | Low | Medium | Configure Redis with `maxmemory-policy noeviction` for session keys |
| OAuth refresh token rot for NotebookLM upload | Medium | Low | Service account + scheduled refresh script |
| Quota exhaustion across all 3 providers | Low | Critical | Already mitigated by `quota_fallback.py` + NVIDIA NIM free tier |
| 1M-context request blowing up cost | Medium | Medium | Pre-call token estimator + warn-then-block above tenant cap |
| **(NEW) Memory layer mismatch with Cloud Run** | **High** | **Medium** | **Sprint 0 spike; openmemory remains broken-but-stable until decision** |
| **(NEW) AGPL-3.0 on claude-mem affects future commercialization** | **Medium** | **Medium** | **Sprint 0 evaluates licensing; in-house option available** |

---

## 6. Open Questions for Stage 2

| Question | Owner | Decide By |
|----------|-------|-----------|
| Free tier vs. paid-only at beta launch | Vernon | Sprint 6 start |
| Domain name for production (`pantheon.app`? `pantheon.ai`?) | Vernon | Sprint 3 start |
| Pricing model: per-session, per-token, monthly subscription? | Vernon | Sprint 6 start |
| Self-host Grafana vs. use GCP Cloud Monitoring | Vernon | Sprint 2 start |
| Telegram bot in prod: shared tenant or per-user webhook? | Vernon | Sprint 1 end |
| **(NEW) Memory layer: claude-mem-adapted / langmem / in-house / defer?** | **Vernon + spike output** | **2026-06-20 (Sprint 0 end)** |

---

## 7. Definition of Done (Stage 2)

- [ ] **Sprint 0 decision document committed**
- [ ] All 6 sprints exit-criteria met
- [ ] `v1.0.0-beta` tag pushed
- [ ] 10 closed-beta users active
- [ ] SLA dashboard green for 7 consecutive days
- [ ] DR restore drill documented and re-tested
- [ ] Stage 3 (Eigent) decision gate held — proceed / skip / defer

---

## 8. Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v4.0 | 2026-05-03 | Sonnet 4.6 | Initial Stage 2 sprint plan — 6 weeks, GCP Cloud Run target, OAuth+API key auth, NextAuth frontend |
| v4.1 | 2026-06-18 | Opus 4.7 | Added Sprint 0 — Memory layer migration spike. openmemory inactive 78d; claude-mem architecturally incompatible with Cloud Run; decision gate before Sprint 1 |

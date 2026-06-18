---
title: Project Pantheon — Stage 2 Sprint Plan
version: v4.2
date: 2026-06-18
status: Active — Sprint 0 (Memory layer assessment) reframed; pre-Sprint-1 decision gate
parent_plan: PROJECT_PLAN_v3.4.md
supersedes: PROJECT_PLAN_v4.1.md
---

# Project Pantheon — Stage 2 Sprint Plan (Production-Grade Deployment)

> **Current file: `PROJECT_PLAN_v4.2.md`** — Sprint-level plan for Stage 2.

---

## 0. Change log v4.0 → v4.1 → v4.2

### v4.1 (retracted — wrong framing)
Treated `openmemory` as Pantheon's production memory layer. Code re-inspection on 2026-06-18 disproved this. v4.1 is preserved in git history but superseded.

### v4.2 — Corrected framing

After reading `agent/agent_factory.py`, `agent/agent_manager.py`, `db/postgres_utils.py`, `db/user_data.py`, `main.py`, and `telegram_adapter/telegram_bot.py`, the **real** memory architecture is:

```
Production runtime memory layer (already in place):
  langmem.create_manage_memory_tool          ─┐
  langgraph.store.postgres.AsyncPostgresStore  │
  langgraph.checkpoint.postgres.AsyncPostgresSaver
  Postgres + pgvector (vector_dims, embed_model from config)
  namespace = (str(user_id),)                ─┘ ← per-user namespace exists

Dev-time MCP only (not runtime):
  .mcp.json → openmemory @ localhost:8080/mcp  ← Claude Code dev helper

Real production risks found while re-inspecting:
  - main.py:233           hardcoded user_id="default_user" for the bootstrap agent
  - telegram_bot.py       user_id = str(update.effective_user.id) — Telegram-ID-as-tenant
  - db/user_data.py:27    clear_user_data has TODO for vector store + checkpoints cleanup
  - No tenants table; no enforced tenant_id boundary above user_id
```

**Sprint 0 reframed**: the question is **not** "replace openmemory with claude-mem". It is **"Should Pantheon keep and harden its existing Postgres-backed memory layer, or adopt a new one?"** — with hardening the strong default.

The `openmemory` entry in `.mcp.json` is a Claude-Code-dev convenience, not a production dependency. It can be cleaned up as a one-line config change after Sprint 0 closes, but it is **not** the Stage 2 risk.

---

## 1. Goals & Non-Goals

### Goals
1. Multi-tenant cloud service with per-tenant rate limits and isolation.
2. Auth — API key (server-to-server) + Google OAuth (browser).
3. Observability — Prometheus, Grafana, OpenTelemetry.
4. Performance — established SLAs.
5. DR — automated backups, runbook, restore drill.
6. UI — accounts, session history, share-by-link.
7. **(NEW) Memory layer hardened for tenant isolation, deletion, audit, backup, and migration semantics — before Sprint 3 deployment.**

### Non-Goals
(unchanged from v4.0)

---

## 2. Decisions Locked

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cloud target | GCP Cloud Run + Memorystore + Cloud SQL | (unchanged) |
| Auth | API Key (server) + Google OAuth (browser) | (unchanged) |
| Frontend | Next.js 14 + NextAuth | (unchanged) |
| Stage 3 (Eigent) | Deferred | (unchanged) |
| Memory layer baseline | **Existing: langmem + AsyncPostgresStore + AsyncPostgresSaver on Postgres + pgvector** | Confirmed by code re-inspection 2026-06-18 |
| Memory layer direction | **Keep & harden by default; alternatives only if Sprint 0 finds a blocking gap** | Migration cost is real; existing stack already covers vector + checkpoints + per-user namespace |

---

## 3. Reference Architecture
(unchanged from v4.0)

---

## 4. Sprint Breakdown

### Sprint 0 — Memory Layer Assessment & Tenantization Audit (2 days, 2026-06-19 → 2026-06-20) — **REFRAMED**

**Core question (singular)**: *Should Pantheon keep and harden its existing Postgres-backed memory layer, or adopt a new one?*

**Default answer going in**: keep & harden. Sprint 0 produces evidence to either confirm or overturn that default.

#### Step 1 — Current-state inventory (must be done first; ~2h)

Produce an authoritative table; commit as `docs/MEMORY_CURRENT_STATE_2026-06-19.md`. Required columns:

| Concern | Where it lives | Current behavior | Tenant-aware? | Notes |
|---------|----------------|------------------|---------------|-------|
| Dev MCP memory | `.mcp.json` `openmemory@localhost:8080/mcp` | Local dev MCP for Claude Code | N/A (dev only) | Not on the runtime path |
| Runtime memory store | `db/postgres_utils.py` `create_memory_store` → `AsyncPostgresStore` | pgvector-backed, `index={dims, embed}` | **Partial** — namespace `(user_id,)` set in `agent_factory.py:66` | Telegram `user_id` flows in via `telegram_bot.py` |
| Memory tool | `agent/agent_factory.py:137` `create_manage_memory_tool(namespace=namespace)` | langmem tool bound per-agent | Yes (via namespace closure) | Closure captures user_id at agent creation |
| Checkpoints | `db/postgres_utils.py` `AsyncPostgresSaver` | LangGraph checkpoints in Postgres | thread_id == user_id (`telegram_bot.py:187`) | Conflates session and tenant |
| Default agent at boot | `main.py:233` | `user_id="default_user"` hardcoded | **No** | Pre-tenant Telegram bootstrap |
| Delete path | `db/user_data.py` `clear_user_data` | Redis keys cleared; **TODO** for checkpoints + vector store | **No** | Explicit TODO at L27-31 |
| Tenant scope above user_id | (none) | Telegram user_id used directly as namespace | **No** | No `tenants` table yet (Sprint 1 adds it) |
| Backup/restore impact | Cloud SQL automated backups (Sprint 5) | Memory + checkpoints in same Postgres | Inherits | Single restore covers both |
| Export | (none) | No user export endpoint | **No** | Not in Stage 2 goals; flag for Stage 3 |
| Auditability | structlog JSON logs only | No audit table for memory writes | **No** | Sprint 2 OpenTelemetry can cover read/write spans |

#### Step 2 — Candidate evaluation (ranked, ~6h total)

**Candidates ranked from most-aligned to least, per existing architecture:**

| Rank | Option | What it means | Effort | License |
|------|--------|---------------|--------|---------|
| **A (default)** | **Keep & harden langmem + AsyncPostgresStore** | Complete `clear_user_data` TODO; replace `default_user` hardcoding; add tenant_id layer above user_id; add audit/export hooks | Low–Medium | MIT (langmem) |
| B | **Thin in-house wrapper on Postgres + pgvector** | Drop langmem; build minimal store API matching langmem's surface; full control over schema | Medium–High | Owned |
| C | Other external memory service (e.g. `rohitg00/agentmemory`) | New external dependency; coding-focused, less LangGraph-native | High | varies |
| D | claude-mem adapted | stdio MCP + local SQLite/Chroma + AGPL-3.0; would need HTTP shim + per-tenant DB partitioning; incompatible with Cloud Run model | High | AGPL-3.0 |

Per-candidate evaluation must produce answers to **all six production concerns** before being ranked:

| # | Production concern | Why it matters |
|---|--------------------|----------------|
| C1 | **Tenant isolation** | Sprint 1 introduces `tenants` table; memory must be filtered by tenant_id, not just user_id |
| C2 | **Delete / export semantics** | GDPR-style "delete my data" must remove vector embeddings + checkpoints atomically |
| C3 | **Backup / restore impact** | Sprint 5 DR drill must cover memory + checkpoints; can a restore leave them inconsistent? |
| C4 | **Migration cost from current Postgres-backed store** | Existing data must be either preserved or explicitly discarded; cost = hours + risk |
| C5 | **Auditability** | Read/write of memory needs structured logs or DB audit table for Sprint 2 / future compliance |
| C6 | **Cloud Run compatibility** | Stateless workers; no local filesystem assumptions; cold-start tolerance |

Any candidate failing C1, C2, or C6 is rejected by the framework, not by preference.

#### Step 3 — Decision document (~1h)

Commit `docs/MEMORY_LAYER_DECISION_2026-06-20.md` with:
- Inventory table from Step 1
- Per-candidate C1–C6 answers from Step 2
- Explicit choice + rationale
- If choice = A (default): a 5–10 task hardening checklist that feeds into Sprint 1
- If choice ≠ A: a migration plan (estimated effort, data preservation strategy, rollback plan)

#### Exit criteria

- [ ] `docs/MEMORY_CURRENT_STATE_2026-06-19.md` committed
- [ ] `docs/MEMORY_LAYER_DECISION_2026-06-20.md` committed
- [ ] All 4 candidates have completed C1–C6 answers (no "TBD" cells)
- [ ] Tenantization gaps explicitly enumerated (default_user, clear_user_data TODO, missing tenants table)
- [ ] `.mcp.json` openmemory entry: **no action yet** — handle as a 1-line cleanup after the decision lands, not before
- [ ] Risk register updated (memory hardening = Sprint 1; tenant isolation gap = Sprint 1)

---

### Sprint 1 — Auth, Multi-tenant Isolation, **and Memory Hardening** (Week 1)

Sprint 1 absorbs the memory-hardening checklist produced by Sprint 0 (assuming default choice A). Even under choices B/C/D, the tenant isolation work below remains valid.

| Task | Files | Owner Model |
|------|-------|------------|
| Add `users` + `api_keys` + `tenants` tables | `db/migrations/` | Sonnet 4.6 |
| Auth middleware (API key OR session cookie) | `api/middleware/auth.py` | Sonnet 4.6 |
| Per-tenant Redis namespace (`tenant:{id}:session:{sid}`) | `api/v1/sessions.py`, `core/redis_utils.py` | Sonnet 4.6 |
| **Replace `default_user` in main.py:233** | `main.py` | Sonnet 4.6 |
| **Promote memory namespace from `(user_id,)` to `(tenant_id, user_id)`** | `agent/agent_factory.py:66, 83, 137` | Sonnet 4.6 |
| **Complete `clear_user_data` TODO** — wipe checkpoints + vector store atomically | `db/user_data.py` | Sonnet 4.6 |
| **Cleanup `.mcp.json`** — remove dev-only `openmemory` entry; document dev MCP setup in README | `.mcp.json`, `README.md` | Haiku 4.5 |
| NextAuth Google provider | `frontend/pages/api/auth/[...nextauth].ts` | Sonnet 4.6 |
| Tests — tenant isolation + memory delete | `tests/test_auth.py`, `tests/test_tenant_isolation.py`, `tests/test_memory_delete.py` | Haiku 4.5 |

**Exit:** A second tenant cannot read another tenant's memories; `clear_user_data` actually clears everything; `default_user` is gone; `.mcp.json` only contains tools genuinely used.

---

### Sprints 2–6
(unchanged from v4.0)

---

## 5. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| LLM cost overrun | Medium | High | Spend cap (Sprint 4) |
| GCP region outage | Low | Medium | Multi-zone Cloud Run |
| Memorystore eviction | Low | Medium | `maxmemory-policy noeviction` |
| OAuth refresh token rot | Medium | Low | Service account |
| Quota exhaustion across providers | Low | Critical | `quota_fallback.py` + NIM free tier |
| 1M-context blowing up cost | Medium | Medium | Pre-call token estimator |
| **(NEW, replaces v4.1 entry) Existing memory layer is not fully tenant-aware — `default_user` hardcoding + namespace at user_id (not tenant_id) + incomplete `clear_user_data`** | **High** | **High** | **Sprint 0 inventory + Sprint 1 hardening tasks** |
| **(NEW) Sprint 0 may pick a non-default candidate, blowing up timeline** | Low | High | Default = keep & harden; framework rejects candidates failing C1/C2/C6 |
| ~~AGPL-3.0 on claude-mem~~ | — | — | Demoted: claude-mem is one of four candidates, not the default |

---

## 6. Open Questions for Stage 2

| Question | Owner | Decide By |
|----------|-------|-----------|
| Free tier vs. paid-only at beta launch | Vernon | Sprint 6 start |
| Domain name for production | Vernon | Sprint 3 start |
| Pricing model | Vernon | Sprint 6 start |
| Self-host Grafana vs. Cloud Monitoring | Vernon | Sprint 2 start |
| Telegram bot in prod: shared tenant or per-user webhook? | Vernon | Sprint 1 end |
| **Memory layer: keep & harden (default) vs. alternative?** | **Vernon + Sprint 0 evidence** | **2026-06-20** |
| **Should `thread_id == user_id` separation be revisited?** | **Vernon** | **Sprint 0 Step 1 inventory output** |

---

## 7. Definition of Done (Stage 2)

- [ ] Sprint 0 inventory + decision documents committed
- [ ] Sprint 1 memory-hardening tasks complete; `default_user` removed; namespace includes tenant_id; `clear_user_data` complete
- [ ] All 6 sprints exit-criteria met
- [ ] `v1.0.0-beta` tag pushed
- [ ] 10 closed-beta users active
- [ ] SLA dashboard green 7 consecutive days
- [ ] DR restore drill (covering memory + checkpoints) documented
- [ ] Stage 3 decision gate held

---

## 8. Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v4.0 | 2026-05-03 | Sonnet 4.6 | Initial Stage 2 sprint plan |
| v4.1 | 2026-06-18 | Opus 4.7 | (retracted — wrong framing: treated openmemory as production layer; superseded same day by v4.2 after code re-inspection) |
| v4.2 | 2026-06-18 | Opus 4.7 | Sprint 0 reframed: keep & harden existing langmem + AsyncPostgresStore by default; mandatory current-state inventory; C1–C6 production concerns must be answered by every candidate; Sprint 1 absorbs memory hardening tasks; risk register updated to surface real tenantization gap (default_user, namespace, clear_user_data TODO) |

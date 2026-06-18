---
title: Project Pantheon — Stage 2 Sprint Plan
version: v4.3
date: 2026-06-18
status: Active — Sprint 0 inventory must be evidence-backed; Sprint 1 absorbs hardening + migration
parent_plan: PROJECT_PLAN_v3.4.md
supersedes: PROJECT_PLAN_v4.2.md
---

# Project Pantheon — Stage 2 Sprint Plan (Production-Grade Deployment)

> **Current file: `PROJECT_PLAN_v4.3.md`** — Sprint-level plan for Stage 2.

---

## 0. Change log v4.2 → v4.3

Feedback-driven tightening. v4.2 framing stays; four operational gaps closed:

1. **Sprint 0 inventory** now requires `code_ref` + `verification_result` columns per row — no plan-quoting allowed; reviewer must have actually run the check.
2. **Namespace migration strategy** is now an explicit Sprint 1 sub-deliverable with a written backfill / dual-read plan, not a side-effect of code changes.
3. **`thread_id == user_id`** promoted from §6 Open Question to a concrete Sprint 0 Step 1.5 decision (with three named options) plus a Sprint 1 enforcement task if the answer is "separate them".
4. **claude-mem gating condition** stated explicitly: only evaluated deeply if option A fails C1/C2/C6 or exposes a blocking operational gap.

---

## 1. Goals & Non-Goals
(unchanged from v4.2)

---

## 2. Decisions Locked
(unchanged from v4.2)

---

## 3. Reference Architecture
(unchanged from v4.0)

---

## 4. Sprint Breakdown

### Sprint 0 — Memory Layer Assessment & Tenantization Audit (2 days, 2026-06-19 → 2026-06-20)

**Core question**: *Should Pantheon keep and harden its existing Postgres-backed memory layer, or adopt a new one?*

**Default**: keep & harden. Sprint 0 produces **evidence** to confirm or overturn.

---

#### Step 1 — Current-state inventory (~2h, evidence-backed)

Commit `docs/MEMORY_CURRENT_STATE_2026-06-19.md`. Each row **must** carry both columns; "TBD" or doc-only assertions are not accepted at exit.

| Concern | Current behavior | `code_ref` (file:line) | `verification_result` (what was actually run / observed) |
|---------|------------------|------------------------|----------------------------------------------------------|
| Dev MCP memory | `.mcp.json` openmemory@localhost:8080 | `.mcp.json` | `curl localhost:8080/mcp` while bot is running → confirm not used by runtime |
| Runtime memory store | `create_memory_store` → `AsyncPostgresStore` | `db/postgres_utils.py:45-91` | start bot locally; write a memory; `psql` query the store table |
| Memory tool binding | `create_manage_memory_tool(namespace=namespace)` | `agent/agent_factory.py:137` | trace one Telegram message; confirm tool called with expected namespace |
| Namespace shape | `(str(user_id),)` | `agent/agent_factory.py:66, 83` | two test users; assert isolation by reading store rows |
| Checkpoints | `AsyncPostgresSaver` | `db/postgres_utils.py:31`, `agent/agent_factory.py:60` | `psql` query `checkpoints` table; confirm thread_id column |
| `default_user` bootstrap | hardcoded at startup | `main.py:233` | grep result + confirm whether any prod path actually uses `default_agent` post-init |
| Delete path | clear_user_data TODO | `db/user_data.py:13-37` (TODO at L27-31) | invoke `/reset` in Telegram; `psql` query store + checkpoints to confirm what is/isn't deleted |
| Tenant scope above user_id | none | (no file) | grep `tenant` repo-wide; confirm absence |
| `thread_id == user_id` | session conflated with tenant | `telegram_adapter/telegram_bot.py:187, 194` | check what happens when same user starts a new chat session; do checkpoints accumulate? |
| Backup/restore impact | same Postgres as everything | Cloud SQL config (Sprint 5) | doc-only — verified during Sprint 5 drill |
| Export | none | (no file) | grep confirm no export endpoint |
| Auditability | structlog only | `core/*.py` log calls | doc-only — confirm no memory-write audit table |

**Exit rule**: every row in `verification_result` must reference either (a) a shell/SQL command run with output captured in the doc, or (b) an explicit "doc-only — to be verified in Sprint N" marker. No bare claims.

---

#### Step 1.5 — `thread_id == user_id` decision (~1h) — **PROMOTED FROM OPEN QUESTION**

`telegram_bot.py:187` invokes the agent with `configurable={"user_id": user_id, "thread_id": user_id}`. This conflates two distinct concerns:
- **user_id** = identity / tenant scope (long-lived)
- **thread_id** = LangGraph checkpoint scope (per conversation thread)

Choose one and commit it to `docs/MEMORY_LAYER_DECISION_2026-06-20.md` §Thread-vs-User:

| Option | Description | Trade-off |
|--------|-------------|-----------|
| T1 | Keep `thread_id == user_id` | Simplest; one continuous thread per user; checkpoints grow unbounded per user; "new conversation" impossible without `/reset` |
| T2 | `thread_id = f"{user_id}:{session_id}"` | Per-session threading; multiple conversations per user; requires session lifecycle (start, end, list) |
| T3 | `thread_id = chat_id` (Telegram chat-scoped) | Telegram-native; works for group chats; couples to Telegram and breaks if other adapters added |

**Default recommendation**: T2 — already aligns with the WebSocket session architecture in v4.0 §3.

If T2 or T3 is chosen, Sprint 1 gets an enforcement task: refactor `telegram_bot.py:187, 194` and any other adapter to pass the chosen thread_id shape.

---

#### Step 2 — Candidate evaluation (~6h)

Candidates ranked (unchanged from v4.2):

| Rank | Option | Effort | License |
|------|--------|--------|---------|
| **A (default)** | Keep & harden langmem + AsyncPostgresStore | Low–Medium | MIT |
| B | Thin in-house wrapper on Postgres + pgvector | Medium–High | Owned |
| C | External service (e.g. agentmemory) | High | varies |
| D | claude-mem adapted | High | AGPL-3.0 |

**Production concerns (C1–C6)** — every candidate must answer all six; failing C1, C2, or C6 → framework-rejected:

| # | Concern |
|---|---------|
| C1 | Tenant isolation (filter by tenant_id, not just user_id) |
| C2 | Delete / export semantics (vector + checkpoints atomic) |
| C3 | Backup / restore impact |
| C4 | Migration cost from current Postgres-backed store |
| C5 | Auditability (logs or audit table) |
| C6 | Cloud Run compatibility (stateless, no local FS) |

**Gating condition for option D (claude-mem)** — **NEW**:

> **D is evaluated in depth only if A fails C1, C2, or C6, or exposes a blocking operational gap discovered in Step 1.**
>
> Otherwise: a 1-paragraph note in the decision doc stating "D not pursued — A passed framework checks; D's stdio + local FS + AGPL profile makes adaptation cost-prohibitive."
>
> This is an explicit time-budget guard. Without it, candidate D will silently eat hours that should fund A's hardening checklist.

---

#### Step 3 — Decision document (~1h)

Commit `docs/MEMORY_LAYER_DECISION_2026-06-20.md` with:
- Inventory table from Step 1 (with `code_ref` + `verification_result`)
- Thread-vs-User decision from Step 1.5
- C1–C6 answers per surviving candidate (D may be 1-paragraph per gating rule)
- Explicit choice + rationale
- If A: hardening checklist → Sprint 1 (must include migration plan, see Sprint 1 below)
- If ≠ A: full migration plan with backfill, rollback, data-preservation strategy

#### Exit criteria

- [ ] Inventory doc committed; every row has `code_ref` + non-bare `verification_result`
- [ ] Step 1.5 decision committed (one of T1/T2/T3)
- [ ] All non-rejected candidates have full C1–C6 cells
- [ ] If A rejected: D's deep eval triggered; otherwise D = 1-paragraph note
- [ ] Tenantization gaps enumerated with code refs
- [ ] `.mcp.json` openmemory entry untouched (1-line cleanup deferred to Sprint 1)
- [ ] Risk register updated

---

### Sprint 1 — Auth, Multi-tenant Isolation, Memory Hardening, **and Namespace Migration** (Week 1)

| Task | Files | Notes |
|------|-------|-------|
| `users` + `api_keys` + `tenants` tables | `db/migrations/` | |
| Auth middleware | `api/middleware/auth.py` | |
| Per-tenant Redis namespace | `api/v1/sessions.py`, `core/redis_utils.py` | |
| Remove `default_user` hardcoding | `main.py:233` | |
| Promote namespace to `(tenant_id, user_id)` | `agent/agent_factory.py:66, 83, 137` | **paired with migration task below** |
| **Namespace migration strategy — NEW EXPLICIT TASK** | `db/migrations/`, `agent/agent_factory.py`, `docs/MEMORY_MIGRATION_PLAN.md` | See sub-tasks below |
| Complete `clear_user_data` TODO | `db/user_data.py:13-37` | atomic wipe: Redis + checkpoints + vector store |
| Apply Step 1.5 decision (if T2/T3) | `telegram_adapter/telegram_bot.py:187, 194` | refactor configurable.thread_id |
| Remove dev-only `.mcp.json` openmemory | `.mcp.json`, `README.md` | 1-line cleanup + README dev-MCP note |
| NextAuth Google provider | `frontend/pages/api/auth/[...nextauth].ts` | |
| Tests | `tests/test_auth.py`, `tests/test_tenant_isolation.py`, `tests/test_memory_delete.py`, `tests/test_namespace_migration.py` | |

---

#### Sprint 1 Sub-deliverable: Namespace Migration Strategy — **NEW**

Old namespace: `(str(user_id),)`. New namespace: `(tenant_id, user_id)`. The migration must be designed before code is written. Commit `docs/MEMORY_MIGRATION_PLAN.md` covering:

| Question | Required output |
|----------|-----------------|
| **What tenant_id do existing user_id rows belong to?** | Mapping rule. Likely: synthesize a default tenant per existing user (1:1), or assign all existing rows to a `legacy` tenant pending user→tenant assignment. Pick one; justify. |
| **Read strategy during migration window** | Dual-read: try `(tenant_id, user_id)` first, fall back to `(user_id,)`. Time-box the fallback (e.g. removed after Sprint 3). Document in code. |
| **Write strategy** | New writes always use `(tenant_id, user_id)`. No more writes to `(user_id,)`. |
| **Backfill plan** | One-shot migration script: copy/rewrite rows from `(user_id,)` namespace into `(tenant_id, user_id)`. Idempotent. Run during deploy. |
| **Rollback plan** | If backfill is wrong: keep old rows untouched until dual-read fallback is removed; rollback = revert code + re-enable fallback. |
| **Verification** | Pre/post row counts match. Spot-check 5 user IDs end-to-end. Tenant isolation test passes (one tenant cannot read another's memories). |
| **Checkpoints handling** | Apply same logic to `AsyncPostgresSaver` checkpoints if its thread_id format also changes (depends on Step 1.5 decision). |

**Exit rule**: namespace promotion code change cannot land before migration plan doc is committed and the backfill script is in `db/migrations/` with passing test.

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
| Quota exhaustion | Low | Critical | `quota_fallback.py` + NIM free tier |
| 1M-context cost blowup | Medium | Medium | Pre-call token estimator |
| Existing memory not fully tenant-aware (`default_user`, user-only namespace, `clear_user_data` TODO) | High | High | Sprint 0 inventory + Sprint 1 hardening |
| **(NEW) Namespace migration leaves old memories unreadable or causes cross-tenant leak** | **Medium** | **High** | **Mandatory `MEMORY_MIGRATION_PLAN.md` + backfill script + dual-read window + `test_namespace_migration.py` before code change lands** |
| **(NEW) `thread_id == user_id` blocks per-session features (multi-conversation, share-by-link)** | **Medium** | **Medium** | **Step 1.5 forces T1/T2/T3 decision; Sprint 1 enforces if not T1** |
| Sprint 0 may pick non-default candidate, blowing timeline | Low | High | Default = keep & harden; gating condition on candidate D; framework rejects C1/C2/C6 failures |

---

## 6. Open Questions for Stage 2

| Question | Owner | Decide By |
|----------|-------|-----------|
| Free tier vs. paid-only at beta launch | Vernon | Sprint 6 start |
| Domain name for production | Vernon | Sprint 3 start |
| Pricing model | Vernon | Sprint 6 start |
| Self-host Grafana vs. Cloud Monitoring | Vernon | Sprint 2 start |
| Telegram bot in prod: shared tenant or per-user webhook? | Vernon | Sprint 1 end |
| Memory layer: keep & harden vs. alternative? | Vernon + Sprint 0 | 2026-06-20 |
| ~~`thread_id == user_id` separation~~ | **Promoted to Sprint 0 Step 1.5 (T1/T2/T3 decision)** | **2026-06-20** |

---

## 7. Definition of Done (Stage 2)

- [ ] Sprint 0 inventory committed with `code_ref` + `verification_result` per row
- [ ] Sprint 0 Step 1.5 thread-vs-user decision committed
- [ ] Sprint 0 candidate D evaluation respects gating condition
- [ ] Sprint 1 `MEMORY_MIGRATION_PLAN.md` committed before namespace promotion lands
- [ ] Sprint 1 backfill script + `test_namespace_migration.py` passing
- [ ] All 6 sprints exit-criteria met
- [ ] `v1.0.0-beta` tag pushed
- [ ] 10 closed-beta users active
- [ ] SLA dashboard green 7 consecutive days
- [ ] DR restore drill (memory + checkpoints) documented
- [ ] Stage 3 decision gate held

---

## 8. Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v4.0 | 2026-05-03 | Sonnet 4.6 | Initial Stage 2 sprint plan |
| v4.1 | 2026-06-18 | Opus 4.7 | (retracted — wrong framing; superseded same day) |
| v4.2 | 2026-06-18 | Opus 4.7 | Sprint 0 reframed to "keep & harden by default"; C1–C6 production concerns mandatory; tenantization gap surfaced |
| v4.3 | 2026-06-18 | Opus 4.7 | Inventory rows require `code_ref` + `verification_result`; namespace migration strategy is explicit Sprint 1 sub-deliverable with backfill + dual-read + rollback; `thread_id == user_id` promoted from Open Question to Step 1.5 decision (T1/T2/T3); claude-mem gating condition stated (deep-eval only if A fails C1/C2/C6) |

---
title: Project Pantheon — Stage 2 Sprint Plan
version: v4.4
date: 2026-06-18
status: Active — final-form Sprint 0/1 hardening before merge
parent_plan: PROJECT_PLAN_v3.4.md
supersedes: PROJECT_PLAN_v4.3.md
---

# Project Pantheon — Stage 2 Sprint Plan (Production-Grade Deployment)

> **Current file: `PROJECT_PLAN_v4.4.md`** — Sprint-level plan for Stage 2.

---

## 0. Change log v4.3 → v4.4

Three operational tightenings on v4.3:

1. **`doc-only` rows in Sprint 0 inventory** now must also carry a `risk_if_unverified` column. No row can be both unverified and unrisked — the framework forces explicit acknowledgment of what we're choosing not to verify and what that costs.
2. **`thread_id` canonical rule** — if Step 1.5 picks T2 (or T3), Pantheon session layer is the **sole** producer of `thread_id`. Adapters (Telegram, Web UI, API) pass only source metadata; they may not synthesize `thread_id` themselves. Prevents Web/API adapter from re-forking the decision.
3. **Checkpoint migration** — promoted from an in-doc "depends on Step 1.5" footnote to a **conditional Sprint 1 task** (`SPRINT1-CKPT-MIG`) that activates automatically if Step 1.5 = T2 or T3. Treated as same-tier work as memory namespace migration.

---

## 1. Goals & Non-Goals
(unchanged from v4.2/v4.3)

---

## 2. Decisions Locked
(unchanged from v4.2/v4.3)

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

Commit `docs/MEMORY_CURRENT_STATE_2026-06-19.md`. **Every row must carry all three columns** — `code_ref`, `verification_result`, and `risk_if_unverified`. `verification_result` may be marked "doc-only — verify in Sprint N" only if `risk_if_unverified` is filled with a concrete consequence statement.

| Concern | `code_ref` | `verification_result` (cmd run + output, or "doc-only — verify in Sprint N") | `risk_if_unverified` (concrete consequence if we ship without verifying) |
|---------|-----------|------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Dev MCP memory | `.mcp.json` | `curl localhost:8080/mcp` while bot runs; confirm not called by runtime | — (verified) |
| Runtime memory store | `db/postgres_utils.py:45-91` | start bot; write memory; `psql` query store table | — (verified) |
| Memory tool binding | `agent/agent_factory.py:137` | trace one Telegram message; confirm tool called with expected namespace | — (verified) |
| Namespace shape | `agent/agent_factory.py:66, 83` | two test users; assert isolation by reading store rows | — (verified) |
| Checkpoints | `db/postgres_utils.py:31`, `agent/agent_factory.py:60` | `psql` query `checkpoints` table; confirm `thread_id` column | — (verified) |
| `default_user` bootstrap | `main.py:233` | grep + post-init usage trace | — (verified) |
| Delete path | `db/user_data.py:13-37` | invoke `/reset`; `psql` query store + checkpoints | — (verified) |
| Tenant scope above user_id | (no file) | grep `tenant` repo-wide; confirm absence | — (verified) |
| `thread_id == user_id` | `telegram_adapter/telegram_bot.py:187, 194` | trigger new chat session; check checkpoint accumulation | — (verified) |
| **Backup/restore impact** | Cloud SQL config (Sprint 5) | **doc-only — verify in Sprint 5 DR drill** | **If unverified at Sprint 1 merge: a restore may leave memory and checkpoints at different timestamps, producing an agent that "remembers" things its checkpointed conversation history never contained, or vice versa. User-facing inconsistency. Decision: ship with this risk; Sprint 5 drill is the gate before beta.** |
| Export | (no file) | grep confirm no export endpoint | — (verified absence; out of Stage 2 scope, flag for Stage 3) |
| **Auditability** | `core/*.py` log calls | **doc-only — verify in Sprint 2 OpenTelemetry rollout** | **If unverified at Sprint 1 merge: no way to forensically reconstruct who wrote/read which memory in the event of a data-leak claim or cross-tenant bug. Decision: structlog covers reads; Sprint 2 OTel spans cover writes; no DB audit table in Stage 2. Risk accepted in writing here.** |

**Exit rule**: any row with `verification_result = "doc-only"` and `risk_if_unverified = "—"` blocks Sprint 0 exit. Reviewer must either run the check or write the risk.

---

#### Step 1.5 — `thread_id == user_id` decision (~1h)

`telegram_bot.py:187` invokes the agent with `configurable={"user_id": user_id, "thread_id": user_id}`. This conflates two concerns:
- **user_id** = identity / tenant scope (long-lived)
- **thread_id** = LangGraph checkpoint scope (per conversation thread)

Choose one and commit to `docs/MEMORY_LAYER_DECISION_2026-06-20.md` §Thread-vs-User:

| Option | Description | Trade-off |
|--------|-------------|-----------|
| T1 | Keep `thread_id == user_id` | Simplest; one continuous thread per user; checkpoints grow unbounded per user; "new conversation" impossible without `/reset` |
| T2 | `thread_id = f"{user_id}:{session_id}"` | Per-session threading; multiple conversations per user; requires session lifecycle (start, end, list) |
| T3 | `thread_id = chat_id` (Telegram chat-scoped) | Telegram-native; works for group chats; couples to Telegram and breaks if other adapters added |

**Default recommendation**: T2 — aligns with WebSocket session architecture in v4.0 §3.

##### Canonical thread_id rule (applies if T2 or T3 selected) — **NEW in v4.4**

> **`thread_id` is generated exclusively by the Pantheon session layer (`api/v1/sessions.py` or equivalent). Adapters — Telegram, Web UI, future REST/SSE clients — pass only source metadata (`source="telegram"`, `source_user_id`, `source_chat_id`). They MUST NOT synthesize or override `thread_id`.**

Rationale: without this rule, the Web UI adapter in Sprint 6 (or any future adapter) can re-fork Step 1.5's decision into its own format, and the system ends up with multiple incompatible `thread_id` schemes coexisting. The session layer becomes the single point of authority.

Enforcement in Sprint 1: `telegram_bot.py:187, 194` is refactored to call the session layer; the session layer returns `thread_id`; the bot does not construct it. A unit test asserts the bot's invocation of `agent.ainvoke` carries a session-layer-derived `thread_id`.

---

#### Step 2 — Candidate evaluation (~6h)

Candidates and C1–C6 production concerns: unchanged from v4.3.

**Gating condition for option D (claude-mem)** — unchanged from v4.3:

> D is evaluated in depth only if A fails C1, C2, or C6, or exposes a blocking operational gap. Otherwise: 1-paragraph note in the decision doc.

---

#### Step 3 — Decision document (~1h)

Commit `docs/MEMORY_LAYER_DECISION_2026-06-20.md` with:
- Inventory table from Step 1 (all three columns filled per Exit rule)
- Step 1.5 decision (T1/T2/T3) **+ canonical thread_id rule** if T2/T3
- C1–C6 answers per surviving candidate
- Explicit choice + rationale
- If A: hardening checklist → Sprint 1, including migration plan and (conditional) checkpoint migration
- If ≠ A: full migration plan with backfill, rollback, data preservation

#### Exit criteria

- [ ] Inventory doc committed; every row has all three columns; no "doc-only + —" pairs
- [ ] Step 1.5 decision committed (T1/T2/T3); if T2/T3, canonical thread_id rule recorded
- [ ] Candidates: full C1–C6 unless D gated out, then 1-paragraph note
- [ ] Tenantization gaps enumerated with code refs
- [ ] `.mcp.json` openmemory entry: untouched (1-line cleanup in Sprint 1)
- [ ] Risk register updated

---

### Sprint 1 — Auth, Multi-tenant Isolation, Memory Hardening, Namespace Migration, **and Conditional Checkpoint Migration** (Week 1)

| Task ID | Task | Files | Conditional? |
|---------|------|-------|--------------|
| S1-AUTH-1 | `users` + `api_keys` + `tenants` tables | `db/migrations/` | — |
| S1-AUTH-2 | Auth middleware | `api/middleware/auth.py` | — |
| S1-AUTH-3 | Per-tenant Redis namespace | `api/v1/sessions.py`, `core/redis_utils.py` | — |
| S1-BOOT-1 | Remove `default_user` hardcoding | `main.py:233` | — |
| S1-NS-1 | Promote namespace to `(tenant_id, user_id)` | `agent/agent_factory.py:66, 83, 137` | — |
| S1-NS-MIG | Namespace migration plan + backfill script + dual-read | `db/migrations/`, `agent/agent_factory.py`, `docs/MEMORY_MIGRATION_PLAN.md` | — (gates S1-NS-1) |
| **SPRINT1-CKPT-MIG** | **Checkpoint thread_id migration** | **`db/migrations/`, `agent/agent_factory.py`, `docs/MEMORY_MIGRATION_PLAN.md` §Checkpoints** | **Conditional — activates if Step 1.5 = T2 or T3** |
| S1-DEL-1 | Complete `clear_user_data` TODO | `db/user_data.py:13-37` | — |
| S1-TID-1 | Apply Step 1.5 decision + canonical thread_id rule | `telegram_adapter/telegram_bot.py:187, 194`, `api/v1/sessions.py` | Conditional — only if T2 or T3 |
| S1-CLEAN-1 | Remove dev-only `.mcp.json` openmemory | `.mcp.json`, `README.md` | — |
| S1-UI-1 | NextAuth Google provider | `frontend/pages/api/auth/[...nextauth].ts` | — |
| S1-TEST-1 | Tests | `tests/test_auth.py`, `tests/test_tenant_isolation.py`, `tests/test_memory_delete.py`, `tests/test_namespace_migration.py` | — |
| S1-TEST-2 | Checkpoint migration test | `tests/test_checkpoint_migration.py` | Conditional — paired with SPRINT1-CKPT-MIG |
| S1-TEST-3 | thread_id canonical rule test | `tests/test_thread_id_canonical.py` | Conditional — paired with S1-TID-1 |

---

#### Sprint 1 Sub-deliverable A: Namespace Migration Strategy

`docs/MEMORY_MIGRATION_PLAN.md` §Memory must answer:

| Question | Required output |
|----------|-----------------|
| What tenant_id do existing `(user_id,)` rows belong to? | Mapping rule (default-tenant-per-user vs. legacy bucket) |
| Read strategy during migration window | Dual-read with time-boxed fallback (e.g. removed after Sprint 3) |
| Write strategy | All new writes use `(tenant_id, user_id)` |
| Backfill plan | Idempotent migration script in `db/migrations/` |
| Rollback plan | Revert code + re-enable fallback; old rows untouched |
| Verification | Pre/post row counts; 5 spot-checks; tenant isolation test |

**Exit rule**: S1-NS-1 cannot land before S1-NS-MIG plan + script + `test_namespace_migration.py` pass.

---

#### Sprint 1 Sub-deliverable B: Checkpoint Migration — **NEW in v4.4, conditional on Step 1.5**

`docs/MEMORY_MIGRATION_PLAN.md` §Checkpoints — **populated only if Step 1.5 = T2 or T3**.

| Question | Required output (if T2/T3) |
|----------|---------------------------|
| Old `thread_id` shape | `user_id` (string) |
| New `thread_id` shape | T2: `f"{user_id}:{session_id}"`; T3: `chat_id` |
| What to do with existing checkpoints? | Three sub-options to choose from in the doc: (a) **preserve as legacy thread** — rename to `f"{user_id}:legacy"` and orphan it from any session; users start fresh on next message; (b) **adopt to one synthetic session** — generate a `legacy_session` row, retag old checkpoints to it; (c) **discard** — drop old checkpoints; users lose continuity. Pick one; justify. |
| Read strategy during migration | Dual-read on `thread_id` similar to memory namespace; remove after Sprint 3 |
| Backfill plan | Migration script in `db/migrations/`; idempotent; logs row counts |
| Rollback plan | Same shape as memory: revert code + re-enable fallback |
| Verification | Pre/post checkpoint counts; spot-check that a known user's old thread is reachable under new shape (or explicitly retired per chosen sub-option) |

**Exit rule**: if conditional, SPRINT1-CKPT-MIG cannot land before S1-TID-1; both gate on `test_checkpoint_migration.py` + `test_thread_id_canonical.py` passing.

**Scope note**: checkpoint migration is **same-tier work** as memory namespace migration. Sprint 1 capacity must budget for both if Step 1.5 ≠ T1. If capacity is tight, Step 1.5 = T1 (keep `thread_id == user_id`) is a legitimate scope-reduction lever — but it must be made consciously, not by under-budgeting Sprint 1.

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
| Existing memory not fully tenant-aware | High | High | Sprint 0 inventory + Sprint 1 hardening |
| Namespace migration leaves old memories unreadable / cross-tenant leak | Medium | High | Mandatory `MEMORY_MIGRATION_PLAN.md` §Memory + backfill + dual-read + test |
| `thread_id == user_id` blocks per-session features | Medium | Medium | Step 1.5 forces T1/T2/T3; canonical thread_id rule prevents adapter forks |
| **(NEW) Checkpoint migration under-scoped if Step 1.5 = T2/T3** | **Medium** | **High** | **SPRINT1-CKPT-MIG conditional task in Sprint 1 table; same-tier as memory migration; `MEMORY_MIGRATION_PLAN.md` §Checkpoints mandatory; capacity check at Sprint 1 start** |
| **(NEW) Backup/restore + Auditability shipped unverified to Sprint 1 merge** | **Low** | **Medium** | **Inventory `risk_if_unverified` column records both as accepted risk; Sprint 5 DR drill is the gate for backup/restore; Sprint 2 OTel is the gate for write auditability** |
| Sprint 0 picks non-default candidate, blowing timeline | Low | High | Default = keep & harden; candidate D gating; framework rejects C1/C2/C6 failures |

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

---

## 7. Definition of Done (Stage 2)

- [ ] Sprint 0 inventory committed with `code_ref` + `verification_result` + `risk_if_unverified` per row; no "doc-only + —" pairs
- [ ] Step 1.5 thread-vs-user decision committed; canonical thread_id rule recorded if T2/T3
- [ ] Candidate D evaluation respects gating condition
- [ ] `MEMORY_MIGRATION_PLAN.md` §Memory committed; backfill + `test_namespace_migration.py` passing
- [ ] If Step 1.5 = T2/T3: `MEMORY_MIGRATION_PLAN.md` §Checkpoints committed; checkpoint backfill + `test_checkpoint_migration.py` + `test_thread_id_canonical.py` passing
- [ ] All 6 sprints exit-criteria met
- [ ] `v1.0.0-beta` tag pushed
- [ ] 10 closed-beta users active
- [ ] SLA dashboard green 7 consecutive days
- [ ] DR restore drill (memory + checkpoints, with row-count consistency verification) documented
- [ ] Stage 3 decision gate held

---

## 8. Version History

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| v4.0 | 2026-05-03 | Sonnet 4.6 | Initial Stage 2 sprint plan |
| v4.1 | 2026-06-18 | Opus 4.7 | (retracted — wrong framing) |
| v4.2 | 2026-06-18 | Opus 4.7 | (retracted — superseded by v4.3) |
| v4.3 | 2026-06-18 | Opus 4.7 | Evidence-backed inventory; namespace migration plan mandatory; thread_id Step 1.5; claude-mem gating |
| v4.4 | 2026-06-18 | Opus 4.7 | Inventory `risk_if_unverified` column mandatory; canonical thread_id rule (session layer is sole producer); checkpoint migration is conditional Sprint 1 task SPRINT1-CKPT-MIG, same-tier as memory migration |

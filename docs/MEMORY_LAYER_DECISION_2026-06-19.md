# Sprint 0 — Memory Layer Decision

**Date**: 2026-06-19
**Sprint**: Sprint 0 Step 3 (final decision)
**Parent**: `docs/PROJECT_PLAN_v4.4.md` §4 Sprint 0
**Companion**: `docs/MEMORY_CURRENT_STATE_2026-06-19.md`, `docs/MEMORY_MIGRATION_PLAN.md`

---

## Decision Summary

**Decision**: **Keep and harden Pantheon's existing Postgres-backed memory layer (Candidate A).**

We reviewed the current implementation and confirmed that Pantheon already runs on `langmem + AsyncPostgresStore + AsyncPostgresSaver + Postgres/pgvector`. The previously discussed `openmemory` path is dev-only and not part of the production runtime.

---

## Key findings (post 2026-06-20 verification)

**New findings from bot-run verification (Row 3 + Row 7 in Step 1 inventory):**

- **Memory write path is broken in current production** — `langmem.create_manage_memory_tool` is bound to the agent (`agent_factory.py:137`) and `store=` is passed correctly (L139), but `MEMORY_SYSTEM_PROMPT` lacks instruction telling the LLM **when** to call the tool. Result: even an explicit "remember X" message produces 0 store rows. This is a Sprint 1 must-fix (S1-MEM-1) — without it, namespace migration is migrating nothing.
- **Delete happy-path partially verified, atomicity unverifiable until write path is fixed** — `clear_user_data` correctly empties `checkpoints` (6→0). `store` and `store_vectors` could not be exercised because Row 3 defect left them empty. Full atomicity test deferred until after S1-MEM-1.
- **This sequencing changes Sprint 1 ordering**: S1-MEM-1 must land **before** S1-NS-MIG (namespace migration), otherwise the migration scripts run against empty tables. The migration plan in `MEMORY_MIGRATION_PLAN.md` §Memory is structurally correct but the data backfill section currently assumes existing rows to copy — adjust expectation: there may be very few/no rows to migrate at the moment.

**Original key findings (from inventory):**

## Key findings (from `MEMORY_CURRENT_STATE_2026-06-19.md`)

- **`default_user` fallback is live code, not dead code** — confirmed reachable via `telegram_bot.py:191-195`. This is a real latent cross-tenant memory leak risk, no longer theoretical.
- **`thread_id == user_id` is currently conflated** (`telegram_bot.py:187, 194`) — confirmed via Row 9 trace: 3 turns under one `thread_id`, checkpoints grow as a single linear chain.
- **No tenant layer exists above `user_id`** — verified absent across the Python codebase.
- **Current delete path (`clear_user_data`) is implemented, not TODO** — v4.4 baseline was inaccurate on this point. Atomic behavior across `checkpoints`, `store`, `store_vectors`, and the langgraph `store.adelete(...)` call still needs live verification (Row 7, pending bot run).
- **Backup/restore and write-side auditability remain deferred and risk-accepted per v4.4** — issues #20 attaches owners to Sprint 5 (DR) and Sprint 2 (OTel write spans).

### Plan baseline corrections discovered during Step 1

These three items in v4.4 are inaccurate enough to track explicitly. They don't change the decision but should be noted before Sprint 1 kickoff:

1. `clear_user_data` is **implemented** (`db/user_data.py:13-99`), not a pure TODO. The stale "TODO" comment at L27-31 is a planning remnant. Sprint 1 task S1-DEL-1 reframes from "implement TODO" to "verify atomicity + tenant scope".
2. `default_user` is a **production fallback path**, not just a startup shim. Removal is must-fix-before-multi-tenant, not a nice-to-have cleanup.
3. The delete path has **two code branches** — raw SQL (L43-80) and langgraph store API (L91 `store.adelete`). Verification must confirm both run, not just one.

---

## Step 1.5 — Thread-vs-User decision

**Choose T2**: `thread_id = f"{user_id}:{session_id}"`

This restores proper per-session checkpoint boundaries while keeping `user_id` as the long-lived identity for memory namespace purposes.

### Evidence supporting T2 (over T1 and T3)

| Source | Finding |
|--------|---------|
| Row 9 verification | `thread_id == user_id` conflation confirmed empirically. Checkpoints accumulate unbounded under a single thread per user — "new conversation" is impossible without `/reset`. T1 ("keep conflated") would ship this design defect to beta. |
| v4.0 §3 architecture | WebSocket session model already assumes session-scoped state. T2 aligns; T1/T3 do not. |
| Stage 2 Goal #6 | "Share-by-link, session history" requires identifiable sessions. T1 makes this impossible; T3 (Telegram chat_id) couples to one adapter. |
| Issue #21 | Canonical thread_id rule requires session layer as sole producer. T2 is the only option where the session layer has something meaningful to produce. |

### Canonical thread_id rule (locked)

> **`thread_id` is generated exclusively by the Pantheon session layer (single authority module — issue #21 will collapse "`api/v1/sessions.py` or equivalent" into one). Adapters (Telegram, future Web UI, future REST/SSE) pass only source metadata. They MUST NOT synthesize or override `thread_id`.**

Enforcement: Sprint 1 task S1-TID-1 refactors `telegram_bot.py:187, 194` to call the session layer. `tests/test_thread_id_canonical.py` asserts no adapter constructs `thread_id` independently.

---

## Step 2 — Candidate evaluation

C1–C6 production concerns per v4.4 §Sprint 0 Step 2:

| # | Concern |
|---|---------|
| C1 | Tenant isolation |
| C2 | Delete / export semantics |
| C3 | Backup / restore impact |
| C4 | Migration cost |
| C5 | Auditability |
| C6 | Cloud Run compatibility |

### Candidate A — Keep & harden langmem + AsyncPostgresStore (**SELECTED**)

| # | Status | Notes |
|---|--------|-------|
| C1 | **Pass with hardening** | Per-user namespace exists today (`(user_id,)`); promote to `(tenant_id, user_id)` and remove `default_user` fallback. Sprint 1 work. |
| C2 | **⚠️ Bugs found — fix required (S1-DEL-1)** | Row 7 verified 2026-06-20 with non-empty store (3 rows pre-reset). Two bugs exposed: **Bug 1** — `store` DELETE is rolled back silently because `store_vectors` DELETE in the same psycopg3 transaction fails (`relation "store_vectors" does not exist` when `EMBED_MODEL=none`); store rows 3→3 post-reset. **Bug 2** — `checkpoint_writes` not deleted (only `checkpoints` targeted at L43-48); 13 orphaned `checkpoint_writes` rows remain post-reset and cause `INVALID_CHAT_HISTORY` on next session. Fix must split the `store`/`store_vectors` transaction and add `DELETE FROM checkpoint_writes WHERE thread_id = %s`. Blocks S1-NS-1 merge until resolved. |
| C3 | **Pass — deferred** | Single Postgres for memory + checkpoints; Sprint 5 DR drill verifies row-count consistency across `store` / `store_vectors` / `checkpoints` after restore (issue #20). |
| C4 | **Pass — bounded** | Stays on current stack. Only namespace shape changes; backfill plan in `MEMORY_MIGRATION_PLAN.md`. Conditional checkpoint migration if T2 implemented (which it will be). |
| C5 | **Partial — accepted** | Read-side: structlog at `agent_factory.py:80, 85, 95`. Write-side: not currently logged; Sprint 2 OTel write spans cover this (issue #20). |
| C6 | **Pass** | Stateless workers + Postgres backend. Already Cloud-Run-ready architecturally. |

**Effort**: Low–Medium. License: MIT (langmem). No new external dependencies.

### Candidate B — Thin in-house wrapper on Postgres + pgvector

| # | Status | Notes |
|---|--------|-------|
| C1 | Pass | Designed in from day 1 |
| C2 | Pass | Explicit atomic API |
| C3 | Pass | Same backend as A |
| C4 | **Worse than A** | Replacing langmem's interface costs more than hardening it; throws away existing test coverage |
| C5 | Pass | Audit hooks easy to add |
| C6 | Pass | Same backend as A |

**Verdict**: Possible, but unnecessary now. Reconsider only if langmem's interface becomes a blocker at scale. **Not selected.**

### Candidate C — External memory service (e.g. `rohitg00/agentmemory`)

| # | Status | Notes |
|---|--------|-------|
| C1 | Depends on service | Each external service has its own tenancy model; needs case-by-case eval |
| C2 | Depends on service | Two-system delete consistency is hard; risk of stale shadows |
| C3 | **Fail (additional system)** | New service = new backup surface; data sovereignty boundary moves |
| C4 | **High** | New SDK, new failure modes, dual-write window during migration |
| C5 | Depends on service | External logs sit outside Pantheon's observability stack |
| C6 | Depends on service | Most are designed for local/dev; few are Cloud-Run-native at this stage |

**Verdict**: Higher integration cost, no clear gain over A. **Not selected.**

### Candidate D — claude-mem adapted

Per the v4.4 Sprint 0 gating rule, candidate D is evaluated in depth **only if** option A fails C1, C2, or C6, or reveals a blocking operational gap during Step 1.

That did not occur. Current evidence supports A as viable, with hardening work required but no framework-level failure on tenant isolation, delete semantics, or Cloud Run compatibility.

Therefore D was **not pursued further in Sprint 0**. This is intentional, not an omission. A deeper claude-mem assessment would consume time without changing the current decision path, while also starting from a poorer architectural fit (`stdio` MCP transport, local filesystem assumptions for the worker, AGPL-3.0 constraints if Pantheon ever ships externally) than the existing Postgres-backed runtime.

**Not selected.**

---

## What Sprint 1 must do

Hardening checklist derived from Sprint 0 findings — feeds into Sprint 1 task table in `PROJECT_PLAN_v4.4.md` §Sprint 1.

| Priority | Task | Existing Sprint 1 ID | Reason |
|----------|------|---------------------|-------|
| **🔴 Must-fix** | Remove `default_user` fallback | S1-BOOT-1 | Row 6 confirmed live code = active cross-tenant leak risk |
| **🔴 Must-fix** | Promote namespace `(user_id,)` → `(tenant_id, user_id)` | S1-NS-1, S1-NS-MIG | C1 hardening; gated on migration plan + test |
| **🔴 Must-fix** | Implement T2 thread_id (session-layer-produced) | S1-TID-1 (conditional → unconditional now), S1-TEST-3 | Step 1.5 locked T2 |
| **🔴 Must-fix** | Checkpoint thread_id migration | SPRINT1-CKPT-MIG (conditional → unconditional now), S1-TEST-2 | T2 chosen → conditional task activates |
| 🟠 High | Verify `clear_user_data` atomicity (raw SQL + `store.adelete`) | S1-DEL-1 (scope shift: verify, not implement) | Plan baseline correction |
| 🟠 High | Add `tenants` + `users` + `api_keys` tables | S1-AUTH-1 | Foundation for tenant_id namespace |
| 🟠 High | Auth middleware + Redis tenant namespace | S1-AUTH-2, S1-AUTH-3 | Multi-tenant baseline |
| 🟠 High | Collapse session layer into single authority module | (issue #21) | Canonical thread_id rule precondition |
| 🟡 Medium | Remove `.mcp.json` openmemory entry | S1-CLEAN-1 | 1-line cleanup |
| 🟡 Medium | NextAuth Google provider | S1-UI-1 | Stage 2 auth goal |

### Capacity note (links to issue #22)

T2 is now confirmed, not tentative. This means SPRINT1-CKPT-MIG is **unconditional**, not conditional. Sprint 1 kickoff MUST re-check capacity per issue #22 — the three legitimate scope cuts (split into 1a/1b, defer Google OAuth, etc.) remain on the table.

---

## Verification status (post bot run 2026-06-20, commit 8f2405c)

| Row | Item | Status | Sprint 1 implication |
|-----|------|--------|---------------------|
| Row 3 | Memory tool write path | ✅ **Fixed (S1-MEM-1)** — `MEMORY_SYSTEM_PROMPT` rewritten; store write confirmed in prod (commit 39f2752). | S1-MEM-2 next: resolve embedding provider (Google quota). |
| Row 7 | `clear_user_data` atomic delete | ⚠️ **Bugs found** — re-run 2026-06-20 with store=3 pre-reset. Bug 1: store DELETE rolled back (store_vectors same-transaction failure). Bug 2: checkpoint_writes not deleted. Post-reset: store 3→3, checkpoint_writes 13→13, checkpoints 6→0. | **S1-DEL-1**: split store/store_vectors transaction; add `DELETE FROM checkpoint_writes`. Blocks S1-NS-1 merge. |
| Row 4 | Second-account isolation | doc-only — single account | Verify when second test account available. Not blocking. |
| Row 10 | Backup/restore | doc-only — deferred | Sprint 5 DR drill (issue #20) |
| Row 12 | Auditability | doc-only — deferred | Sprint 2 OTel write spans (issue #20) |

---

## Bottom line

Stage 2 should not replace the memory layer right now. The correct move is to **harden the current implementation** for tenant safety, session correctness, and migration safety. `claude-mem` and other external candidates remain available as fallbacks if hardening surfaces a blocker, but A is the working assumption going into Sprint 1.

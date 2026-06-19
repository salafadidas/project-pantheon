# Memory Migration Plan — Direction (Sprint 0 deliverable)

**Date**: 2026-06-20
**Status**: Direction-only skeleton — Sprint 0 sets direction; Sprint 1 owner produces the executable plan (backfill SQL, dual-read code, tests).
**Parent**: `docs/PROJECT_PLAN_v4.4.md` §Sprint 1 Sub-deliverable A + B
**Companion**: `docs/MEMORY_LAYER_DECISION_2026-06-20.md`

---

## Why this is a skeleton, not the full plan

v4.4 puts the migration plan inside Sprint 1's exit rule:

> S1-NS-1 cannot land before S1-NS-MIG plan + script + `test_namespace_migration.py` pass.

The full migration plan needs to be written by whoever holds Sprint 1, not pre-baked by Sprint 0. This document **sets direction** so Sprint 1 kickoff doesn't start from a blank page, but leaves the executable detail (SQL, code, tests) to the implementer who will own it.

The full document should land in Sprint 1 with both §Memory and §Checkpoints sections populated before any namespace code change merges.

---

## §Memory — namespace `(user_id,)` → `(tenant_id, user_id)`

### Direction

| Question | Sprint 0 direction (Sprint 1 makes binding) |
|----------|---------------------------------------------|
| **Tenant assignment for existing rows** | **Default tenant per existing user** (1:1 synthesis). Justification: simpler than a "legacy" bucket; preserves all existing user-scoped memories without ambiguity; aligns with Sprint 1 introducing `tenants` table where each existing user gets exactly one tenant_id at migration time. |
| **Read strategy during migration window** | **Dual-read** with `(tenant_id, user_id)` preferred, `(user_id,)` fallback. Time-box fallback removal to end of Sprint 3. |
| **Write strategy** | All new writes use `(tenant_id, user_id)`. No new writes to legacy shape. |
| **Backfill plan** | Idempotent migration script in `db/migrations/`. Rewrites `store` and `store_vectors` rows from `(user_id,)` namespace to `(tenant_id, user_id)`. Logs row counts pre/post. |
| **Rollback plan** | Old rows untouched until end-of-Sprint-3 cleanup. Rollback = revert code (re-enable fallback). Old rows remain accessible via legacy path. |
| **Verification** | Pre/post row counts match. Spot-check 5 user_ids end-to-end (write under new shape, read returns previous memories). Tenant isolation test (`tests/test_namespace_migration.py`) confirms tenant A cannot read tenant B's namespace. |

### Open detail for Sprint 1 to resolve

- Exact SQL form depending on `prefix` column type (Row 2 verified `prefix TEXT`, so query is straightforward `LIKE` — not array/JSONB)
- How `tenants` table primary key relates to existing user_ids (UUID? auto-increment?)
- Whether dual-read is implemented in langmem wrapper or in `agent_factory.py` closure

---

## §Checkpoints — `thread_id = user_id` → `thread_id = f"{user_id}:{session_id}"`

### Direction (T2 confirmed by Step 1.5; this section is unconditional)

| Question | Sprint 0 direction |
|----------|-------------------|
| **Old `thread_id` shape** | `user_id` (string, equals Telegram numeric user_id) |
| **New `thread_id` shape** | `f"{user_id}:{session_id}"` |
| **What to do with existing checkpoints?** | **Preserve as legacy thread** — rename existing rows to `f"{user_id}:legacy"`. Orphan them from any active session; reachable only via explicit "show legacy history" path (not in Stage 2 UI). Justification: discards nothing, but doesn't pollute fresh-session UX. Alternative "adopt to one synthetic session" rejected because it implies a synthetic session lifecycle (start, end timestamps) that doesn't actually exist. Alternative "discard" rejected because user-facing data loss without recovery option. |
| **Read strategy during migration** | Dual-read on `thread_id` similar to namespace. Live sessions use new shape; legacy fallback for explicit history queries. Remove fallback at end of Sprint 3. |
| **Backfill plan** | One-shot rename `UPDATE checkpoints SET thread_id = thread_id \|\| ':legacy' WHERE thread_id NOT LIKE '%:%'`. Idempotent. Logs counts. |
| **Rollback plan** | Reverse rename: `UPDATE checkpoints SET thread_id = SUBSTRING(thread_id FROM 1 FOR POSITION(':' IN thread_id) - 1) WHERE thread_id LIKE '%:legacy'`. Code revert + redeploy. |
| **Verification** | Pre/post checkpoint counts match (only renamed, none lost). `tests/test_checkpoint_migration.py` confirms a known user's old thread is reachable under `f"{user_id}:legacy"`. `tests/test_thread_id_canonical.py` confirms adapters call session layer. |

### Open detail for Sprint 1 to resolve

- Where session_id is generated (almost certainly in the collapsed session-layer authority module — issue #21)
- Whether legacy threads are exposed in Sprint 2 UI or hidden until Stage 3
- Lifecycle of session_id: per-message session? Per-conversation? Timeout-based?

---

## What Sprint 1 owner must do before merging any namespace/thread_id code change

1. Expand both §Memory and §Checkpoints with executable SQL + Python interface
2. Land `db/migrations/<timestamp>_namespace_migration.py` with idempotency test
3. Land `db/migrations/<timestamp>_checkpoint_thread_id_migration.py`
4. Land `tests/test_namespace_migration.py` + `tests/test_checkpoint_migration.py` + `tests/test_thread_id_canonical.py`
5. Verify pre-merge: row counts, isolation test, rollback dry-run
6. Update this document's status header from "Direction-only skeleton" to "Executable plan, Sprint 1 owner: <name>, merged: <commit-sha>"

---

## What is intentionally NOT in this skeleton

- Concrete SQL (depends on Sprint 1 schema decisions for `tenants` table)
- Python code samples (depends on whether dual-read lives in langmem wrapper or `agent_factory.py`)
- Test fixtures (Sprint 1 owner picks the test pattern that matches existing test suite)
- Cutover timing (Sprint 1 owner chooses deploy window)

These belong in the executable plan, not the direction skeleton. Sprint 0 deliberately stops here to avoid pre-baking decisions that should sit with the implementer.

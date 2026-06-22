# Memory Migration Plan

**Date**: 2026-06-22
**Sprint**: Sprint 1
**Status**: Executable plan — owner: Sprint 1, merged: pending
**Parent**: `docs/PROJECT_PLAN_v4.4.md`
**Related**:
- `docs/MEMORY_LAYER_DECISION_2026-06-19.md`
- `docs/MEMORY_CURRENT_STATE_2026-06-19.md`

---

## 1. Scope

This migration plan covers the transition from the current single-dimension user-scoped memory model to a tenant-aware memory model.

### In scope
- Memory namespace migration:
  - old: `(user_id,)`
  - new: `(tenant_id, user_id)`
- Dual-read support during migration window
- Backfill of existing memory rows
- Rollback strategy
- Verification strategy

### Conditionally in scope
Step 1.5 decision is **T2** — checkpoint migration is therefore unconditional and fully covered in §8.
- old `thread_id`: `user_id`
- new `thread_id`: `f"{user_id}:{session_id}"`

### Out of scope
- Export endpoint
- Long-term tenant merge / reassignment flows
- Multi-user-per-tenant product workflows beyond the initial mapping rule
- Audit-table design beyond current Sprint 1 scope

---

## 2. Mapping Rule

### Default mapping rule
For all existing rows, use the following migration rule:

- each existing `telegram_user_id` maps to one synthesized tenant
- initial rule: **1 user = 1 tenant**

This is the safest default because it preserves current effective isolation semantics while introducing a tenant layer required by Stage 2.

### Rationale
- current system has no tenant model above `user_id`
- current production-like behavior is already effectively per-user
- forcing multi-user tenant grouping during Sprint 1 would add ambiguity and migration risk

### Future note
If future product requirements need multiple users under one tenant, that should be handled by a later reassignment / merge process, not by Sprint 1 migration.

---

## 3. Read Strategy

During the migration window, runtime reads must use dual-read logic.

### Read order
1. Try new namespace: `(tenant_id, user_id)`
2. If not found, fall back to old namespace: `(user_id,)`

### Sunset rule
Dual-read is temporary and must be removed after the migration window closes.

### Proposed fallback window
- enabled in Sprint 1
- retained through Sprint 2
- removed after Sprint 3, once backfill verification is complete

### Rationale
This prevents old memories from becoming unreadable immediately after the namespace promotion lands.

---

## 4. Write Strategy

Once namespace promotion code lands:

- all new writes must go only to `(tenant_id, user_id)`
- no new writes may go to `(user_id,)`

### Rationale
If old namespace writes remain enabled, the system never exits migration mode and data consistency becomes unboundedly harder.

---

## 5. Backfill Plan

### Objective
Move existing memory rows from old namespace `(user_id,)` to new namespace `(tenant_id, user_id)` without breaking reads.

### Requirements
- backfill script must be idempotent
- script must live under `db/migrations/`
- script must log pre/post row counts
- old rows remain intact during fallback window

### Backfill approach
1. Read existing rows under old namespace `(user_id,)`
2. Resolve synthesized tenant for that `user_id`
3. Write corresponding rows into new namespace `(tenant_id, user_id)`
4. Skip or safely upsert rows already migrated
5. Emit row-count summary

### Data preservation rule
Old rows are not immediately deleted. They remain available during the dual-read window.

---

## 6. Rollback Plan

If namespace migration causes regressions:

1. revert runtime code to old read/write behavior
2. keep dual-read fallback enabled
3. leave old rows intact
4. ignore or quarantine newly written migrated rows if needed
5. re-run verification before attempting migration again

### Rollback principle
Rollback must not depend on reconstructing deleted old rows. Therefore old rows must remain untouched until fallback removal is explicitly approved.

---

## 7. Verification

The migration is not complete until the following checks pass.

### Required checks
- pre/post row counts match expectations
- 5-user spot check passes end-to-end
- tenant isolation test passes
- old data remains readable during fallback window
- new writes land only in new namespace
- no new rows are written to old namespace after cutover

### Suggested verification artifacts
- SQL row-count snapshots before migration
- SQL row-count snapshots after migration
- application-level read test for migrated users
- regression test for dual-read behavior
- regression test for "new write goes only to new namespace"

---

## 8. Checkpoint Migration

This section is required because Step 1.5 selected **T2**.

### Old shape
- `thread_id = user_id`

### New shape
- `thread_id = f"{user_id}:{session_id}"`

### Selected preservation strategy
**Preserve as legacy thread**

Existing checkpoints will not be discarded and will not be force-fit into a synthetic live session.
Instead, all pre-migration checkpoints for a given user will be preserved under a legacy thread:

- old: `thread_id = user_id`
- new legacy form: `thread_id = f"{user_id}:legacy"`

### Rationale
This approach preserves historical checkpoint continuity without inventing artificial session semantics for old conversations. It is safer than discard, and simpler than synthesizing a legacy session object for every prior user.

New conversations after migration will always use session-scoped thread IDs:
- `thread_id = f"{user_id}:{session_id}"`

---

### Backfill rule

For each existing checkpoint row whose `thread_id = user_id`, rewrite it to:

- `thread_id = f"{user_id}:legacy"`

The same rule must be applied consistently to all checkpoint-related tables that key by `thread_id`, including:
- `checkpoints`
- `checkpoint_writes`
- any other LangGraph checkpoint tables that require thread-level consistency

Backfill must be:
- idempotent
- row-count logged
- safe to rerun

### SQL direction

```sql
UPDATE checkpoints
SET thread_id = thread_id || ':legacy'
WHERE thread_id NOT LIKE '%:%';

-- Apply equivalent update to checkpoint_writes
UPDATE checkpoint_writes
SET thread_id = thread_id || ':legacy'
WHERE thread_id NOT LIKE '%:%';
```

Both updates are idempotent: the `NOT LIKE '%:%'` guard prevents double-suffixing on rerun.

---

### Compatibility window

During the migration compatibility window:

1. all new writes use the new T2 format: `f"{user_id}:{session_id}"`
2. legacy checkpoint chains remain readable via: `f"{user_id}:legacy"`
3. old raw `thread_id = user_id` must not remain active after backfill completes

This compatibility window aligns with the namespace migration dual-read window:
- enabled in Sprint 1
- retained through Sprint 2
- removed after Sprint 3 once migration verification is complete

---

### Rollback rule

If checkpoint migration causes regressions:

1. revert runtime code that assumes T2-only thread shape
2. keep legacy checkpoint rows intact
3. restore compatibility reads if needed
4. do not delete legacy rows during rollback window

Rollback does not require reconstructing deleted old rows, because old checkpoints are preserved under the `:legacy` suffix rather than destroyed.

---

### Verification plan

Checkpoint migration is complete only when all of the following pass:

- pre/post `checkpoints` row counts match
- pre/post `checkpoint_writes` row counts match
- spot-check at least 5 users:
  - old checkpoint chain is reachable under `f"{user_id}:legacy"`
  - new session writes land under `f"{user_id}:{session_id}"`
- no new writes occur under raw `thread_id = user_id`
- application-level regression test confirms canonical thread_id generation
- checkpoint migration test confirms legacy preservation works as designed

### Required verification artifacts

- SQL row counts before migration
- SQL row counts after migration
- sample query showing a migrated `:legacy` thread
- sample query showing a newly created session-scoped thread
- passing `tests/test_checkpoint_migration.py`
- passing `tests/test_thread_id_canonical.py`

---

### Exit rule

Checkpoint migration cannot be considered complete until:

- legacy backfill has run
- compatibility reads work
- new session-scoped thread IDs are in use
- no raw `thread_id = user_id` writes remain
- migration tests pass

---

## 9. Exit Criteria

This migration plan is considered executable only when all sections below are confirmed fixed:

| Section | Status |
|---------|--------|
| Mapping rule (§2) | ✅ fixed — 1 user = 1 tenant |
| Dual-read strategy (§3) | ✅ fixed — new preferred, old fallback, sunset Sprint 3 |
| Write strategy (§4) | ✅ fixed — new namespace only after cutover |
| Rollback principle (§6) | ✅ fixed — old rows untouched until fallback removal approved |
| Backfill script approach (§5) | ✅ fixed — idempotent, logged, under `db/migrations/` |
| Verification checklist (§7) | ✅ fixed — row counts + 5-user spot check + isolation test |
| Checkpoint migration (§8) | ✅ fixed — preserve as `:legacy`, backfill SQL defined, rollback and verification specified |

**All exit criteria met. This plan is ready for implementation (S1-NS-1).**

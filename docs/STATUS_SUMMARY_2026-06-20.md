---
title: Project Pantheon — Status Summary
date: 2026-06-20
sprint: Sprint 0 closed → Sprint 1 in progress
branch: claude/remote-control-Q2YAQ (S1-MEM-1 PR)
---

# Project Pantheon — Status Summary (2026-06-20)

## 整體進度

| 階段 | 狀態 | 說明 |
|------|------|------|
| Sprint 0 — Memory Layer Assessment | ✅ Closed | Issue #23; decision doc + migration skeleton committed |
| Sprint 1 capacity decision | ✅ Resolved | Issue #22; keep T2, defer OAuth → Sprint 6, 1-week timeline preserved |
| **S1-MEM-1** — Memory tool prompt fix + format hardening + store setup fix | ✅ **Today** | PR pending (this branch) |
| S1-MEM-2 — Retrieval quality / embedding | 🔜 Queued | Blocked on embedding provider decision |
| S1-DEL-1, S1-BOOT-1, S1-AUTH-1/2/3, S1-NS-MIG, S1-NS-1, S1-TID-1, SPRINT1-CKPT-MIG, S1-CLEAN-1, #21 | 🔜 Sprint 1 remainder | 1-week timeline |

---

## Sprint 0 closure recap

### Step 1 — Current-state inventory
- File: `docs/MEMORY_CURRENT_STATE_2026-06-19.md`
- **12 rows**: 8 verified + 2 defect-found (Rows 3 & 7) + 1 doc-only acceptable (Row 4 single account) + 3 deferred-with-owner (Rows 10/12 + Row 4 partial)
- Row 3 (memory tool write path): ⚠️ defect found → fixed today by S1-MEM-1
- Row 7 (clear_user_data atomicity): ⚠️ happy-path only → S1-DEL-1 to re-run with non-empty store

### Step 1.5 — thread_id decision
- **T2 locked**: `thread_id = f"{user_id}:{session_id}"`
- File: `docs/MEMORY_LAYER_DECISION_2026-06-19.md` §Thread-vs-User
- Consequence: SPRINT1-CKPT-MIG is **mandatory** (not conditional), and S1-TID-1 / S1-TEST-2 / S1-TEST-3 are all active in Sprint 1

### Step 2/3 — Candidate decision
- **Candidate A** (Keep & harden langmem + AsyncPostgresStore) selected
- Candidate D (claude-mem) gated out per v4.4 gating rule

### Sprint 1 capacity (#22) outcome
- Keep T2 ✅
- SPRINT1-CKPT-MIG mandatory ✅
- **Defer NextAuth / Google OAuth → Sprint 6** ✅
- Sprint 1 timeline preserved at 1 week ✅
- API-key-only auth for Sprint 1; OAuth lands at beta in Sprint 6

---

## Today's work: S1-MEM-1 (this branch)

### Problem
LLM was not calling `manage_memory` tool even when user explicitly said "remember that X". Sprint 0 Row 3 verification surfaced this defect.

### Root cause (3 layers)
1. **`MEMORY_SYSTEM_PROMPT`** had no instruction telling the LLM when to use the tool
2. **`agent_factory.py:120`** used `.format()` which would raise `KeyError` on any memory content containing `{` or `}` characters (latent bug, would have surfaced once memory writes started working)
3. **`db/postgres_utils.py`** `AsyncPostgresStore.setup()` always tried to build a vector index. When `EMBED_MODEL=none`, the `store` table was silently skipped (third bug discovered during S1-MEM-1 implementation, not originally in scope)

### Fix

| File | Change |
|------|--------|
| `agent/prompts.py` | Rewrote `MEMORY_SYSTEM_PROMPT` with explicit `manage_memory` rules and negative rules |
| `agent/agent_factory.py:120` | `.format()` → `.replace()` |
| `db/postgres_utils.py` | Conditional `index_config = None` when `EMBED_MODEL=none` |

### Verification ✅

```sql
SELECT prefix, key, value FROM store WHERE value::text ILIKE '%green%';

 prefix     | key          | value
------------+--------------+-----------------------------------------------
 5178700920 | 7d509a25-... | {"content": "User's favorite color is green"}
```

Row 3 in `MEMORY_CURRENT_STATE_2026-06-19.md` is now ✅ verified.

Commit: `39f2752` — `fix(memory): S1-MEM-1 — add memory tool usage instructions to system prompt`

### Scope expansion note
The `.format()` → `.replace()` fix was added to the original S1-MEM-1 scope after Vernon flagged it as a P0 latent bug (would have crashed bot for any user whose stored memory contained `{}`). The `EMBED_MODEL=none` fix in `postgres_utils.py` was discovered during implementation and necessary to make verification possible. All three changes are one logical unit (make memory write path production-safe) and ship in one commit.

---

## Known issues / tech debt surfaced during S1-MEM-1

| Item | Severity | Action |
|------|----------|--------|
| `EMBED_MODEL=none` in current env | Medium | S1-MEM-2 — choose embedding provider (Google quota exhausted, Ollama local, or alternative) |
| Google API Key quota exhausted | Medium | External — wait for reset or upgrade billing |
| `store_migrations` blind spot | Low | If `store` table is manually deleted, `setup()` won't rebuild it (migration table sees prior version). Add idempotent check in future task. |
| Bot LLM provider availability | Low | Only claude-haiku and gemini-2.5-flash-lite verified healthy in current env |

---

## Sprint 1 remaining task list (per PROJECT_PLAN_v4.4.md §Sprint 1)

| Task ID | Task | Gate / order | Status |
|---------|------|--------------|--------|
| ~~S1-MEM-1~~ | ~~Memory tool prompt fix~~ | — | ✅ **Done today** |
| S1-DEL-1 | Re-run Row 7 with non-empty store + atomicity test | After S1-MEM-1 merged | ⬜ |
| S1-BOOT-1 | Remove `default_user` hardcoding (`main.py:233`) | Can start in parallel | ⬜ |
| S1-AUTH-1 | `tenants` + `users` + `api_keys` tables | Required before S1-NS-1 | ⬜ |
| S1-AUTH-2 | Auth middleware (API-key-only; Google OAuth deferred to Sprint 6) | After S1-AUTH-1 | ⬜ |
| S1-AUTH-3 | Per-tenant Redis namespace | After S1-AUTH-1 | ⬜ |
| #21 | Collapse session layer into single authority module | Required before S1-TID-1 | ⬜ |
| S1-NS-MIG | Executable namespace migration plan + backfill SQL | After S1-AUTH-1 | ⬜ |
| S1-NS-1 | Namespace `(user_id,)` → `(tenant_id, user_id)` code change | Gated by S1-NS-MIG | ⬜ |
| S1-TID-1 | T2 thread_id implementation + adapter refactor | After #21 | ⬜ |
| **SPRINT1-CKPT-MIG** | **Checkpoint migration (mandatory; T2 locked)** | After S1-TID-1 | ⬜ |
| S1-CLEAN-1 | Remove `.mcp.json` openmemory dev-only entry | Any time | ⬜ |
| S1-TEST-1/2/3 + namespace + memory_delete + tenant_isolation tests | 6 test files | Paired with each task | ⬜ |
| S1-MEM-2 | Embedding provider + retrieval quality | Independent track | ⬜ |

**Deferred to Sprint 6**: S1-UI-1 (NextAuth Google provider) per #22 decision.

---

## Environment snapshot (local dev)

```
Bot: python main.py running (LLM_MODEL=claude-haiku)
EMBED_MODEL=none — temporary, until S1-MEM-2
Postgres: pantheon DB (vernon@localhost:5432) — store ✅, store_vectors (empty, embedding disabled), checkpoints ✅
Redis: localhost:6379 ✅
Branch: claude/remote-control-Q2YAQ (this PR)
```

---

## Cross-references

- Sprint 0 closure: issue #23
- Capacity re-check: issue #22
- Backup/restore + Auditability owners: issue #20
- Session layer collapse: issue #21
- Stage 2 plan: `docs/PROJECT_PLAN_v4.4.md`
- Sprint 0 decision: `docs/MEMORY_LAYER_DECISION_2026-06-19.md`
- Sprint 0 inventory: `docs/MEMORY_CURRENT_STATE_2026-06-19.md`
- Migration skeleton: `docs/MEMORY_MIGRATION_PLAN.md`

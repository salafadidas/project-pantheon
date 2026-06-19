# Sprint 0 Step 1 — Pantheon Memory Layer Current-State Inventory

**Date**: 2026-06-19
**Sprint**: Sprint 0 (Memory Layer Assessment)
**Status**: Draft (Claude-generated code_ref + cmd; verification_result pending local execution)
**Parent**: `docs/PROJECT_PLAN_v4.4.md` §4 Sprint 0 Step 1
**Companion**: `docs/SPRINT0_RUNBOOK.md` (local execution guide)

---

## How to use this document

1. Read `docs/SPRINT0_RUNBOOK.md` first for environment setup.
2. For each row below, run the command in the `verification_result` block.
3. Paste actual output into the `Your output` section under each command.
4. Update the row's verdict using the `Expected` block.
5. Commit when all rows have either real output or explicit "doc-only — verify in Sprint N" + non-empty `risk_if_unverified`.

**Exit rule (from v4.4)**: a row with `verification_result = "doc-only"` AND `risk_if_unverified = "—"` blocks Sprint 0 exit.

---

## Plan baseline corrections (found while drafting inventory)

While locating `code_ref` line numbers for this draft, three things in v4.4 plan baseline were discovered to be inaccurate. Worth fixing in v4.5 or noting in decision doc:

| v4.4 assumption | Reality found in code | Implication |
|-----------------|----------------------|-------------|
| `clear_user_data` is a TODO at `db/user_data.py:27-31` | Function is **implemented** L13-99; deletes from `checkpoints`, `store`, `store_vectors`. The "TODO" string at L27-31 is a stale planning comment from an earlier draft. | Sprint 1 task S1-DEL-1 reframes from "implement TODO" to "verify atomicity + tenant scope + audit existing implementation". Possibly less work than estimated. |
| `default_user` at `main.py:233` is "bootstrap" | Hardcoded as the `default_agent`'s user_id, passed to `TelegramBot(...)` at L238 and used as **production fallback** when `agent_manager.get_agent(user_id)` returns None (see `telegram_bot.py:191-195`). | **Cross-tenant memory leak risk**: if agent_manager fails for tenant A, the fallback agent's namespace is `("default_user",)` — meaning any user hitting the fallback writes/reads memories in the same shared bucket. Confirms High-impact tenantization risk in v4.4 risk register. |
| `clear_user_data` only via raw SQL | L91 also calls `store.adelete(old_namespace, user_id)` — a langgraph store API path coexists with raw SQL deletes. | Verification must cover both code paths; check whether they run in sequence or one short-circuits the other. |

---

## Inventory Table

> Markdown table is dense by necessity. If a `code_ref` line number is off by ±1, fix in place and note in commit message.

### Row 1 — Dev MCP memory (`.mcp.json` openmemory)

| Field | Content |
|-------|---------|
| **code_ref** | `.mcp.json:13` |
| **verification_result** | ⏳ pending — run locally:<br>```bash<br>cat .mcp.json \| python -m json.tool<br>grep -r "openmemory" --include="*.py" .<br>```<br>**Expected if dev-only (assumption holds)**: `.mcp.json` shows `openmemory` entry; `grep` returns 0 Python references.<br>**Expected if production-coupled (assumption broken)**: `grep` returns Python files importing or calling openmemory.<br>**Your output**:<br>```<br>[paste grep output here]<br>```<br>**Verdict**: ☐ dev-only confirmed / ☐ production-coupled (escalate) |
| **risk_if_unverified** | — (verification cost is ~30 seconds; no acceptable doc-only path) |

---

### Row 2 — Runtime memory store (AsyncPostgresStore)

| Field | Content |
|-------|---------|
| **code_ref** | `db/postgres_utils.py:45-91`, `agent/agent_factory.py:10` (`from langmem import create_manage_memory_tool`) |
| **verification_result** | ⏳ pending — run locally with bot running:<br>```bash<br>psql $DATABASE_URL -c "\dt" \| grep -E "store\|checkpoint"<br>psql $DATABASE_URL -c "SELECT prefix, key FROM store LIMIT 5;"<br>```<br>**Expected**: tables `store`, `store_vectors`, `checkpoints` exist; `store` has rows when bot has handled messages.<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ store exists & writes flow / ☐ schema mismatch (escalate) |
| **risk_if_unverified** | — |

---

### Row 3 — Memory tool binding (`create_manage_memory_tool`)

| Field | Content |
|-------|---------|
| **code_ref** | `agent/agent_factory.py:137` (`tools=[create_manage_memory_tool(namespace=namespace)]`) |
| **verification_result** | ⏳ pending — run locally:<br>1. Send Telegram bot a message: `"remember that my favorite color is blue"`<br>2. Then query:<br>```bash<br>psql $DATABASE_URL -c "SELECT prefix, key, value FROM store WHERE value::text ILIKE '%blue%' LIMIT 5;"<br>```<br>**Expected**: row(s) with `prefix` containing your Telegram user_id (string form).<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ tool writes confirmed / ☐ no rows written (escalate — tool may not be bound) |
| **risk_if_unverified** | — |

---

### Row 4 — Namespace shape (`(user_id,)` tuple)

| Field | Content |
|-------|---------|
| **code_ref** | `agent/agent_factory.py:66` (`namespace = (str(user_id),)`), `agent/agent_factory.py:83` (same, in closure), `agent/agent_factory.py:137` (passed to tool) |
| **verification_result** | ⏳ pending — run locally with **two different Telegram accounts**:<br>1. Account A sends: `"remember my name is Alice"`<br>2. Account B sends: `"remember my name is Bob"`<br>3. Query:<br>```bash<br>psql $DATABASE_URL -c "SELECT DISTINCT prefix FROM store;"<br>psql $DATABASE_URL -c "SELECT prefix, value FROM store WHERE value::text ILIKE '%lice%' OR value::text ILIKE '%ob%';"<br>```<br>**Expected**: two distinct prefixes, one per Telegram user_id; no rows leak across prefixes.<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ user-level isolation works / ☐ shared prefix (escalate — major bug) / ☐ skipped (only have one test account) |
| **risk_if_unverified** | If skipped (one account only): cannot confirm `user_id`-level isolation works as designed; Sprint 1 namespace migration would be flying blind on what "current isolation" actually means. If skipped, mark as doc-only and verify on first available second account. |

---

### Row 5 — Checkpoints (`AsyncPostgresSaver`)

| Field | Content |
|-------|---------|
| **code_ref** | `db/postgres_utils.py:31` (`AsyncPostgresSaver(setup_conn)`), `agent/agent_factory.py:60` (`checkpointer = AsyncPostgresSaver(pool)`) |
| **verification_result** | ⏳ pending — run locally with bot handling a few messages:<br>```bash<br>psql $DATABASE_URL -c "SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id;"<br>```<br>**Expected**: rows with `thread_id` equal to Telegram user_id (string); count grows per turn.<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ checkpoints written, thread_id == user_id confirmed / ☐ thread_id differs from user_id (escalate — different scoping than assumed) |
| **risk_if_unverified** | — |

---

### Row 6 — `default_user` bootstrap (production fallback)

| Field | Content |
|-------|---------|
| **code_ref** | `main.py:233` (`user_id="default_user"`), `main.py:238` (`TelegramBot(..., default_agent, ...)`), `telegram_adapter/telegram_bot.py:191-195` (fallback path: `logger.warning(f"No agent_manager available, using shared agent for user {user_id}")` followed by invoke with `thread_id=user_id` but the agent's bound namespace is still `("default_user",)`) |
| **verification_result** | ⏳ pending — two checks:<br>**A. Confirm default_user namespace gets written**:<br>```bash<br># Trigger fallback by temporarily disabling agent_manager (or check existing logs)<br>psql $DATABASE_URL -c "SELECT * FROM store WHERE prefix::text LIKE '%default_user%';"<br>```<br>**B. Confirm fallback path is reachable in production code**:<br>```bash<br>grep -n "agent_manager" telegram_adapter/telegram_bot.py<br>grep -n "default_agent" telegram_adapter/telegram_bot.py<br>```<br>**Expected**: (A) `default_user` rows may or may not exist depending on past fallbacks; (B) fallback path confirmed live (not dead code).<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ fallback live, default_user namespace risk confirmed / ☐ dead code, lower severity |
| **risk_if_unverified** | — (this is a High-impact risk per v4.4 register; must be verified) |

---

### Row 7 — Delete path (`clear_user_data` — implemented, not TODO)

| Field | Content |
|-------|---------|
| **code_ref** | `db/user_data.py:13-99` (function implemented; "TODO" comment at L27-31 is stale). Deletes from: `checkpoints` (L43-48 raw SQL), `store` (L61-69 raw SQL), `store_vectors` (L72-80 raw SQL), AND `store.adelete(old_namespace, user_id)` at L91 (langgraph API). |
| **verification_result** | ⏳ pending — run `/reset` in Telegram, then verify deletion:<br>1. Send bot: `"remember X for me"` (write memory)<br>2. Confirm row exists:<br>```bash<br>psql $DATABASE_URL -c "SELECT COUNT(*) FROM store WHERE prefix::text LIKE '%<your_user_id>%';"<br>psql $DATABASE_URL -c "SELECT COUNT(*) FROM checkpoints WHERE thread_id = '<your_user_id>';"<br>```<br>3. Trigger `/reset` (or whatever command invokes `clear_user_data`; see `telegram_bot.py:339`)<br>4. Re-run queries above — both counts should be 0.<br>**Expected**: all three tables clear atomically for the target user_id.<br>**Your output**:<br>```<br>[paste pre-reset counts]<br>[paste post-reset counts]<br>```<br>**Verdict**: ☐ atomic clear works / ☐ partial clear (specify which table not cleared) — partial = escalate |
| **risk_if_unverified** | If unverified: `MEMORY_LAYER_DECISION` cannot honestly answer C2 (delete/export semantics) for option A; Sprint 1 may falsely assume delete works and skip the test. Verification is ~5 minutes; doc-only not justified. |

---

### Row 8 — Tenant scope above user_id (absent)

| Field | Content |
|-------|---------|
| **code_ref** | (no file — verifying absence) |
| **verification_result** | ⏳ pending — run locally:<br>```bash<br>grep -rn "tenant" --include="*.py" . \| grep -v test_ \| head -20<br>grep -rn "tenant_id" --include="*.py" .<br>```<br>**Expected**: 0 hits, or only doc/comment mentions, no schema or model references.<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ absent confirmed (Sprint 1 introduces tenants) / ☐ partial scaffolding exists (good news — note where) |
| **risk_if_unverified** | — |

---

### Row 9 — `thread_id == user_id` conflation

| Field | Content |
|-------|---------|
| **code_ref** | `telegram_adapter/telegram_bot.py:187` (`config={"configurable": {"user_id": user_id, "thread_id": user_id}}`), `telegram_adapter/telegram_bot.py:194` (same in fallback) |
| **verification_result** | ⏳ pending — observation test:<br>1. Send bot a message at time T1. Note the conversation context.<br>2. Wait long enough that you'd consider it a "new conversation" (or use a different chat session if possible).<br>3. Send a new message that references something from T1 (e.g. "what did I just ask you?").<br>4. Query:<br>```bash<br>psql $DATABASE_URL -c "SELECT thread_id, checkpoint_id, parent_checkpoint_id, type FROM checkpoints WHERE thread_id = '<your_user_id>' ORDER BY checkpoint_id DESC LIMIT 10;"<br>```<br>**Expected if conflated (T1 assumption)**: same `thread_id` for both turns; bot recalls old context indefinitely; checkpoints grow unbounded under one thread.<br>**Expected if separated**: different `thread_id` per session.<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ conflation confirmed (Step 1.5 T2/T3 strongly indicated) / ☐ already separated (Step 1.5 = T1 viable) |
| **risk_if_unverified** | — |

---

### Row 10 — Backup/restore impact (DEFERRED to Sprint 5)

| Field | Content |
|-------|---------|
| **code_ref** | Cloud SQL config (not yet committed; lives in Sprint 3 deliverable) |
| **verification_result** | **doc-only — verify in Sprint 5 DR drill**.<br>Reason: backup/restore atomicity between `store`, `store_vectors`, and `checkpoints` tables can only be tested with Cloud SQL backups in place, which is a Sprint 5 deliverable. Local PITR drill possible in dev but doesn't exercise the Cloud SQL path. |
| **risk_if_unverified** | **A restore (e.g. after a corruption incident or DR drill) may leave `store` and `checkpoints` at different point-in-times, producing an agent that "remembers" facts via `store` whose corresponding conversation history in `checkpoints` no longer exists, or vice versa. User sees an inconsistent agent: it claims to remember things it shouldn't, or has lost things it should.** Mitigation: Sprint 5 DR runbook must verify row-count consistency across the three tables post-restore (issue #20). |

---

### Row 11 — Export endpoint (absent)

| Field | Content |
|-------|---------|
| **code_ref** | (no file — verifying absence) |
| **verification_result** | ⏳ pending — run locally:<br>```bash<br>grep -rn "export" --include="*.py" api/ \| head -10<br>```<br>**Expected**: 0 hits for user/memory export endpoints. Out of Stage 2 scope; flag for Stage 3.<br>**Your output**:<br>```<br>[paste]<br>```<br>**Verdict**: ☐ absent confirmed / ☐ partial export exists (note where) |
| **risk_if_unverified** | — |

---

### Row 12 — Auditability (DEFERRED to Sprint 2)

| Field | Content |
|-------|---------|
| **code_ref** | `core/` log calls (structlog only; no audit table) |
| **verification_result** | **doc-only — verify in Sprint 2 OpenTelemetry rollout**.<br>Reason: write-side audit spans are a Sprint 2 deliverable. Read-side is partially covered by existing structlog calls. |
| **risk_if_unverified** | **No way to forensically reconstruct who wrote/read which memory in the event of a cross-tenant bug or data-leak claim.** Read-side: structlog at `agent_factory.py:80, 85, 95` partially covers reads. Write-side: not currently logged at all. Mitigation: Sprint 2 OTel write-spans on memory writes (issue #20). Risk accepted in writing for Stage 2; revisit at Sprint 6 beta gate. |

---

## Step 1.5 — `thread_id == user_id` decision

**To be completed in `MEMORY_LAYER_DECISION_2026-06-20.md` §Thread-vs-User, informed by Row 9 verification.**

Default recommendation: **T2** (`thread_id = f"{user_id}:{session_id}"`). See v4.4 Step 1.5 + canonical thread_id rule + issue #21 (collapse `api/v1/sessions.py or equivalent` into single authority module).

---

## Sprint 0 Exit Checklist

- [ ] All 12 rows have non-pending `verification_result` OR explicit `risk_if_unverified` text
- [ ] Plan baseline corrections (3 items above) acknowledged in `MEMORY_LAYER_DECISION_2026-06-20.md`
- [ ] Step 1.5 thread_id decision committed in decision doc
- [ ] Step 2 candidate evaluation (A vs. B/C/D with C1-C6) completed in decision doc
- [ ] Step 3 final choice + Sprint 1 hardening checklist committed

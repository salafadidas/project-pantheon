# Sprint 0 Step 1 — Pantheon Memory Layer Current-State Inventory

**Date**: 2026-06-19
**Sprint**: Sprint 0 (Memory Layer Assessment)
**Status**: Step 1 in progress — 8/12 rows verified; 2 rows need live bot session (Row 3, Row 7); 1 doc-only (Row 4); 1 doc-only deferred (Row 10, 12)
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
| **verification_result** | ✅ **dev-only confirmed** (2026-06-19)<br>```bash<br>cat .mcp.json \| python3 -m json.tool<br># → openmemory entry present at top level mcpServers<br>grep -r "openmemory" --include="*.py" .<br># → exit 1, 0 matches<br>```<br>**Output**: `.mcp.json` has `"openmemory": {"type":"http","url":"http://localhost:8080/mcp"}`. No Python files import or reference openmemory.<br>**Verdict**: ✅ dev-only confirmed — openmemory is a local MCP sidecar with zero production code coupling |
| **risk_if_unverified** | — (verification cost is ~30 seconds; no acceptable doc-only path) |

---

### Row 2 — Runtime memory store (AsyncPostgresStore)

| Field | Content |
|-------|---------|
| **code_ref** | `db/postgres_utils.py:45-91`, `agent/agent_factory.py:10` (`from langmem import create_manage_memory_tool`) |
| **verification_result** | ✅ **schema confirmed** (2026-06-19); writes pending bot session<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "\dt" \| grep -E "store\|checkpoint"<br># → checkpoints, checkpoint_blobs, checkpoint_migrations, checkpoint_writes,<br>#   store, store_migrations, store_vectors — all present<br>psql ... -c "SELECT prefix, key FROM store LIMIT 5;"<br># → 0 rows (bot not run with memory writes yet in this env)<br>\d store<br># → prefix TEXT, key TEXT, value JSONB — matches Pitfall 1 variant: use WHERE prefix LIKE '%X%'<br>```<br>**Verdict**: ✅ all 7 tables exist, schema is `prefix TEXT` (not array/JSONB). Store empty — Row 3 will confirm writes once bot runs. |
| **risk_if_unverified** | — |

---

### Row 3 — Memory tool binding (`create_manage_memory_tool`)

| Field | Content |
|-------|---------|
| **code_ref** | `agent/agent_factory.py:137` (`tools=[create_manage_memory_tool(namespace=namespace)]`) |
| **verification_result** | ⏳ **manual step required** — bot must be running<br>1. Start bot: `python main.py`<br>2. Send Telegram: `"remember that my favorite color is blue"`<br>3. Then query:<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "SELECT prefix, key, value FROM store WHERE value::text ILIKE '%blue%' LIMIT 5;"<br>```<br>**Expected**: row(s) with `prefix` containing your Telegram numeric user_id (e.g. `"5178700920"`).<br>**Your output**:<br>```<br>[paste after running bot]<br>```<br>**Verdict**: ☐ tool writes confirmed / ☐ no rows written (escalate) |
| **risk_if_unverified** | — |

---

### Row 4 — Namespace shape (`(user_id,)` tuple)

| Field | Content |
|-------|---------|
| **code_ref** | `agent/agent_factory.py:66` (`namespace = (str(user_id),)`), `agent/agent_factory.py:83` (same, in closure), `agent/agent_factory.py:137` (passed to tool) |
| **verification_result** | **doc-only — verify on first available second Telegram account** (2026-06-19)<br>Current store has 0 rows; checkpoints show only one user (`thread_id = 5178700920`). Two-account test not yet possible.<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "SELECT DISTINCT prefix FROM store;"<br># → 0 rows<br>```<br>**Verdict**: ☐ skipped (only one test account) — see `risk_if_unverified` |
| **risk_if_unverified** | If skipped (one account only): cannot confirm `user_id`-level isolation works as designed; Sprint 1 namespace migration would be flying blind on what "current isolation" actually means. If skipped, mark as doc-only and verify on first available second account. |

---

### Row 5 — Checkpoints (`AsyncPostgresSaver`)

| Field | Content |
|-------|---------|
| **code_ref** | `db/postgres_utils.py:31` (`AsyncPostgresSaver(setup_conn)`), `agent/agent_factory.py:60` (`checkpointer = AsyncPostgresSaver(pool)`) |
| **verification_result** | ✅ **checkpoints written, thread_id == user_id confirmed** (2026-06-19)<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id;"<br>#  thread_id  | count<br># ------------+-------<br>#  5178700920 |     3<br>```<br>**Verdict**: ✅ `thread_id = "5178700920"` (numeric Telegram user_id as string), 3 turns. One user, confirmed scoping. |
| **risk_if_unverified** | — |

---

### Row 6 — `default_user` bootstrap (production fallback)

| Field | Content |
|-------|---------|
| **code_ref** | `main.py:233` (`user_id="default_user"`), `main.py:238` (`TelegramBot(..., default_agent, ...)`), `telegram_adapter/telegram_bot.py:191-195` (fallback path: `logger.warning(f"No agent_manager available, using shared agent for user {user_id}")` followed by invoke with `thread_id=user_id` but the agent's bound namespace is still `("default_user",)`) |
| **verification_result** | ✅ **fallback live, default_user namespace risk confirmed** (2026-06-19)<br>**A.**<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "SELECT * FROM store WHERE prefix::text LIKE '%default_user%';"<br># → 0 rows (fallback never triggered yet in this environment)<br>```<br>**B.**<br>```bash<br>grep -n "agent_manager" telegram_adapter/telegram_bot.py<br># L178: agent_manager = getattr(self, 'agent_manager', None)<br># L180: if agent_manager:<br># L182:   user_agent = await agent_manager.get_agent(user_id)<br># L190: # Fall back to the shared agent if agent_manager is not available<br># L191: logger.warning(f"No agent_manager available, using shared agent for user {user_id}")<br># L284, L342-344: shutdown / remove_agent paths also present<br>```<br>**Verdict**: ✅ Fallback path is **live code** (not dead). `default_user` rows not yet present because `agent_manager` always returns successfully in current env. Cross-tenant leak risk is latent, not yet materialized — but path is reachable in production if `agent_manager.get_agent()` raises or returns None. |
| **risk_if_unverified** | — (this is a High-impact risk per v4.4 register; must be verified) |

---

### Row 7 — Delete path (`clear_user_data` — implemented, not TODO)

| Field | Content |
|-------|---------|
| **code_ref** | `db/user_data.py:13-99` (function implemented; "TODO" comment at L27-31 is stale). Deletes from: `checkpoints` (L43-48 raw SQL), `store` (L61-69 raw SQL), `store_vectors` (L72-80 raw SQL), AND `store.adelete(old_namespace, user_id)` at L91 (langgraph API). |
| **verification_result** | ⏳ **manual step required** — bot must be running<br>Command confirmed: `telegram_bot.py:319` → `/reset` command handler invokes `clear_user_data`.<br>Steps:<br>1. Start bot: `python main.py`<br>2. Send bot: `"remember X for me"` — confirm Row 3 write first<br>3. Pre-reset counts:<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "SELECT COUNT(*) FROM store WHERE prefix LIKE '%5178700920%';"<br>psql "postgresql://vernon@localhost:5432/pantheon" -c "SELECT COUNT(*) FROM checkpoints WHERE thread_id = '5178700920';"<br>```<br>4. Send `/reset` to bot<br>5. Re-run queries — expect both 0<br>**Your output**:<br>```<br>[paste pre-reset counts]<br>[paste post-reset counts]<br>```<br>**Verdict**: ☐ atomic clear works / ☐ partial clear (escalate) |
| **risk_if_unverified** | If unverified: `MEMORY_LAYER_DECISION` cannot honestly answer C2 (delete/export semantics) for option A; Sprint 1 may falsely assume delete works and skip the test. Verification is ~5 minutes; doc-only not justified. |

---

### Row 8 — Tenant scope above user_id (absent)

| Field | Content |
|-------|---------|
| **code_ref** | (no file — verifying absence) |
| **verification_result** | ✅ **absent confirmed** (2026-06-19)<br>```bash<br>grep -rn "tenant" --include="*.py" . \| grep -v test_ \| head -20<br># → 0 matches<br>grep -rn "tenant_id" --include="*.py" .<br># → 0 matches<br>```<br>**Verdict**: ✅ No tenant layer exists anywhere in Python code. Sprint 1 introduces it from scratch. |
| **risk_if_unverified** | — |

---

### Row 9 — `thread_id == user_id` conflation

| Field | Content |
|-------|---------|
| **code_ref** | `telegram_adapter/telegram_bot.py:187` (`config={"configurable": {"user_id": user_id, "thread_id": user_id}}`), `telegram_adapter/telegram_bot.py:194` (same in fallback) |
| **verification_result** | ✅ **conflation confirmed** (2026-06-19)<br>```bash<br>psql "postgresql://vernon@localhost:5432/pantheon" -c \<br>  "SELECT thread_id, checkpoint_id, parent_checkpoint_id FROM checkpoints WHERE thread_id = '5178700920' ORDER BY checkpoint_id DESC LIMIT 10;"<br>#  thread_id  | checkpoint_id                        | parent_checkpoint_id<br># ------------+--------------------------------------+--------------------------------------<br>#  5178700920 | 1f142291-7068-6072-8001-8a3854b2f533 | 1f142291-440e-68c8-8000-0d9bc1d3adc9<br>#  5178700920 | 1f142291-440e-68c8-8000-0d9bc1d3adc9 | 1f142291-440b-6b6e-bfff-e06e19f0756f<br>#  5178700920 | 1f142291-440b-6b6e-bfff-e06e19f0756f | (null)<br># 3 rows — all under one thread, linear chain<br>```<br>**Verdict**: ✅ Conflation confirmed. All 3 turns share `thread_id = user_id`; checkpoints grow as a single linear chain. **Step 1.5 T2 strongly indicated** (`thread_id = f"{user_id}:{session_id}"`). |
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
| **verification_result** | ✅ **absent confirmed** (2026-06-19)<br>```bash<br>grep -rn "export" --include="*.py" api/ \| head -10<br># → 0 matches<br>```<br>**Verdict**: ✅ No export endpoint exists in `api/`. Out of Stage 2 scope — flag for Stage 3 roadmap. |
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

**To be completed in `MEMORY_LAYER_DECISION_2026-06-19.md` §Thread-vs-User, informed by Row 9 verification.**

Default recommendation: **T2** (`thread_id = f"{user_id}:{session_id}"`). See v4.4 Step 1.5 + canonical thread_id rule + issue #21 (collapse `api/v1/sessions.py or equivalent` into single authority module).

---

## Sprint 0 Exit Checklist

- [ ] All 12 rows have non-pending `verification_result` OR explicit `risk_if_unverified` text
- [ ] Plan baseline corrections (3 items above) acknowledged in `MEMORY_LAYER_DECISION_2026-06-19.md`
- [ ] Step 1.5 thread_id decision committed in decision doc
- [ ] Step 2 candidate evaluation (A vs. B/C/D with C1-C6) completed in decision doc
- [ ] Step 3 final choice + Sprint 1 hardening checklist committed

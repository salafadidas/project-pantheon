# Sprint 0 — Local Execution Runbook

**For**: Vernon executing Sprint 0 Step 1 verification on 2026-06-19
**Companion**: `docs/MEMORY_CURRENT_STATE_2026-06-19.md` (the inventory to fill in)
**Time budget**: 2–3 hours

---

## 0. Prerequisites — confirm these before starting

```bash
# A. Confirm Pantheon repo is on latest main
git pull origin main
git log -1 --oneline  # should show v4.4 merge commit

# B. Confirm docker stack can start
docker-compose ps     # if not running: docker-compose up -d

# C. Confirm env vars
cat .env | grep -E "^(DATABASE_URL|REDIS_URL|TELEGRAM_TOKEN)="
# Should see all three set
```

**If any of the above fails, fix that first.** Don't proceed with broken environment; verification results will be misleading.

---

## 1. Convenience: shell exports

Run these once in your terminal session so the inventory's `psql $DATABASE_URL` commands just work:

```bash
export DATABASE_URL=$(grep -E "^DATABASE_URL=" .env | cut -d= -f2-)
# OR construct manually:
# export DATABASE_URL="postgresql://USER:PASS@localhost:5432/pantheon"

# Sanity check:
psql $DATABASE_URL -c "\dt" | head
# should list Pantheon tables
```

If you don't have `psql` locally, exec into the Postgres container:
```bash
docker exec -it pantheon-postgres psql -U <user> -d <db>
# (replace with your actual container name + creds)
```

---

## 2. Test accounts

Some rows (especially **Row 4 — namespace isolation**) want two Telegram accounts. If you only have one, that's OK — mark Row 4 as `doc-only` and document the gap. Per v4.4 exit rule, doc-only requires a `risk_if_unverified` statement, which the inventory already pre-fills for Row 4.

---

## 3. Execution order (recommended)

The 12 rows are ordered for an efficient sweep — earlier rows set up state that later rows verify. Suggested order:

| Order | Row | Type | Approx time |
|-------|-----|------|-------------|
| 1 | Row 1 — `.mcp.json` openmemory dev-only | grep | 1 min |
| 2 | Row 8 — tenant scope absence | grep | 1 min |
| 3 | Row 11 — export endpoint absence | grep | 1 min |
| 4 | Row 2 — store table exists | psql | 2 min |
| 5 | Row 3 — write a memory, see it in store | telegram + psql | 5 min |
| 6 | Row 5 — checkpoint writes | psql | 2 min |
| 7 | Row 4 — two-account namespace isolation | telegram (2 accts) + psql | 10 min (or skip per §2) |
| 8 | Row 9 — thread_id conflation observation | telegram + psql | 10 min |
| 9 | Row 7 — `/reset` atomic delete | telegram + psql | 5 min |
| 10 | Row 6 — `default_user` fallback live? | grep + psql | 10 min |
| 11 | Row 10 — backup/restore | (doc-only, paste rationale) | 1 min |
| 12 | Row 12 — auditability | (doc-only, paste rationale) | 1 min |

Total active time: ~50 min if everything works first try. Budget 2–3h for environment hiccups and re-runs.

---

## 4. Pitfalls

### Pitfall 1 — `prefix` column vs `namespace` tuple
The langgraph store's Postgres schema stores namespace as a `prefix` column (text or array depending on version). If your query returns no rows for `WHERE prefix LIKE '%user_id%'`, try:
```bash
psql $DATABASE_URL -c "\d store"  # check column types first
```
Common variants:
- `prefix TEXT`: query with `prefix LIKE '%X%'`
- `prefix TEXT[]`: query with `'X' = ANY(prefix)`
- `namespace JSONB`: query with `namespace::text LIKE '%X%'`

If your schema differs, **note this in inventory Row 2 verdict** — it's a useful baseline finding.

### Pitfall 2 — Telegram user_id vs `default_user`
`telegram_bot.py:320` does `user_id = str(update.effective_user.id)` — so when you write memories, the prefix is your numeric Telegram ID as string (e.g. `"123456789"`), **not** `"default_user"`. `"default_user"` only appears if the fallback path at `telegram_bot.py:194` fires. Row 6 specifically probes whether this path is dead code or live.

### Pitfall 3 — `/reset` command name
The actual reset command may be `/reset`, `/clear`, or something else. Check:
```bash
grep -n "command" telegram_adapter/telegram_bot.py | grep -i "reset\|clear"
```
Use whatever command corresponds to `telegram_bot.py:339` (`await clear_user_data(...)`).

---

## 5. When you hit something you don't understand

Two paths:

**A. The output is unexpected but you can describe it.** Paste the output into the inventory row, mark verdict as "escalate", commit, move on. Sprint 0 Step 3 (decision doc) is where escalations are addressed.

**B. The command itself fails or you don't know what to do.** Stop. Open Claude.ai, paste:
> "Sprint 0 inventory Row N. I ran [cmd] and got [output / error]. Pantheon plan v4.4. How do I interpret this?"

New session can read `MEMORY_CURRENT_STATE_2026-06-19.md` + `PROJECT_PLAN_v4.4.md` from main and respond.

---

## 6. After Step 1

Once all 12 rows are filled:

```bash
git add docs/MEMORY_CURRENT_STATE_2026-06-19.md
git commit -m "verify(sprint0): complete Step 1 inventory with local evidence"
git push origin main
```

Then move to:
- **Step 1.5** — Thread-vs-User decision (T1/T2/T3), informed by Row 9 verdict
- **Step 2** — Candidate evaluation (A vs. B/C/D, C1-C6 per surviving candidate)
- **Step 3** — `docs/MEMORY_LAYER_DECISION_2026-06-20.md`

Steps 1.5–3 can be drafted in conversation with me after Step 1 is done — they're judgment-heavy, not test-heavy.

---

## 7. If you get stuck on environment

Sprint 0 verification depends on a working Pantheon dev environment. If `docker-compose up` fails or the bot won't connect, **that** becomes the blocker, not the inventory. In that case:

- File the environment issue as a sub-task
- Mark inventory rows that require runtime as `doc-only — blocked by env issue #N`
- The `risk_if_unverified` for those rows escalates: shipping Sprint 1 hardening without ever verifying current behavior means flying blind

Don't paper over environment problems by guessing what the rows would have shown.

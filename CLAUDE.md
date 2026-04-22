# Project Pantheon — Claude Instructions

## Session Start Protocol

**REQUIRED before any other action in every session:**

```bash
# 1. Confirm which directory and branch you're in
pwd && git branch --show-current

# 2. Fetch and check divergence
git fetch origin
git status
git log origin/main..HEAD --oneline   # local-only commits
git log HEAD..origin/main --oneline   # upstream commits you don't have

# 3. If local is behind origin: pull before writing any code
git pull --rebase origin main
```

**Rules:**
- NEVER `git stash` if the upcoming pull may include file renames or deletions — use `git commit -m "wip: ..."` instead
- NEVER start coding when `git log HEAD..origin/main` shows commits — get in sync first
- If two local clones exist for the same repo, prefer `git worktree` to avoid divergence confusion
- CLAUDE.md is the **first** file committed, not the last — keep Project Context current

---

## Before Starting Any New Day/Stage

**REQUIRED before writing any implementation code:**

1. Find the current plan file: `ls docs/PROJECT_PLAN_v*.md` — the highest version number is the active file
2. Read that file in full
3. Update the **Current Progress Snapshot** table to reflect what is actually complete
4. Update the **Day status** in the relevant day tables (e.g., `⏳ Pending` → `✅ Done`)
5. **Rename the file** to the next patch version:
   ```
   git mv docs/PROJECT_PLAN_vX.Y.md docs/PROJECT_PLAN_vX.(Y+1).md
   ```
6. Inside the renamed file, update:
   - `version:` in the YAML front-matter (e.g., `v3.0` → `v3.1`)
   - `date:` to today
   - `status:` line
   - Title line: `Current file: PROJECT_PLAN_vX.(Y+1).md`
   - Add a row to the **Version History** table at the bottom
7. `git add` + `git commit` the renamed plan file **before** writing any other code

### Bump size guide

| Change | Bump |
|--------|------|
| Day/task completes, status rows updated | Patch (v3.0 → v3.1) |
| Scope added or removed within a stage | Minor (v3.1 → v3.2) |
| A full stage completes, next stage sprint plan written | Major (v3.x → v4.0) |

### Example rename + front-matter

```bash
git mv docs/PROJECT_PLAN_v3.0.md docs/PROJECT_PLAN_v3.1.md
```

```yaml
---
title: Project Pantheon — Master Implementation Plan
version: v3.1
date: 2026-04-14
status: Active — Stage 2 Day 1 in progress
---
```

> **Only one `PROJECT_PLAN_vX.Y.md` file should exist in `docs/` at any time.**
> Delete (or do not keep) the previous version after renaming.

---

## Branch

Always develop on: `claude/remote-control-Q2YAQ`

## Repository

`salafadidas/project-pantheon`

## NotebookLM

Upload account: **salafadidas@gmail.com**
Always delete the old source before uploading the new versioned plan file.

### NotebookLM upload protocol
- Prior sessions have used **Playwright MCP** (`browser_navigate`, `browser_click` tools) to upload plan files
- At session start: verify Playwright availability via `ToolSearch` (search "playwright browser navigate")
- If Playwright MCP is unavailable: check for local binary (`which playwright`) and any stored auth cookies before declaring failure
- Report concrete investigative steps taken — never a generic "I cannot do this"

---

## Operational Standards — Error Prevention

### NEVER deny a capability without first investigating

**Critical lesson from 2026-04-13 session:** Claude denied Playwright/browser capability
multiple times without checking, forcing the user to produce screenshots as proof.
This is unacceptable.

**Before stating any capability is unavailable, always:**
1. Run `ToolSearch` with relevant keywords (playwright, browser, computer-use, automation)
2. Check filesystem: `which playwright`, `which chromium`, `node_modules/.bin/`, `~/.cache/ms-playwright/`
3. Read prior session evidence: `/root/.claude/projects/` — look for capability use in logs
4. Check for stored browser state/cookies that prior sessions may have written

**Forbidden anti-pattern** (violated 4+ times in 2026-04-13 session):
> Deny capability → wait for user to bring proof → apologize → offer options menu

The user should NEVER have to bring proof of something Claude can verify by investigation.
One acknowledgment of error is sufficient — do not repeat apologies, investigate and act.

### CLAUDE.md Update Policy

Whenever Claude identifies a lesson learned, recurring process gap, or missing instruction
that would prevent future errors or improve consistency:
1. **Draft the proposed addition** in the response to the user
2. **Explain why** it is needed and what problem it prevents
3. **Wait for explicit user confirmation** before editing CLAUDE.md
4. If confirmed: edit CLAUDE.md, bump the plan version (patch), commit both together

---

## Project Context

> 這個區段由 Claude Code 自動維護，記錄跨 session 的架構決策與進行中狀態。

### Architecture

- **Stack**: FastAPI + LangGraph + Redis + Telegram Bot (python-telegram-bot)
- **Entry point**: `main.py` — 啟動 FastAPI app + Telegram bot + Redis（單一進程）
- **Graph**: `graph/pantheon_graph.py` — 5 節點: `pm_router → researcher → debater → voter → synthesizer`
- **State**: `graph/state.py` — `PantheonState` TypedDict，所有節點共享
- **LLM ensemble**: `claude-sonnet`, `gpt-4o`, `gemini-2.5-pro`（三模型並發）
- **API**: `api/v1/sessions.py`（REST）+ `api/v1/websocket.py`（WebSocket 串流）
- **Telegram**: `telegram_adapter/telegram_bot.py` — class-based `TelegramBot`，4 個指令（submit/status/report/cancel）+ 圖片訊息處理（MessageHandler + filters.PHOTO）
- **Redis session storage**: `hset/hgetall` hash per session（TTL 86400s）
- **Config**: `config/base_config.py`（`dotenv.load_dotenv(override=True)`）→ `config/bot_config.py` / `config/agent_config.py`

### Confirmed Decisions

- **Prompts language**: 所有 LLM prompt 已改為繁體中文（researcher, synthesizer, debater, voter）
- **Synthesizer output**: 結構化報告每節最少 100-300 字，章節：摘要、關鍵洞見、共識決定、異見觀點、建議行動、費用明細
- **Phase emoji**: 🔬 research / 💬 debate / 🗳️ voting / 📝 synthesis / ✅ complete
- **Cost display**: Telegram 完成訊息顯示費用摘要（USD + token count）
- **dotenv**: `config/base_config.py` 使用 `dotenv.load_dotenv(override=True)`（確保 .env 優先於 shell 環境）
- **Photo support**: `handle_photo()` 使用 GPT-4o Vision 分析圖片 → 生成任務描述 → 進入標準 5 階段流程；附 caption 則作為針對圖片的具體問題
- **Status command（中文化）**: `/status` 顯示 emoji 狀態/階段、來源（📸/💬）、已耗時、任務預覽（120字）、完成時間、錯誤訊息，全部繁體中文
- **Architecture migration**: `bot/telegram_handler.py`（函數式）→ `telegram_adapter/telegram_bot.py`（class-based `TelegramBot`）

### Remote Control Mechanism (Designed, Not Yet Implemented)

- **Pattern**: `asyncio.Event` + Redis Pub/Sub
- **Checkpoint timeout**: 3 分鐘（180 秒），Redis TTL 同為 180 秒
- **Control flow**: graph node 執行前等待 checkpoint event；Telegram bot 透過 Redis 訊息觸發繼續

### Committed Changes (2026-04-22)

- `telegram_adapter/telegram_bot.py` — **圖片支援（handle_photo + MessageHandler）** + **/status 中文化（耗時/來源/emoji）**
- `graph/nodes/synthesizer.py` — 繁體中文 prompt + richer output
- `graph/nodes/researcher.py` — 繁體中文 prompt
- `graph/nodes/debater.py`, `voter.py`, `pm_router.py` — 繁體中文 prompt
- `config/base_config.py` — dotenv override=True
- `.gitignore` — 小幅調整

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **project-pantheon** (751 symbols, 1777 relationships, 60 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/project-pantheon/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/project-pantheon/context` | Codebase overview, check index freshness |
| `gitnexus://repo/project-pantheon/clusters` | All functional areas |
| `gitnexus://repo/project-pantheon/processes` | All execution flows |
| `gitnexus://repo/project-pantheon/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

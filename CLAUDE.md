# Project Pantheon — Claude Instructions

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

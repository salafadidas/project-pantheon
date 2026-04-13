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

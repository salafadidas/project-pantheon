# Sprint 1 — Closure Note

**Date:** 2026-06-24
**Status:** ✅ CLOSED

## PR stack landed

| PR | Task | Merge SHA |
|----|------|-----------|
| #35 | fix(ci): ChatLiteLLM import migration | `dc4acf0a` |
| #30 | #21 session layer — `core/session.py` | `2cc772c6` |
| #31 | S1-TID-1 — T2 `thread_id` + Redis persistence | `3a793d28` |
| #32 | S1-AUTH-3 — Redis `pantheon:` namespace | `8e470ac1` |
| #33 | S1-AUTH-2 — API-key middleware | `346a3abd` |
| #29 | S1-NS-1 + SPRINT1-CKPT-MIG | `e1e5c159` |

## All Sprint 1 tasks

| Task | Merged |
|------|--------|
| S1-MEM-1 | PR #24 (earlier) |
| S1-DEL-1 | PR #26 |
| S1-BOOT-1 | PR #27 |
| S1-AUTH-1 | PR #28 |
| S1-CLEAN-1 | direct to main |
| S1-NS-MIG | direct to main |
| #21 + S1-TID-1 | PR #30 + #31 |
| S1-AUTH-3 | PR #32 |
| S1-AUTH-2 | PR #33 |
| S1-NS-1 + CKPT-MIG | PR #29 |
| S1-UI-1 (NextAuth) | ⏸ deferred → Sprint 6 |

## Open follow-ups

- Issue #34 — S1-MEM-2: embedding provider (Google quota) → Sprint 2
- CI: `langchain_litellm` fix landed on main (`dc4acf0a`); all tests green

## Next

Sprint 2: Aletheia QMD RAG pipeline, Raphael Phase 1, S1-MEM-2 embedding resolution.
